/**
 * tests/tools.test.ts
 *
 * Unit tests for @hebbianvault/mcp tool handlers.
 *
 * Tests mock the HebbianClient — no real HTTP calls.
 * Coverage: input validation, happy-path response shaping, error handling
 * for each of the 8 tools.
 */

import { jest, describe, test, expect, beforeEach } from "@jest/globals";
import type { HebbianClient } from "../src/client.js";
import { HebbianApiError } from "../src/client.js";
import { handleReadNode } from "../src/tools/read_node.js";
import { handleSearch } from "../src/tools/search.js";
import { handleAsk } from "../src/tools/ask.js";
import { handleCapture } from "../src/tools/capture.js";
import { handleTraverse } from "../src/tools/traverse.js";
import { handleProvenance } from "../src/tools/provenance.js";
import { handleSalience } from "../src/tools/salience.js";
import { handleRecentActivity } from "../src/tools/recent_activity.js";

// ── Mock client factory ───────────────────────────────────────────────────────

function mockClient(overrides?: {
  get?: jest.Mock;
  post?: jest.Mock;
}): HebbianClient {
  return {
    get: overrides?.get ?? jest.fn().mockResolvedValue({}),
    post: overrides?.post ?? jest.fn().mockResolvedValue({}),
  } as unknown as HebbianClient;
}

// ── hebbian_read_node ─────────────────────────────────────────────────────────

describe("hebbian_read_node", () => {
  const UUID = "550e8400-e29b-41d4-a716-446655440000";

  test("calls GET /api/v1/nodes/:uuid", async () => {
    const node = { uuid: UUID, title: "Test node", domain: "Compass" };
    const client = mockClient({ get: jest.fn().mockResolvedValue(node) });

    const result = await handleReadNode(client, { uuid: UUID });

    expect(client.get).toHaveBeenCalledWith(`/api/v1/nodes/${UUID}`);
    expect(JSON.parse(result)).toEqual(node);
  });

  test("throws on missing uuid", async () => {
    const client = mockClient();
    await expect(handleReadNode(client, { uuid: "" })).rejects.toThrow("uuid is required");
  });

  test("surfaces HebbianApiError.toToolError() on 401", async () => {
    const client = mockClient({
      get: jest.fn().mockRejectedValue(
        new HebbianApiError(401, "TOKEN_EXPIRED", "Token has expired"),
      ),
    });

    await expect(handleReadNode(client, { uuid: UUID })).rejects.toThrow(
      "Authentication failed",
    );
  });

  test("surfaces HebbianApiError.toToolError() on 404", async () => {
    const client = mockClient({
      get: jest.fn().mockRejectedValue(
        new HebbianApiError(404, "NODE_NOT_FOUND", "Node not found"),
      ),
    });

    await expect(handleReadNode(client, { uuid: UUID })).rejects.toThrow(
      "Not found",
    );
  });
});

// ── hebbian_search ────────────────────────────────────────────────────────────

describe("hebbian_search", () => {
  test("calls GET /api/v1/search with query params", async () => {
    const results = { nodes: [], total: 0 };
    const client = mockClient({ get: jest.fn().mockResolvedValue(results) });

    await handleSearch(client, { q: "project decisions", limit: 5 });

    expect(client.get).toHaveBeenCalledWith("/api/v1/search", expect.objectContaining({
      q: "project decisions",
      limit: 5,
    }));
  });

  test("passes lens and types when provided", async () => {
    const client = mockClient({ get: jest.fn().mockResolvedValue({ nodes: [], total: 0 }) });

    await handleSearch(client, {
      q: "strategy",
      lens: "Company",
      types: ["Decision", "Principle"],
    });

    expect(client.get).toHaveBeenCalledWith("/api/v1/search", expect.objectContaining({
      lens: "Company",
      types: "Decision,Principle",
    }));
  });

  test("throws on empty query", async () => {
    const client = mockClient();
    await expect(handleSearch(client, { q: "   " })).rejects.toThrow("q is required");
  });

  test("clamps limit to max 50", async () => {
    const client = mockClient({ get: jest.fn().mockResolvedValue({ nodes: [], total: 0 }) });
    await handleSearch(client, { q: "test", limit: 999 });

    expect(client.get).toHaveBeenCalledWith(
      "/api/v1/search",
      expect.objectContaining({ limit: 50 }),
    );
  });
});

