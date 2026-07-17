/**
 * Tool: hebbian_whoami
 * Return the server-verified identity and scope for the configured token.
 * Maps to: GET /tenant/whoami
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";
import { stringifyUntrustedResult } from "./untrusted_content.js";

export const HEBBIAN_WHOAMI: Tool = {
  name: "hebbian_whoami",
  description:
    "Show the identity verified for the configured Hebbian token. Returns the " +
    "tenant slug, role, token scope, and principal information.",
  inputSchema: {
    type: "object",
    properties: {},
    additionalProperties: false,
  },
};

/** Return server-derived identity data. This is not workspace content. */
export async function handleWhoami(client: HebbianClient): Promise<string> {
  try {
    const result = await client.get("/tenant/whoami");
    return stringifyUntrustedResult(result);
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
