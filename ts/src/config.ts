/**
 * src/config.ts
 *
 * Configuration loading for @hebbian/mcp-tenant.
 *
 * Auth: bearer token from HEBBIAN_API_TOKEN env var (preferred) or
 *       HEBBIAN_TOKEN (alternative) or config-file JSON path.
 * URL:  HEBBIAN_API_URL env var (default: placeholder, apex parked — ADR-023).
 */

import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// TODO(apex): replace placeholder once domain name is locked (ADR-023 URL correction 2026-05-09)
const DEFAULT_API_URL = "https://api.<saas-apex>";

export interface HebbianConfig {
  /** Base URL of the Hebbian API (configurable for Enterprise self-host). */
  apiUrl: string;
  /** Bearer token for authentication (never log this). */
  token: string;
}

interface ConfigFile {
  api_url?: string;
  token?: string;
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

  // ── Token (env first) ──────────────────────────────────────────────────────
  const envToken = process.env.HEBBIAN_API_TOKEN ?? process.env.HEBBIAN_TOKEN;
  if (envToken && envToken.length > 0) {
    return { apiUrl, token: envToken };
  }

  // ── Token (config file) ────────────────────────────────────────────────────
  const configPath = resolveConfigPath();
  if (configPath) {
    const file = readConfigFile(configPath);
    if (file.token && file.token.length > 0) {
      return {
        apiUrl: file.api_url ?? apiUrl,
        token: file.token,
      };
    }
  }

  throw new Error(
    "Hebbian MCP: No API token found. " +
    "Set HEBBIAN_API_TOKEN env var or HEBBIAN_TOKEN env var, " +
    "or write your token to ~/.config/hebbian/mcp-tenant.json as { \"token\": \"hbn_...\" }. " +
    "Generate a token from the AI Tools tab in your Hebbian integrations page."
  );
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
