/**
 * src/tools/provenance.ts
 *
 * Tool: hebbian_provenance
 * Retrieve the provenance trail for a node — where its knowledge came from.
 *
 * The node's provenance travels with it in the workspace graph
 * (GET /vault/graph). This tool reads the node and returns its provenance
 * plus identifying metadata. Access is enforced server-side, so a node is
 * only returned when the caller's token may see it.
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";
import { fetchGraph } from "./graph_helpers.js";

export const HEBBIAN_PROVENANCE: Tool = {
  name: "hebbian_provenance",
  description:
    "Retrieve the provenance trail for a workspace node — where the knowledge came " +
    "from. Use this to verify a source, trace an insight back to where it " +
    "originated, or understand how a node was formed. Returns nothing if the node " +
    "is outside your token's scope.",
  inputSchema: {
    type: "object",
    properties: {
      uuid: {
        type: "string",
        description:
          "UUID of the node whose provenance to retrieve. " +
          "Obtain from hebbian_search or hebbian_traverse.",
      },
    },
    required: ["uuid"],
    additionalProperties: false,
  },
};

interface ProvenanceArgs {
  uuid: string;
}

export async function handleProvenance(
  client: HebbianClient,
  args: ProvenanceArgs,
): Promise<string> {
  const { uuid } = args;

  if (!uuid || typeof uuid !== "string" || uuid.trim().length === 0) {
    throw new Error("uuid is required and must be a non-empty string");
  }

  const target = uuid.trim();

  try {
    const nodes = await fetchGraph(client);
    const node = nodes.find((n) => n.uuid === target);

    if (!node) {
      return JSON.stringify(
        {
          uuid: target,
          message:
            "Node not found in the visible workspace graph. It may not exist or " +
            "may be outside your token's scope.",
          provenance: null,
        },
        null,
        2,
      );
    }

    return JSON.stringify(
      {
        uuid: node.uuid,
        title: node.title ?? null,
        domain: node.domain ?? null,
        provenance: node.provenance ?? null,
      },
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
