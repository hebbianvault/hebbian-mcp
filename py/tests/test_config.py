"""
tests/test_config.py

Unit tests for hebbian_mcp_tenant.config — token loading priority logic.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from hebbian_mcp_tenant.config import load_config


class TestLoadConfig:
    def test_loads_token_from_hebbian_api_token_env(self) -> None:
        with patch.dict(os.environ, {"HEBBIAN_API_TOKEN": "hbn_emp_abc123", "HEBBIAN_TOKEN": ""}, clear=False):
            # Remove HEBBIAN_TOKEN to isolate
            env = {k: v for k, v in os.environ.items() if k != "HEBBIAN_TOKEN"}
            env["HEBBIAN_API_TOKEN"] = "hbn_emp_abc123"
            with patch.dict(os.environ, env, clear=True):
                cfg = load_config()
        assert cfg.token == "hbn_emp_abc123"

    def test_loads_token_from_hebbian_token_env_as_fallback(self) -> None:
        env = {k: v for k, v in os.environ.items()
               if k not in {"HEBBIAN_API_TOKEN", "HEBBIAN_TOKEN", "HEBBIAN_CONFIG_PATH"}}
        env["HEBBIAN_TOKEN"] = "hbn_co_xyz789"
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        assert cfg.token == "hbn_co_xyz789"

    def test_loads_token_from_config_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"token": "hbn_emp_from_file"}, f)
            config_path = f.name

        env = {k: v for k, v in os.environ.items()
               if k not in {"HEBBIAN_API_TOKEN", "HEBBIAN_TOKEN"}}
        env["HEBBIAN_CONFIG_PATH"] = config_path
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()

        assert cfg.token == "hbn_emp_from_file"
        Path(config_path).unlink(missing_ok=True)

    def test_loads_api_url_from_env(self) -> None:
        with patch.dict(os.environ, {
            "HEBBIAN_API_TOKEN": "hbn_any",
            "HEBBIAN_API_URL": "https://my.enterprise.api",
        }, clear=False):
            cfg = load_config()
        assert cfg.api_url == "https://my.enterprise.api"

    def test_raises_when_no_token_available(self) -> None:
        env = {k: v for k, v in os.environ.items()
               if k not in {"HEBBIAN_API_TOKEN", "HEBBIAN_TOKEN", "HEBBIAN_CONFIG_PATH"}}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="No API token found"):
                load_config()

    def test_config_file_api_url_overrides_default(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"token": "hbn_any", "api_url": "https://custom.api"}, f)
            config_path = f.name

        env = {k: v for k, v in os.environ.items()
               if k not in {"HEBBIAN_API_TOKEN", "HEBBIAN_TOKEN", "HEBBIAN_API_URL"}}
        env["HEBBIAN_CONFIG_PATH"] = config_path
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()

        assert cfg.api_url == "https://custom.api"
        Path(config_path).unlink(missing_ok=True)
