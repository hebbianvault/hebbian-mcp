# hebbianvault-mcp (Python)

Python sibling of `@hebbianvault/mcp`. Connect a Python MCP host to your Hebbian workspace with the same 11 tools and the same configuration. A thin client; all intelligence and access control live in the Hebbian service.

## Quick start

```bash
pip install hebbianvault-mcp
# or with uv (preferred)
uv add hebbianvault-mcp
```

Generate a token from your Hebbian integrations page (AI Tools tab → Generate token).

## Host configuration

Use the configuration for your host below. Replace `your_token_here` with the token you generated.

### Claude Code

```bash
claude mcp add hebbian -e HEBBIAN_API_TOKEN=your_token_here -- npx -y @hebbianvault/mcp
```

### Codex (CLI + Desktop app)

```bash
codex mcp add hebbian --env HEBBIAN_API_TOKEN=your_token_here -- npx -y @hebbianvault/mcp
```

For the Codex desktop app, add this to `~/.codex/config.toml`, or use Settings → MCP servers:

```toml
[mcp_servers.hebbian]
command = "npx"
args = ["-y", "@hebbianvault/mcp"]
env = { HEBBIAN_API_TOKEN = "your_token_here" }
```

### Gemini CLI

```bash
gemini mcp add hebbian -e HEBBIAN_API_TOKEN=your_token_here npx -y @hebbianvault/mcp
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hebbian": {
      "command": "npx",
      "args": ["-y", "@hebbianvault/mcp"],
      "env": { "HEBBIAN_API_TOKEN": "your_token_here" }
    }
  }
}
```

### Cowork

```json
{
  "mcpServers": {
    "hebbian": {
      "command": "npx",
      "args": ["-y", "@hebbianvault/mcp"],
      "env": { "HEBBIAN_API_TOKEN": "your_token_here" }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "hebbian": {
      "command": "npx",
      "args": ["-y", "@hebbianvault/mcp"],
      "env": { "HEBBIAN_API_TOKEN": "your_token_here" }
    }
  }
}
```

### Generic Agent

For an MCP-compatible agent that accepts a standard input/output command:

```bash
HEBBIAN_API_TOKEN=your_token_here npx -y @hebbianvault/mcp
```

Or use the Python package:

```bash
# pip install hebbianvault-mcp   (or: uv add hebbianvault-mcp)
HEBBIAN_API_TOKEN=your_token_here hebbian-mcp
```

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

## Python server API

```python
import os
os.environ["HEBBIAN_API_TOKEN"] = "your_token_here"
from hebbianvault_mcp import create_server
server = create_server()
# server.run() to start serving over stdio
```

## Token scope

Your token decides what the adapter can see and do — a personal-workspace token gives access to your own knowledge; a company-workspace token gives access to the shared company workspace (where your role allows). Scope is decided by the Hebbian service. Graph-backed search, traverse, and provenance tools route company-scoped tokens to the company graph and other tokens to the workspace graph. If the advisory scope probe fails, the adapter caches the employee-graph fallback for its process lifetime; restarting the MCP process clears that cached fallback.

## Tools

| Tool | What it does |
|---|---|
| `hebbian_read_node` | Read a single node by UUID |
| `hebbian_search` | Find nodes in your workspace matching a query |
| `hebbian_ask` | Ask a question and get an answer backed by source quotes |
| `hebbian_context` | Describe a task and a token budget, get back a salience-ranked context pack that fits |
| `hebbian_capture` | Write a note into your workspace |
| `hebbian_traverse` | Explore nodes connected to a starting node |
| `hebbian_provenance` | See where a node's knowledge came from |
| `hebbian_salience` | See a node's recent activity over time |
| `hebbian_recent_activity` | Catch up on recent changes in your workspace |
| `hebbian_whoami` | Show the tenant, role, scope, and principal for your token |
| `hebbian_usage` | Show your usage and spend-meter summary; optionally view company usage |

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
