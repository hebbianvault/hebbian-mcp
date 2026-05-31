# hebbianvault-mcp (Python)

Python sibling of `@hebbianvault/mcp`. Connect a Python MCP host to your Hebbian workspace — same 8 tools, same configuration. A thin client; all intelligence and access control live in the Hebbian service.

## Quick start

```bash
pip install hebbianvault-mcp
# or with uv (preferred)
uv add hebbianvault-mcp
```

Generate a token from your Hebbian integrations page (AI Tools tab → Generate token).

## Configuration

Set `HEBBIAN_API_TOKEN` (or `HEBBIAN_TOKEN`) env var:

```bash
HEBBIAN_API_TOKEN=your_token_here hebbian-mcp
```

Or write `~/.config/hebbian/mcp-tenant.json`:

```json
{
  "token": "your_token_here"
}
```

| Variable | Purpose |
|---|---|
| `HEBBIAN_API_TOKEN` | Your token (required). `HEBBIAN_TOKEN` is also accepted. |
| `HEBBIAN_API_URL` | Override the API base URL (Enterprise self-host). Defaults to the Hebbian SaaS API. |
| `HEBBIAN_TENANT` | Optional workspace slug — only needed if your account belongs to more than one workspace. |

## Generic agent config

```python
import os
os.environ["HEBBIAN_API_TOKEN"] = "your_token_here"
from hebbianvault_mcp import create_server
server = create_server()
# server.run() to start serving over stdio
```

## Token scope

Your token decides what the adapter can see and do — a personal-workspace token gives access to your own knowledge; a company-workspace token gives access to the shared company workspace (where your role allows). Scope is decided by the Hebbian service.

## Tools

| Tool | What it does |
|---|---|
| `hebbian_read_node` | Read a single node by UUID |
| `hebbian_search` | Find nodes in your workspace matching a query |
| `hebbian_ask` | Ask a question and get an answer backed by source quotes |
| `hebbian_capture` | Write a note into your workspace |
| `hebbian_traverse` | Explore nodes connected to a starting node |
| `hebbian_provenance` | See where a node's knowledge came from |
| `hebbian_salience` | See a node's recent activity over time |
| `hebbian_recent_activity` | Catch up on recent changes in your workspace |

Results only ever include what your token is allowed to see.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
pytest
ruff check src/ tests/
```

## Node.js version

The canonical package is `@hebbianvault/mcp` on npm. This Python sibling has identical tools and configuration. Use whichever matches your MCP host environment.

## License

Apache-2.0. See the root [LICENSE](../LICENSE) file.
