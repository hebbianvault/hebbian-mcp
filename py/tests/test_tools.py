"""
tests/test_tools.py

Unit tests for hebbianvault-mcp tool handlers.

Tests mock the HebbianClient — no real HTTP calls. (End-to-end validation
against the live API is exercised separately; see the PR description.)
Coverage: endpoint/contract shaping, input validation, error handling.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from hebbianvault_mcp.client import HebbianApiError, HebbianClient
from hebbianvault_mcp.tools import (
    handle_ask,
    handle_capture,
    handle_context,
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


def _graph() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "uuid": "n1",
                "title": "2026 Company Strategy",
                "summary": "The annual company strategy and roadmap.",
                "domain": "Company",
                "archetype": "INDEX",
                "tags": ["strategy"],
                "edges": [{"to": "n2", "relation_type": "part_of", "weight": 0.7}],
                "provenance": {"path": "B", "source_artifacts": []},
            },
            {
                "uuid": "n2",
                "title": "Q2 Roadmap",
                "summary": "Product roadmap detail.",
                "domain": "Company",
                "archetype": "MOLECULE",
                "tags": [],
                "edges": [],
                "provenance": None,
            },
        ]
    }


# ── hebbian_read_node ─────────────────────────────────────────────────────────

class TestReadNode:
    UUID = "550e8400-e29b-41d4-a716-446655440000"

    @pytest.mark.asyncio
    async def test_calls_get_nodes_uuid(self) -> None:
        node = {"uuid": self.UUID, "frontmatter": {"title": "Test node"}}
        client = mock_client(get_return=node)
        result = await handle_read_node(client, {"uuid": self.UUID})
        client.get.assert_called_once_with(f"/nodes/{self.UUID}")
        assert json.loads(result) == node

    @pytest.mark.asyncio
    async def test_raises_on_missing_uuid(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'uuid' is required"):
            await handle_read_node(client, {"uuid": ""})

    @pytest.mark.asyncio
    async def test_surfaces_auth_error(self) -> None:
        client = mock_client(get_side_effect=HebbianApiError(401, "invalid_token", "x"))
        with pytest.raises(RuntimeError, match="Authentication failed"):
            await handle_read_node(client, {"uuid": self.UUID})


# ── hebbian_search (graph-derived) ─────────────────────────────────────────────

class TestSearch:
    @pytest.mark.asyncio
    async def test_fetches_graph_and_ranks(self) -> None:
        client = mock_client(get_return=_graph())
        out = json.loads(await handle_search(client, {"q": "strategy roadmap", "limit": 5}))
        client.get.assert_called_once_with("/vault/graph")
        assert out["count"] > 0
        assert out["results"][0]["uuid"] == "n1"
        assert "snippet" in out["results"][0]

    @pytest.mark.asyncio
    async def test_filters_by_domain(self) -> None:
        client = mock_client(get_return=_graph())
        out = json.loads(await handle_search(client, {"q": "roadmap", "domain": "Company"}))
        assert all(r["domain"] == "Company" for r in out["results"])

    @pytest.mark.asyncio
    async def test_clamps_limit(self) -> None:
        client = mock_client(get_return=_graph())
        out = json.loads(await handle_search(client, {"q": "strategy", "limit": 999}))
        assert out["count"] <= 50

    @pytest.mark.asyncio
    async def test_raises_on_empty_query(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'q' is required"):
            await handle_search(client, {"q": "   "})


# ── hebbian_ask ───────────────────────────────────────────────────────────────

class TestAsk:
    @pytest.mark.asyncio
    async def test_calls_post_ask_with_query(self) -> None:
        response = {"answer": "Yes", "sources": [], "scope_receipt": "ok"}
        client = mock_client(post_return=response)
        result = await handle_ask(client, {"question": "What is the strategy?"})
        client.post.assert_called_once_with("/ask", {"query": "What is the strategy?"})
        assert json.loads(result) == response

    @pytest.mark.asyncio
    async def test_raises_on_empty_question(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'question' is required"):
            await handle_ask(client, {"question": ""})

    @pytest.mark.asyncio
    async def test_surfaces_permission_denied(self) -> None:
        client = mock_client(post_side_effect=HebbianApiError(403, "forbidden", "scope"))
        with pytest.raises(RuntimeError, match="Permission denied"):
            await handle_ask(client, {"question": "test"})


# ── hebbian_context ────────────────────────────────────────────────────────────

class TestContext:
    @pytest.mark.asyncio
    async def test_calls_post_context_with_task_and_default_budget(self) -> None:
        response = {"items": [], "budget_tokens": 2000, "budget_used": 0, "truncated": False}
        client = mock_client(post_return=response)
        result = await handle_context(client, {"task": "draft the Q3 board update"})
        client.post.assert_called_once_with(
            "/v1/context", {"task": "draft the Q3 board update", "budget_tokens": 2000}
        )
        assert json.loads(result) == response

    @pytest.mark.asyncio
    async def test_passes_budget_and_scope_filter(self) -> None:
        client = mock_client(post_return={"items": []})
        await handle_context(
            client, {"task": "summarise pipeline", "budget_tokens": 800, "scope": "company"}
        )
        client.post.assert_called_once_with(
            "/v1/context",
            {"task": "summarise pipeline", "budget_tokens": 800, "filters": {"scope": "company"}},
        )

    @pytest.mark.asyncio
    async def test_clamps_budget_to_max(self) -> None:
        client = mock_client(post_return={"items": []})
        await handle_context(client, {"task": "anything", "budget_tokens": 9_999_999})
        body = client.post.call_args[0][1]
        assert body["budget_tokens"] == 32000

    @pytest.mark.asyncio
    async def test_raises_on_empty_task(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'task' is required"):
            await handle_context(client, {"task": ""})

    @pytest.mark.asyncio
    async def test_surfaces_permission_denied(self) -> None:
        client = mock_client(post_side_effect=HebbianApiError(403, "forbidden", "scope"))
        with pytest.raises(RuntimeError, match="Permission denied"):
            await handle_context(client, {"task": "test"})


# ── hebbian_capture ───────────────────────────────────────────────────────────

class TestCapture:
    @pytest.mark.asyncio
    async def test_calls_post_capture_with_title_body(self) -> None:
        response = {"uuid": "abc-123", "created": True}
        client = mock_client(post_return=response)
        result = await handle_capture(client, {"title": "Insight", "text": "Q3 note"})
        client.post.assert_called_once_with("/capture", {"title": "Insight", "body": "Q3 note"})
        assert json.loads(result) == response

    @pytest.mark.asyncio
    async def test_company_scope_maps_to_owner_kind(self) -> None:
        client = mock_client(post_return={"uuid": "x", "created": True})
        await handle_capture(
            client,
            {"title": "D", "text": "B", "domain": "Company", "tags": ["hr"], "scope": "company"},
        )
        client.post.assert_called_once_with(
            "/capture",
            {"title": "D", "body": "B", "domain": "Company", "tags": ["hr"], "owner_kind": "company"},
        )

    @pytest.mark.asyncio
    async def test_private_scope_omits_owner_kind(self) -> None:
        client = mock_client(post_return={"uuid": "x", "created": True})
        await handle_capture(client, {"title": "T", "text": "B", "scope": "private"})
        body = client.post.call_args.args[1]
        assert "owner_kind" not in body

    @pytest.mark.asyncio
    async def test_raises_on_empty_fields(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'title' is required"):
            await handle_capture(client, {"title": "", "text": "x"})
        with pytest.raises(ValueError, match="'text' is required"):
            await handle_capture(client, {"title": "x", "text": ""})


# ── hebbian_traverse (graph-derived BFS) ───────────────────────────────────────

class TestTraverse:
    @pytest.mark.asyncio
    async def test_walks_to_edge_shape(self) -> None:
        client = mock_client(get_return=_graph())
        out = json.loads(await handle_traverse(client, {"start_uuid": "n1", "max_hops": 2}))
        client.get.assert_called_once_with("/vault/graph")
        assert out["node_count"] == 2
        assert out["edge_count"] == 1
        assert out["edges"][0]["source_uuid"] == "n1"
        assert out["edges"][0]["target_uuid"] == "n2"

    @pytest.mark.asyncio
    async def test_missing_start_friendly(self) -> None:
        client = mock_client(get_return=_graph())
        out = json.loads(await handle_traverse(client, {"start_uuid": "missing"}))
        assert out["nodes"] == []
        assert "not found" in out["message"].lower()

    @pytest.mark.asyncio
    async def test_raises_on_missing_start(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'start_uuid' is required"):
            await handle_traverse(client, {"start_uuid": ""})


# ── hebbian_provenance (graph-derived) ─────────────────────────────────────────

class TestProvenance:
    @pytest.mark.asyncio
    async def test_returns_provenance(self) -> None:
        client = mock_client(get_return=_graph())
        out = json.loads(await handle_provenance(client, {"uuid": "n1"}))
        client.get.assert_called_once_with("/vault/graph")
        assert out["uuid"] == "n1"
        assert out["provenance"]["path"] == "B"

    @pytest.mark.asyncio
    async def test_missing_node_friendly(self) -> None:
        client = mock_client(get_return=_graph())
        out = json.loads(await handle_provenance(client, {"uuid": "nope"}))
        assert out["provenance"] is None
        assert "not found" in out["message"].lower()

    @pytest.mark.asyncio
    async def test_raises_on_empty_uuid(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'uuid' is required"):
            await handle_provenance(client, {"uuid": ""})


# ── hebbian_salience ──────────────────────────────────────────────────────────

class TestSalience:
    UUID = "salience-uuid"

    @pytest.mark.asyncio
    async def test_calls_activation_history(self) -> None:
        data = {"node_uuid": self.UUID, "count": 0, "history": []}
        client = mock_client(get_return=data)
        result = await handle_salience(client, {"uuid": self.UUID})
        client.get.assert_called_once_with(f"/metrics/nodes/{self.UUID}/activation-history")
        assert json.loads(result) == data

    @pytest.mark.asyncio
    async def test_surfaces_auth_error(self) -> None:
        client = mock_client(get_side_effect=HebbianApiError(401, "invalid_token", "x"))
        with pytest.raises(RuntimeError, match="Authentication failed"):
            await handle_salience(client, {"uuid": self.UUID})

    @pytest.mark.asyncio
    async def test_raises_on_empty_uuid(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="'uuid' is required"):
            await handle_salience(client, {"uuid": ""})


# ── hebbian_recent_activity ───────────────────────────────────────────────────

class TestRecentActivity:
    @pytest.mark.asyncio
    async def test_calls_vault_activity_default_limit(self) -> None:
        client = mock_client(get_return={"events": [], "total": 0})
        await handle_recent_activity(client, {})
        client.get.assert_called_once_with("/vault/activity", params={"limit": 20})

    @pytest.mark.asyncio
    async def test_passes_since(self) -> None:
        client = mock_client(get_return={"events": [], "total": 0})
        await handle_recent_activity(client, {"since": "2026-05-14T09:00:00Z", "limit": 10})
        client.get.assert_called_once_with(
            "/vault/activity", params={"limit": 10, "since": "2026-05-14T09:00:00Z"}
        )

    @pytest.mark.asyncio
    async def test_clamps_limit(self) -> None:
        client = mock_client(get_return={"events": [], "total": 0})
        await handle_recent_activity(client, {"limit": 999})
        client.get.assert_called_once_with("/vault/activity", params={"limit": 100})

    @pytest.mark.asyncio
    async def test_raises_on_invalid_since(self) -> None:
        client = mock_client()
        with pytest.raises(ValueError, match="valid ISO 8601"):
            await handle_recent_activity(client, {"since": "not-a-date"})
