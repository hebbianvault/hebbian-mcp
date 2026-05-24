<p align="center">
  <img src="https://raw.githubusercontent.com/hebbianvault/hebbian-mcp/main/brand/hebbian-lockup-cyan.png" alt="Hebbian" width="520">
</p>

# @hebbianvault/mcp

Customer-installable MCP server for the Hebbian tenant brain.

One package, scope-by-token (Employee or Company). Install in Claude Code, Claude Desktop, Cursor, Cowork, or any MCP-compatible agent. Configure with a token issued from your Hebbian integrations page (AI Tools tab).

## Quick start

```bash
# Install globally (or use npx — no install needed)
npm install -g @hebbianvault/mcp
```

Generate a token from your Hebbian integrations page (AI Tools tab → Generate token).

## Configuration

### Claude Code (recommended)

```bash
claude mcp add hebbian \
  -e HEBBIAN_API_TOKEN=hbn_emp_your_token_here \
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
        "HEBBIAN_API_TOKEN": "hbn_emp_your_token_here"
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
        "HEBBIAN_API_TOKEN": "hbn_emp_your_token_here"
      }
    }
  }
}
```

### Config file (alternative to env var)

Write `~/.config/hebbian/mcp-tenant.json`:

```json
{
  "token": "hbn_emp_your_token_here",
  "api_url": "https://api.<saas-apex>"
}
```

> **Note:** `api.<saas-apex>` is a placeholder. The domain is parked (ADR-023, 2026-05-09). Enterprise self-host customers set `HEBBIAN_API_URL` to their VM's API endpoint.

## Token types

| Token prefix | Scope | Issued from |
|---|---|---|
| `hbn_emp_` | Employee — your personal brain | `/integrations?tab=tools` |
| `hbn_co_` | Company — full org brain (admin only) | `/co/integrations?tab=tools` |

Token scope is enforced at the API layer (RLS). The MCP is a thin bearer-auth client — it sends your token to every request; the API enforces what you can read and write.

## Tools

| Tool | Description |
|---|---|
| `hebbian_read_node` | Fetch a single node by UUID (body, frontmatter, provenance) |
| `hebbian_search` | Full-text + semantic search across vault nodes |
| `hebbian_ask` | Synthesis Q&A grounded in source_quotes (RAG) |
| `hebbian_capture` | Capture text as a new seed into the vault |
| `hebbian_traverse` | Walk the typed graph from a starting node |
| `hebbian_provenance` | Source trail for a node |
| `hebbian_salience` | Salience snapshot (no-op until SNN Phase 10) |
| `hebbian_recent_activity` | Recent brain activity timeline |

## Security

- Tokens are bearer credentials — treat like passwords.
- Never commit tokens to git. Use env vars or a config file outside your repo.
- Tokens expire after 90 days. Refresh from the AI Tools tab.
- A 401 error with code `TOKEN_EXPIRED` means your token needs refreshing.
- HTTPS-only transport; HTTP is rejected at the API edge.

## Python

A Python sibling package is available as `hebbianvault-mcp` on PyPI. Same 8 tools, same auth, same transport. See `packages/mcp-tenant-py/README.md`.

## Development

```bash
npm install
npm run build
npm test
```

## License

Apache-2.0. See the root [LICENSE](../LICENSE) file.
