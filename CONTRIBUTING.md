# Contributing to hebbian-mcp

Bug fixes and protocol-compliance improvements are welcome. Broader feature additions need an issue discussion first to align with the closed-source API roadmap.

## What this repo covers

This repo contains the customer-installable adapter packages only — thin bearer-auth shims that marshal MCP-protocol calls into HTTPS requests against the Hebbian API. No proprietary logic lives here. All access control, graph logic, and synthesis are server-side.

## Thin client rule

This repo is a thin client and stays one. It holds transport, auth handoff, tool schemas, client-side secret redaction, and calls to `api.hebbianvault.com`. It holds no product logic: no access or scope rules, no ranking or synthesis, no database, graph, or storage clients, and no credentials. All product behaviour lives behind the Hebbian API.

CI enforces this with `scripts/check_thin_client.py`, which fails on imports of database or storage clients and on any host other than `api.hebbianvault.com` or localhost.

## Bug fixes

Open a PR. Include:
- What the bug is and how to reproduce it.
- The fix and why it is correct.
- A test that covers the regression.

## Protocol compliance

The adapter implements the [Model Context Protocol](https://modelcontextprotocol.io) (MCP). If you find a deviation from the spec, open an issue with the spec reference and a concrete description of the behaviour difference.

## Feature requests

Open an issue before writing code. Features that require API surface changes need coordination with the closed-source Hebbian API team. We will let you know in the issue whether the API already supports the feature or whether it is on the roadmap.

## Style

- TypeScript: ESM modules, strict mode, `biome` for linting.
- Python: 3.11+, `ruff` for linting, `pyright` for type-checking.

## Tests

Every change must pass existing tests and add coverage for new behaviour. Run:

```bash
# TypeScript
cd ts/ && npm test

# Python
cd py/ && pytest
```

## Code of conduct

Be direct and specific. Assume good faith. Focus on the code.
