"""DEC #284: the everyday tool set carries no admin power.

usage, audit_log and the GDPR export are an opt-in admin set: not listed and
not callable unless HEBBIAN_ADMIN_TOOLS is on (off by default).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams, ListToolsRequest

from hebbianvault_mcp.client import HebbianClient
from hebbianvault_mcp.config import HebbianConfig, load_config
from hebbianvault_mcp.server import create_server

ADMIN = {"hebbian_usage", "hebbian_gdpr_export", "hebbian_audit_log"}


def _server(admin_tools: bool | None) -> tuple[object, MagicMock]:
    client = MagicMock(spec=HebbianClient)
    client.get = AsyncMock(return_value={"items": []})
    kwargs = {} if admin_tools is None else {"admin_tools": admin_tools}
    config = HebbianConfig(api_url="https://api.example.test", token="test-token", **kwargs)
    return create_server(config=config, client=client), client


async def _listed(server: object) -> set[str]:
    handler = server.request_handlers[ListToolsRequest]  # type: ignore[attr-defined]
    result = await handler(ListToolsRequest(method="tools/list"))
    return {tool.name for tool in result.root.tools}


async def _call(server: object, name: str) -> str:
    handler = server.request_handlers[CallToolRequest]  # type: ignore[attr-defined]
    result = await handler(
        CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(name=name, arguments={}),
        )
    )
    return "".join(getattr(item, "text", "") for item in result.root.content)


@pytest.mark.asyncio
async def test_default_listing_has_no_admin_tools() -> None:
    server, _ = _server(None)
    names = await _listed(server)
    assert not names & ADMIN
    assert {"hebbian_search", "hebbian_ask", "hebbian_read_node", "hebbian_capture"} <= names


@pytest.mark.asyncio
async def test_admin_tools_listed_only_with_opt_in() -> None:
    server, _ = _server(True)
    assert ADMIN <= await _listed(server)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(ADMIN))
async def test_admin_tool_call_refused_by_default(name: str) -> None:
    server, client = _server(None)
    text = await _call(server, name)
    assert "HEBBIAN_ADMIN_TOOLS" in text
    client.get.assert_not_awaited()


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, False), ("", False), ("0", False), ("no", False), ("1", True), ("true", True)],
)
def test_admin_tools_env_flag(
    monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool
) -> None:
    monkeypatch.setenv("HEBBIAN_API_TOKEN", "test-token")
    if value is None:
        monkeypatch.delenv("HEBBIAN_ADMIN_TOOLS", raising=False)
    else:
        monkeypatch.setenv("HEBBIAN_ADMIN_TOOLS", value)
    assert getattr(load_config(), "admin_tools", None) is expected
