"""Package metadata used for MCP self-identification."""

from __future__ import annotations

import tomllib
from importlib import metadata
from pathlib import Path


def _read_package_version() -> str:
    """Return installed package metadata, with a source-checkout fallback."""
    try:
        return metadata.version("hebbianvault-mcp")
    except metadata.PackageNotFoundError:
        pass
    except Exception:  # pragma: no cover - defensive metadata-reader fallback
        return "0.0.0-dev"

    try:
        package_file = Path(__file__).resolve().parents[2] / "pyproject.toml"
        package_data = tomllib.loads(package_file.read_text(encoding="utf-8"))
        return str(package_data["project"]["version"])
    except (FileNotFoundError, KeyError, OSError, TypeError, tomllib.TOMLDecodeError):
        return "0.0.0-dev"


PACKAGE_VERSION = _read_package_version()
