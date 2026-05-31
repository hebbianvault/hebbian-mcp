<p align="center">
  <img src="https://raw.githubusercontent.com/hebbianvault/hebbian-mcp/main/brand/hebbian-lockup-cyan.png" alt="Hebbian" width="520">
</p>

# @hebbianvault/mcp

Connect Claude Code, Claude Desktop, Cursor, and any MCP-compatible agent to your Hebbian workspace.

One package, configured with a single token. Install in your MCP host, paste a token issued from your Hebbian integrations page (AI Tools tab), and your agent can read from and write to your workspace. This package is a thin client — all the intelligence and access control lives in the Hebbian service.

## Quick start

```bash
# Install globally, or use npx — no install needed
npm install -g @hebbianvault/mcp
```

Generate a token from your Hebbian integrations page (AI Tools tab → Generate token).

## Configuration

### Claude Code (recommended)

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

### Config file (alternative to env var)

Write `~/.config/hebbian/mcp-tenant.json`:

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

## Token scope

Your token decides what the adapter can see and do — a personal-workspace token gives access to your own knowledge; a company-workspace token gives access to the shared company workspace (where your role allows). Scope is decided by the Hebbian service. The adapter just carries your token.

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

Results only ever include what your token is allowed to see.

## Security

- Tokens are bearer credentials — treat like passwords.
- Never commit tokens to git. Use env vars or a config file outside your repo.
- A `401` error means your token is expired or revoked — generate a new one from the AI Tools tab.
- HTTPS-only transport.

## Python

A Python sibling package is available as `hebbianvault-mcp` on PyPI. Same 8 tools, same configuration.

## Development

```bash
npm install
npm run build
npm test
```

## License

Apache-2.0. See the root [LICENSE](../LICENSE) file.
