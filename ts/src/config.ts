/**
 * src/config.ts
 *
 * Configuration loading for @hebbianvault/mcp.
 *
 * Auth: bearer token from HEBBIAN_API_TOKEN env var (preferred) or
 *       HEBBIAN_TOKEN (alternative) or config-file JSON path.
 * URL:  HEBBIAN_API_URL env var (default: the Hebbian SaaS API). Enterprise
 *       self-host customers override this to point at their own VM.
 * Tenant: HEBBIAN_TENANT (optional) — only needed when your account belongs to
 *       more than one Hebbian workspace, to disambiguate which one to act in.
 */

import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// Hebbian SaaS API. Enterprise/self-host customers override with HEBBIAN_API_URL.
const DEFAULT_API_URL = "https://api.hebbianvault.com";

export interface HebbianConfig {
  /** Base URL of the Hebbian API (configurable for Enterprise self-host). */
  apiUrl: string;
  /** Bearer token for authentication (never log this). */
  token: string;
  /**
   * Optional workspace slug. Only required when your account belongs to more
   * than one Hebbian workspace; sent as the X-Hebbian-Tenant header so the API
   * knows which workspace you are acting in. Single-workspace accounts can omit.
   */
  tenant?: string;
  /** Opt in to UUID-keyset pagination when retrieving the workspace graph. */
  graphPagination: boolean;
}

interface ConfigFile {
  api_url?: string;
  token?: string;
  tenant?: string;
}

/**
 * Load configuration from environment variables and optional config file.
 *
 * Priority (highest first):
 *   1. HEBBIAN_API_TOKEN / HEBBIAN_TOKEN env vars
 *   2. HEBBIAN_CONFIG_PATH — path to a JSON config file
 *   3. ~/.config/hebbian/mcp-tenant.json
 *
 * Throws if no token can be resolved — the MCP server cannot start without auth.
 */
export function loadConfig(): HebbianConfig {
  // ── API URL ────────────────────────────────────────────────────────────────
  const apiUrl = process.env.HEBBIAN_API_URL ?? DEFAULT_API_URL;

  // ── Tenant (optional) ────────────────────────────────────────────────────────
  const envTenant = process.env.HEBBIAN_TENANT?.trim() || undefined;

  // ── Graph pagination (opt-in) ─────────────────────────────────────────────
  const graphPagination = isTruthy(process.env.HEBBIAN_GRAPH_PAGINATION);

  // ── Token (env first) ──────────────────────────────────────────────────────
  const envToken = process.env.HEBBIAN_API_TOKEN ?? process.env.HEBBIAN_TOKEN;
  if (envToken && envToken.length > 0) {
    return { apiUrl, token: envToken, tenant: envTenant, graphPagination };
  }

  // ── Token (config file) ────────────────────────────────────────────────────
  const configPath = resolveConfigPath();
  if (configPath) {
    const file = readConfigFile(configPath);
    if (file.token && file.token.length > 0) {
      return {
        apiUrl: file.api_url ?? apiUrl,
        token: file.token,
        tenant: envTenant ?? file.tenant,
        graphPagination,
      };
    }
  }

  throw new Error(
    "Hebbian MCP: No API token found. " +
    "Set HEBBIAN_API_TOKEN env var or HEBBIAN_TOKEN env var, " +
    "or write your token to ~/.config/hebbian/mcp-tenant.json as { \"token\": \"...\" }. " +
    "Generate a token from the AI Tools tab in your Hebbian integrations page."
  );
}

/** Accept the conventional env-var spellings for an enabled boolean flag. */
function isTruthy(value: string | undefined): boolean {
  return value !== undefined && ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
}

/** Resolve config file path — explicit env var or default location. */
function resolveConfigPath(): string | null {
  const explicit = process.env.HEBBIAN_CONFIG_PATH;
  if (explicit) {
    const abs = resolve(explicit);
    if (existsSync(abs)) return abs;
    // Warn but don't throw — fall back to env token check result above
    process.stderr.write(
      `[hebbian-mcp] Warning: HEBBIAN_CONFIG_PATH set to "${explicit}" but file not found.\n`
    );
    return null;
  }

  const homeDir = process.env.HOME ?? process.env.USERPROFILE ?? "";
  if (!homeDir) return null;

  const defaultPath = resolve(homeDir, ".config", "hebbian", "mcp-tenant.json");
  return existsSync(defaultPath) ? defaultPath : null;
}

/** Read and parse a JSON config file; tolerates missing fields. */
function readConfigFile(path: string): ConfigFile {
  try {
    const raw = readFileSync(path, "utf-8");
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed !== "object" || parsed === null) {
      throw new Error("Config file must be a JSON object");
    }
    return parsed as ConfigFile;
  } catch (err) {
    process.stderr.write(
      `[hebbian-mcp] Warning: Could not read config file at "${path}": ${String(err)}\n`
    );
    return {};
  }
}
