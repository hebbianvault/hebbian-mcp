/**
 * src/tools/capture.ts
 *
 * Tool: hebbian_capture
 * Writes a note into the workspace. Confidential-by-default: captures are
 * private to you unless you explicitly contribute them to the company pool.
 * Maps to: POST /capture
 *   body: { title, body, domain?, tags?, owner_kind? }
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";

export const HEBBIAN_CAPTURE: Tool = {
  name: "hebbian_capture",
  description:
    "Capture a note into your Hebbian workspace directly from your AI session. " +
    "Captures are confidential-by-default — private to you unless you set " +
    "scope='company' to contribute the note to the shared company workspace. " +
    "Returns the created node UUID. Captured notes appear in the activity " +
    "timeline. Note: writes are subject to your token's permissions, enforced " +
    "server-side.",
  inputSchema: {
    type: "object",
    properties: {
      title: {
        type: "string",
        description: "Short title for the note. Required.",
      },
      text: {
        type: "string",
        description:
          "Body of the note (Markdown). A raw thought, meeting note, decision, " +
          "code snippet with context, or any knowledge worth preserving.",
      },
      domain: {
        type: "string",
        description:
          "Optional knowledge domain hint (e.g. 'Company', 'CRM', 'Compass', " +
          "'Axis', 'Mirror'). Omit to let the workspace classify it.",
      },
      tags: {
        type: "array",
        items: { type: "string" },
        description: "Optional free-form tags.",
      },
      scope: {
        type: "string",
        enum: ["private", "company"],
        description:
          "Where this note lives. 'private' (default) keeps it visible only to " +
          "you; 'company' contributes it to the shared company workspace. " +
          "Company-scope writes require the appropriate permission on your token.",
      },
    },
    required: ["title", "text"],
    additionalProperties: false,
  },
};

interface CaptureArgs {
  title: string;
  text: string;
  domain?: string;
  tags?: string[];
  scope?: "private" | "company";
}

export async function handleCapture(
  client: HebbianClient,
  args: CaptureArgs,
): Promise<string> {
  const { title, text, domain, tags, scope } = args;

  if (!title || typeof title !== "string" || title.trim().length === 0) {
    throw new Error("title is required and must be a non-empty string");
  }
  if (!text || typeof text !== "string" || text.trim().length === 0) {
    throw new Error("text is required and must be a non-empty string");
  }

  // API contract: { title, body, domain?, tags?, owner_kind? }.
  // owner_kind defaults to employee-private at the API; we only send 'company'
  // when the caller explicitly opts in.
  const body: Record<string, unknown> = {
    title: title.trim(),
    body: text.trim(),
  };
  if (domain) body["domain"] = domain;
  if (tags && tags.length > 0) body["tags"] = tags;
  if (scope === "company") body["owner_kind"] = "company";

  try {
    const result = await client.post("/capture", body);
    return JSON.stringify(result, null, 2);
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
