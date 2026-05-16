"""
hebbian_mcp_tenant.config — Configuration loading.

Auth: bearer token from HEBBIAN_API_TOKEN env var (preferred) or
      HEBBIAN_TOKEN (alternative) or config-file JSON path.
URL:  HEBBIAN_API_URL env var (default: placeholder, apex parked — ADR-023).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# TODO(apex): replace placeholder once domain name is locked (ADR-023 URL correction 2026-05-09)
DEFAULT_API_URL = "https://api.<saas-apex>"


@dataclass(frozen=True)
class HebbianConfig:
    """Resolved configuration for the MCP server."""

    api_url: str
    """Base URL of the Hebbian API. Configurable for Enterprise self-host."""

    token: str
    """Bearer token for authentication. Never log this value."""


def load_config() -> HebbianConfig:
    """
    Load configuration from environment variables and optional config file.

    Priority (highest first):
      1. HEBBIAN_API_TOKEN / HEBBIAN_TOKEN env vars
      2. HEBBIAN_CONFIG_PATH — path to a JSON config file
      3. ~/.config/hebbian/mcp-tenant.json

    Raises:
        RuntimeError: if no token can be resolved.
    """
    api_url = os.environ.get("HEBBIAN_API_URL", DEFAULT_API_URL)

    # ── Token from env ─────────────────────────────────────────────────────────
    env_token = os.environ.get("HEBBIAN_API_TOKEN") or os.environ.get("HEBBIAN_TOKEN")
    if env_token:
        return HebbianConfig(api_url=api_url, token=env_token)

    # ── Token from config file ─────────────────────────────────────────────────
    config_path = _resolve_config_path()
    if config_path:
        file_cfg = _read_config_file(config_path)
        if file_cfg.get("token"):
            return HebbianConfig(
                api_url=file_cfg.get("api_url", api_url),
                token=file_cfg["token"],
            )

    raise RuntimeError(
        "Hebbian MCP: No API token found. "
        "Set HEBBIAN_API_TOKEN env var or HEBBIAN_TOKEN env var, "
        "or write your token to ~/.config/hebbian/mcp-tenant.json as "
        '{"token": "hbn_..."}. '
        "Generate a token from the AI Tools tab in your Hebbian integrations page."
    )


def _resolve_config_path() -> Path | None:
    """Resolve config file path — explicit env var or XDG default."""
    explicit = os.environ.get("HEBBIAN_CONFIG_PATH")
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if p.exists():
            return p
        logger.warning(
            "HEBBIAN_CONFIG_PATH set to %r but file not found.", explicit
        )
        return None

    home = Path.home()
    default = home / ".config" / "hebbian" / "mcp-tenant.json"
    return default if default.exists() else None


def _read_config_file(path: Path) -> dict[str, str]:
    """Read and parse a JSON config file; tolerates missing fields."""
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Config file must be a JSON object")
        return {k: str(v) for k, v in parsed.items() if isinstance(v, str)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read config file at %r: %s", str(path), exc)
        return {}
