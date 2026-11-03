/**
 * src/toolset.ts
 *
 * Which tools this adapter lists and serves.
 *
 * DEC #284 (founder 2026-10-22): the everyday AI tool set carries no admin
 * power. usage, audit_log and the GDPR export move to an opt-in admin set, so
 * they are NOT listed or callable unless the operator sets
 * HEBBIAN_ADMIN_TOOLS=1 (off by default). The API still enforces what the
 * token may do; this flag only decides whether the agent is offered the tool.
 */

import {
  HEBBIAN_READ_NODE,
  HEBBIAN_SEARCH,
  HEBBIAN_ASK,
  HEBBIAN_CONTEXT,
  HEBBIAN_CAPTURE,
  HEBBIAN_TRAVERSE,
  HEBBIAN_PROVENANCE,
  HEBBIAN_SALIENCE,
  HEBBIAN_RECENT_ACTIVITY,
  HEBBIAN_WHOAMI,
  HEBBIAN_USAGE,
  HEBBIAN_GDPR_EXPORT,
  HEBBIAN_AUDIT_LOG,
} from "./tools/index.js";

/** Env var that opts in to the admin tool set. Off unless set to 1/true/yes/on. */
export const ADMIN_TOOLS_ENV = "HEBBIAN_ADMIN_TOOLS";

/** Tools every agent gets. */
export const EVERYDAY_TOOLS = [
  HEBBIAN_READ_NODE,
  HEBBIAN_SEARCH,
  HEBBIAN_ASK,
  HEBBIAN_CONTEXT,
  HEBBIAN_CAPTURE,
  HEBBIAN_TRAVERSE,
  HEBBIAN_PROVENANCE,
  HEBBIAN_SALIENCE,
  HEBBIAN_RECENT_ACTIVITY,
  HEBBIAN_WHOAMI,
] as const;

/** Admin tools: listed and served only with HEBBIAN_ADMIN_TOOLS on. */
export const ADMIN_TOOLS = [
  HEBBIAN_USAGE,
  HEBBIAN_GDPR_EXPORT,
  HEBBIAN_AUDIT_LOG,
] as const;

export const ADMIN_TOOL_NAMES: ReadonlySet<string> = new Set(ADMIN_TOOLS.map((t) => t.name));

/** The tools to list for this run. */
export function listedTools(adminTools: boolean) {
  return adminTools ? [...EVERYDAY_TOOLS, ...ADMIN_TOOLS] : [...EVERYDAY_TOOLS];
}

/** Refusal text for an admin tool called while the admin set is off, else null. */
export function adminToolRefusal(name: string, adminTools: boolean): string | null {
  if (adminTools || !ADMIN_TOOL_NAMES.has(name)) return null;
  return (
    `Tool ${name} is an admin tool and is off. Admin tools are opt-in: ` +
    `set ${ADMIN_TOOLS_ENV}=1 in this MCP server's environment to enable them.`
  );
}
