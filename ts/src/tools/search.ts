/**
 * src/tools/search.ts
 *
 * Tool: hebbian_search
 * Full-text + semantic search across vault nodes.
 * Maps to: GET /api/v1/search
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";

// Valid domain/lens values (from knowledge-graph.md)
const VALID_LENSES = [
  "Mirror", "Compass", "Axis", "Company", "CRM", "EMAIL", "LEEXI",
  "Finance", "Oracle",
] as const;

const VALID_TYPES = [
  "Observation", "Principle", "Question", "Person", "Event", "Project",
  "Decision", "Asset", "Signal",
] as const;

export const HEBBIAN_SEARCH: Tool = {
  name: "hebbian_search",
  description:
    "Search the Hebbian vault for nodes matching a query. Combines full-text and " +
    "semantic (vector) search. Returns a list of matching nodes with their UUID, " +
    "title, domain, archetype, fidelity, and a snippet. Use this as the starting " +
    "point for exploring the brain when you have a topic or question. " +
    "The 'lens' param filters by knowledge domain (e.g. 'Company' for org knowledge, " +
    "'Compass' for personal professional knowledge). " +
    "The 'types' param filters by node archetype.",
  inputSchema: {
    type: "object",
    properties: {
      q: {
        type: "string",
        description: "Search query — natural language or keyword. Required.",
      },
      types: {
        type: "array",
        items: {
          type: "string",
          enum: [...VALID_TYPES],
        },
        description:
          "Optional filter by node archetype. Valid values: " +
          VALID_TYPES.join(", ") + ". Omit to search all types.",
      },
      lens: {
        type: "string",
        enum: [...VALID_LENSES],
        description:
          "Optional filter by knowledge lens/domain. Valid values: " +
          VALID_LENSES.join(", ") + ". Omit to search all lenses.",
      },
      limit: {
        type: "number",
        description:
          "Maximum number of results to return. Default: 10. Max: 50.",
        minimum: 1,
        maximum: 50,
      },
    },
    required: ["q"],
    additionalProperties: false,
  },
};

interface SearchArgs {
  q: string;
  types?: string[];
  lens?: string;
  limit?: number;
}

export async function handleSearch(
  client: HebbianClient,
  args: SearchArgs,
): Promise<string> {
  const { q, types, lens, limit = 10 } = args;

  if (!q || typeof q !== "string" || q.trim().length === 0) {
    throw new Error("q is required and must be a non-empty string");
  }

  const query: Record<string, string | number | boolean | undefined> = {
    q: q.trim(),
    limit: Math.min(Math.max(1, limit), 50),
  };

  if (lens) {
    query["lens"] = lens;
  }
  if (types && types.length > 0) {
    query["types"] = types.join(",");
  }

  try {
    const results = await client.get("/api/v1/search", query);
    return JSON.stringify(results, null, 2);
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
