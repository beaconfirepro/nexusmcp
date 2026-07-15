"""
Shared Pydantic v2 base models for all MCP tool inputs.
Every tool input model inherits BaseToolInput (account + response_format)
and uses extra='forbid', strict=True for validated, fail-fast inputs.
"""
from pydantic import BaseModel, ConfigDict, Field


class BaseToolInput(BaseModel):
    """Base for all tool inputs. Provides account alias + response format."""
    model_config = ConfigDict(extra="forbid", strict=True)

    account: str | None = Field(
        default=None,
        description="Account alias to use (e.g. 'qbo:main'). "
                    "If omitted, defaults to the provider's single registered login.",
        examples=["qbo:main", "microsoft:main"],
    )
    response_format: str = Field(
        default="markdown",
        description="Response format: 'json' (raw JSON string) or 'markdown' (human-readable).",
        examples=["json", "markdown"],
    )


class DryRunInput(BaseModel):
    """Mixin for write/destructive tools that support dry_run."""
    dry_run: bool = Field(
        default=False,
        description="If true, validate the request but do NOT execute the write. "
                    "Returns what would have been done.",
        examples=[True],
    )