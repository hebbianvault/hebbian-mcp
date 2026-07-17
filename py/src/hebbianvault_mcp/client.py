"""
hebbianvault_mcp.client — HTTPS client for the Hebbian API.

- Adds Authorization: Bearer header to every request.
- Surfaces API errors as HebbianApiError with status_code + error_code + message.
- No business logic — thin transport wrapper over httpx.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx

from . import __version__

logger = logging.getLogger(__name__)

USER_AGENT = f"hebbianvault-mcp/{__version__} (Python)"
DEFAULT_TIMEOUT_MS = 30_000


class HebbianApiError(Exception):
    """Structured API error returned by the Hebbian API."""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail

    def to_tool_error(self) -> str:
        """Human-readable string for MCP tool error responses."""
        server_reason = _detail_reason(self.detail)
        if self.status_code == 401:
            tool_error = f"Authentication failed ({self.error_code}): {server_reason or self}."
            if server_reason:
                return tool_error
            return (
                f"{tool_error} Your token may be expired or revoked. "
                "Generate a new token from the AI Tools tab in your Hebbian integrations page."
            )
        if self.status_code == 403:
            tool_error = f"Permission denied ({self.error_code}): {server_reason or self}."
            if server_reason:
                return tool_error
            return (
                f"{tool_error} Check that your token scope "
                "(employee/company) matches the operation."
            )
        if self.status_code == 404:
            return f"Not found ({self.error_code}): {self}"
        if self.status_code == 429:
            return f"Rate limit exceeded ({self.error_code}): {self}. Slow down and retry."
        return f"API error {self.status_code} ({self.error_code}): {self}"


class HebbianTimeoutError(HebbianApiError):
    """Raised when an API request exceeds the configured client-side deadline."""

    def __init__(self, timeout_ms: int) -> None:
        super().__init__(408, "request_timeout", f"Request timed out after {timeout_ms}ms.")
        self.timeout_ms = timeout_ms

    def to_tool_error(self) -> str:
        return (
            f"Request timed out after {self.timeout_ms}ms. "
            "Set HEBBIAN_TIMEOUT_MS to a larger value if needed."
        )


def _detail_reason(detail: Any) -> str | None:
    """Extract an actionable reason from structured API and FastAPI detail bodies."""
    if isinstance(detail, str):
        return detail.strip() or None
    if not isinstance(detail, dict):
        return None

    for field in ("reason", "message", "error", "msg"):
        value = detail.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class HebbianClient:
    """Thin async HTTP client for the Hebbian API."""

    def __init__(
        self,
        api_url: str,
        token: str,
        tenant: str | None = None,
        graph_pagination: bool = False,
    ) -> None:
        # Normalise: strip trailing slash
        self._api_url = api_url.rstrip("/")
        self._timeout_ms = _timeout_ms_from_env()
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        # Only sent when the account belongs to more than one workspace; the API
        # resolves the single-membership case from the token alone.
        if tenant and tenant.strip():
            self._headers["X-Hebbian-Tenant"] = tenant.strip()
        self.graph_pagination = graph_pagination
        # Set lazily by graph-backed MCP tools after their advisory whoami probe.
        # Keeping this on the client scopes the result to the configured token.
        self._graph_token_scope: str | None = None
        self._graph_token_scope_resolved = False
        self._graph_token_scope_resolution_task: asyncio.Task[None] | None = None
        self._graph_cache_task: asyncio.Task[list[dict[str, Any]]] | None = None
        self._graph_cache_expires_at = 0.0

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a GET request and return parsed JSON."""
        url = f"{self._api_url}{path}"
        return await self._request("GET", url, params=params)

    async def post(self, path: str, body: dict[str, Any]) -> Any:
        """Execute a POST request and return parsed JSON."""
        url = f"{self._api_url}{path}"
        return await self._request(
            "POST",
            url,
            content=json.dumps(body).encode(),
            headers={**self._headers, "Content-Type": "application/json"},
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Make a timed request, retrying only GET network and 5xx failures once."""
        max_attempts = 2 if method == "GET" else 1
        headers = kwargs.pop("headers", self._headers)
        for attempt in range(max_attempts):
            try:
                timeout_seconds = self._timeout_ms / 1000
                # HTTPX applies its single-value timeout to every I/O phase. The
                # enclosing deadline covers the whole request, including a
                # slow-drip body, to match the TypeScript client's timeout.
                async with asyncio.timeout(timeout_seconds):
                    async with httpx.AsyncClient(
                        timeout=httpx.Timeout(timeout=timeout_seconds)
                    ) as http:
                        response = await http.request(
                            method,
                            url,
                            headers=headers,
                            **kwargs,
                        )
            except (TimeoutError, httpx.TimeoutException) as exc:
                if attempt + 1 < max_attempts:
                    continue
                raise HebbianTimeoutError(self._timeout_ms) from exc
            except httpx.RequestError:
                if attempt + 1 < max_attempts:
                    continue
                raise

            if response.status_code >= 500 and attempt + 1 < max_attempts:
                continue
            return await self._handle_response(response)

        raise RuntimeError("Request retry loop exited unexpectedly")

    @staticmethod
    async def _handle_response(response: httpx.Response) -> Any:
        """Parse and validate a response. Raises HebbianApiError on non-2xx."""
        if response.is_success:
            return response.json()

        # Try to parse structured error body
        error_code = f"HTTP_{response.status_code}"
        message = response.reason_phrase or f"Status {response.status_code}"
        detail = None
        try:
            body = response.json()
            error_code = body.get("code") or body.get("error") or error_code
            detail = body.get("detail")
            message = _detail_reason(detail) or body.get("message") or body.get("error") or message
        except Exception:  # noqa: BLE001
            message = response.text or message

        raise HebbianApiError(
            status_code=response.status_code,
            error_code=error_code,
            message=message,
            detail=detail,
        )


def _timeout_ms_from_env() -> int:
    """Read a positive millisecond timeout, falling back to the safe default."""
    value = os.environ.get("HEBBIAN_TIMEOUT_MS", "").strip()
    if not value.isdigit():
        return DEFAULT_TIMEOUT_MS
    timeout_ms = int(value)
    return timeout_ms if 0 < timeout_ms <= 9_007_199_254_740_991 else DEFAULT_TIMEOUT_MS
