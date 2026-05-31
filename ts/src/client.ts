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
    if (this.statusCode === 401) {
      return (
        `Authentication failed (${this.errorCode}): ${this.message}. ` +
        "Your token may be expired or revoked. " +
        "Generate a new token from the AI Tools tab in your Hebbian integrations page."
      );
    }
    if (this.statusCode === 403) {
      return (
        `Permission denied (${this.errorCode}): ${this.message}. ` +
        "Check that your token scope (employee/company) matches the operation."
      );
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

  constructor(apiUrl: string, token: string, tenant?: string) {
    // Normalise: strip trailing slash
    this.apiUrl = apiUrl.replace(/\/+$/, "");
    this.token = token;
    this.tenant = tenant && tenant.trim().length > 0 ? tenant.trim() : undefined;
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

  /** Standard request headers including bearer auth. */
  private headers(): Record<string, string> {
    const h: Record<string, string> = {
      Authorization: `Bearer ${this.token}`,
      Accept: "application/json",
      "User-Agent": "@hebbianvault/mcp/0.2.0",
    };
    // Only sent when the caller's account belongs to more than one workspace.
    // The API resolves the single-membership case from the token alone.
    if (this.tenant) {
      h["X-Hebbian-Tenant"] = this.tenant;
    }
    return h;
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
      errBody.message ??
      errBody.error ??
      `Request failed with status ${response.status}`;

    throw new HebbianApiError(
      response.status,
      errorCode,
      message,
      errBody.detail,
    );
  }
}
