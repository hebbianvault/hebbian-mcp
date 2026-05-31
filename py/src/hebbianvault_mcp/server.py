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
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .client import HebbianClient
from .config import load_config
from .tools import TOOL_HANDLERS, TOOL_SCHEMAS

logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("hebbianvault_mcp")

SERVER_NAME = "hebbianvault-mcp"
SERVER_VERSION = "0.1.0"


def create_server() -> Server:
    """
    Create and configure the Hebbian MCP server.

    Call server.run() or use as an async context to start serving.
    """
    config = load_config()
    client = HebbianClient(api_url=config.api_url, token=config.token, tenant=config.tenant)

    app = Server(SERVER_NAME)

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


def main() -> None:
    """Entry point for `hebbian-mcp` CLI command."""
    server = create_server()

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
