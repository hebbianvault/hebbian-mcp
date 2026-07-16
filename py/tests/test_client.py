"""Unit tests for HTTP client error formatting and package self-reporting."""

from __future__ import annotations

import tomllib
from pathlib import Path

import httpx
import pytest

from hebbianvault_mcp.client import HebbianApiError, HebbianClient
from hebbianvault_mcp.config import HebbianConfig
from hebbianvault_mcp.server import SERVER_VERSION, create_server


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
