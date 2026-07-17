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
import { invalidateGraphCache } from "./graph_helpers.js";
import { stringifyUntrustedResult } from "./untrusted_content.js";

// The server owns the authoritative limit. Keep this client-side guard in
// sync so invalid batches fail before spending a network request.
export const BATCH_CAPTURE_MAX_ITEMS = 25;

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
      items: {
        type: "array",
        description:
          "Capture multiple notes in one request (up to 25). Mutually exclusive " +
          "with title, text, domain, tags, and scope.",
        minItems: 1,
        maxItems: BATCH_CAPTURE_MAX_ITEMS,
        items: {
          type: "object",
          properties: {
            title: {
              type: "string",
              description: "Short title for the note. Required.",
            },
            text: {
              type: "string",
              description: "Body of the note (Markdown). Required.",
            },
            domain: {
              type: "string",
              description: "Optional knowledge domain hint.",
            },
            tags: {
              type: "array",
              items: { type: "string" },
              description: "Optional free-form tags.",
            },
            scope: {
              type: "string",
              enum: ["private", "company"],
              description: "Optional capture scope; private is the default.",
            },
          },
          required: ["title", "text"],
          additionalProperties: false,
        },
      },
    },
    oneOf: [
      {
        required: ["title", "text"],
        not: { required: ["items"] },
      },
      {
        required: ["items"],
        not: {
          anyOf: [
            { required: ["title"] },
            { required: ["text"] },
            { required: ["domain"] },
            { required: ["tags"] },
            { required: ["scope"] },
          ],
        },
      },
    ],
    additionalProperties: false,
  },
};

interface CaptureItem {
  title: string;
  text: string;
  domain?: string;
  tags?: string[];
  scope?: "private" | "company";
}

interface CaptureArgs extends Partial<CaptureItem> {
  items?: CaptureItem[];
}

function validateCaptureItem({ title, text }: CaptureItem): void {
  if (!title || typeof title !== "string" || title.trim().length === 0) {
    throw new Error("title is required and must be a non-empty string");
  }
  if (!text || typeof text !== "string" || text.trim().length === 0) {
    throw new Error("text is required and must be a non-empty string");
  }
}

function captureRequestBody({ title, text, domain, tags, scope }: CaptureItem): Record<string, unknown> {
  validateCaptureItem({ title, text });

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
  return body;
}

export async function handleCapture(
  client: HebbianClient,
  args: CaptureArgs,
): Promise<string> {
  const { items, title, text, domain, tags, scope } = args;
  const hasSingleItemFields =
    title !== undefined ||
    text !== undefined ||
    domain !== undefined ||
    tags !== undefined ||
    scope !== undefined;

  if (items !== undefined && hasSingleItemFields) {
    throw new Error("items_exclusive: items cannot be combined with single-item fields");
  }

  let requestBody: Record<string, unknown>;
  if (items !== undefined) {
    if (!Array.isArray(items) || items.length === 0) {
      throw new Error("items must contain at least one capture item");
    }
    if (items.length > BATCH_CAPTURE_MAX_ITEMS) {
      throw new Error(`batch_too_large: items may contain at most ${BATCH_CAPTURE_MAX_ITEMS} capture items`);
    }
    requestBody = { items: items.map(captureRequestBody) };
  } else {
    requestBody = captureRequestBody({ title: title as string, text: text as string, domain, tags, scope });
  }

  try {
    const result = await client.post("/capture", requestBody);
    invalidateGraphCache(client);
    return stringifyUntrustedResult(result);
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
