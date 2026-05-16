"""
tests/test_tools.py

Unit tests for hebbian-mcp-tenant tool handlers.

Tests mock the HebbianClient — no real HTTP calls.
Coverage: input validation, happy-path response shaping, error handling
for each of the 8 tools.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from hebbian_mcp_tenant.client import HebbianApiError, HebbianClient
from hebbian_mcp_tenant.tools import (
    handle_ask,
    handle_capture,
    handle_provenance,
    handle_read_node,
    handle_recent_activity,
    handle_salience,
    handle_search,
    handle_traverse,
)

# ── Mock client factory ───────────────────────────────────────────────────────

def mock_client(
    get_return: Any = None,
    post_return: Any = None,
    get_side_effect: Any = None,
    post_side_effect: Any = None,
) -> HebbianClient:
    client = MagicMock(spec=HebbianClient)
    client.get = AsyncMock(return_value=get_return, side_effect=get_side_effect)
    client.post = AsyncMock(return_value=post_return, side_effect=post_side_effect)
    return client  # type: ignore[return-value]


# ── hebbian_read_node ─────────────────────────────────────────────────────────

class TestReadNode:
    UUID = "550e8400-e29b-41d4-a716-446655440000"

    async def test_calls_get_nodes_uuid(self) -> None:
        node = {"uuid": self.UUID, "title": "Test node", "domain": "Compass"}
        client = mock_client(get_return=node)

        result = await handle_read_node(client, {"uuid": self.UUID})

        client.get.assert_called_once_with(f"/api/v1/nodes/{self.UUID}")
        assert json.loads(result) == node

    async def test_raises_on_missing_uuid(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'uuid' is required"):
            await handle_read_node(client, {"uuid": ""})

    async def test_surfaces_401_as_auth_error(self) -> None:
        client = mock_client(
            get_side_effect=HebbianApiError(401, "TOKEN_EXPIRED", "Token expired")
        )
        with pytest.raises(RuntimeError, match="Authentication failed"):
            await handle_read_node(client, {"uuid": self.UUID})

    async def test_surfaces_404_as_not_found(self) -> None:
        client = mock_client(
            get_side_effect=HebbianApiError(404, "NODE_NOT_FOUND", "Not found")
        )
        with pytest.raises(RuntimeError, match="Not found"):
            await handle_read_node(client, {"uuid": self.UUID})


# ── hebbian_search ────────────────────────────────────────────────────────────

class TestSearch:
    async def test_calls_get_search_with_query(self) -> None:
        results = {"nodes": [], "total": 0}
        client = mock_client(get_return=results)

        await handle_search(client, {"q": "project decisions", "limit": 5})

        client.get.assert_called_once_with(
            "/api/v1/search",
            params={"q": "project decisions", "limit": 5},
        )

    async def test_passes_lens_and_types(self) -> None:
        client = mock_client(get_return={"nodes": [], "total": 0})

        await handle_search(client, {
            "q": "strategy",
            "lens": "Company",
            "types": ["Decision", "Principle"],
        })

        call_params = client.get.call_args[1]["params"]
        assert call_params["lens"] == "Company"
        assert call_params["types"] == "Decision,Principle"

    async def test_raises_on_empty_query(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'q' is required"):
            await handle_search(client, {"q": "   "})

    async def test_clamps_limit_to_50(self) -> None:
        client = mock_client(get_return={"nodes": [], "total": 0})
        await handle_search(client, {"q": "test", "limit": 999})

        call_params = client.get.call_args[1]["params"]
        assert call_params["limit"] == 50


# ── hebbian_ask ───────────────────────────────────────────────────────────────

class TestAsk:
    async def test_calls_post_ask(self) -> None:
        response = {"answer": "Yes", "citations": [], "lens_scope": {}}
        client = mock_client(post_return=response)

        result = await handle_ask(client, {"question": "What is the strategy?"})

        client.post.assert_called_once_with(
            "/api/v1/ask", {"question": "What is the strategy?"}
        )
        assert json.loads(result) == response

    async def test_raises_on_empty_question(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'question' is required"):
            await handle_ask(client, {"question": ""})

    async def test_surfaces_403_as_permission_denied(self) -> None:
        client = mock_client(
            post_side_effect=HebbianApiError(403, "SCOPE_INSUFFICIENT", "Company scope required")
        )
        with pytest.raises(RuntimeError, match="Permission denied"):
            await handle_ask(client, {"question": "test"})


# ── hebbian_capture ───────────────────────────────────────────────────────────

class TestCapture:
    async def test_calls_post_capture(self) -> None:
        response = {"seed_uuid": "abc", "status": "promoted", "node_uuid": "def"}
        client = mock_client(post_return=response)

        result = await handle_capture(client, {"text": "Important insight"})

        client.post.assert_called_once_with(
            "/api/v1/capture", {"text": "Important insight"}
        )
        assert json.loads(result) == response

    async def test_includes_lens_and_subject(self) -> None:
        client = mock_client(post_return={"seed_uuid": "x", "status": "pending"})

        await handle_capture(client, {
            "text": "Decision about hiring",
            "lens": "Company",
            "subject": "Acme",
        })

        client.post.assert_called_once_with(
            "/api/v1/capture",
            {"text": "Decision about hiring", "lens": "Company", "subject": "Acme"},
        )

    async def test_raises_on_empty_text(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'text' is required"):
            await handle_capture(client, {"text": ""})


# ── hebbian_traverse ──────────────────────────────────────────────────────────

class TestTraverse:
    UUID = "traverse-uuid"

    async def test_calls_get_traverse_with_default_hops(self) -> None:
        response = {"nodes": [], "edges": [], "start_uuid": self.UUID, "hops": 2}
        client = mock_client(get_return=response)

        await handle_traverse(client, {"start_uuid": self.UUID})

        client.get.assert_called_once_with(
            f"/api/v1/traverse/{self.UUID}",
            params={"max_hops": 2},
        )

    async def test_clamps_max_hops_to_5(self) -> None:
        client = mock_client(get_return={"nodes": [], "edges": [], "start_uuid": self.UUID, "hops": 5})

        await handle_traverse(client, {"start_uuid": self.UUID, "max_hops": 100})

        call_params = client.get.call_args[1]["params"]
        assert call_params["max_hops"] == 5

    async def test_raises_on_missing_start_uuid(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'start_uuid' is required"):
            await handle_traverse(client, {"start_uuid": ""})


# ── hebbian_provenance ────────────────────────────────────────────────────────

class TestProvenance:
    UUID = "prov-uuid"

    async def test_calls_get_provenance(self) -> None:
        response = {"uuid": self.UUID, "paths": [], "source_quotes": [], "intake_events": []}
        client = mock_client(get_return=response)

        result = await handle_provenance(client, {"uuid": self.UUID})

        client.get.assert_called_once_with(f"/api/v1/nodes/{self.UUID}/provenance")
        assert json.loads(result) == response

    async def test_raises_on_empty_uuid(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'uuid' is required"):
            await handle_provenance(client, {"uuid": ""})


# ── hebbian_salience ──────────────────────────────────────────────────────────

class TestSalience:
    UUID = "salience-uuid"

    async def test_returns_stub_when_404(self) -> None:
        client = mock_client(
            get_side_effect=HebbianApiError(404, "NOT_FOUND", "Salience endpoint not found")
        )

        result = await handle_salience(client, {"uuid": self.UUID})
        parsed = json.loads(result)

        assert parsed["status"] == "pending_snn_p10"
        assert parsed["uuid"] == self.UUID
        assert parsed["synaptic_fidelity"] is None

    async def test_returns_real_data_when_api_responds(self) -> None:
        real_data = {"uuid": self.UUID, "activation_strength": 0.87, "synaptic_fidelity": 0.92}
        client = mock_client(get_return=real_data)

        result = await handle_salience(client, {"uuid": self.UUID})
        assert json.loads(result) == real_data

    async def test_raises_on_401_not_swallowed(self) -> None:
        client = mock_client(
            get_side_effect=HebbianApiError(401, "TOKEN_EXPIRED", "Expired")
        )
        with pytest.raises(RuntimeError, match="Authentication failed"):
            await handle_salience(client, {"uuid": self.UUID})

    async def test_raises_on_empty_uuid(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'uuid' is required"):
            await handle_salience(client, {"uuid": ""})


# ── hebbian_recent_activity ───────────────────────────────────────────────────

class TestRecentActivity:
    async def test_calls_get_activity_with_default_limit(self) -> None:
        response = {"items": [], "total": 0, "generated_at": "2026-05-15T12:00:00Z"}
        client = mock_client(get_return=response)

        await handle_recent_activity(client, {})

        call_params = client.get.call_args[1]["params"]
        assert call_params["limit"] == 20

    async def test_passes_since_param(self) -> None:
        client = mock_client(get_return={"items": [], "total": 0, "generated_at": ""})

        await handle_recent_activity(client, {
            "since": "2026-05-14T09:00:00Z",
            "limit": 10,
        })

        call_params = client.get.call_args[1]["params"]
        assert call_params["since"] == "2026-05-14T09:00:00Z"
        assert call_params["limit"] == 10

    async def test_clamps_limit_to_100(self) -> None:
        client = mock_client(get_return={"items": [], "total": 0, "generated_at": ""})
        await handle_recent_activity(client, {"limit": 999})

        call_params = client.get.call_args[1]["params"]
        assert call_params["limit"] == 100

    async def test_raises_on_invalid_since(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="valid ISO 8601 datetime"):
            await handle_recent_activity(client, {"since": "not-a-date"})


# ── HebbianApiError ───────────────────────────────────────────────────────────

class TestHebbianApiError:
    def test_401_includes_refresh_hint(self) -> None:
        err = HebbianApiError(401, "TOKEN_EXPIRED", "Expired")
        assert "Generate a new token" in err.to_tool_error()

    def test_403_includes_scope_hint(self) -> None:
        err = HebbianApiError(403, "SCOPE_DENIED", "Denied")
        assert "token scope" in err.to_tool_error()

    def test_429_includes_retry_hint(self) -> None:
        err = HebbianApiError(429, "RATE_LIMITED", "Too many requests")
        assert "Slow down" in err.to_tool_error()

    def test_500_includes_status_code(self) -> None:
        err = HebbianApiError(500, "INTERNAL_ERROR", "Server fault")
        assert "500" in err.to_tool_error()
