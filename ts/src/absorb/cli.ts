/**
 * src/absorb/cli.ts
 *
 * The `absorb` command (ADR-055 §4). Onboard an agent you already use by
 * uploading its existing context store as review-lane seeds.
 *
 *   hebbian-mcp absorb claude-code <dir> --agent <agent_id>
 *   hebbian-mcp absorb markdown    <dir> --agent <agent_id>
 *
 * Reads *.md files locally (Claude Code memory dir: MEMORY.md index + CLAUDE.md
 * files; generic markdown: any *.md), skips credential-named files, redacts
 * token-shaped strings, then batches the items to
 * POST /v1/agents/{agent_id}/absorb with the agent token from the existing
 * config/env convention (config.ts).
 *
 * --dry-run walks and reports without uploading. The auth token + API URL come
 * from HEBBIAN_API_TOKEN / config file exactly like the MCP server.
 */

import { HebbianClient } from "../client.js";
import { loadConfig } from "../config.js";
import {
  isSupportedStore,
  scanDirectory,
  supportedStores,
  type AbsorbItem,
} from "./importers.js";

/** Server-side batch cap (ADR-055 §2). Keep in sync with MAX_BATCH_ITEMS. */
const BATCH_SIZE = 200;

interface AbsorbArgs {
  store: string;
  dir: string;
  agentId: string;
  dryRun: boolean;
}

interface ParsedFlags {
  agentId?: string;
  dryRun: boolean;
  positionals: string[];
}

function parseFlags(argv: string[]): ParsedFlags {
  const positionals: string[] = [];
  let agentId: string | undefined;
  let dryRun = false;
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--agent" || a === "--agent-id") {
      agentId = argv[i + 1];
      i += 1;
    } else if (a.startsWith("--agent=")) {
      agentId = a.slice("--agent=".length);
    } else if (a === "--dry-run") {
      dryRun = true;
    } else {
      positionals.push(a);
    }
  }
  return { agentId, dryRun, positionals };
}

const USAGE = [
  "Usage: hebbian-mcp absorb <store> <dir> --agent <agent_id> [--dry-run]",
  "",
  `  store    one of: ${supportedStores().join(", ")}`,
  "  dir      path to the context store directory",
  "  --agent  the agent principal UUID to absorb into (the agent you already use)",
  "  --dry-run  walk and report; do not upload",
  "",
  "Auth: set HEBBIAN_API_TOKEN to the agent's token (or use the config file).",
  "Reads *.md files, skips credential-named files and symlinks, redacts token-shaped strings,",
  "then uploads each file as a review-lane seed attributed to the agent.",
].join("\n");

/** Resolve + validate args. Returns null (after printing usage) on a usage error. */
function resolveArgs(argv: string[]): AbsorbArgs | null {
  const { agentId, dryRun, positionals } = parseFlags(argv);
  const [store, dir] = positionals;
  if (!store || !dir) {
    process.stderr.write(`${USAGE}\n`);
    return null;
  }
  if (!isSupportedStore(store)) {
    process.stderr.write(
      `absorb: unsupported store "${store}". Supported: ${supportedStores().join(", ")}\n`,
    );
    return null;
  }
  if (!dryRun && !agentId) {
    process.stderr.write("absorb: --agent <agent_id> is required (or use --dry-run)\n");
    return null;
  }
  return { store, dir, agentId: agentId ?? "", dryRun };
}

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

interface AbsorbBatchResponse {
  accepted?: number;
  duplicates?: number;
  errors?: number;
}

/**
 * Run the absorb command. Returns the process exit code (0 ok, non-zero error).
 * Reads the store, prints the skipped/redacted summary, then (unless --dry-run)
 * uploads in batches and prints the per-batch tally.
 */
export async function runAbsorb(argv: string[]): Promise<number> {
  const args = resolveArgs(argv);
  if (args === null) return 2;

  const scan = scanDirectory(args.dir, args.store);

  // Honest summary line (ADR-055 §4): how many files, skipped secrets, redactions.
  process.stderr.write(
    `[absorb] store=${args.store} dir=${args.dir}: ` +
      `${scan.items.length} file(s) to absorb, ` +
      `skipped ${scan.skippedSecretFiles.length} credential-named file(s), ` +
      `skipped ${scan.skippedSymlinks.length} symlink(s), ` +
      `redacted ${scan.redactedSecrets} token-shaped string(s) across ${scan.redactedItems} file(s)\n`,
  );
  if (scan.skippedSecretFiles.length > 0) {
    for (const f of scan.skippedSecretFiles) {
      process.stderr.write(`[absorb]   skipped (looks like secrets): ${f}\n`);
    }
  }
  if (scan.skippedSymlinks.length > 0) {
    for (const f of scan.skippedSymlinks) {
      process.stderr.write(`[absorb]   skipped (symlink): ${f}\n`);
    }
  }

  if (scan.items.length === 0) {
    process.stderr.write("[absorb] nothing to absorb.\n");
    return 0;
  }

  if (args.dryRun) {
    process.stderr.write(
      `[absorb] dry-run: would upload ${scan.items.length} item(s) to ` +
        `/v1/agents/${args.agentId || "<agent_id>"}/absorb in ` +
        `${chunk(scan.items, BATCH_SIZE).length} batch(es). No upload performed.\n`,
    );
    return 0;
  }

  const config = loadConfig();
  const client = new HebbianClient(
    config.apiUrl,
    config.token,
    config.tenant,
    config.graphPagination,
  );

  let accepted = 0;
  let duplicates = 0;
  let errors = 0;
  const batches = chunk(scan.items, BATCH_SIZE);
  for (let i = 0; i < batches.length; i += 1) {
    const batch: AbsorbItem[] = batches[i];
    try {
      const resp = (await client.post(`/v1/agents/${args.agentId}/absorb`, {
        items: batch,
      })) as AbsorbBatchResponse;
      accepted += resp.accepted ?? 0;
      duplicates += resp.duplicates ?? 0;
      errors += resp.errors ?? 0;
      process.stderr.write(
        `[absorb] batch ${i + 1}/${batches.length}: ` +
          `accepted ${resp.accepted ?? 0}, duplicate ${resp.duplicates ?? 0}, error ${resp.errors ?? 0}\n`,
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      process.stderr.write(`[absorb] batch ${i + 1}/${batches.length} failed: ${message}\n`);
      return 1;
    }
  }

  process.stderr.write(
    `[absorb] done: ${accepted} new seed(s), ${duplicates} already absorbed, ${errors} error(s). ` +
      "New seeds await review in the Hebbian review lane.\n",
  );
  return errors > 0 ? 1 : 0;
}
