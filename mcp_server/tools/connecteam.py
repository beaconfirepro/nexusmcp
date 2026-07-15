"""
Connecteam MCP tools.
Auth: X-API-KEY header. https://developer.connecteam.com/docs/authentication-1
Base URL: https://api.connecteam.com
Pagination: limit/offset.
"""
from pydantic import Field

from src.clients import get_client, resolve_account
from src.mcp_instance import DESTRUCTIVE, IDEMPOTENT, RO, WRITE, mcp
from src.models import BaseToolInput, DryRunInput


# ── Account / verify ──

class ConnecteamGetMeInput(BaseToolInput):
    pass


@mcp.tool(annotations=RO, description="Get the current Connecteam account info (verify API key).")
async def connecteam_get_me(input: ConnecteamGetMeInput) -> str:
    client = get_client("connecteam")
    result = await client.get_me()
    return client.format(result, input.response_format)


# ── Users ──

class ConnecteamListUsersInput(BaseToolInput):
    limit: int = Field(default=50, ge=1, le=200, description="Max results per page.", examples=[50])
    offset: int = Field(default=0, ge=0, description="Offset for pagination.", examples=[0])


@mcp.tool(annotations=RO, description="List Connecteam users with pagination.")
async def connecteam_list_users(input: ConnecteamListUsersInput) -> str:
    client = get_client("connecteam")
    result = await client.list_users(limit=input.limit, offset=input.offset)
    return client.format(result, input.response_format)


class ConnecteamGetUserInput(BaseToolInput):
    user_id: str = Field(description="Connecteam user ID.", examples=["12345"])


@mcp.tool(annotations=RO, description="Get a single Connecteam user by ID.")
async def connecteam_get_user(input: ConnecteamGetUserInput) -> str:
    client = get_client("connecteam")
    result = await client.get_user(input.user_id)
    return client.format(result, input.response_format)


class ConnecteamCreateUserInput(BaseToolInput, DryRunInput):
    user_data: dict = Field(description="User object per Connecteam API schema.", examples=[{
        "first_name": "Jane", "last_name": "Doe", "email": "jane@example.com",
    }])


@mcp.tool(annotations=WRITE, description="Create a Connecteam user. Use dry_run=true to validate without creating.")
async def connecteam_create_user(input: ConnecteamCreateUserInput) -> str:
    client = get_client("connecteam")
    if input.dry_run:
        return f"[DRY RUN] Would create user: {input.user_data}"
    result = await client.create_user(input.user_data)
    return client.format(result, input.response_format)


class ConnecteamUpdateUserInput(BaseToolInput, DryRunInput):
    user_id: str = Field(description="User ID to update.", examples=["12345"])
    user_data: dict = Field(description="Fields to update.", examples=[{"first_name": "Jane Updated"}])


@mcp.tool(annotations=IDEMPOTENT, description="Update a Connecteam user. Use dry_run=true to validate.")
async def connecteam_update_user(input: ConnecteamUpdateUserInput) -> str:
    client = get_client("connecteam")
    if input.dry_run:
        return f"[DRY RUN] Would update user {input.user_id}: {input.user_data}"
    result = await client.update_user(input.user_id, input.user_data)
    return client.format(result, input.response_format)


class ConnecteamDeleteUserInput(BaseToolInput, DryRunInput):
    user_id: str = Field(description="User ID to delete.", examples=["12345"])
    confirm: bool = Field(default=False, description="Must be true to execute the deletion.")


@mcp.tool(annotations=DESTRUCTIVE, description="Delete a Connecteam user. Requires confirm=true. DESTRUCTIVE.")
async def connecteam_delete_user(input: ConnecteamDeleteUserInput) -> str:
    if not input.confirm:
        return "Deletion requires confirm=true. Re-run with confirm=true to proceed."
    client = get_client("connecteam")
    result = await client.delete_user(input.user_id)
    return client.format(result, input.response_format)


# ── Scheduler / shifts ──

class ConnecteamListShiftsInput(BaseToolInput):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


@mcp.tool(annotations=RO, description="List scheduler shifts.")
async def connecteam_list_shifts(input: ConnecteamListShiftsInput) -> str:
    client = get_client("connecteam")
    result = await client.list_shifts(limit=input.limit, offset=input.offset)
    return client.format(result, input.response_format)


class ConnecteamCreateShiftInput(BaseToolInput, DryRunInput):
    shift_data: dict = Field(description="Shift object per Connecteam API.", examples=[{
        "user_id": "12345", "start_time": "2025-01-15T09:00:00Z", "end_time": "2025-01-15T17:00:00Z",
    }])


@mcp.tool(annotations=WRITE, description="Create a scheduler shift.")
async def connecteam_create_shift(input: ConnecteamCreateShiftInput) -> str:
    client = get_client("connecteam")
    if input.dry_run:
        return f"[DRY RUN] Would create shift: {input.shift_data}"
    result = await client.create_shift(input.shift_data)
    return client.format(result, input.response_format)


# ── Time clock ──

class ConnecteamListTimeClockInput(BaseToolInput):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


@mcp.tool(annotations=RO, description="List time clock entries.")
async def connecteam_list_time_clock(input: ConnecteamListTimeClockInput) -> str:
    client = get_client("connecteam")
    result = await client.list_time_clock_entries(limit=input.limit, offset=input.offset)
    return client.format(result, input.response_format)


# ── Jobs, forms, tasks ──

class ConnecteamListJobsInput(BaseToolInput):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


@mcp.tool(annotations=RO, description="List jobs.")
async def connecteam_list_jobs(input: ConnecteamListJobsInput) -> str:
    client = get_client("connecteam")
    result = await client.list_jobs(limit=input.limit, offset=input.offset)
    return client.format(result, input.response_format)


class ConnecteamListFormsInput(BaseToolInput):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


@mcp.tool(annotations=RO, description="List forms.")
async def connecteam_list_forms(input: ConnecteamListFormsInput) -> str:
    client = get_client("connecteam")
    result = await client.list_forms(limit=input.limit, offset=input.offset)
    return client.format(result, input.response_format)


class ConnecteamListTasksInput(BaseToolInput):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


@mcp.tool(annotations=RO, description="List tasks.")
async def connecteam_list_tasks(input: ConnecteamListTasksInput) -> str:
    client = get_client("connecteam")
    result = await client.list_tasks(limit=input.limit, offset=input.offset)
    return client.format(result, input.response_format)


# ── Escape-hatch ──

class ConnecteamRequestInput(BaseToolInput):
    method: str = Field(description="HTTP method.", examples=["GET", "POST", "PUT", "DELETE"])
    path: str = Field(description="API path (starts with /).", examples=["/users/12345"])
    query: dict | None = Field(default=None, description="Query parameters.")
    body: dict | None = Field(default=None, description="Request body (JSON).")


@mcp.tool(annotations=WRITE,
          description="Call ANY Connecteam API endpoint. Escape-hatch for full API coverage.")
async def connecteam_request(input: ConnecteamRequestInput) -> str:
    client = get_client("connecteam")
    result = await client.generic_request(input.method, input.path, query=input.query, body=input.body)
    return client.format(result, input.response_format)