// ── hebbian_ask ───────────────────────────────────────────────────────────────

describe("hebbian_ask", () => {
  test("calls POST /api/v1/ask with question body", async () => {
    const response = { answer: "Yes", citations: [], lens_scope: {} };
    const client = mockClient({ post: jest.fn().mockResolvedValue(response) });

    const result = await handleAsk(client, { question: "What is the company strategy?" });

    expect(client.post).toHaveBeenCalledWith("/api/v1/ask", {
      question: "What is the company strategy?",
    });
    expect(JSON.parse(result)).toEqual(response);
  });

  test("throws on empty question", async () => {
    const client = mockClient();
    await expect(handleAsk(client, { question: "" })).rejects.toThrow("question is required");
  });

  test("surfaces 403 as permission denied message", async () => {
    const client = mockClient({
      post: jest.fn().mockRejectedValue(
        new HebbianApiError(403, "SCOPE_INSUFFICIENT", "Company scope required"),
      ),
    });

    await expect(handleAsk(client, { question: "test" })).rejects.toThrow(
      "Permission denied",
    );
  });
});

// ── hebbian_capture ───────────────────────────────────────────────────────────

describe("hebbian_capture", () => {
  test("calls POST /api/v1/capture with text body", async () => {
    const response = { seed_uuid: "abc-123", status: "promoted", node_uuid: "def-456" };
    const client = mockClient({ post: jest.fn().mockResolvedValue(response) });

    const result = await handleCapture(client, { text: "Important insight about Q3" });

    expect(client.post).toHaveBeenCalledWith("/api/v1/capture", {
      text: "Important insight about Q3",
    });
    expect(JSON.parse(result)).toEqual(response);
  });

  test("includes lens and subject when provided", async () => {
    const client = mockClient({ post: jest.fn().mockResolvedValue({ seed_uuid: "x", status: "pending" }) });

    await handleCapture(client, {
      text: "Decision made about hiring",
      lens: "Company",
      subject: "Acme Inc",
    });

    expect(client.post).toHaveBeenCalledWith("/api/v1/capture", {
      text: "Decision made about hiring",
      lens: "Company",
      subject: "Acme Inc",
    });
  });

  test("throws on empty text", async () => {
    const client = mockClient();
    await expect(handleCapture(client, { text: "" })).rejects.toThrow("text is required");
  });
});

// ── hebbian_traverse ──────────────────────────────────────────────────────────

describe("hebbian_traverse", () => {
  const UUID = "abc-456";

  test("calls GET /api/v1/traverse/:uuid with default hops", async () => {
    const response = { nodes: [], edges: [], start_uuid: UUID, hops: 2 };
    const client = mockClient({ get: jest.fn().mockResolvedValue(response) });

    await handleTraverse(client, { start_uuid: UUID });

    expect(client.get).toHaveBeenCalledWith(
      `/api/v1/traverse/${UUID}`,
      expect.objectContaining({ max_hops: 2 }),
    );
  });

  test("clamps max_hops to 5", async () => {
    const client = mockClient({ get: jest.fn().mockResolvedValue({ nodes: [], edges: [], start_uuid: UUID, hops: 5 }) });

    await handleTraverse(client, { start_uuid: UUID, max_hops: 100 });

    expect(client.get).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ max_hops: 5 }),
    );
  });

  test("throws on missing start_uuid", async () => {
    const client = mockClient();
    await expect(handleTraverse(client, { start_uuid: "" })).rejects.toThrow("start_uuid is required");
  });
});

// ── hebbian_provenance ────────────────────────────────────────────────────────

describe("hebbian_provenance", () => {
  const UUID = "prov-uuid-789";

  test("calls GET /api/v1/nodes/:uuid/provenance", async () => {
    const response = { uuid: UUID, paths: [], source_quotes: [], intake_events: [] };
    const client = mockClient({ get: jest.fn().mockResolvedValue(response) });

    const result = await handleProvenance(client, { uuid: UUID });

    expect(client.get).toHaveBeenCalledWith(`/api/v1/nodes/${UUID}/provenance`);
    expect(JSON.parse(result)).toEqual(response);
  });

  test("throws on empty uuid", async () => {
    const client = mockClient();
    await expect(handleProvenance(client, { uuid: "" })).rejects.toThrow("uuid is required");
  });
});

