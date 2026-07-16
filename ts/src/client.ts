/**
 * src/client.ts
 *
 * HTTPS client for the Hebbian API.
 *
 * - Adds Authorization: Bearer header to every request.
 * - Surfaces API errors as structured HebbianApiError with code + message.
 * - No business logic — thin transport wrapper over fetch.
 * - All tool call implementations live in src/tools/*.ts.
 */

import { PACKAGE_VERSION } from "./package_info.js";

/** Structured API error returned by the Hebbian API (RFC 7807 variant). */
export class HebbianApiError extends Error {
  constructor(
    public readonly statusCode: number,
    public readonly errorCode: string,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "HebbianApiError";
  }

  /** Human-readable string for MCP tool error responses. */
  toToolError(): string {
    const serverReason = detailReason(this.detail);
    const message = serverReason ?? this.message;
    if (this.statusCode === 401) {
      const toolError = `Authentication failed (${this.errorCode}): ${message}.`;
      if (serverReason) return toolError;
      return `${toolError} Your token may be expired or revoked. ` +
        "Generate a new token from the AI Tools tab in your Hebbian integrations page.";
    }
    if (this.statusCode === 403) {
      const toolError = `Permission denied (${this.errorCode}): ${message}.`;
      if (serverReason) return toolError;
      return `${toolError} Check that your token scope (employee/company) matches the operation.`;
    }
    if (this.statusCode === 404) {
      return `Not found (${this.errorCode}): ${this.message}`;
    }
    if (this.statusCode === 429) {
      return `Rate limit exceeded (${this.errorCode}): ${this.message}. Slow down and retry.`;
    }
    return `API error ${this.statusCode} (${this.errorCode}): ${this.message}`;
  }
}

/** Extract the actionable reason from structured API and FastAPI detail bodies. */
function detailReason(detail: unknown): string | undefined {
  if (typeof detail === "string") {
    return detail.trim() || undefined;
  }
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) {
    return undefined;
  }

  const values = detail as Record<string, unknown>;
  for (const field of ["reason", "message", "error", "msg"]) {
    const value = values[field];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return undefined;
}

/** Shape of Hebbian API error response bodies. */
interface ApiErrorBody {
  error?: string;
  code?: string;
  message?: string;
  detail?: unknown;
}

export class HebbianClient {
  private readonly apiUrl: string;
  private readonly token: string;
  private readonly tenant?: string;
  /** Whether graph-derived tools should request UUID-keyset paginated graphs. */
  public readonly graphPagination: boolean;

  constructor(apiUrl: string, token: string, tenant?: string, graphPagination = false) {
    // Normalise: strip trailing slash
    this.apiUrl = apiUrl.replace(/\/+$/, "");
    this.token = token;
    this.tenant = tenant && tenant.trim().length > 0 ? tenant.trim() : undefined;
    this.graphPagination = graphPagination;
  }

  /**
   * Execute a GET request against the Hebbian API.
   * @param path Path relative to apiUrl (must start with "/")
   * @param query Optional query parameters
   */
  async get(
    path: string,
    query?: Record<string, string | number | boolean | undefined>,
  ): Promise<unknown> {
    const url = this.buildUrl(path, query);
    const response = await fetch(url.toString(), {
      method: "GET",
      headers: this.headers(),
    });
    return this.handleResponse(response);
  }

  /**
   * Execute a POST request against the Hebbian API.
   * @param path Path relative to apiUrl (must start with "/")
   * @param body Request body (serialised to JSON)
   */
  async post(
    path: string,
    body: Record<string, unknown>,
  ): Promise<unknown> {
    const url = this.buildUrl(path);
    const response = await fetch(url.toString(), {
      method: "POST",
      headers: {
        ...this.headers(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    return this.handleResponse(response);
  }

  /** Build an absolute URL from path + optional query params. */
  private headers(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.token}`,
      "User-Agent": `@hebbianvault/mcp/${PACKAGE_VERSION}`,
      Accept: "application/json",
      ...(this.tenant && { "X-Hebbian-Tenant": this.tenant }),
    };
  }

  private buildUrl(
    path: string,
    query?: Record<string, string | number | boolean | undefined>,
  ): URL {
    const url = new URL(`${this.apiUrl}${path}`);
    if (query) {
      for (const [k, v] of Object.entries(query)) {
        if (v !== undefined) {
          url.searchParams.set(k, String(v));
        }
      }
    }
    return url;
  }

  /**
   * Parse and validate a fetch response.
   * Throws HebbianApiError on non-2xx status codes.
   */
  private async handleResponse(
    response: Response,
  ): Promise<unknown> {
    if (response.ok) {
      const data: unknown = await response.json();
      return data;
    }

    // Parse error body for structured error info
    let errBody: ApiErrorBody = {};
    try {
      errBody = (await response.json()) as ApiErrorBody;
    } catch {
      // Error body couldn't be parsed — use raw text
      const rawText = await response.text().catch(() => "");
      errBody = { message: rawText || response.statusText };
    }

    const errorCode =
      errBody.code ?? errBody.error ?? `HTTP_${response.status}`;
    const message =
      detailReason(errBody.detail) ||
      errBody.message ||
      errBody.error ||
      `Request failed with status ${response.status}`;

    throw new HebbianApiError(
      response.status,
      errorCode,
      message,
      errBody.detail,
    );
  }
}
