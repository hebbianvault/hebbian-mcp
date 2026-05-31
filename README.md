<p align="center">
  <img src="brand/hebbian-lockup-cyan.png" alt="Hebbian" width="520">
</p>

# hebbian-mcp

[![npm](https://img.shields.io/npm/v/@hebbianvault/mcp?logo=npm)](https://www.npmjs.com/package/@hebbianvault/mcp)
[![PyPI](https://img.shields.io/pypi/v/hebbianvault-mcp?logo=pypi&logoColor=white)](https://pypi.org/project/hebbianvault-mcp/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Customer-installable adapter that connects Claude Code, Claude Desktop, Cursor, and any MCP-compatible agent to your Hebbian workspace.

The adapter is a thin client. Your token goes in; the Hebbian service decides what you can read and write. This package contains no business logic — it is intentionally small and auditable before you paste a credential.

## Install

Both packages are published and expose the same 8 tools and the same configuration — use whichever matches your MCP host.

```bash
# Node.js (npm) — run directly, no global install needed
npx @hebbianvault/mcp

# Python (PyPI)
pip install hebbianvault-mcp   # or: uv pip install hebbianvault-mcp
```

See [Quick start (TypeScript)](#quick-start-typescript) and [Quick start (Python)](#quick-start-python) below for adding the server to your MCP host and generating a token.

## Packages

| Package | Language | Install |
|---|---|---|
| `@hebbianvault/mcp` | TypeScript / Node.js | `npm install -g @hebbianvault/mcp` |
| `hebbianvault-mcp` | Python | `pip install hebbianvault-mcp` |

Both expose the same 8 tools and the same configuration. Use whichever matches your MCP host.

## Quick start (TypeScript)

```bash
npm install -g @hebbianvault/mcp
```

Generate a token from your Hebbian integrations page (AI Tools tab → Generate token), then add the server to your MCP host.

### Claude Code

```bash
claude mcp add hebbian \
  -e HEBBIAN_API_TOKEN=your_token_here \
  -- npx -y @hebbianvault/mcp
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hebbian": {
      "command": "npx",
      "args": ["-y", "@hebbianvault/mcp"],
      "env": {
        "HEBBIAN_API_TOKEN": "your_token_here"
      }
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
      "env": {
        "HEBBIAN_API_TOKEN": "your_token_here"
      }
    }
  }
}
```

## Quick start (Python)

```bash
pip install hebbianvault-mcp
# or with uv (preferred)
uv add hebbianvault-mcp
```

```bash
HEBBIAN_API_TOKEN=your_token_here hebbian-mcp
```

## Token scope

Your token determines what the adapter can see and do — a personal-workspace token gives access to your own knowledge; a company-workspace token gives access to the shared company workspace (where your role allows). Scope is decided by the Hebbian service, not by this package.

Generate, name, and revoke tokens from the AI Tools tab of your Hebbian integrations page. Never commit tokens to git.

## Tools

| Tool | What it does |
|---|---|
| `hebbian_read_node` | Read a single node by UUID (content, metadata, connected edges) |
| `hebbian_search` | Find nodes in your workspace matching a query |
| `hebbian_ask` | Ask a question and get an answer backed by source quotes |
| `hebbian_capture` | Write a note into your workspace |
| `hebbian_traverse` | Explore nodes connected to a starting node |
| `hebbian_provenance` | See where a node's knowledge came from |
| `hebbian_salience` | See a node's recent activity over time |
| `hebbian_recent_activity` | Catch up on recent changes in your workspace |

All access control is decided by the Hebbian service; results only ever include what your token is allowed to see.

## Configuration

| Variable | Purpose |
|---|---|
| `HEBBIAN_API_TOKEN` | Your token (required). `HEBBIAN_TOKEN` is also accepted. |
| `HEBBIAN_API_URL` | Override the API base URL (Enterprise self-host). Defaults to the Hebbian SaaS API. |
| `HEBBIAN_TENANT` | Optional workspace slug — only needed if your account belongs to more than one workspace. |

### Config file (alternative)

Write `~/.config/hebbian/mcp-tenant.json`:

```json
{
  "token": "your_token_here"
}
```

Enterprise self-host customers add `"api_url": "https://api.your-hebbian-host.example"` (or set `HEBBIAN_API_URL`) to point the adapter at their own deployment.

## Security

- Tokens are bearer credentials — treat them like passwords.
- Never commit tokens to git. Use env vars or a config file outside your repo.
- A `401` response means your token is expired or revoked — generate a new one from the AI Tools tab.
- HTTPS-only transport.
- The adapter source is public so you can audit exactly what runs on your machine before pasting a credential. All access control is enforced by the Hebbian service.

## Source layout

```
ts/    — TypeScript package (@hebbianvault/mcp, npm)
py/    — Python package (hebbianvault-mcp, PyPI)
```

## Development

### TypeScript

```bash
cd ts/
npm install
npm run build
npm test
```

### Python

```bash
cd py/
uv venv && uv pip install -e ".[dev]"
pytest
ruff check src/ tests/
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0. See [LICENSE](LICENSE).

The Hebbian service this adapter connects to is proprietary. This adapter is the open-source reference client.
