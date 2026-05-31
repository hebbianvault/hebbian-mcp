/**
 * src/tools/read_node.ts
 *
 * Tool: hebbian_read_node
 * Fetches a single node by UUID — body, frontmatter, and connected edges.
 * Maps to: GET /nodes/:uuid
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";

export const HEBBIAN_READ_NODE: Tool = {
  name: "hebbian_read_node",
  description:
    "Retrieve a single Hebbian workspace node by its UUID. Returns the node body, " +
    "frontmatter (domain, archetype, actor, title, summary), and the edges that " +
    "connect it to other nodes. Use this when you have a specific node ID from a " +
    "previous search or traversal and want to read its full content.",
  inputSchema: {
    type: "object",
    properties: {
      uuid: {
        type: "string",
        description:
          "The UUID of the node to retrieve (e.g. '550e8400-e29b-41d4-a716-446655440000'). " +
          "Obtain from hebbian_search, hebbian_traverse, or hebbian_recent_activity.",
      },
    },
    required: ["uuid"],
    additionalProperties: false,
  },
};

interface ReadNodeArgs {
  uuid: string;
}

export async function handleReadNode(
  client: HebbianClient,
  args: ReadNodeArgs,
): Promise<string> {
  const { uuid } = args;

  if (!uuid || typeof uuid !== "string" || uuid.trim().length === 0) {
    throw new Error("uuid is required and must be a non-empty string");
  }

  try {
    const node = await client.get(
      `/nodes/${encodeURIComponent(uuid.trim())}`,
    );
    return JSON.stringify(node, null, 2);
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
