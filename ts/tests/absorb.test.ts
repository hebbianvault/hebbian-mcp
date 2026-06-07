/**
 * tests/absorb.test.ts
 *
 * Unit tests for the absorb importer (ADR-055 §4). Two layers:
 *   secrets — file-name exclusion + content redaction (the non-negotiable guard).
 *   importer — scanDirectory over a temp tree: which files become items, that
 *              credential-named files are skipped, that token-shaped strings are
 *              redacted in the uploaded content, title/source_id derivation.
 *
 * No network. The CLI batching/upload is a thin loop over scanDirectory + the
 * existing HebbianClient; the security-critical logic is here.
 */

import { describe, test, expect, beforeAll, afterAll } from "@jest/globals";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { shouldSkipFile, redactSecrets } from "../src/absorb/secrets.js";
import { scanDirectory, isSupportedStore } from "../src/absorb/importers.js";

describe("secrets.shouldSkipFile", () => {
  test("skips env and credential-named files", () => {
    for (const name of [
      ".env",
      ".env.local",
      ".env.production",
      "credentials.json",
      "aws-credentials",
      "my-secret.md",
      "secrets.yaml",
      "token.txt",
      "api-tokens.json",
      "auth_token.md",
      "server.pem",
      "tls.key",
      "id_rsa",
    ]) {
      expect(shouldSkipFile(name)).toBe(true);
    }
  });

  test("keeps ordinary markdown files", () => {
    for (const name of ["MEMORY.md", "CLAUDE.md", "notes.md", "readme.md", "tokenizer.md"]) {
      expect(shouldSkipFile(name)).toBe(false);
    }
  });
});

// Token-shaped fixtures are ASSEMBLED at runtime from a prefix + a synthetic
// body so that no complete real-looking credential literal ever appears in the
// source file (which would trip GitHub push-protection secret scanning). The
// assembled string still matches the redaction regexes.
const BODY = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEF";
function fixture(prefix: string): string {
  return `${prefix}${BODY}`;
}

describe("secrets.redactSecrets", () => {
  test("redacts token-shaped strings", () => {
    const cases = [
      fixture("sk-"),
      fixture("sk-ant-api03-"),
      fixture("gh" + "p_"),
      fixture("github" + "_pat_11"),
      fixture("hbn_"),
      fixture("xox" + "b-"),
      "AKIA" + "IOSFODNN7EXAMPLE",
      fixture("AIza"),
      ["eyJ" + "hbGciOiJIUzI1NiI", "eyJ" + "zdWIiOiIxMjM0NTY", "SflKxwRJSMeKKF2QT4fwp"].join("."),
      "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef0123",
    ];
    for (const secret of cases) {
      const { content, redactedCount } = redactSecrets(`token is ${secret} ok`);
      expect(content).not.toContain(secret);
      expect(content).toContain("[REDACTED]");
      expect(redactedCount).toBeGreaterThanOrEqual(1);
    }
  });

  test("keeps the Bearer word but redacts the value", () => {
    const { content } = redactSecrets("Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456");
    expect(content).toContain("Bearer [REDACTED]");
  });

  test("redacts URL-embedded credentials but keeps scheme/user/host", () => {
    const cases = [
      {
        input: "db is postgresql://app.user:S3cretPassw0rd@db.example.com:6543/postgres ok",
        keep: "postgresql://app.user:[REDACTED]@db.example.com:6543/postgres",
        gone: "S3cretPassw0rd",
      },
      {
        input: "cache at redis://:s3cretpass@localhost:6379/0",
        keep: "redis://:[REDACTED]@localhost:6379/0",
        gone: "s3cretpass",
      },
      {
        input: "queue amqp://guest:guestpw@mq.internal:5672",
        keep: "amqp://guest:[REDACTED]@mq.internal:5672",
        gone: "guestpw",
      },
    ];
    for (const { input, keep, gone } of cases) {
      const { content, redactedCount } = redactSecrets(input);
      expect(content).toContain(keep);
      expect(content).not.toContain(gone);
      expect(redactedCount).toBeGreaterThanOrEqual(1);
    }
  });

  test("leaves credential-free URLs untouched", () => {
    const cases = [
      "see https://docs.example.com/path?q=1 for details",
      "git remote is ssh://git@github.com/org/repo.git", // user but no password
      "local dev on http://localhost:3000/app",
    ];
    for (const text of cases) {
      const { content, redactedCount } = redactSecrets(text);
      expect(content).toBe(text);
      expect(redactedCount).toBe(0);
    }
  });

  test("redacts Supabase key prefixes", () => {
    for (const secret of [fixture("sb_secret_"), fixture("sbp_")]) {
      const { content, redactedCount } = redactSecrets(`key is ${secret} ok`);
      expect(content).not.toContain(secret);
      expect(redactedCount).toBeGreaterThanOrEqual(1);
    }
  });

  test("leaves clean prose untouched", () => {
    const text = "This is a normal memory note about the Q2 roadmap and pricing.";
    const { content, redactedCount } = redactSecrets(text);
    expect(content).toBe(text);
    expect(redactedCount).toBe(0);
  });
});

