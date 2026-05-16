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

logger = logging.getLogger(__name__)

USER_AGENT = "hebbianvault-mcp/0.1.0 (Python)"


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
        if self.status_code == 401:
            return (
                f"Authentication failed ({self.error_code}): {self}. "
                "Your token may be expired or revoked. "
                "Generate a new token from the AI Tools tab in your Hebbian integrations page."
            )
        if self.status_code == 403:
            return (
                f"Permission denied ({self.error_code}): {self}. "
                "Check that your token scope (employee/company) matches the operation."
            )
        if self.status_code == 404:
            return f"Not found ({self.error_code}): {self}"
        if self.status_code == 429:
            return f"Rate limit exceeded ({self.error_code}): {self}. Slow down and retry."
        return f"API error {self.status_code} ({self.error_code}): {self}"


class HebbianClient:
    """Thin async HTTP client for the Hebbian API."""

    def __init__(self, api_url: str, token: str) -> None:
        # Normalise: strip trailing slash
        self._api_url = api_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

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
            message = body.get("message") or body.get("error") or message
            detail = body.get("detail")
        except Exception:  # noqa: BLE001
            message = response.text or message

        raise HebbianApiError(
            status_code=response.status_code,
            error_code=error_code,
            message=message,
            detail=detail,
        )
