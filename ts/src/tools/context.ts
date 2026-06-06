/**
 * src/tools/context.ts
 *
 * Tool: hebbian_context
 * Task-shaped retrieval: describe a task and a token budget, get back the most
 * relevant context from the workspace, ranked by salience and trimmed to fit.
 * Maps to: POST /v1/context  (request body: { task, budget_tokens, filters? })
 *
 * This is the agent-native read. Instead of browsing nodes or running raw
 * search, ask for the context a task needs. The API ranks the workspace by
 * salience and returns a pack of items (each with the node, an excerpt, a
 * score, and a short reason it was included) within your token budget. What
 * the pack can draw on is enforced server-side by your token's scope.
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";

const DEFAULT_BUDGET_TOKENS = 2000;
const MIN_BUDGET_TOKENS = 50;
const MAX_BUDGET_TOKENS = 32000;

export const HEBBIAN_CONTEXT: Tool = {
  name: "hebbian_context",
  description:
    "Get the most relevant context for a task from your Hebbian workspace, " +
    "ranked by salience and trimmed to a token budget. Give a plain-language " +
    "task description and a budget; get back a context pack. Each item carries " +
    "its source node, an excerpt, a salience score, and a short reason it was " +
    "included. Use this instead of search when you want context shaped for a " +
    "task rather than a raw list of nodes. Results only ever include what your " +
    "token is allowed to see, enforced server-side.",
  inputSchema: {
    type: "object",
    properties: {
      task: {
        type: "string",
        description:
          "Plain-language description of the task the context is for. " +
          "The more specific the task, the better the pack is targeted.",
      },
      budget_tokens: {
        type: "number",
        description:
          `Token budget for the returned pack. Default: ${DEFAULT_BUDGET_TOKENS}. ` +
          `Min: ${MIN_BUDGET_TOKENS}. Max: ${MAX_BUDGET_TOKENS}. The pack is ` +
          "trimmed in salience order to fit; the response reports how much was " +
          "used and whether anything was left out.",
        minimum: MIN_BUDGET_TOKENS,
        maximum: MAX_BUDGET_TOKENS,
      },
      scope: {
        type: "string",
        enum: ["synthesis", "company", "employee", "bridge"],
        description:
          "Which part of the workspace to draw from. 'synthesis' (default) " +
          "blends company and your own notes; 'company' is the company brain " +
          "only; 'employee' is your own notes only; 'bridge' is the " +
          "cross-pollinated view. Your token's scope still bounds what is reachable.",
      },
    },
    required: ["task"],
    additionalProperties: false,
  },
};

interface ContextArgs {
  task: string;
  budget_tokens?: number;
  scope?: "synthesis" | "company" | "employee" | "bridge";
}

export async function handleContext(
  client: HebbianClient,
  args: ContextArgs,
): Promise<string> {
  const { task, budget_tokens, scope } = args;

  if (!task || typeof task !== "string" || task.trim().length === 0) {
    throw new Error("task is required and must be a non-empty string");
  }

  const budget = Math.min(
    Math.max(MIN_BUDGET_TOKENS, budget_tokens ?? DEFAULT_BUDGET_TOKENS),
    MAX_BUDGET_TOKENS,
  );

  const body: Record<string, unknown> = {
    task: task.trim(),
    budget_tokens: budget,
  };
  if (scope) {
    body.filters = { scope };
  }

  try {
    const result = await client.post("/v1/context", body);
    return JSON.stringify(result, null, 2);
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
