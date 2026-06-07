/**
 * src/absorb/secrets.ts
 *
 * Secret exclusion + redaction for the absorb importers (ADR-055 §4).
 *
 * Two layers, both non-negotiable:
 *   1. File exclusion — never read a file whose name looks like it holds
 *      credentials (.env*, *credentials*, *secret*, *token*-named files).
 *   2. Content redaction — even in a file we DO read, replace token-shaped
 *      strings (long base64/hex, sk-..., ghp_..., hbn_..., AWS keys, JWTs)
 *      with a [REDACTED] marker before the content ever leaves the machine.
 *
 * Nothing here talks to the network. The importer calls shouldSkipFile() per
 * file and redactSecrets() on every body it is about to upload.
 */

/** A file basename matches one of these → skip it entirely. */
const SKIP_NAME_PATTERNS: RegExp[] = [
  /^\.env(\..*)?$/i, // .env, .env.local, .env.production, …
  /credentials/i, // aws credentials, gcloud credentials, *credentials*.json
  /secret/i, // secrets.yaml, my-secret.md, *secret*
  /(^|[._-])tokens?([._-]|$)/i, // token.txt, api-tokens.json, auth_token.md
  /\.pem$/i, // private keys
  /\.key$/i,
  /id_rsa/i, // ssh keys
  /\.p12$/i,
  /\.pfx$/i,
];

/**
 * Token-shaped substrings to redact from content. Ordered specific → generic so
 * a prefixed key (sk-…, ghp_…) is matched by its own rule before the generic
 * long-base64 catch-all. Each match is replaced with [REDACTED].
 */
const REDACT_PATTERNS: RegExp[] = [
  // OpenAI / Anthropic style: sk-… , sk-ant-…
  /\bsk-[A-Za-z0-9_-]{16,}\b/g,
  // GitHub tokens: ghp_, gho_, ghu_, ghs_, ghr_, github_pat_
  /\bgh[opusr]_[A-Za-z0-9]{16,}\b/g,
  /\bgithub_pat_[A-Za-z0-9_]{20,}\b/g,
  // Hebbian tokens.
  /\bhbn_[A-Za-z0-9_-]{16,}\b/g,
  // Slack tokens: xoxb-, xoxp-, xapp-…
  /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/g,
  // AWS access key id.
  /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/g,
  // Google API key.
  /\bAIza[A-Za-z0-9_-]{30,}\b/g,
  // JWT (three base64url segments).
  /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g,
  // Bearer headers — redact the value, keep the word.
  /\b([Bb]earer\s+)[A-Za-z0-9._-]{20,}\b/g,
  // URL-embedded credentials: scheme://user:password@host (postgres://, redis://,
  // amqp://, mongodb://, …). Redact the password, keep scheme/user/host so the
  // surrounding prose still reads sensibly.
  /\b([a-zA-Z][a-zA-Z0-9+.-]*:\/\/[^:@\/\s]*:)[^@\s]{3,}(?=@)/g,
  // Supabase secret / personal-access keys.
  /\bsb_secret_[A-Za-z0-9_-]{10,}\b/g,
  /\bsbp_[A-Za-z0-9]{20,}\b/g,
  // Generic long hex (>= 40 chars) — sha-like / hex secrets.
  /\b[0-9a-fA-F]{40,}\b/g,
  // Generic long base64-ish blob (>= 40 chars). Last so prefixed keys win first.
  /\b[A-Za-z0-9+/]{40,}={0,2}\b/g,
];

const REDACTION_MARKER = "[REDACTED]";

/**
 * True when a file should be skipped entirely because its NAME indicates it
 * holds credentials. Matches on the basename only (path is ignored), case-
 * insensitively.
 */
export function shouldSkipFile(filename: string): boolean {
  const base = filename.split(/[\\/]/).pop() ?? filename;
  return SKIP_NAME_PATTERNS.some((re) => re.test(base));
}

/** Result of redacting a string: the cleaned text + how many secrets were hit. */
export interface RedactionResult {
  content: string;
  redactedCount: number;
}

/**
 * Redact token-shaped strings from content. Returns the cleaned content and the
 * number of distinct matches replaced. Idempotent on already-clean text
 * (redactedCount === 0). The Bearer rule keeps the leading "Bearer " word so the
 * surrounding prose still reads sensibly.
 */
export function redactSecrets(content: string): RedactionResult {
  let redactedCount = 0;
  let out = content;
  for (const re of REDACT_PATTERNS) {
    out = out.replace(re, (match, ...groups) => {
      redactedCount += 1;
      // Rules with a capture group ("Bearer ", "scheme://user:") keep the prefix
      // so the surrounding prose still reads sensibly; only the secret is replaced.
      const prefix = typeof groups[0] === "string" ? groups[0] : "";
      return `${prefix}${REDACTION_MARKER}`;
    });
  }
  return { content: out, redactedCount };
}
