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
    instance_ids: list | None = Field(
        default=None,
        description="Filter by scheduler / time-clock instance IDs.",
        examples=[[14341327, 15711684]],
    )
    job_ids: list | None = Field(default=None, description="Filter by job IDs.")
    job_names: list | None = Field(default=None, description="Filter by job names.")
    job_codes: list | None = Field(
        default=None,
        description="Filter by job codes (Beacon numbers).",
        examples=[["BFP24-00100"]],
    )
    include_deleted: bool = Field(
        default=True,
        description="Include deleted jobs (Connecteam's API default is true). "
                    "Pass false to return active jobs only.",
    )
    sort: str | None = Field(default=None, description="Sort field. Allowed: 'title'.", examples=["title"])
    order: str = Field(default="asc", description="Sort order: 'asc' or 'desc'.", examples=["asc", "desc"])
    limit: int = Field(default=50, ge=1, le=500, description="Max results per page (1-500).", examples=[50])
    offset: int = Field(default=0, ge=0, description="Offset for pagination.", examples=[0])


@mcp.tool(annotations=RO,
          description="List Connecteam jobs (GET /jobs/v1/jobs). Filter by instance IDs, "
                      "job IDs / names / codes; supports include_deleted, sort, and pagination.")
async def connecteam_list_jobs(input: ConnecteamListJobsInput) -> str:
    client = get_client("connecteam")
    params: dict = {
        "includeDeleted": input.include_deleted,
        "order": input.order,
        "limit": input.limit,
        "offset": input.offset,
    }
    if input.instance_ids is not None:
        params["instanceIds"] = input.instance_ids
    if input.job_ids is not None:
        params["jobIds"] = input.job_ids
    if input.job_names is not None:
        params["jobNames"] = input.job_names
    if input.job_codes is not None:
        params["jobCodes"] = input.job_codes
    if input.sort is not None:
        params["sort"] = input.sort
    result = await client.list_jobs(params)
    return client.format(result, input.response_format)


class ConnecteamListJobCustomFieldsInput(BaseToolInput):
    custom_field_ids: list | None = Field(default=None, description="Filter by custom field IDs.")
    category_ids: list | None = Field(default=None, description="Filter by category IDs.")
    custom_field_types: list | None = Field(default=None, description="Filter by field types.")
    custom_field_names: list | None = Field(default=None, description="Filter by field names.")
    sort: str | None = Field(default=None, description="Sort field. Allowed: 'name', 'type'.")
    order: str = Field(default="asc", description="Sort order: 'asc' or 'desc'.", examples=["asc", "desc"])
    limit: int = Field(default=50, ge=1, le=500, description="Max results per page (1-500).", examples=[50])
    offset: int = Field(default=0, ge=0, description="Offset for pagination.", examples=[0])


@mcp.tool(annotations=RO,
          description="List Connecteam job resource custom fields (GET /jobs/v1/custom-fields).")
async def connecteam_list_job_custom_fields(input: ConnecteamListJobCustomFieldsInput) -> str:
    client = get_client("connecteam")
    params: dict = {"order": input.order, "limit": input.limit, "offset": input.offset}
    if input.custom_field_ids is not None:
        params["customFieldIds"] = input.custom_field_ids
    if input.category_ids is not None:
        params["categoryIds"] = input.category_ids
    if input.custom_field_types is not None:
        params["customFieldTypes"] = input.custom_field_types
    if input.custom_field_names is not None:
        params["customFieldNames"] = input.custom_field_names
    if input.sort is not None:
        params["sort"] = input.sort
    result = await client.list_job_custom_fields(params)
    return client.format(result, input.response_format)


class ConnecteamCreateJobsInput(BaseToolInput, DryRunInput):
    jobs: list = Field(
        description="List of job objects to create. POST /jobs/v1/jobs takes a top-level array; "
                    "each element is a job (or sub-job) object. A parent job requires instanceIds "
                    "(scheduler / time-clock IDs), title, and assign {type, userIds, groupIds}; optional "
                    "code, description, color, gps {address, longitude, latitude}, customFields, and "
                    "subJobs. Sub-jobs with useParentData=true inherit the parent's settings.",
        examples=[[{
            "instanceIds": [14341327, 15711684],
            "title": "1400 Cedar Ave Townhomes",
            "code": "BFP24-00072",
            "description": "Client: Zach Savage Custom Homes\nSystem Type: 13D SF",
            "assign": {"type": "both", "userIds": [], "groupIds": [10820945]},
            "subJobs": [
                {"title": "1: Sales", "useParentData": True},
                {"title": "2: Planning", "useParentData": True},
            ],
        }]],
    )


@mcp.tool(annotations=WRITE,
          description="Create one or more Connecteam jobs (POST /jobs/v1/jobs). The body is a "
                      "top-level array of job objects. Use dry_run=true to validate without creating.")
async def connecteam_create_jobs(input: ConnecteamCreateJobsInput) -> str:
    client = get_client("connecteam")
    if input.dry_run:
        return f"[DRY RUN] Would create {len(input.jobs)} job(s): {input.jobs}"
    result = await client.create_jobs(input.jobs)
    return client.format(result, input.response_format)


class ConnecteamUpdateJobInput(BaseToolInput, DryRunInput):
    job_id: str = Field(description="The jobId to update (path parameter).",
                        examples=["a3efa69b-e17d-4b46-9ac9-3f27e686a36c"])
    job_data: dict = Field(
        description="Fields to update on the job (PUT /jobs/v1/jobs/{jobId}, a single object). "
                    "Updatable: title, code, description, color, gps, assign, customFields, "
                    "instanceIds, useParentData. Updating a job that has nested sub-jobs is not "
                    "supported by Connecteam.",
        examples=[{"description": "Client: Zach Savage Custom Homes\nSystem Type: 13D SF"}],
    )


@mcp.tool(annotations=IDEMPOTENT,
          description="Update a single Connecteam job by jobId (PUT /jobs/v1/jobs/{jobId}). "
                      "Use dry_run=true to validate without writing.")
async def connecteam_update_job(input: ConnecteamUpdateJobInput) -> str:
    client = get_client("connecteam")
    if input.dry_run:
        return f"[DRY RUN] Would update job {input.job_id}: {input.job_data}"
    result = await client.update_job(input.job_id, input.job_data)
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
    body: dict | list | None = Field(
        default=None,
        description="Request body (JSON). Accepts a JSON object or a top-level JSON array; some "
                    "Connecteam endpoints require an array body.",
    )


@mcp.tool(annotations=WRITE,
          description="Call ANY Connecteam API endpoint. Escape-hatch for full API coverage.")
async def connecteam_request(input: ConnecteamRequestInput) -> str:
    client = get_client("connecteam")
    result = await client.generic_request(input.method, input.path, query=input.query, body=input.body)
    return client.format(result, input.response_format)