"""
HubSpot MCP tools.
Private-app access token (bearer). https://developers.hubspot.com/docs/api/private-apps
CRM v3: /crm/v3/objects/{objectType}
The typed tools accept `object_type` as a parameter, covering ALL HubSpot
CRM objects (contacts, companies, deals, tickets, products, line_items,
custom objects) without one tool per type.
"""
from pydantic import Field

from src.clients import get_client
from src.mcp_instance import DESTRUCTIVE, IDEMPOTENT, RO, WRITE, mcp
from src.models import BaseToolInput, DryRunInput


# ── List objects ──

class HubspotListObjectsInput(BaseToolInput):
    object_type: str = Field(
        description="Object type (contacts, companies, deals, tickets, products, line_items, or custom object type).",
        examples=["contacts"],
    )
    limit: int = Field(default=50, ge=1, le=100, description="Max results per page.")
    after: str | None = Field(default=None, description="Pagination cursor (from previous response).")
    properties: list[str] | None = Field(default=None, description="Properties to include.",
                                         examples=[["firstname", "lastname", "email"]])


@mcp.tool(annotations=RO, description="List HubSpot CRM objects with pagination.")
async def hubspot_list_objects(input: HubspotListObjectsInput) -> str:
    client = get_client("hubspot")
    result = await client.list_objects(input.object_type, limit=input.limit,
                                       after=input.after, properties=input.properties)
    return client.format(result, input.response_format)


# ── Get object ──

class HubspotGetObjectInput(BaseToolInput):
    object_type: str = Field(description="Object type.", examples=["contacts"])
    object_id: str = Field(description="Object ID.", examples=["123456"])
    properties: list[str] | None = Field(default=None, description="Properties to include.")


@mcp.tool(annotations=RO, description="Get a single HubSpot CRM object by ID.")
async def hubspot_get_object(input: HubspotGetObjectInput) -> str:
    client = get_client("hubspot")
    result = await client.get_object(input.object_type, input.object_id, input.properties)
    return client.format(result, input.response_format)


# ── Create object ──

class HubspotCreateObjectInput(BaseToolInput, DryRunInput):
    object_type: str = Field(description="Object type.", examples=["contacts"])
    properties: dict = Field(description="Object properties.", examples=[{
        "firstname": "Jane", "lastname": "Doe", "email": "jane@example.com",
    }])
    associations: list[dict] | None = Field(default=None, description="Associations to create.")


@mcp.tool(annotations=WRITE,
          description="Create a HubSpot CRM object. Use dry_run=true to validate without creating.")
async def hubspot_create_object(input: HubspotCreateObjectInput) -> str:
    client = get_client("hubspot")
    if input.dry_run:
        return f"[DRY RUN] Would create {input.object_type}: {input.properties}"
    result = await client.create_object(input.object_type, input.properties, input.associations)
    return client.format(result, input.response_format)


# ── Update object ──

class HubspotUpdateObjectInput(BaseToolInput, DryRunInput):
    object_type: str = Field(description="Object type.", examples=["contacts"])
    object_id: str = Field(description="Object ID.", examples=["123456"])
    properties: dict = Field(description="Properties to update.", examples=[{"firstname": "Updated"}])


@mcp.tool(annotations=IDEMPOTENT, description="Update a HubSpot CRM object. Use dry_run=true to validate.")
async def hubspot_update_object(input: HubspotUpdateObjectInput) -> str:
    client = get_client("hubspot")
    if input.dry_run:
        return f"[DRY RUN] Would update {input.object_type}/{input.object_id}: {input.properties}"
    result = await client.update_object(input.object_type, input.object_id, input.properties)
    return client.format(result, input.response_format)


# ── Archive (delete) object ──

class HubspotArchiveObjectInput(BaseToolInput, DryRunInput):
    object_type: str = Field(description="Object type.", examples=["contacts"])
    object_id: str = Field(description="Object ID to archive.", examples=["123456"])
    confirm: bool = Field(default=False, description="Must be true to execute.")


@mcp.tool(annotations=DESTRUCTIVE,
          description="Archive (soft delete) a HubSpot CRM object. DESTRUCTIVE — requires confirm=true.")
async def hubspot_archive_object(input: HubspotArchiveObjectInput) -> str:
    if not input.confirm:
        return "Archiving requires confirm=true. Re-run with confirm=true to proceed."
    client = get_client("hubspot")
    if input.dry_run:
        return f"[DRY RUN] Would archive {input.object_type}/{input.object_id}"
    result = await client.archive_object(input.object_type, input.object_id)
    return client.format(result, input.response_format)


# ── Search ──

class HubspotSearchObjectsInput(BaseToolInput):
    object_type: str = Field(description="Object type.", examples=["contacts"])
    filters: list[dict] | None = Field(
        default=None,
        description="Filter groups. E.g. [{\"propertyName\":\"email\",\"operator\":\"EQ\",\"value\":\"jane@example.com\"}]",
        examples=[None],
    )
    query: str | None = Field(default=None, description="Full-text search query.")
    limit: int = Field(default=50, ge=1, le=100)
    after: str | None = Field(default=None, description="Pagination cursor.")
    properties: list[str] | None = Field(default=None, description="Properties to return.")


