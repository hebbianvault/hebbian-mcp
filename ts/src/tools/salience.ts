/**
 * src/tools/salience.ts
 *
 * Tool: hebbian_salience
 * Return the salience snapshot for a node — current activation strength,
 * synaptic fidelity, and reinforcement signal.
 *
 * NOTE: This tool is a no-op until SNN Phase 10 ships (ADR-023).
 * It returns a stub response indicating the feature is pending.
 * Maps to: GET /api/v1/nodes/:uuid/salience
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";

export const HEBBIAN_SALIENCE: Tool = {
  name: "hebbian_salience",
  description:
    "Retrieve the salience snapshot for a Hebbian vault node. Returns the node's " +
    "current activation strength, synaptic fidelity score, and reinforcement signal. " +
    "High-salience nodes are surfacing in the activity timeline; low-salience nodes " +
    "are fading from daily relevance. " +
    "NOTE: This tool returns a placeholder response until the SNN (Spiking Neural " +
    "Network) layer ships in Phase 10. The synaptic fidelity and activation values " +
    "are mock data — do not treat them as ground truth yet.",
  inputSchema: {
    type: "object",
    properties: {
      uuid: {
        type: "string",
        description:
          "UUID of the node whose salience snapshot to retrieve. " +
          "Obtain from hebbian_search or hebbian_traverse.",
      },
    },
    required: ["uuid"],
    additionalProperties: false,
  },
};

interface SalienceArgs {
  uuid: string;
}

// Placeholder response shape until SNN P10 ships
interface SalienceStub {
  uuid: string;
  status: "pending_snn_p10";
  message: string;
  fidelity_check_score: null;
  synaptic_fidelity: null;
  activation_strength: null;
  signal: null;
}

export async function handleSalience(
  client: HebbianClient,
  args: SalienceArgs,
): Promise<string> {
  const { uuid } = args;

  if (!uuid || typeof uuid !== "string" || uuid.trim().length === 0) {
    throw new Error("uuid is required and must be a non-empty string");
  }

  // Try the real endpoint first — if SNN P10 has shipped, use real data
  try {
    const result = await client.get(`/api/v1/nodes/${encodeURIComponent(uuid.trim())}/salience`);
    return JSON.stringify(result, null, 2);
  } catch (err) {
    if (err instanceof HebbianApiError && err.statusCode === 404) {
      // SNN not yet live — return stub
      const stub: SalienceStub = {
        uuid: uuid.trim(),
        status: "pending_snn_p10",
        message:
          "Salience data is not yet available. The SNN reinforcement layer " +
          "(Phase 10) has not shipped yet. This tool will return real activation " +
          "and fidelity values once SNN P10 is live.",
        fidelity_check_score: null,
        synaptic_fidelity: null,
        activation_strength: null,
        signal: null,
      };
      return JSON.stringify(stub, null, 2);
    }
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
