"""Unit tests for HTTP client error formatting and package self-reporting."""

from __future__ import annotations

import asyncio
import tomllib
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx

from hebbianvault_mcp.client import HebbianApiError, HebbianClient
from hebbianvault_mcp.config import HebbianConfig
from hebbianvault_mcp.server import SERVER_VERSION, create_server
from hebbianvault_mcp.tools import handle_capture


class TestErrorResponses:
    async def test_403_feature_disabled_detail_surfaces_server_reason(self) -> None:
        response = httpx.Response(
            403,
            json={
                "code": "forbidden",
                "detail": {
                    "error": "feature_disabled",
                    "reason": "This feature is disabled for your workspace.",
                },
            },
        )

        with pytest.raises(HebbianApiError) as exc_info:
            await HebbianClient._handle_response(response)

        tool_error = exc_info.value.to_tool_error()
        assert "This feature is disabled for your workspace." in tool_error
        assert "token scope" not in tool_error

    async def test_403_without_detail_falls_back_to_scope_hint(self) -> None:
        response = httpx.Response(403, content=b"")

        with pytest.raises(HebbianApiError) as exc_info:
            await HebbianClient._handle_response(response)

        assert "token scope" in exc_info.value.to_tool_error()

    async def test_detail_reason_is_the_error_message_for_all_status_codes(self) -> None:
        response = httpx.Response(
            404,
            json={
                "code": "not_found",
                "message": "Generic not-found message",
                "detail": {"reason": "This node is outside your current scope."},
            },
        )

        with pytest.raises(HebbianApiError) as exc_info:
            await HebbianClient._handle_response(response)

        assert exc_info.value.args[0] == "This node is outside your current scope."
        assert "This node is outside your current scope." in exc_info.value.to_tool_error()

    def test_401_detail_surfaces_server_reason(self) -> None:
        error = HebbianApiError(
            401,
            "unauthorized",
            "Unauthorized",
            {"message": "This token has been revoked."},
        )

        tool_error = error.to_tool_error()
        assert "This token has been revoked." in tool_error
        assert "Generate a new token" not in tool_error


class TestTimeoutAndRetry:
    async def test_hanging_capture_call_uses_configured_timeout_tool_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HEBBIAN_TIMEOUT_MS", "25")

        class SlowDripBody(httpx.AsyncByteStream):
            async def __aiter__(self) -> AsyncIterator[bytes]:
                while True:
                    yield b" "
                    await asyncio.sleep(0.01)

            async def aclose(self) -> None:
                return None

        async def slow_drip(
            _transport: httpx.AsyncHTTPTransport, _request: httpx.Request
        ) -> httpx.Response:
            return httpx.Response(200, stream=SlowDripBody())

        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", slow_drip)
        client = HebbianClient("https://api.example.test", "test-token")
        started_at = asyncio.get_running_loop().time()
        with pytest.raises(RuntimeError, match="Request timed out after 25ms"):
            await handle_capture(client, {"title": "T", "text": "B"})

        assert asyncio.get_running_loop().time() - started_at < 0.3

    async def test_capture_post_is_not_retried_after_a_5xx(self) -> None:
        with respx.mock(assert_all_called=False) as mock:
            route = mock.post("https://api.example.test/capture")
            route.side_effect = [
                httpx.Response(500, json={"code": "server_error", "message": "Try later"}),
                httpx.Response(200, json={"uuid": "would-be-duplicate"}),
            ]

            client = HebbianClient("https://api.example.test", "test-token")
            with pytest.raises(RuntimeError, match="API error 500 \\(server_error\\): Try later"):
                await handle_capture(client, {"title": "T", "text": "B"})

        assert route.call_count == 1

    async def test_get_retries_once_after_a_5xx_and_returns_second_response(self) -> None:
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get("https://api.example.test/nodes/retried")
            route.side_effect = [
                httpx.Response(500, json={"message": "Try later"}),
                httpx.Response(200, json={"uuid": "retried"}),
            ]

            client = HebbianClient("https://api.example.test", "test-token")
            assert await client.get("/nodes/retried") == {"uuid": "retried"}

        assert route.call_count == 2

    async def test_get_retries_once_after_a_network_error(self) -> None:
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get("https://api.example.test/nodes/retried")
            route.side_effect = [
                httpx.ConnectError("network unavailable"),
                httpx.Response(200, json={"uuid": "retried"}),
            ]

            client = HebbianClient("https://api.example.test", "test-token")
            assert await client.get("/nodes/retried") == {"uuid": "retried"}

        assert route.call_count == 2

    async def test_get_fails_after_exactly_two_5xx_attempts(self) -> None:
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get("https://api.example.test/nodes/retried")
            route.side_effect = [
                httpx.Response(500, json={"message": "first failure"}),
                httpx.Response(500, json={"code": "server_error", "message": "second failure"}),
            ]

            client = HebbianClient("https://api.example.test", "test-token")
            with pytest.raises(HebbianApiError, match="second failure") as exc_info:
                await client.get("/nodes/retried")

        assert exc_info.value.status_code == 500
        assert route.call_count == 2


def test_handshake_version_matches_package_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    package_metadata = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    monkeypatch.setattr(
        "hebbianvault_mcp.server.load_config",
        lambda: HebbianConfig(api_url="https://api.example.test", token="test-token"),
    )
    server = create_server()

    assert SERVER_VERSION == package_metadata["project"]["version"]
    assert server.create_initialization_options().server_version == SERVER_VERSION
