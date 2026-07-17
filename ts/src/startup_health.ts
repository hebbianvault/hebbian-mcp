/** Non-fatal API reachability and identity check run before MCP serving starts. */

import { HebbianApiError, type HebbianClient } from "./client.js";

type StderrWriter = (line: string) => void;

/** A startup probe is advisory and must never delay the MCP handshake for long. */
export const STARTUP_HEALTH_TIMEOUT_MS = 5_000;

async function awaitStartupProbe<T>(request: Promise<T>): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      request,
      new Promise<never>((_, reject) => {
        timer = setTimeout(
          () => reject(new Error(`startup probe timed out after ${STARTUP_HEALTH_TIMEOUT_MS}ms`)),
          STARTUP_HEALTH_TIMEOUT_MS,
        );
      }),
    ]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}

function startupHealthHint(error: unknown): string {
  if (error instanceof HebbianApiError) {
    if (error.statusCode === 401) {
      return "authentication rejected (401). Your token may be invalid, expired, or revoked. " +
        "Generate a new token from the AI Tools tab in your Hebbian integrations page.";
    }
    if (error.statusCode === 403) {
      return "access denied (403). Check that the token scope and selected tenant are valid.";
    }
  }
  return "API unreachable or unavailable. Check your network connection and HEBBIAN_API_URL.";
}

/**
 * Check the public health endpoint, then validate the configured token identity.
 * Failures are deliberately reported but never allowed to prevent MCP startup.
 */
export async function runStartupHealthCheck(
  client: Pick<HebbianClient, "get">,
  writeStderr: StderrWriter = (line) => process.stderr.write(line),
): Promise<void> {
  try {
    await awaitStartupProbe(client.get("/healthz"));
    await awaitStartupProbe(client.get("/tenant/whoami"));
  } catch (error) {
    writeStderr(`[hebbian-mcp] Startup health check failed: ${startupHealthHint(error)}\n`);
  }
}
