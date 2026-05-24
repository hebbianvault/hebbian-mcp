#!/usr/bin/env node
/**
 * ts/scripts/postinstall.mjs
 *
 * Prints the cyan Hebbian lockup banner to stderr on `npm install @hebbianvault/mcp`.
 * The "pro install" moment — first thing customers see.
 *
 * RULES:
 * - Always print to STDERR (never stdout — MCP transport protocol).
 * - Never crash the install. Every code path is wrapped in try/catch.
 * - Self-contained: reads lockup.txt relative to this script; no dist/ dependency.
 * - Fast: pure filesystem read + string operations, no network, no shell.
 *
 * Brand spec: HEBBIAN_CYAN (#00CFE8) mark + #00CFE8→#1AA3FF wordmark gradient.
 * Ported from ~/.claude/skills/hebbian-logo/color_lockup.py.
 */

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

// ── Colours ────────────────────────────────────────────────────────────────────

const CYAN = [0, 207, 232];   // #00CFE8
const C0   = [0, 207, 232];   // #00CFE8 wordmark start
const C1   = [26, 163, 255];  // #1AA3FF wordmark end
const RESET = "\x1b[0m";

function fg(r, g, b) {
  return `\x1b[38;2;${r};${g};${b}m`;
}

function lerp(a, b, t) {
  return Math.round(a + (b - a) * t);
}

// ── Render ─────────────────────────────────────────────────────────────────────

function renderBanner() {
  const __dirname = dirname(fileURLToPath(import.meta.url));
  // lockup.txt lives next to the src/ dir: ts/src/assets/lockup.txt
  const lockupPath = resolve(__dirname, "..", "src", "assets", "lockup.txt");
  const raw = readFileSync(lockupPath, "utf-8");
  const lines = raw.replace(/\n$/, "").split("\n");

  // Find wordmark split column: first █ in any line
  let split = 14;
  for (const line of lines) {
    const idx = line.indexOf("█"); // █
    if (idx !== -1 && idx < split) {
      split = idx;
    }
  }

  const maxLen = Math.max(...lines.map((l) => l.length));
  const wordW = maxLen - split;

  return lines.map((line) => {
    let out = "";
    for (let ci = 0; ci < line.length; ci++) {
      const ch = line[ci];
      if (ch === " ") { out += " "; continue; }
      if (ci < split) {
        out += fg(CYAN[0], CYAN[1], CYAN[2]) + ch;
      } else {
        const f = wordW > 1 ? (ci - split) / (wordW - 1) : 0;
        out += fg(lerp(C0[0], C1[0], f), lerp(C0[1], C1[1], f), lerp(C0[2], C1[2], f)) + ch;
      }
    }
    return out + RESET;
  }).join("\n");
}

// ── Main ───────────────────────────────────────────────────────────────────────

try {
  const banner = renderBanner();
  process.stderr.write("\n" + banner + "\n\n");
  process.stderr.write(
    "\x1b[38;2;0;207;232m  Hebbian MCP installed. " +
    "Generate your token at the AI Tools tab.\x1b[0m\n\n"
  );
} catch {
  // Banner is cosmetic — never break the install.
}
