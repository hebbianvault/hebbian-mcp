/**
 * src/tools/ask.ts
 *
 * Tool: hebbian_ask
 * Synthesis Q&A grounded in the vault's source_quotes.
 * Maps to: POST /api/v1/ask
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";

export const HEBBIAN_ASK: Tool = {
  name: "hebbian_ask",
  description:
    "Ask a synthesis question grounded in the Hebbian vault. The API runs " +
    "retrieval-augmented generation (RAG) against the tenant brain and returns " +
    "an answer with citations (node UUIDs + source_quotes). Use this when you " +
    "need synthesised insight — not just a list of nodes. Token scope determines " +
    "which lenses are searched: an employee token searches employee + company " +
    "brains; a company token searches the full org brain. " +
    "Note: each call consumes tenant AI-action budget (metered in billing).",
  inputSchema: {
    type: "object",
    properties: {
      question: {
        type: "string",
        description:
          "Natural language question to ask the Hebbian vault. " +
          "Be specific — the synthesis is grounded in source quotes, " +
          "so precise questions yield more accurate citations.",
      },
    },
    required: ["question"],
    additionalProperties: false,
  },
};

interface AskArgs {
  question: string;
}

export async function handleAsk(
  client: HebbianClient,
  args: AskArgs,
): Promise<string> {
  const { question } = args;

  if (!question || typeof question !== "string" || question.trim().length === 0) {
    throw new Error("question is required and must be a non-empty string");
  }

  try {
    const result = await client.post("/api/v1/ask", { question: question.trim() });
    return JSON.stringify(result, null, 2);
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
