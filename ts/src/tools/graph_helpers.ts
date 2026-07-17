/**
 * src/tools/graph_helpers.ts
 *
 * Shared helpers for tools that operate over the workspace graph.
 *
 * The Hebbian API exposes the workspace as a single scoped graph
 * (GET /vault/graph) where every node carries its title, summary, domain,
 * archetype, tags, inline edges, and provenance. Several MCP tools
 * (search, traverse, provenance) are presentation-layer views over that
 * graph: the API returns the data, this module shapes it for the agent.
 * Access control is enforced server-side — the graph only ever contains
 * what the caller's token is allowed to see.
 */

import type { HebbianClient } from "../client.js";

export interface GraphEdge {
  // /vault/graph emits adjacency edges as { to, relation_type, weight } where
  // `to` is the neighbour and the owning node is the implicit other endpoint.
  // /nodes/:uuid emits { source_uuid, target_uuid, direction }. We tolerate both.
  to?: string;
  source_uuid?: string;
  target_uuid?: string;
  direction?: "in" | "out";
  relation_type?: string;
  weight?: number;
  [k: string]: unknown;
}

/**
 * Normalise an edge owned by `ownerUuid` into (source, target, relation, weight).
 * Handles both the /vault/graph `{ to }` shape and the /nodes/:uuid
 * `{ source_uuid, target_uuid }` shape.
 */
export function normaliseEdge(
  e: GraphEdge,
  ownerUuid: string,
): { source: string; target: string; relation?: string; weight?: number } {
  if (typeof e.to === "string") {
    // Adjacency form: owner -> to (direction not exposed; treat owner as source).
    return { source: ownerUuid, target: e.to, relation: e.relation_type, weight: e.weight };
  }
  const src = (e.source_uuid as string) ?? ownerUuid;
  const tgt = (e.target_uuid as string) ?? ownerUuid;
  return { source: src, target: tgt, relation: e.relation_type, weight: e.weight };
}

export interface GraphNode {
  uuid: string;
  title?: string;
  summary?: string;
  detail?: string;
  domain?: string;
  archetype?: string;
  actor?: string;
  tags?: string[];
  edges?: GraphEdge[];
  provenance?: unknown;
  [k: string]: unknown;
}

interface GraphResponse {
  nodes?: GraphNode[];
  next_cursor?: string | null;
  [k: string]: unknown;
}

export const MAX_GRAPH_PAGES = 10_000;

const EMPLOYEE_GRAPH_PATH = "/vault/graph";
const COMPANY_GRAPH_PATH = "/vault/company-graph";

// Scope is immutable for a client because its token is immutable. Cache the
// promise itself so concurrent graph-tool calls share the same advisory probe.
const graphPathByClient = new WeakMap<HebbianClient, Promise<string>>();

async function graphPathFor(client: HebbianClient): Promise<string> {
  let graphPath = graphPathByClient.get(client);
  if (!graphPath) {
    graphPath = Promise.resolve()
      .then(() => client.get("/tenant/whoami"))
      .then((identity) => {
        if (
          identity &&
          typeof identity === "object" &&
          (identity as Record<string, unknown>).token_scope === "company"
        ) {
          return COMPANY_GRAPH_PATH;
        }
        return EMPLOYEE_GRAPH_PATH;
      })
      // Whoami is advisory. A failed probe must never prevent graph tools from
      // using the existing employee-scoped endpoint.
      .catch(() => {
        process.stderr.write(
          "[hebbian-mcp] Token scope probe failed; caching the employee graph fallback. " +
            "Restarting the MCP process clears it.\n",
        );
        return EMPLOYEE_GRAPH_PATH;
      });
    graphPathByClient.set(client, graphPath);
  }
  return graphPath;
}

/** Fetch the full scoped workspace graph for the current token. */
export async function fetchGraph(client: HebbianClient): Promise<GraphNode[]> {
  const graphPath = await graphPathFor(client);

  // Preserve the legacy request exactly unless pagination is explicitly enabled.
  if (!client.graphPagination) {
    const resp = (await client.get(graphPath)) as GraphResponse;
    return Array.isArray(resp.nodes) ? resp.nodes : [];
  }

  const nodes: GraphNode[] = [];
  let cursor: string | undefined;

  for (let page = 0; page < MAX_GRAPH_PAGES; page++) {
    const query = cursor === undefined ? { limit: 1000 } : { limit: 1000, cursor };
    const resp = (await client.get(graphPath, query)) as GraphResponse;

    if (Array.isArray(resp.nodes)) nodes.push(...resp.nodes);
    if (resp.next_cursor === null) return nodes;
    if (typeof resp.next_cursor !== "string") {
      if (page === 0 && resp.next_cursor === undefined) return nodes;
      throw new Error("Hebbian MCP: Paginated graph response is missing next_cursor");
    }
    if (resp.next_cursor === cursor) {
      throw new Error("Hebbian MCP: Graph pagination received a duplicate cursor");
    }
    cursor = resp.next_cursor;
  }

  throw new Error(
    `Hebbian MCP: Graph pagination exceeded ${MAX_GRAPH_PAGES} pages; refusing to loop forever`,
  );
}

/** Lower-cased haystack of a node's searchable text fields. */
function nodeHaystack(n: GraphNode): string {
  const parts = [
    n.title,
    n.summary,
    n.detail,
    n.domain,
    n.archetype,
    ...(Array.isArray(n.tags) ? n.tags : []),
  ];
  return parts.filter(Boolean).join(" \n ").toLowerCase();
}

/** Score a node against query terms. Returns 0 when no term matches. */
export function scoreNode(n: GraphNode, terms: string[]): number {
  if (terms.length === 0) return 0;
  const hay = nodeHaystack(n);
  const title = (n.title ?? "").toLowerCase();
  let score = 0;
  for (const t of terms) {
    if (!t) continue;
    if (title.includes(t)) score += 3; // title hits weigh more
    else if (hay.includes(t)) score += 1;
  }
  return score;
}

/** Split a query string into lower-cased terms. */
export function queryTerms(q: string): string[] {
  return q
    .toLowerCase()
    .split(/\s+/)
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
}

/** A compact node summary for search/traverse result lists. */
export function summarise(n: GraphNode): Record<string, unknown> {
  const snippet = (n.summary ?? n.detail ?? "").toString().slice(0, 280);
  return {
    uuid: n.uuid,
    title: n.title ?? null,
    domain: n.domain ?? null,
    archetype: n.archetype ?? null,
    tags: n.tags ?? [],
    snippet,
  };
}
