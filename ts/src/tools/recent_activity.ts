/**
 * src/tools/recent_activity.ts
 *
 * Tool: hebbian_recent_activity
 * Retrieve recent activity in the tenant brain — brain-mode firings,
 * cross-node editor mutations, new seeds, and quality events.
 * Maps to: GET /api/v1/activity
 */

import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { HebbianClient } from "../client.js";
import { HebbianApiError } from "../client.js";

export const HEBBIAN_RECENT_ACTIVITY: Tool = {
  name: "hebbian_recent_activity",
  description:
    "Retrieve recent activity in the Hebbian tenant brain — what the formation " +
    "pipeline has been doing, which nodes were created or updated, and any quality " +
    "events. Use this to catch up on what the brain has learned since your last " +
    "session, or to find recently-created nodes by topic. " +
    "Returns a reverse-chronological activity timeline matching the /today UI view. " +
    "The 'since' param accepts an ISO 8601 datetime; omit for the last 24 hours.",
  inputSchema: {
    type: "object",
    properties: {
      since: {
        type: "string",
        description:
          "ISO 8601 datetime to retrieve activity from (e.g. '2026-05-14T09:00:00Z'). " +
          "Omit to get the last 24 hours of activity.",
      },
      limit: {
        type: "number",
        description:
          "Maximum number of activity items to return. Default: 20. Max: 100.",
        minimum: 1,
        maximum: 100,
      },
    },
    required: [],
    additionalProperties: false,
  },
};

interface RecentActivityArgs {
  since?: string;
  limit?: number;
}

export async function handleRecentActivity(
  client: HebbianClient,
  args: RecentActivityArgs,
): Promise<string> {
  const { since, limit = 20 } = args;

  const query: Record<string, string | number | boolean | undefined> = {
    limit: Math.min(Math.max(1, limit), 100),
  };

  if (since) {
    // Validate ISO 8601 format — basic check
    const parsed = Date.parse(since);
    if (isNaN(parsed)) {
      throw new Error(`'since' must be a valid ISO 8601 datetime, got: "${since}"`);
    }
    query["since"] = since;
  }

  try {
    const result = await client.get("/api/v1/activity", query);
    return JSON.stringify(result, null, 2);
  } catch (err) {
    if (err instanceof HebbianApiError) {
      throw new Error(err.toToolError());
    }
    throw err;
  }
}
