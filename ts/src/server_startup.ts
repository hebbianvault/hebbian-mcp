/** Coordinate the non-fatal startup probe before MCP transport begins serving. */

import { type HebbianClient } from "./client.js";
import { runStartupHealthCheck } from "./startup_health.js";

type StartServing = () => Promise<void>;
type StderrWriter = (line: string) => void;

/**
 * Run the advisory API/token probe before connecting the MCP transport.
 * A probe failure is reported by runStartupHealthCheck and never blocks serving.
 */
export async function startServingAfterHealthCheck(
  client: Pick<HebbianClient, "get">,
  startServing: StartServing,
  writeStderr?: StderrWriter,
): Promise<void> {
  await runStartupHealthCheck(client, writeStderr);
  await startServing();
}
