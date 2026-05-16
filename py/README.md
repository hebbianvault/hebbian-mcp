# hebbian-mcp-tenant (Python)

Python sibling of `@hebbian/mcp-tenant`. Customer-installable MCP server for the Hebbian tenant brain. Same 8 tools, same auth, same transport — for Python MCP hosts.

## Quick start

```bash
pip install hebbian-mcp-tenant
# or with uv (preferred)
uv add hebbian-mcp-tenant
```

Generate a token from your Hebbian integrations page (AI Tools tab → Generate token).

## Configuration

Set `HEBBIAN_API_TOKEN` (or `HEBBIAN_TOKEN`) env var:

```bash
HEBBIAN_API_TOKEN=hbn_emp_your_token_here hebbian-mcp
```

Or write `~/.config/hebbian/mcp-tenant.json`:

```json
{
  "token": "hbn_emp_your_token_here",
  "api_url": "https://api.<saas-apex>"
}
```

> **Note:** `api.<saas-apex>` is a placeholder. Enterprise self-host customers set `HEBBIAN_API_URL` to their VM's API endpoint.

## Generic agent config

```python
import os
os.environ["HEBBIAN_API_TOKEN"] = "hbn_emp_your_token_here"
from hebbian_mcp_tenant import create_server
server = create_server()
# server.run() to start serving over stdio
```

## Tools

| Tool | Description |
|---|---|
| `hebbian_read_node` | Fetch a single node by UUID |
| `hebbian_search` | Full-text + semantic search |
| `hebbian_ask` | Synthesis Q&A grounded in source_quotes |
| `hebbian_capture` | Capture text as a new seed |
| `hebbian_traverse` | Walk the typed graph |
| `hebbian_provenance` | Source trail for a node |
| `hebbian_salience` | Salience snapshot (no-op until SNN Phase 10) |
| `hebbian_recent_activity` | Recent brain activity timeline |

## Development

```bash
uv install --dev
pytest
ruff check src/ tests/
```

## Node.js version

The canonical package is `@hebbian/mcp-tenant` on npm. This Python sibling has identical tool shapes and auth. Use whichever matches your MCP host environment.

## License

UNLICENSED — proprietary. See the Hebbian Enterprise License Agreement.
