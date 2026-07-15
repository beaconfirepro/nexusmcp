"""
QuickBooks Online MCP tools.
OAuth 2.0 — refresh tokens ROTATE on every use (persisted to Table Storage).
https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0
API path: /v3/company/{realmId}/{entity}
Query: /v3/company/{realmId}/query?query=SELECT * FROM {Entity}
Reports: /v3/company/{realmId}/reports/{ReportName}

The typed tools accept `entity` as a parameter, covering ALL QBO entities
(Invoice, Customer, Item, Bill, Payment, Account, JournalEntry, Vendor,
Estimate, CreditMemo, Purchase, SalesReceipt, etc.) without one tool per entity.
The escape-hatch (qbo_request) covers any endpoint not explicitly typed.
"""
from pydantic import Field

from src.clients import get_client, resolve_account
from src.mcp_instance import DESTRUCTIVE, IDEMPOTENT, RO, WRITE, mcp
from src.models import BaseToolInput, DryRunInput


# ── Query (read) ──

class QboQueryInput(BaseToolInput):
    entity: str = Field(
        description="QBO entity name (e.g. Invoice, Customer, Item, Bill, Payment, "
                    "Account, JournalEntry, Vendor, Estimate, CreditMemo, Purchase, SalesReceipt).",
        examples=["Invoice"],
    )
    where: str = Field(
        default="",
        description="Optional WHERE clause (QBO SQL syntax). E.g. \"CustomerRef = '1'\".",
        examples=["", "CustomerRef = '1'"],
    )
    limit: int = Field(default=50, ge=1, le=1000, description="Max results.", examples=[50])
    offset: int = Field(default=1, ge=1, description="Start position (1-based).", examples=[1])


@mcp.tool(annotations=RO,
          description="Query QBO entities using SQL-like syntax. Covers ALL entity types. "
                      "Returns paginated results.")
async def qbo_query(input: QboQueryInput) -> str:
    client = get_client("qbo")
    alias = resolve_account("qbo", input.account)
    result = await client.query_entity(input.entity, alias, where=input.where,
                                       limit=input.limit, offset=input.offset)
    return client.format(result, input.response_format)


# ── Get by ID ──

class QboGetEntityInput(BaseToolInput):
    entity: str = Field(description="Entity name (e.g. Invoice, Customer).", examples=["Invoice"])
    entity_id: str = Field(description="Entity ID.", examples=["123"])


@mcp.tool(annotations=RO, description="Get a single QBO entity by ID.")
async def qbo_get_entity(input: QboGetEntityInput) -> str:
    client = get_client("qbo")
    alias = resolve_account("qbo", input.account)
    result = await client.get_entity(input.entity, input.entity_id, alias)
    return client.format(result, input.response_format)


# ── Create ──

class QboCreateEntityInput(BaseToolInput, DryRunInput):
    entity: str = Field(description="Entity name (e.g. Invoice, Customer, Item, Payment).",
                        examples=["Invoice"])
    data: dict = Field(description="Entity object per QBO API schema.", examples=[{
        "Line": [{"Amount": 100, "DetailType": "SalesItemLineDetail",
                  "SalesItemLineDetail": {"ItemRef": {"value": "1"}}}],
        "CustomerRef": {"value": "1"},
    }])


@mcp.tool(annotations=WRITE,
          description="Create a QBO entity (invoice, customer, item, etc.). "
                      "Use dry_run=true to validate without creating.")
async def qbo_create_entity(input: QboCreateEntityInput) -> str:
    client = get_client("qbo")
    alias = resolve_account("qbo", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would create {input.entity}: {input.data}"
    result = await client.create_entity(input.entity, input.data, alias)
    return client.format(result, input.response_format)


# ── Update ──

class QboUpdateEntityInput(BaseToolInput, DryRunInput):
    entity: str = Field(description="Entity name.", examples=["Invoice"])
    entity_id: str = Field(description="Entity ID to update.", examples=["123"])
    data: dict = Field(description="Updated fields. Must include SyncToken for QBO updates.",
                       examples=[{"Id": "123", "SyncToken": "0", "PrivateNote": "Updated"}])


@mcp.tool(annotations=IDEMPOTENT,
          description="Update a QBO entity. Requires SyncToken in the data. Use dry_run=true to validate.")
async def qbo_update_entity(input: QboUpdateEntityInput) -> str:
    client = get_client("qbo")
    alias = resolve_account("qbo", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would update {input.entity}/{input.entity_id}: {input.data}"
    result = await client.update_entity(input.entity, input.entity_id, input.data, alias)
    return client.format(result, input.response_format)


# ── Delete ──

class QboDeleteEntityInput(BaseToolInput, DryRunInput):
    entity: str = Field(description="Entity name.", examples=["Invoice"])
    entity_id: str = Field(description="Entity ID to delete.", examples=["123"])
    confirm: bool = Field(default=False, description="Must be true to execute.")


@mcp.tool(annotations=DESTRUCTIVE,
          description="Delete a QBO entity. DESTRUCTIVE — requires confirm=true.")
async def qbo_delete_entity(input: QboDeleteEntityInput) -> str:
    if not input.confirm:
        return "Deletion requires confirm=true. Re-run with confirm=true to proceed."
    client = get_client("qbo")
    alias = resolve_account("qbo", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would delete {input.entity}/{input.entity_id}"
    result = await client.delete_entity(input.entity, input.entity_id, alias)
    return client.format(result, input.response_format)


# ── Reports ──

class QboGetReportInput(BaseToolInput):
    report_name: str = Field(
        description="Report name (e.g. ProfitAndLoss, BalanceSheet, CashFlow, "
                    "AgedReceivables, AgedPayables, CustomerIncome, TrialBalance).",
        examples=["ProfitAndLoss"],
    )
    params: dict | None = Field(
        default=None,
        description="Report parameters (start_date, end_date, etc.).",
        examples=[{"start_date": "2025-01-01", "end_date": "2025-06-30"}],
    )


@mcp.tool(annotations=RO, description="Get a QBO report (P&L, balance sheet, cash flow, etc.).")
async def qbo_get_report(input: QboGetReportInput) -> str:
    client = get_client("qbo")
    alias = resolve_account("qbo", input.account)
    result = await client.get_report(input.report_name, alias, params=input.params)
    return client.format(result, input.response_format)


# ── Escape-hatch ──

class QboRequestInput(BaseToolInput):
    method: str = Field(description="HTTP method.", examples=["GET", "POST"])
    path: str = Field(description="Full API path after base URL (e.g. /v3/company/{realmId}/invoice).",
                      examples=["/v3/company/12345/invoice"])
    query: dict | None = Field(default=None, description="Query parameters.")
    body: dict | None = Field(default=None, description="Request body (JSON).")


@mcp.tool(annotations=WRITE,
          description="Call ANY QuickBooks Online API endpoint. Escape-hatch for full API coverage. "
                      "Authenticates with the resolved account's OAuth token automatically.")
async def qbo_request(input: QboRequestInput) -> str:
    client = get_client("qbo")
    alias = resolve_account("qbo", input.account)
    result = await client.generic_request(input.method, input.path, alias,
                                          query=input.query, body=input.body)
    return client.format(result, input.response_format)