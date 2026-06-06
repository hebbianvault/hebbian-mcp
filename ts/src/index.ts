#!/usr/bin/env node
/**
 * @hebbianvault/mcp — Customer-installable MCP server for the Hebbian tenant brain.
 *
 * One package, scope-by-token (Employee or Company). Install in Claude Code,
 * Claude Desktop, Cursor, Cowork, or any MCP-compatible agent. Configure with a
 * token issued from your Hebbian integrations page (AI Tools tab).
 *
 * Auth: set HEBBIAN_API_TOKEN (or HEBBIAN_TOKEN) env var, or write a config
 * file at ~/.config/hebbian/mcp-tenant.json with { "token": "hbn_..." }.
 *
 * 9 tools:
 *   hebbian_read_node       — fetch a node by UUID
 *   hebbian_search          — search the workspace for matching nodes
 *   hebbian_ask             — synthesis Q&A returned with source quotes
 *   hebbian_context         — task-shaped retrieval: a salience-ranked context pack within a token budget
 *   hebbian_capture         — write a note into the workspace
 *   hebbian_traverse        — walk the graph from a starting node
 *   hebbian_provenance      — source trail for a node
 *   hebbian_salience        — salience/activity history for a node
 *   hebbian_recent_activity — recent workspace activity timeline
 *
 * All access control is enforced server-side by the API. What a token can
 * read and write is determined by its scope; this package is a thin client.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { loadConfig } from "./config.js";
import { HebbianClient } from "./client.js";
import { printBanner } from "./banner.js";
import { runAbsorb } from "./absorb/cli.js";
import {
  HEBBIAN_READ_NODE, handleReadNode,
  HEBBIAN_SEARCH, handleSearch,
  HEBBIAN_ASK, handleAsk,
  HEBBIAN_CONTEXT, handleContext,
  HEBBIAN_CAPTURE, handleCapture,
  HEBBIAN_TRAVERSE, handleTraverse,
  HEBBIAN_PROVENANCE, handleProvenance,
  HEBBIAN_SALIENCE, handleSalience,
  HEBBIAN_RECENT_ACTIVITY, handleRecentActivity,
} from "./tools/index.js";

// ── Constants ──────────────────────────────────────────────────────────────────

const SERVER_NAME = "@hebbianvault/mcp";
const SERVER_VERSION = "0.2.0";

// ── All registered tools ───────────────────────────────────────────────────────

const TOOLS = [
  HEBBIAN_READ_NODE,
  HEBBIAN_SEARCH,
  HEBBIAN_ASK,
  HEBBIAN_CONTEXT,
  HEBBIAN_CAPTURE,
  HEBBIAN_TRAVERSE,
  HEBBIAN_PROVENANCE,
  HEBBIAN_SALIENCE,
  HEBBIAN_RECENT_ACTIVITY,
] as const;

// ── Boot ───────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  // Print brand banner to STDERR before transport connects.
  // STDERR only — stdout is the JSON-RPC wire; any write there corrupts the protocol.
  printBanner();

  // Load config early — throw clearly if no token
  const config = loadConfig();

  const client = new HebbianClient(config.apiUrl, config.token, config.tenant);

  const server = new Server(
    { name: SERVER_NAME, version: SERVER_VERSION },
    { capabilities: { tools: {} } },
  );

  // ── list_tools ─────────────────────────────────────────────────────────────
  server.setRequestHandler(ListToolsRequestSchema, () => ({
    tools: [...TOOLS],
  }));

  // ── call_tool ──────────────────────────────────────────────────────────────
  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const { name, arguments: rawArgs } = req.params;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const args = (rawArgs ?? {}) as Record<string, any>;

    try {
      let result: string;

      switch (name) {
        case "hebbian_read_node":
          result = await handleReadNode(client, args as { uuid: string });
          break;
        case "hebbian_search":
          result = await handleSearch(client, args as {
            q: string;
            domain?: string;
            limit?: number;
          });
          break;
        case "hebbian_ask":
          result = await handleAsk(client, args as { question: string });
          break;
        case "hebbian_context":
          result = await handleContext(client, args as {
            task: string;
            budget_tokens?: number;
            scope?: "synthesis" | "company" | "employee" | "bridge";
          });
          break;
        case "hebbian_capture":
          result = await handleCapture(client, args as {
            title: string;
            text: string;
            domain?: string;
            tags?: string[];
            scope?: "private" | "company";
          });
          break;
        case "hebbian_traverse":
          result = await handleTraverse(client, args as {
            start_uuid: string;
            max_hops?: number;
          });
          break;
        case "hebbian_provenance":
          result = await handleProvenance(client, args as { uuid: string });
          break;
        case "hebbian_salience":
          result = await handleSalience(client, args as { uuid: string });
          break;
        case "hebbian_recent_activity":
          result = await handleRecentActivity(client, args as {
            since?: string;
            limit?: number;
          });
          break;
        default:
          return {
            content: [{ type: "text", text: `Unknown tool: ${name}` }],
            isError: true,
          };
      }

      return {
        content: [{ type: "text", text: result }],
      };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return {
        content: [{ type: "text", text: `Error: ${message}` }],
        isError: true,
      };
    }
  });

  // ── Transport ──────────────────────────────────────────────────────────────
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr only (stdout is the MCP wire)
  process.stderr.write(
    `[hebbian-mcp] ${SERVER_NAME}@${SERVER_VERSION} started. ` +
    `API: ${config.apiUrl}\n`,
  );
}

// ── Entry dispatch ───────────────────────────────────────────────────────────
// With NO subcommand, boot the MCP stdio server (unchanged default). The first
// argv is the subcommand: `hebbian-mcp absorb <store> <dir> --agent <id>` runs
// the one-shot context-absorption importer (ADR-055) instead of the server.
const subcommand = process.argv[2];

if (subcommand === "absorb") {
  runAbsorb(process.argv.slice(3))
    .then((code) => process.exit(code))
    .catch((err: unknown) => {
      process.stderr.write(
        `[hebbian-mcp] absorb error: ${err instanceof Error ? err.message : String(err)}\n`,
      );
      process.exit(1);
    });
} else {
  main().catch((err: unknown) => {
    process.stderr.write(
      `[hebbian-mcp] Fatal startup error: ${err instanceof Error ? err.message : String(err)}\n`,
    );
    process.exit(1);
  });
}
