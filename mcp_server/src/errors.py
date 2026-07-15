"""
Shared error types and formatter. Every provider error is converted
to an actionable MCP-friendly message. Secrets and stack traces are
NEVER included in error responses or logs.
"""
import json
import logging

logger = logging.getLogger("mcp_server")

# All logging goes to stderr only — never stdout (MCP uses stdout for protocol).
logging.basicConfig(
    stream=__import__("sys").stderr,
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
)


class ProviderError(Exception):
    """Base error for all provider failures. Always carries an actionable message."""

    def __init__(self, message: str, *, provider: str = "", status_code: int = 0, hint: str = ""):
        self.provider = provider
        self.status_code = status_code
        self.hint = hint
        super().__init__(message)

    def to_message(self) -> str:
        parts = [self.args[0]]
        if self.provider:
            parts.append(f"[provider: {self.provider}]")
        if self.status_code:
            parts.append(f"[status: {self.status_code}]")
        if self.hint:
            parts.append(f"→ {self.hint}")
        return " ".join(parts)


class UnknownAliasError(ProviderError):
    """Raised when an account alias is not found in the registry."""

    def __init__(self, alias: str, provider: str, valid_aliases: list[str]):
        valid = ", ".join(valid_aliases) if valid_aliases else "(none registered)"
        super().__init__(
            f"Unknown account alias '{alias}' for provider '{provider}'. "
            f"Valid aliases: {valid}.",
            provider=provider,
            hint="Pass one of the listed aliases, or register a new one via the account registry.",
        )


class AuthExpiredError(ProviderError):
    """Raised when OAuth refresh fails and re-authentication is required."""

    def __init__(self, provider: str, alias: str, detail: str = ""):
        super().__init__(
            f"OAuth credentials for {provider}:{alias} have expired and cannot be refreshed. {detail}",
            provider=provider,
            hint="Re-run scripts/seed_oauth.py to obtain a new refresh token for this provider.",
        )


class RateLimitError(ProviderError):
    """Raised when a provider returns 429 and retries are exhausted."""

    def __init__(self, provider: str, retry_after: int = 0):
        hint = f"Retry after {retry_after}s." if retry_after else "Retry later."
        super().__init__(
            f"Rate limit exceeded for {provider}. {hint}",
            provider=provider,
            status_code=429,
            hint=hint,
        )


class ScopeError(ProviderError):
    """Raised when the OAuth token lacks a required scope."""

    def __init__(self, provider: str, required_scope: str):
        super().__init__(
            f"The {provider} OAuth token lacks scope '{required_scope}'.",
            provider=provider,
            hint=f"Re-authenticate via scripts/seed_oauth.py and grant scope '{required_scope}'.",
        )


class DryRunError(ProviderError):
    """Raised when dry_run is requested — not an error, signals no mutation was performed."""


def format_response(data, response_format: str = "markdown") -> str:
    """Format provider response as JSON string or markdown."""
    if response_format == "json":
        return json.dumps(data, indent=2, default=str, ensure_ascii=False)
    # Markdown
    if isinstance(data, dict):
        lines = []
        for key, val in data.items():
            if isinstance(val, (dict, list)):
                lines.append(f"### {key}\n```json\n{json.dumps(val, indent=2, default=str, ensure_ascii=False)}\n```")
            else:
                lines.append(f"**{key}:** {val}")
        return "\n\n".join(lines) if lines else "_empty response_"
    if isinstance(data, list):
        return f"```json\n{json.dumps(data, indent=2, default=str, ensure_ascii=False)}\n```"
    return str(data)


def paginate_response(items: list, limit: int, offset: int, total: int | None = None) -> dict:
    """Wrap a list of items with pagination metadata."""
    has_more = (total is not None and offset + len(items) < total) or (len(items) == limit and total is None)
    return {
        "items": items,
        "count": len(items),
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "total_count": total,
    }