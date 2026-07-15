"""
Base provider client — shared HTTP infrastructure for all providers.
Provides:
  - async httpx client
  - rate-limit handling (429 → exponential backoff with jitter)
  - error formatting (actionable, never leaks secrets)
  - response formatting (json | markdown)
"""
import asyncio
import json
import logging
import random

import httpx

from src.errors import ProviderError, RateLimitError, format_response

logger = logging.getLogger("mcp_server.providers.base")

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 30.0


class BaseProviderClient:
    """Base for all provider clients. Handles HTTP, retries, errors."""

    def __init__(self, provider: str, base_url: str):
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=30.0)

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict | None = None,
        params: dict | None = None,
        json_body: dict | None = None,
        content: bytes | None = None,
        full_url: str | None = None,
    ) -> dict | list | str:
        """
        Execute an HTTP request with rate-limit retry logic.
        Returns parsed JSON (dict/list) or raw text.
        Raises ProviderError on failure with actionable messages.
        """
        url = full_url or f"{self.base_url}/{path.lstrip('/')}"
        req_headers = headers or {}
        backoff = INITIAL_BACKOFF

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._http.request(
                    method, url,
                    headers=req_headers,
                    params=params,
                    json=json_body,
                    content=content,
                )
            except httpx.HTTPError as exc:
                raise ProviderError(
                    f"Network error calling {self.provider}: {exc}",
                    provider=self.provider,
                )

            # 429 → exponential backoff with jitter
            if resp.status_code == 429:
                if attempt < MAX_RETRIES:
                    retry_after = int(resp.headers.get("Retry-After", backoff))
                    wait = min(retry_after, MAX_BACKOFF) + random.uniform(0, 0.5)
                    logger.warning(
                        "Rate limited by %s (429). Retrying in %.1fs (attempt %d/%d)",
                        self.provider, wait, attempt + 1, MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    continue
                raise RateLimitError(self.provider, retry_after=int(resp.headers.get("Retry-After", 0)))

            # 5xx → retry with backoff
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                wait = backoff + random.uniform(0, 0.5)
                logger.warning(
                    "Server error from %s (%d). Retrying in %.1fs",
                    self.provider, resp.status_code, wait,
                )
                await asyncio.sleep(wait)
                backoff = min(backoff * 2, MAX_BACKOFF)
                continue

            # 401 → auth expired (caller should handle token refresh)
            if resp.status_code == 401:
                raise ProviderError(
                    f"Authentication failed for {self.provider} (401). "
                    f"The OAuth token may have expired.",
                    provider=self.provider,
                    status_code=401,
                    hint="The OAuth refresh helper should retry. If this persists, "
                         "re-run scripts/seed_oauth.py to obtain a new refresh token.",
                )

            # 403 → wrong scope
            if resp.status_code == 403:
                body = self._safe_body(resp)
                raise ProviderError(
                    f"Permission denied by {self.provider} (403). "
                    f"The OAuth token may lack required scopes.",
                    provider=self.provider,
                    status_code=403,
                    hint=f"Response: {body[:200]}. Check that the delegated scopes include "
                         f"the required permissions. Re-authenticate if needed.",
                )

            # Other errors
            if resp.status_code >= 400:
                body = self._safe_body(resp)
                raise ProviderError(
                    f"{self.provider} API error (HTTP {resp.status_code}): {body[:500]}",
                    provider=self.provider,
                    status_code=resp.status_code,
                )

            # Success
            return self._parse_response(resp)

        # Should not reach here
        raise ProviderError(f"Exhausted retries for {self.provider}", provider=self.provider)

    @staticmethod
    def _safe_body(resp: httpx.Response) -> str:
        """Get response body as text, never raising."""
        try:
            return resp.text
        except Exception:
            return "(unable to read response body)"

    @staticmethod
    def _parse_response(resp: httpx.Response) -> dict | list | str:
        """Parse JSON or return text."""
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError):
            return resp.text

    @staticmethod
    def format(data, response_format: str = "markdown") -> str:
        """Format provider response as JSON string or markdown."""
        return format_response(data, response_format)

    async def close(self):
        await self._http.aclose()