// ── hebbian_salience ──────────────────────────────────────────────────────────

describe("hebbian_salience", () => {
  const UUID = "sal-uuid-000";

  test("returns stub when API returns 404 (SNN not live)", async () => {
    const client = mockClient({
      get: jest.fn().mockRejectedValue(
        new HebbianApiError(404, "NOT_FOUND", "Salience endpoint not found"),
      ),
    });

    const result = await handleSalience(client, { uuid: UUID });
    const parsed = JSON.parse(result) as {
      status: string;
      uuid: string;
      synaptic_fidelity: null;
    };

    expect(parsed.status).toBe("pending_snn_p10");
    expect(parsed.uuid).toBe(UUID);
    expect(parsed.synaptic_fidelity).toBeNull();
  });

  test("returns real data when API responds successfully", async () => {
    const realData = { uuid: UUID, activation_strength: 0.87, synaptic_fidelity: 0.92 };
    const client = mockClient({ get: jest.fn().mockResolvedValue(realData) });

    const result = await handleSalience(client, { uuid: UUID });
    expect(JSON.parse(result)).toEqual(realData);
  });

  test("throws on 401 (not swallowed as 404)", async () => {
    const client = mockClient({
      get: jest.fn().mockRejectedValue(
        new HebbianApiError(401, "TOKEN_EXPIRED", "Token expired"),
      ),
    });

    await expect(handleSalience(client, { uuid: UUID })).rejects.toThrow(
      "Authentication failed",
    );
  });

  test("throws on empty uuid", async () => {
    const client = mockClient();
    await expect(handleSalience(client, { uuid: "" })).rejects.toThrow("uuid is required");
  });
});

// ── hebbian_recent_activity ───────────────────────────────────────────────────

describe("hebbian_recent_activity", () => {
  test("calls GET /api/v1/activity with default limit", async () => {
    const response = { items: [], total: 0, generated_at: "2026-05-15T12:00:00Z" };
    const client = mockClient({ get: jest.fn().mockResolvedValue(response) });

    await handleRecentActivity(client, {});

    expect(client.get).toHaveBeenCalledWith(
      "/api/v1/activity",
      expect.objectContaining({ limit: 20 }),
    );
  });

  test("passes 'since' param when provided", async () => {
    const client = mockClient({ get: jest.fn().mockResolvedValue({ items: [], total: 0, generated_at: "" }) });

    await handleRecentActivity(client, { since: "2026-05-14T09:00:00Z", limit: 10 });

    expect(client.get).toHaveBeenCalledWith("/api/v1/activity", expect.objectContaining({
      since: "2026-05-14T09:00:00Z",
      limit: 10,
    }));
  });

  test("clamps limit to max 100", async () => {
    const client = mockClient({ get: jest.fn().mockResolvedValue({ items: [], total: 0, generated_at: "" }) });

    await handleRecentActivity(client, { limit: 999 });

    expect(client.get).toHaveBeenCalledWith(
      "/api/v1/activity",
      expect.objectContaining({ limit: 100 }),
    );
  });

  test("throws on invalid 'since' datetime", async () => {
    const client = mockClient();
    await expect(
      handleRecentActivity(client, { since: "not-a-date" }),
    ).rejects.toThrow("valid ISO 8601 datetime");
  });
});

// ── HebbianApiError ───────────────────────────────────────────────────────────

describe("HebbianApiError.toToolError()", () => {
  test("401 includes refresh hint", () => {
    const err = new HebbianApiError(401, "TOKEN_EXPIRED", "Expired");
    expect(err.toToolError()).toContain("Generate a new token");
  });

  test("403 includes scope hint", () => {
    const err = new HebbianApiError(403, "SCOPE_DENIED", "Denied");
    expect(err.toToolError()).toContain("token scope");
  });

  test("429 includes retry hint", () => {
    const err = new HebbianApiError(429, "RATE_LIMITED", "Too many requests");
    expect(err.toToolError()).toContain("Slow down");
  });

  test("generic error includes status code", () => {
    const err = new HebbianApiError(500, "INTERNAL_ERROR", "Server fault");
    expect(err.toToolError()).toContain("500");
  });
});
