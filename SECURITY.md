# Security Policy

## Supported versions

The latest published version of `@hebbianvault/mcp` (npm) and `hebbianvault-mcp` (PyPI) receive security fixes. Older versions are not backported.

## Reporting a vulnerability

Report security vulnerabilities to: `security@hebbian.ai` (placeholder — domain TBD).

Please do not open a public GitHub issue for security vulnerabilities.

### What to include

- Description of the vulnerability and its potential impact.
- Steps to reproduce.
- Any relevant code or configuration.

### Response timeline

- Acknowledgement within 48 hours of receipt.
- Status update within 7 days.
- Fix or remediation plan within 90 days.

We follow responsible disclosure: we ask that you do not publish details publicly until we have had 90 days to investigate and patch.

## Scope

This repo covers the adapter packages only. Vulnerabilities in the Hebbian API (server-side) should also be sent to the same address — the server is not in scope for this repo but we will route reports appropriately.

## Token security

Workspace tokens are bearer credentials. If you believe a token has been exposed, rotate it immediately from the Hebbian AI Tools tab.

Never commit tokens to git. The adapter reads tokens from environment variables (`HEBBIAN_API_TOKEN`) or a config file (`~/.config/hebbian/mcp-tenant.json`) that should be outside any git repository.
