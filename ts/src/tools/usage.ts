/**
 * Tool: hebbian_usage
 * Return usage and spending-meter summaries for the configured token.
 * Maps to: GET /usage/me and GET /usage/company
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";
import { stringifyUntrustedResult } from "./untrusted_content.js";

export const HEBBIAN_USAGE: Tool = {
  name: "hebbian_usage",
  description:
    "Show your current Hebbian usage and spend-meter summary. Set 'company' to " +
    "true for the company-wide view, including employee summaries; that view " +
    "requires an Owner/Admin or company-scope token.",
  inputSchema: {
    type: "object",
    properties: {
      company: {
        type: "boolean",
        description:
          "Return the company-wide usage view. Default: false (your employee and company summaries).",
        default: false,
      },
    },
    additionalProperties: false,
  },
};

interface UsageArgs {
  company?: boolean;
}

/** Return caller usage, or the company roll-up when the token permits it. */
export async function handleUsage(
  client: HebbianClient,
  { company = false }: UsageArgs,
): Promise<string> {
  try {
    // Strict boolean check mirrors the Python handler: a host that skips
    // inputSchema validation and sends company:"true" gets the default view.
    const result = await client.get(company === true ? "/usage/company" : "/usage/me");
    return stringifyUntrustedResult(result);
  } catch (err) {
    if (company && err instanceof HebbianApiError && err.statusCode === 403) {
      return stringifyUntrustedResult({
        message:
          "Company usage view requires an Owner/Admin role or a company-scope token.",
      });
    }
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