@mcp.tool(annotations=RO, description="Search HubSpot CRM objects with filters.")
async def hubspot_search_objects(input: HubspotSearchObjectsInput) -> str:
    client = get_client("hubspot")
    result = await client.search_objects(
        input.object_type, filter_properties=input.filters,
        query=input.query, limit=input.limit, after=input.after,
        properties=input.properties,
    )
    return client.format(result, input.response_format)


# ── Associations ──

class HubspotListAssociationsInput(BaseToolInput):
    object_type: str = Field(description="Source object type.", examples=["contacts"])
    object_id: str = Field(description="Source object ID.", examples=["123456"])
    to_object_type: str = Field(description="Target object type.", examples=["companies"])
    limit: int = Field(default=50, ge=1, le=500)


@mcp.tool(annotations=RO, description="List associations from one object to another type.")
async def hubspot_list_associations(input: HubspotListAssociationsInput) -> str:
    client = get_client("hubspot")
    result = await client.list_associations(input.object_type, input.object_id,
                                            input.to_object_type, input.limit)
    return client.format(result, input.response_format)


class HubspotCreateAssociationInput(BaseToolInput, DryRunInput):
    object_type: str = Field(description="Source object type.", examples=["contacts"])
    object_id: str = Field(description="Source object ID.", examples=["123456"])
    to_object_type: str = Field(description="Target object type.", examples=["companies"])
    to_object_id: str = Field(description="Target object ID.", examples=["789012"])
    association_type: str = Field(description="Association type ID.", examples=["1"])


@mcp.tool(annotations=WRITE, description="Create an association between two CRM objects.")
async def hubspot_create_association(input: HubspotCreateAssociationInput) -> str:
    client = get_client("hubspot")
    if input.dry_run:
        return f"[DRY RUN] Would associate {input.object_type}/{input.object_id} → {input.to_object_type}/{input.to_object_id}"
    result = await client.create_association(input.object_type, input.object_id,
                                             input.to_object_type, input.to_object_id,
                                             input.association_type)
    return client.format(result, input.response_format)


# ── Notes / engagements ──

class HubspotCreateNoteInput(BaseToolInput, DryRunInput):
    body_text: str = Field(description="Note body text.", examples=["Called customer about invoice."])
    associated_object_type: str = Field(description="Associated object type.", examples=["contacts"])
    associated_object_id: str = Field(description="Associated object ID.", examples=["123456"])


@mcp.tool(annotations=WRITE, description="Create a note engagement associated with a CRM object.")
async def hubspot_create_note(input: HubspotCreateNoteInput) -> str:
    client = get_client("hubspot")
    if input.dry_run:
        return f"[DRY RUN] Would create note on {input.associated_object_type}/{input.associated_object_id}: {input.body_text}"
    result = await client.create_note(
        engagement={"type": "NOTE"},
        metadata={"body": input.body_text},
        associations=[{
            "to": {"id": input.associated_object_id},
            "type": f"{input.associated_object_type.upper()}_TO_NOTE",
        }],
    )
    return client.format(result, input.response_format)


# ── Properties ──

class HubspotListPropertiesInput(BaseToolInput):
    object_type: str = Field(description="Object type.", examples=["contacts"])


@mcp.tool(annotations=RO, description="List all properties for an object type.")
async def hubspot_list_properties(input: HubspotListPropertiesInput) -> str:
    client = get_client("hubspot")
    result = await client.list_properties(input.object_type)
    return client.format(result, input.response_format)


# ── Pipelines ──

class HubspotListPipelinesInput(BaseToolInput):
    object_type: str = Field(description="Object type (deals, tickets).", examples=["deals"])


@mcp.tool(annotations=RO, description="List pipelines for an object type.")
async def hubspot_list_pipelines(input: HubspotListPipelinesInput) -> str:
    client = get_client("hubspot")
    result = await client.list_pipelines(input.object_type)
    return client.format(result, input.response_format)


# ── Escape-hatch ──

class HubspotRequestInput(BaseToolInput):
    method: str = Field(description="HTTP method.", examples=["GET", "POST", "PATCH", "DELETE"])
    path: str = Field(description="API path (starts with /).", examples=["/crm/v3/objects/contacts/123"])
    query: dict | None = Field(default=None, description="Query parameters.")
    body: dict | None = Field(default=None, description="Request body (JSON).")


@mcp.tool(annotations=WRITE,
          description="Call ANY HubSpot API endpoint. Escape-hatch for full API coverage.")
async def hubspot_request(input: HubspotRequestInput) -> str:
    client = get_client("hubspot")
    result = await client.generic_request(input.method, input.path,
                                          query=input.query, body=input.body)
    return client.format(result, input.response_format)