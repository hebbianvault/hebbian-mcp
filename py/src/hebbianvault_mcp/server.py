#!/usr/bin/env python3
"""
hebbianvault_mcp.server — MCP server entry point.

Boots the Hebbian tenant MCP server over stdio transport.

Usage:
    python -m hebbianvault_mcp.server
    hebbian-mcp          # via pyproject.toml [project.scripts]

Auth:
    HEBBIAN_API_TOKEN env var (or HEBBIAN_TOKEN)
    or ~/.config/hebbian/mcp-tenant.json with {"token": "hbn_..."}
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .client import HebbianApiError, HebbianClient
from .config import HebbianConfig, load_config
from .package_info import PACKAGE_VERSION
from .tools import TOOL_HANDLERS, TOOL_SCHEMAS

logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("hebbianvault_mcp")

SERVER_NAME = "hebbianvault-mcp"
SERVER_VERSION = PACKAGE_VERSION


def create_server(
    config: HebbianConfig | None = None,
    client: HebbianClient | None = None,
) -> Server:
    """
    Create and configure the Hebbian MCP server.

    Call server.run() or use as an async context to start serving.
    """
    config = config or load_config()
    client = client or HebbianClient(
        api_url=config.api_url,
        token=config.token,
        tenant=config.tenant,
    )

    app = Server(SERVER_NAME, version=SERVER_VERSION)

    @app.list_tools()
    async def list_tools() -> list[Tool]:  # type: ignore[override]
        return [
            Tool(
                name=schema["name"],
                description=schema["description"],
                inputSchema=schema["inputSchema"],
            )
            for schema in TOOL_SCHEMAS
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:  # type: ignore[override]
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            return [
                TextContent(
                    type="text",
                    text=f"Unknown tool: {name}. Available tools: {', '.join(TOOL_HANDLERS)}",
                )
            ]
        try:
            result = await handler(client, arguments or {})
            return [TextContent(type="text", text=result)]
        except Exception as exc:  # noqa: BLE001
            logger.error("Tool %r raised: %s", name, exc)
            return [TextContent(type="text", text=f"Error: {exc}")]

    logger.info(
        "%s@%s started. API: %s",
        SERVER_NAME,
        SERVER_VERSION,
        config.api_url,
    )
    return app


def _startup_health_hint(error: Exception) -> str:
    """Turn a startup probe failure into a safe, actionable stderr hint."""
    if isinstance(error, HebbianApiError):
        if error.status_code == 401:
            return (
                "authentication rejected (401). Your token may be invalid, expired, or revoked. "
                "Generate a new token from the AI Tools tab in your Hebbian integrations page."
            )
        if error.status_code == 403:
            return "access denied (403). Check that the token scope and selected tenant are valid."
    return "API unreachable or unavailable. Check your network connection and HEBBIAN_API_URL."


def _write_stderr(line: str) -> None:
    print(line, file=sys.stderr)


async def run_startup_health_check(
    client: HebbianClient,
    write_stderr: Callable[[str], None] = _write_stderr,
) -> None:
    """Check API reachability and token identity without preventing MCP startup."""
    try:
        await client.get("/healthz")
        await client.get("/tenant/whoami")
    except Exception as exc:  # noqa: BLE001 - startup probes must never crash serving
        write_stderr(f"[hebbian-mcp] Startup health check failed: {_startup_health_hint(exc)}")


async def start_serving_after_health_check(
    client: HebbianClient,
    start_serving: Callable[[], Awaitable[None]],
    write_stderr: Callable[[str], None] = _write_stderr,
) -> None:
    """Run the advisory probe before the MCP transport begins serving."""
    await run_startup_health_check(client, write_stderr)
    await start_serving()


def main() -> None:
    """Entry point for `hebbian-mcp` CLI command."""
    config = load_config()
    client = HebbianClient(api_url=config.api_url, token=config.token, tenant=config.tenant)
    server = create_server(config=config, client=client)

    async def _serve() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    try:
        asyncio.run(start_serving_after_health_check(client, _serve))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
