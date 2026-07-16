"""
hebbianvault_mcp — Customer-installable MCP server for the Hebbian tenant brain.

One package, scope-by-token (Employee or Company). Install in any MCP-compatible
Python environment. Configure with a token issued from your Hebbian integrations page.

Usage:
    $ hebbian-mcp

Or programmatically:
    from hebbianvault_mcp import create_server
    server = create_server()
    server.run()
"""

from .package_info import PACKAGE_VERSION

__version__ = PACKAGE_VERSION

from .server import create_server, main

__all__ = ["create_server", "main"]
