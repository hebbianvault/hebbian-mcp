/**
 * src/absorb/importers.ts
 *
 * Local importers for the absorb command (ADR-055 §4). An importer walks a
 * directory, reads the files relevant to one store kind, and turns each into an
 * AbsorbItem. It NEVER posts anything — the CLI batches the items to the API.
 *
 * Two importers ship in this slice:
 *   claude-code — a Claude Code memory directory: every *.md file, including
 *                 the MEMORY.md index and any CLAUDE.md files.
 *   markdown    — generic catch-all: walk a directory tree for every *.md file.
 *
 * Both reuse the same secret guards (secrets.ts): a credential-named file is
 * skipped, and token-shaped strings are redacted from the content before it is
 * handed back. Each importer reports skipped/redacted counts so the CLI can
 * print an honest summary.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

import { redactSecrets, shouldSkipFile } from "./secrets.js";

/** One memory item ready to absorb. Matches the API's AbsorbItem shape. */
export interface AbsorbItem {
  store_kind: string;
  /** Stable identifier within the store — the file's path relative to the root. */
  source_id: string;
  /** First markdown heading, else the filename. */
  title: string;
  /** Redacted file content. */
  content: string;
  /** Filesystem birthtime (ISO-8601), best-effort. */
  created_at?: string;
  /** Filesystem mtime (ISO-8601). */
  updated_at?: string;
}

/** Outcome of walking a directory: items to upload + what was skipped/redacted. */
export interface ScanResult {
  items: AbsorbItem[];
  skippedSecretFiles: string[];
  redactedItems: number;
  redactedSecrets: number;
}

/** Directories never descended into (noise + secret stores). */
const SKIP_DIRS = new Set([
  "node_modules",
  ".git",
  ".venv",
  "venv",
  "__pycache__",
  "dist",
  "build",
  ".next",
  ".cache",
]);

const SUPPORTED_STORES = ["claude-code", "markdown"] as const;
export type StoreKind = (typeof SUPPORTED_STORES)[number];

export function isSupportedStore(kind: string): kind is StoreKind {
  return (SUPPORTED_STORES as readonly string[]).includes(kind);
}

export function supportedStores(): readonly string[] {
  return SUPPORTED_STORES;
}

/** Recursively collect every *.md file under root (relative paths). */
function collectMarkdownFiles(root: string): string[] {
  const out: string[] = [];
  const walk = (dir: string): void => {
    let entries: string[];
    try {
      entries = readdirSync(dir);
    } catch {
      return; // unreadable dir — skip quietly
    }
    for (const entry of entries) {
      const abs = join(dir, entry);
      let st;
      try {
        st = statSync(abs);
      } catch {
        continue;
      }
      if (st.isDirectory()) {
        if (!SKIP_DIRS.has(entry)) walk(abs);
        continue;
      }
      if (st.isFile() && entry.toLowerCase().endsWith(".md")) {
        out.push(relative(root, abs));
      }
    }
  };
  walk(root);
  return out.sort();
}

/** First markdown heading in the content, else the basename without extension. */
function deriveTitle(content: string, relPath: string): string {
  for (const raw of content.split("\n")) {
    const line = raw.trim();
    const m = /^#{1,6}\s+(.+?)\s*#*$/.exec(line);
    if (m && m[1]) return m[1].trim();
  }
  const base = relPath.split(/[\\/]/).pop() ?? relPath;
  return base.replace(/\.md$/i, "");
}

/**
 * Walk a directory and build absorb items for one store kind.
 *
 * Shared by both importers — they differ only in the store_kind tag and (for
 * documentation) the expectation of what lives in the directory; the file
 * selection (every *.md, including MEMORY.md and CLAUDE.md) is identical, which
 * is exactly what a Claude Code memory directory contains.
 */
export function scanDirectory(root: string, storeKind: string): ScanResult {
  const rel = collectMarkdownFiles(root);
  const items: AbsorbItem[] = [];
  const skippedSecretFiles: string[] = [];
  let redactedItems = 0;
  let redactedSecrets = 0;

  for (const relPath of rel) {
    const base = relPath.split(/[\\/]/).pop() ?? relPath;
    if (shouldSkipFile(base)) {
      skippedSecretFiles.push(relPath);
      continue;
    }
    const abs = join(root, relPath);
    let raw: string;
    let st;
    try {
      raw = readFileSync(abs, "utf-8");
      st = statSync(abs);
    } catch {
      continue;
    }
    const { content, redactedCount } = redactSecrets(raw);
    if (redactedCount > 0) {
      redactedItems += 1;
      redactedSecrets += redactedCount;
    }
    // Normalise source_id to forward slashes so it is stable across OSes.
    const sourceId = relPath.split(sep).join("/");
    items.push({
      store_kind: storeKind,
      source_id: sourceId,
      title: deriveTitle(content, relPath),
      content,
      created_at: st.birthtime?.toISOString?.(),
      updated_at: st.mtime?.toISOString?.(),
    });
  }

  return { items, skippedSecretFiles, redactedItems, redactedSecrets };
}
