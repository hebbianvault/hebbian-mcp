/**
 * src/banner.ts
 *
 * Prints the Hebbian cyan lockup banner to STDERR on server startup.
 * STDERR only — stdout carries JSON-RPC and any write there corrupts the MCP protocol.
 *
 * Brand spec: mark region = solid HEBBIAN_CYAN (#00CFE8);
 * wordmark region = gradient #00CFE8 → #1AA3FF.
 * Split column: first column (from left) where the block glyph █ appears.
 *
 * Vendored asset: src/assets/lockup.txt (baked, no network call).
 * Logic ported from ~/.claude/skills/hebbian-logo/color_lockup.py.
 */

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

// ── Constants ──────────────────────────────────────────────────────────────────

// Colours as [r, g, b] tuples
const CYAN: [number, number, number] = [0, 207, 232];   // #00CFE8
const C0: [number, number, number] = [0, 207, 232];     // #00CFE8 (wordmark start)
const C1: [number, number, number] = [26, 163, 255];    // #1AA3FF (wordmark end)
const RESET = "\x1b[0m";

// ── Helpers ────────────────────────────────────────────────────────────────────

function fg(r: number, g: number, b: number): string {
  return `\x1b[38;2;${r};${g};${b}m`;
}

function lerp(a: number, b: number, t: number): number {
  return Math.round(a + (b - a) * t);
}

// ── Core render ────────────────────────────────────────────────────────────────

/**
 * Renders the lockup.txt with 24-bit ANSI cyan colouring.
 * Returns the coloured string (does NOT write to stderr itself —
 * printBanner() handles that so callers can test the output).
 */
export function renderBanner(): string {
  const __dirname = dirname(fileURLToPath(import.meta.url));
  const lockupPath = resolve(__dirname, "assets", "lockup.txt");
  const raw = readFileSync(lockupPath, "utf-8");
  const lines = raw.replace(/\n$/, "").split("\n");

  // Find the wordmark start column: first column where █ appears in any line.
  let split = 14; // fallback default
  for (const line of lines) {
    const idx = line.indexOf("█");
    if (idx !== -1 && idx < split) {
      split = idx;
    }
  }

  const maxLen = Math.max(...lines.map((l) => l.length));
  const wordW = maxLen - split;

  const rendered = lines.map((line) => {
    let out = "";
    for (let ci = 0; ci < line.length; ci++) {
      const ch = line[ci];
      if (ch === " ") {
        out += " ";
        continue;
      }
      if (ci < split) {
        // Mark region — solid HEBBIAN_CYAN
        out += fg(CYAN[0], CYAN[1], CYAN[2]) + ch;
      } else {
        // Wordmark region — gradient C0 → C1
        const f = wordW > 1 ? (ci - split) / (wordW - 1) : 0;
        const r = lerp(C0[0], C1[0], f);
        const g = lerp(C0[1], C1[1], f);
        const b = lerp(C0[2], C1[2], f);
        out += fg(r, g, b) + ch;
      }
    }
    return out + RESET;
  });

  return rendered.join("\n");
}

/**
 * Print the cyan lockup banner to stderr.
 * Call once at server startup — before the MCP transport connects.
 * Failure-tolerant: catches all errors and silently skips the banner
 * rather than crashing the server over a cosmetic output issue.
 */
export function printBanner(): void {
  try {
    const banner = renderBanner();
    process.stderr.write(banner + "\n");
  } catch {
    // Banner is cosmetic — never let it crash the server.
  }
}
