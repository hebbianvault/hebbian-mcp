"""
hebbianvault_mcp.client — HTTPS client for the Hebbian API.

- Adds Authorization: Bearer header to every request.
- Surfaces API errors as HebbianApiError with status_code + error_code + message.
- No business logic — thin transport wrapper over httpx.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from . import __version__

logger = logging.getLogger(__name__)

USER_AGENT = f"hebbianvault-mcp/{__version__} (Python)"


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

    def __init__(self, api_url: str, token: str, tenant: str | None = None) -> None:
        # Normalise: strip trailing slash
        self._api_url = api_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        # Only sent when the account belongs to more than one workspace; the API
        # resolves the single-membership case from the token alone.
        if tenant and tenant.strip():
            self._headers["X-Hebbian-Tenant"] = tenant.strip()

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a GET request and return parsed JSON."""
        url = f"{self._api_url}{path}"
        async with httpx.AsyncClient() as http:
            response = await http.get(url, headers=self._headers, params=params)
        return await self._handle_response(response)

    async def post(self, path: str, body: dict[str, Any]) -> Any:
        """Execute a POST request and return parsed JSON."""
        url = f"{self._api_url}{path}"
        async with httpx.AsyncClient() as http:
            response = await http.post(
                url,
                headers={**self._headers, "Content-Type": "application/json"},
                content=json.dumps(body).encode(),
            )
        return await self._handle_response(response)

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
