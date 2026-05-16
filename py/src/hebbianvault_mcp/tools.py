"""
hebbianvault_mcp.tools — All 8 Hebbian MCP tool definitions + handlers.

Tools are 1:1 with Hebbian API cognitive endpoints (ADR-023).
Each tool handler takes a HebbianClient and returns a JSON-serialisable string.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from .client import HebbianApiError, HebbianClient

logger = logging.getLogger(__name__)

# Valid domain/lens values (from knowledge-graph.md)
VALID_LENSES = frozenset({
    "Mirror", "Compass", "Axis", "Company", "CRM", "EMAIL", "LEEXI",
    "Finance", "Oracle",
})

VALID_TYPES = frozenset({
    "Observation", "Principle", "Question", "Person", "Event", "Project",
    "Decision", "Asset", "Signal",
})

MAX_HOPS = 5
DEFAULT_HOPS = 2
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50
DEFAULT_ACTIVITY_LIMIT = 20
MAX_ACTIVITY_LIMIT = 100


# ── Tool schemas (used by the MCP server to register tools) ───────────────────

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "hebbian_read_node",
        "description": (
            "Retrieve a single Hebbian vault node by its UUID. Returns the node body, "
            "frontmatter (domain, archetype, actor, fidelity scores), provenance trail, "
            "and top related nodes. Use this when you have a specific node ID from a "
            "previous search or traversal and want to read its full content."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "uuid": {
                    "type": "string",
                    "description": "The UUID of the node to retrieve.",
                },
            },
            "required": ["uuid"],
            "additionalProperties": False,
        },
    },
    {
        "name": "hebbian_search",
        "description": (
            "Search the Hebbian vault for nodes matching a query. Combines full-text "
            "and semantic (vector) search. The 'lens' param filters by knowledge domain; "
            "the 'types' param filters by node archetype."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Search query — natural language or keyword."},
                "types": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(VALID_TYPES)},
                    "description": "Optional filter by node archetype.",
                },
                "lens": {
                    "type": "string",
                    "enum": sorted(VALID_LENSES),
                    "description": "Optional filter by knowledge lens/domain.",
                },
                "limit": {
                    "type": "number",
                    "description": "Max results to return. Default: 10. Max: 50.",
                    "minimum": 1,
                    "maximum": MAX_SEARCH_LIMIT,
                },
            },
            "required": ["q"],
            "additionalProperties": False,
        },
    },
    {
        "name": "hebbian_ask",
        "description": (
            "Ask a synthesis question grounded in the Hebbian vault. Runs RAG and "
            "returns an answer with citations. Consumes tenant AI-action budget."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Natural language question."},
            },
            "required": ["question"],
            "additionalProperties": False,
        },
    },
    {
        "name": "hebbian_capture",
        "description": (
            "Capture text into the Hebbian vault as a new seed. Runs quality gates "
            "and promotes to a graph node if thresholds pass. "
            "Audited with 'source: mcp' + token name. Consumes AI-action budget."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to capture."},
                "lens": {
                    "type": "string",
                    "enum": ["Mirror", "Compass", "Axis", "Company", "CRM"],
                    "description": "Optional domain routing hint.",
                },
                "subject": {"type": "string", "description": "Optional subject hint."},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "hebbian_traverse",
        "description": (
            "Walk the Hebbian knowledge graph from a starting node, returning connected "
            "nodes up to N hops away. RLS enforced by token scope."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_uuid": {"type": "string", "description": "UUID of the starting node."},
                "max_hops": {
                    "type": "number",
                    "description": f"Max hops to traverse. Default: {DEFAULT_HOPS}. Max: {MAX_HOPS}.",
                    "minimum": 1,
                    "maximum": MAX_HOPS,
                },
            },
            "required": ["start_uuid"],
            "additionalProperties": False,
        },
    },
    {
        "name": "hebbian_provenance",
        "description": (
            "Retrieve the provenance trail for a vault node — source_quotes, "
            "source_external_ids, intake events, and quality-gate history."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "uuid": {"type": "string", "description": "UUID of the node."},
            },
            "required": ["uuid"],
            "additionalProperties": False,
        },
    },
    {
        "name": "hebbian_salience",
        "description": (
            "Retrieve the salience snapshot for a vault node (activation, synaptic "
            "fidelity, reinforcement signal). NOTE: Returns placeholder data until "
            "SNN Phase 10 ships."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "uuid": {"type": "string", "description": "UUID of the node."},
            },
            "required": ["uuid"],
            "additionalProperties": False,
        },
    },
    {
        "name": "hebbian_recent_activity",
        "description": (
            "Retrieve recent activity in the tenant brain — brain-mode firings, "
            "mutations, new seeds, and quality events. The 'since' param accepts "
            "an ISO 8601 datetime; omit for the last 24 hours."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "since": {
                    "type": "string",
                    "description": "ISO 8601 datetime (e.g. '2026-05-14T09:00:00Z'). Omit for last 24h.",
                },
                "limit": {
                    "type": "number",
                    "description": "Max items to return. Default: 20. Max: 100.",
                    "minimum": 1,
                    "maximum": MAX_ACTIVITY_LIMIT,
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
]


# ── Tool handlers ─────────────────────────────────────────────────────────────

async def handle_read_node(client: HebbianClient, args: dict[str, Any]) -> str:
    """Fetch a single node by UUID."""
    uuid = _require_str(args, "uuid")
    try:
        node = await client.get(f"/api/v1/nodes/{uuid}")
        return json.dumps(node, indent=2)
    except HebbianApiError as exc:
        raise RuntimeError(exc.to_tool_error()) from exc


async def handle_search(client: HebbianClient, args: dict[str, Any]) -> str:
    """Full-text + semantic search."""
    q = _require_str(args, "q")

    params: dict[str, Any] = {
        "q": q,
        "limit": min(max(1, int(args.get("limit", DEFAULT_SEARCH_LIMIT))), MAX_SEARCH_LIMIT),
    }
    if lens := args.get("lens"):
        params["lens"] = str(lens)
    if types := args.get("types"):
        if isinstance(types, list):
            params["types"] = ",".join(str(t) for t in types)

    try:
        results = await client.get("/api/v1/search", params=params)
        return json.dumps(results, indent=2)
    except HebbianApiError as exc:
        raise RuntimeError(exc.to_tool_error()) from exc


async def handle_ask(client: HebbianClient, args: dict[str, Any]) -> str:
    """Synthesis Q&A."""
    question = _require_str(args, "question")
    try:
        result = await client.post("/api/v1/ask", {"question": question})
        return json.dumps(result, indent=2)
    except HebbianApiError as exc:
        raise RuntimeError(exc.to_tool_error()) from exc


async def handle_capture(client: HebbianClient, args: dict[str, Any]) -> str:
    """Capture text as a new seed."""
    text = _require_str(args, "text")
    body: dict[str, str] = {"text": text}
    if lens := args.get("lens"):
        body["lens"] = str(lens)
    if subject := args.get("subject"):
        body["subject"] = str(subject)
    try:
        result = await client.post("/api/v1/capture", body)
        return json.dumps(result, indent=2)
    except HebbianApiError as exc:
        raise RuntimeError(exc.to_tool_error()) from exc


async def handle_traverse(client: HebbianClient, args: dict[str, Any]) -> str:
    """Graph traversal from a starting node."""
    start_uuid = _require_str(args, "start_uuid")
    hops = min(max(1, int(args.get("max_hops", DEFAULT_HOPS))), MAX_HOPS)
    try:
        result = await client.get(
            f"/api/v1/traverse/{start_uuid}",
            params={"max_hops": hops},
        )
        return json.dumps(result, indent=2)
    except HebbianApiError as exc:
        raise RuntimeError(exc.to_tool_error()) from exc


async def handle_provenance(client: HebbianClient, args: dict[str, Any]) -> str:
    """Provenance trail for a node."""
    uuid = _require_str(args, "uuid")
    try:
        result = await client.get(f"/api/v1/nodes/{uuid}/provenance")
        return json.dumps(result, indent=2)
    except HebbianApiError as exc:
        raise RuntimeError(exc.to_tool_error()) from exc


async def handle_salience(client: HebbianClient, args: dict[str, Any]) -> str:
    """Salience snapshot — no-op until SNN P10."""
    uuid = _require_str(args, "uuid")
    try:
        result = await client.get(f"/api/v1/nodes/{uuid}/salience")
        return json.dumps(result, indent=2)
    except HebbianApiError as exc:
        if exc.status_code == 404:
            # SNN not yet live — return stub
            stub = {
                "uuid": uuid,
                "status": "pending_snn_p10",
                "message": (
                    "Salience data is not yet available. The SNN reinforcement layer "
                    "(Phase 10) has not shipped yet. This tool will return real activation "
                    "and fidelity values once SNN P10 is live."
                ),
                "fidelity_check_score": None,
                "synaptic_fidelity": None,
                "activation_strength": None,
                "signal": None,
            }
            return json.dumps(stub, indent=2)
        raise RuntimeError(exc.to_tool_error()) from exc


async def handle_recent_activity(client: HebbianClient, args: dict[str, Any]) -> str:
    """Recent brain activity timeline."""
    params: dict[str, Any] = {
        "limit": min(max(1, int(args.get("limit", DEFAULT_ACTIVITY_LIMIT))), MAX_ACTIVITY_LIMIT),
    }
    if since := args.get("since"):
        # Validate ISO 8601 format
        try:
            datetime.fromisoformat(str(since).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"'since' must be a valid ISO 8601 datetime, got: \"{since}\""
            ) from exc
        params["since"] = str(since)

    try:
        result = await client.get("/api/v1/activity", params=params)
        return json.dumps(result, indent=2)
    except HebbianApiError as exc:
        raise RuntimeError(exc.to_tool_error()) from exc


# ── Dispatch table (tool name → handler) ──────────────────────────────────────

TOOL_HANDLERS: dict[str, Any] = {
    "hebbian_read_node": handle_read_node,
    "hebbian_search": handle_search,
    "hebbian_ask": handle_ask,
    "hebbian_capture": handle_capture,
    "hebbian_traverse": handle_traverse,
    "hebbian_provenance": handle_provenance,
    "hebbian_salience": handle_salience,
    "hebbian_recent_activity": handle_recent_activity,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_str(args: dict[str, Any], key: str) -> str:
    """Extract and validate a required non-empty string argument."""
    val = args.get(key)
    if not val or not isinstance(val, str) or not val.strip():
        raise ValueError(f"'{key}' is required and must be a non-empty string")
    return val.strip()
