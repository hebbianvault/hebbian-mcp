/**
 * src/tools/search.ts
 *
 * Tool: hebbian_search
 * Search the workspace for nodes matching a query.
 *
 * The Hebbian API exposes the workspace as a scoped graph (GET /vault/graph),
 * already filtered to what the caller's token may see. This tool ranks that
 * graph against the query and returns the best matches. The graph is the
 * authoritative source; ranking is a thin presentation layer.
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";
import {
  fetchGraph,
  queryTerms,
  scoreNode,
  summarise,
  type GraphNode,
} from "./graph_helpers.js";

export const HEBBIAN_SEARCH: Tool = {
  name: "hebbian_search",
  description:
    "Search your Hebbian workspace for nodes matching a query. Returns a ranked " +
    "list of matching nodes with their UUID, title, domain, archetype, tags, and " +
    "a snippet. Use this as the starting point for exploring the workspace when " +
    "you have a topic or question. The 'domain' param filters by knowledge area " +
    "(e.g. 'Company', 'Compass'). Results only ever include what your token is " +
    "allowed to see — access is enforced server-side.",
  inputSchema: {
    type: "object",
    properties: {
      q: {
        type: "string",
        description: "Search query — natural language or keywords. Required.",
      },
      domain: {
        type: "string",
        description:
          "Optional filter by knowledge domain (e.g. 'Company', 'CRM', 'Compass', " +
          "'Axis', 'Mirror', 'Finance', 'Oracle'). Omit to search all domains.",
      },
      limit: {
        type: "number",
        description: "Maximum number of results to return. Default: 10. Max: 50.",
        minimum: 1,
        maximum: 50,
      },
    },
    required: ["q"],
    additionalProperties: false,
  },
};

interface SearchArgs {
  q: string;
  domain?: string;
  limit?: number;
}

export async function handleSearch(
  client: HebbianClient,
  args: SearchArgs,
): Promise<string> {
  const { q, domain, limit = 10 } = args;

  if (!q || typeof q !== "string" || q.trim().length === 0) {
    throw new Error("q is required and must be a non-empty string");
  }

  const cap = Math.min(Math.max(1, limit), 50);
  const terms = queryTerms(q);

  try {
    let nodes: GraphNode[] = await fetchGraph(client);

    if (domain) {
      const d = domain.toLowerCase();
      nodes = nodes.filter((n) => (n.domain ?? "").toLowerCase() === d);
    }

    const ranked = nodes
      .map((n) => ({ n, score: scoreNode(n, terms) }))
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, cap)
      .map((x) => summarise(x.n));

    return JSON.stringify(
      { query: q.trim(), domain: domain ?? null, count: ranked.length, results: ranked },
      null,
      2,
    );
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
