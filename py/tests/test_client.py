"""Unit tests for HTTP client error formatting and package self-reporting."""

from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call

import httpx
import pytest

from hebbianvault_mcp.client import HebbianApiError, HebbianClient
from hebbianvault_mcp.config import HebbianConfig
from hebbianvault_mcp.server import (
    SERVER_VERSION,
    STARTUP_HEALTH_TIMEOUT_SECONDS,
    create_server,
    run_startup_health_check,
    start_serving_after_health_check,
)


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


@pytest.mark.asyncio
async def test_startup_probe_reports_garbage_token_before_tool_handling(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = MagicMock(spec=HebbianClient)
    client.get = AsyncMock(
        side_effect=[
            {"ok": True},
            HebbianApiError(401, "invalid_token", "garbage token"),
        ]
    )

    await run_startup_health_check(client)

    assert client.get.await_args_list == [call("/healthz"), call("/tenant/whoami")]
    stderr = capsys.readouterr().err
    assert stderr.count("Startup health check failed") == 1
    assert "authentication rejected (401)" in stderr
    assert "Generate a new token" in stderr
    assert "garbage token" not in stderr


@pytest.mark.asyncio
async def test_startup_probe_bounds_each_request_to_five_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock(spec=HebbianClient)
    client.get = AsyncMock(side_effect=[{"ok": True}, {"tenant_slug": "acme"}])
    timeouts: list[float] = []

    async def wait_for(awaitable: object, *, timeout: float) -> object:
        timeouts.append(timeout)
        return await awaitable  # type: ignore[misc]

    monkeypatch.setattr("hebbianvault_mcp.server.asyncio.wait_for", wait_for)

    await run_startup_health_check(client)

    assert timeouts == [STARTUP_HEALTH_TIMEOUT_SECONDS, STARTUP_HEALTH_TIMEOUT_SECONDS]


@pytest.mark.asyncio
async def test_startup_probe_reports_access_denied(capsys: pytest.CaptureFixture[str]) -> None:
    client = MagicMock(spec=HebbianClient)
    client.get = AsyncMock(side_effect=HebbianApiError(403, "forbidden", "scope"))

    await run_startup_health_check(client)

    assert "access denied (403)" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_startup_probe_reports_unreachable_api(capsys: pytest.CaptureFixture[str]) -> None:
    client = MagicMock(spec=HebbianClient)
    client.get = AsyncMock(side_effect=OSError("network unreachable"))

    await run_startup_health_check(client)

    assert "API unreachable or unavailable" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_garbage_token_diagnostic_precedes_mcp_transport_serving() -> None:
    client = MagicMock(spec=HebbianClient)
    client.get = AsyncMock(
        side_effect=[
            {"ok": True},
            HebbianApiError(401, "invalid_token", "garbage token"),
        ]
    )
    events: list[str] = []

    async def connect_transport() -> None:
        events.append("transport-connected")

    await start_serving_after_health_check(
        client,
        connect_transport,
        lambda line: events.append(f"stderr:{line}"),
    )

    assert len(events) == 2
    assert "authentication rejected (401)" in events[0]
    assert "Generate a new token" in events[0]
    assert "garbage token" not in events[0]
    assert events[1] == "transport-connected"
