/**
 * src/tools/capture.ts
 *
 * Tool: hebbian_capture
 * Path-A intake — captures text into the vault as a seed, runs quality gates,
 * and promotes to a node if quality thresholds pass.
 * Maps to: POST /api/v1/capture
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";

export const HEBBIAN_CAPTURE: Tool = {
  name: "hebbian_capture",
  description:
    "Capture a piece of text into the Hebbian vault as a new seed. The API " +
    "runs the formation pipeline: extraction → quality gates → graph promotion. " +
    "Returns the created seed UUID and promotion status. Use this to save " +
    "important insights, decisions, or notes directly from your AI session. " +
    "Captured nodes appear in the activity timeline and are audited with " +
    "'source: mcp' and your token name. Note: each capture call consumes " +
    "tenant AI-action budget (metered in billing).",
  inputSchema: {
    type: "object",
    properties: {
      text: {
        type: "string",
        description:
          "Text to capture. Can be a raw thought, a meeting note, a decision, " +
          "a code snippet with context, or any knowledge worth preserving.",
      },
      lens: {
        type: "string",
        enum: ["Mirror", "Compass", "Axis", "Company", "CRM"],
        description:
          "Optional lens hint for domain routing. If omitted the API's " +
          "classifier determines the best domain. Use 'Company' or 'CRM' " +
          "for company-scope tokens; 'Compass'/'Axis' for employee scope.",
      },
      subject: {
        type: "string",
        description:
          "Optional subject hint — a person name, project name, or topic " +
          "that helps the classifier anchor the node correctly.",
      },
    },
    required: ["text"],
    additionalProperties: false,
  },
};

interface CaptureArgs {
  text: string;
  lens?: string;
  subject?: string;
}

export async function handleCapture(
  client: HebbianClient,
  args: CaptureArgs,
): Promise<string> {
  const { text, lens, subject } = args;

  if (!text || typeof text !== "string" || text.trim().length === 0) {
    throw new Error("text is required and must be a non-empty string");
  }

  const body: Record<string, string> = { text: text.trim() };
  if (lens) body["lens"] = lens;
  if (subject) body["subject"] = subject;

  try {
    const result = await client.post("/api/v1/capture", body);
    return JSON.stringify(result, null, 2);
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
