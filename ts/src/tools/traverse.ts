/**
 * src/tools/traverse.ts
 *
 * Tool: hebbian_traverse
 * Walk the typed graph from a starting node up to N hops.
 * Maps to: GET /api/v1/traverse/:uuid
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";

const MAX_HOPS = 5;
const DEFAULT_HOPS = 2;

export const HEBBIAN_TRAVERSE: Tool = {
  name: "hebbian_traverse",
  description:
    "Walk the Hebbian knowledge graph from a starting node, returning connected " +
    "nodes up to N hops away. Returns a list of nodes and edges encountered. " +
    "Use this to explore the context around a node — e.g. all decisions related " +
    "to a project, all signals connected to a person, or all principles that " +
    "inform a strategy. Scope is enforced by your token's RLS.",
  inputSchema: {
    type: "object",
    properties: {
      start_uuid: {
        type: "string",
        description:
          "UUID of the starting node. Obtain from hebbian_search or " +
          "hebbian_recent_activity.",
      },
      max_hops: {
        type: "number",
        description:
          `Maximum number of hops to traverse. Default: ${DEFAULT_HOPS}. Max: ${MAX_HOPS}. ` +
          "Higher values return more context but may include loosely-related nodes.",
        minimum: 1,
        maximum: MAX_HOPS,
      },
    },
    required: ["start_uuid"],
    additionalProperties: false,
  },
};

interface TraverseArgs {
  start_uuid: string;
  max_hops?: number;
}

export async function handleTraverse(
  client: HebbianClient,
  args: TraverseArgs,
): Promise<string> {
  const { start_uuid, max_hops = DEFAULT_HOPS } = args;

  if (!start_uuid || typeof start_uuid !== "string" || start_uuid.trim().length === 0) {
    throw new Error("start_uuid is required and must be a non-empty string");
  }

  const hops = Math.min(Math.max(1, max_hops), MAX_HOPS);

  try {
    const result = await client.get(`/api/v1/traverse/${encodeURIComponent(start_uuid.trim())}`, { max_hops: hops });
    return JSON.stringify(result, null, 2);
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
