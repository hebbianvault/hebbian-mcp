/**
 * src/tools/provenance.ts
 *
 * Tool: hebbian_provenance
 * Retrieve the full provenance trail for a node — where it came from,
 * which sources contributed, which extraction events created it.
 * Maps to: GET /api/v1/nodes/:uuid/provenance
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";

export const HEBBIAN_PROVENANCE: Tool = {
  name: "hebbian_provenance",
  description:
    "Retrieve the provenance trail for a Hebbian vault node — the source_quotes, " +
    "source_external_ids, intake events, and quality-gate history that created it. " +
    "Use this when you need to verify where a piece of knowledge came from, " +
    "trace an insight back to its primary source, or check whether the node " +
    "has been updated by later intakes. The trail includes confidence scores " +
    "per provenance path (A = direct extraction, B = inferred, C = cross-domain).",
  inputSchema: {
    type: "object",
    properties: {
      uuid: {
        type: "string",
        description:
          "UUID of the node whose provenance trail to retrieve. " +
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

  try {
    const result = await client.get(`/api/v1/nodes/${encodeURIComponent(uuid.trim())}/provenance`);
    return JSON.stringify(result, null, 2);
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