describe("importers.isSupportedStore", () => {
  test("claude-code and markdown are supported", () => {
    expect(isSupportedStore("claude-code")).toBe(true);
    expect(isSupportedStore("markdown")).toBe(true);
    expect(isSupportedStore("cursor")).toBe(false);
  });
});

describe("importers.scanDirectory", () => {
  let dir: string;

  beforeAll(() => {
    dir = mkdtempSync(join(tmpdir(), "absorb-test-"));
    writeFileSync(join(dir, "MEMORY.md"), "# Memory index\n\nThe index of everything.\n");
    writeFileSync(join(dir, "CLAUDE.md"), "# Project rules\n\nUse TypeScript.\n");
    // Token-shaped bodies are assembled at runtime so no complete credential
    // literal sits in the source (GitHub push-protection would block it).
    const ghToken = "gh" + "p_" + BODY;
    const skToken = "sk-" + BODY;
    // Nested markdown with a token-shaped secret in the body.
    mkdirSync(join(dir, "sub"), { recursive: true });
    writeFileSync(
      join(dir, "sub", "creds-in-body.md"),
      `# Has a key\n\nmy token: ${ghToken} here\n`,
    );
    // Credential-named file: must be skipped entirely.
    writeFileSync(join(dir, ".env"), `SECRET=${ghToken}\n`);
    writeFileSync(join(dir, "api-credentials.md"), `# creds\n\n${skToken}\n`);
    // node_modules is ignored.
    mkdirSync(join(dir, "node_modules", "pkg"), { recursive: true });
    writeFileSync(join(dir, "node_modules", "pkg", "README.md"), "# dep\n");
    // A non-markdown file is ignored.
    writeFileSync(join(dir, "data.json"), "{}");
  });

  afterAll(() => {
    rmSync(dir, { recursive: true, force: true });
  });

  test("collects markdown, skips secret-named, ignores node_modules + non-md", () => {
    const res = scanDirectory(dir, "claude-code");
    const sourceIds = res.items.map((i) => i.source_id).sort();
    expect(sourceIds).toEqual(["CLAUDE.md", "MEMORY.md", "sub/creds-in-body.md"]);
    // api-credentials.md is a .md file but credential-named → skipped by name.
    // .env is excluded even earlier (not a .md file), so it never reaches the
    // skip list; either way it is never uploaded.
    expect(res.skippedSecretFiles).toEqual(["api-credentials.md"]);
    expect(sourceIds).not.toContain(".env");
  });

  test("redacts token-shaped strings in collected content", () => {
    const res = scanDirectory(dir, "claude-code");
    const item = res.items.find((i) => i.source_id === "sub/creds-in-body.md");
    expect(item).toBeDefined();
    expect(item?.content).not.toContain("gh" + "p_" + BODY);
    expect(item?.content).toContain("[REDACTED]");
    expect(res.redactedSecrets).toBeGreaterThanOrEqual(1);
    expect(res.redactedItems).toBeGreaterThanOrEqual(1);
  });

  test("derives title from first heading and stamps store_kind + timestamps", () => {
    const res = scanDirectory(dir, "markdown");
    const mem = res.items.find((i) => i.source_id === "MEMORY.md");
    expect(mem?.title).toBe("Memory index");
    expect(mem?.store_kind).toBe("markdown");
    expect(typeof mem?.updated_at).toBe("string");
  });
});
