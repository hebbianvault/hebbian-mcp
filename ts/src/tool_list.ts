/**
 * src/tool_list.ts
 *
 * Which tools this adapter lists and serves.
 *
 * DEC #284 (founder 2026-10-22): the everyday AI tool set carries no admin
 * power. usage, audit_log and the GDPR export move to an opt-in admin set, so
 * they are NOT listed or callable unless the operator sets
 * HEBBIAN_ADMIN_TOOLS=1 (off by default). The API still enforces what the
 * token may do; this flag only decides whether the agent is offered the tool.
 */

import type { HebbianConfig } from "./config.js";
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

type ToolConfig = Pick<HebbianConfig, "adminTools">;

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

/** The tools to list for this run. */
export function listTools(config: ToolConfig) {
  return config.adminTools ? [...EVERYDAY_TOOLS, ...ADMIN_TOOLS] : [...EVERYDAY_TOOLS];
}

/** True when `name` is in the list this run offers. */
export function isListedTool(config: ToolConfig, name: string): boolean {
  return listTools(config).some((t) => t.name === name);
}

/**
 * The error for a name that is not listed. An admin tool called without the
 * opt-in gets exactly this, so the answer is not an oracle for which admin
 * tools exist.
 */
export function unknownToolResult(name: string) {
  return {
    content: [{ type: "text" as const, text: `Unknown tool: ${name}` }],
    isError: true,
  };
}
