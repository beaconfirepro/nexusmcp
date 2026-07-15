# Multi-Account MCP Server

A production Model Context Protocol (MCP) server that gives an AI agent unified,
full read/write access to eight business services in a single session:

| Service | Provider Login | Auth Method |
|---------|---------------|-------------|
| Connecteam | `connecteam:main` | API key (`X-API-KEY` header) |
| QuickBooks Online | `qbo:main` | OAuth 2.0 (refresh tokens rotate on every use) |
| HubSpot | `hubspot:main` | Private-app access token (bearer) |
| SharePoint | `microsoft:main` | Microsoft Graph delegated user OAuth |
| Outlook Mail | `microsoft:main` | Microsoft Graph delegated user OAuth |
| Outlook Calendar | `microsoft:main` | Microsoft Graph delegated user OAuth |
| Gmail | `google:main` | Google delegated OAuth |
| Google Calendar | `google:main` | Google delegated OAuth |

The server acts **as the owner** via delegated OAuth (Microsoft + Google), not
app-only. It covers the **entire documented API** of every service through a
combination of typed tools and provider escape-hatch tools.

---

## Architecture

### Identity separation (critical)

Three completely separate identity layers — do NOT conflate them:

| Layer | What it does | Credential |
|-------|-------------|------------|
| **Inbound** | Who may call this MCP server | `INBOUND_TOKEN` (static bearer) |
| **Outbound (Microsoft Graph)** | How the server talks to Graph | Entra app registration (`GRAPH_CLIENT_ID` / `GRAPH_CLIENT_SECRET` / `TENANT_ID`) via delegated user OAuth |
| **Managed identity** | Azure Table Storage ONLY | `AZURE_CLIENT_ID` (user-assigned managed identity) |

The managed identity is **NEVER** used to call Microsoft Graph. It is used
exclusively to read/write rotating OAuth refresh tokens in Azure Table Storage.

### 12-factor: no Key Vault SDK calls

Azure Container Apps injects Key Vault secret values as environment variables
(via Key Vault-reference secrets resolved with the attached managed identity).
The app reads `os.environ` exclusively — it never calls the Key Vault SDK or
uses `DefaultAzureCredential` for Key Vault access.

### Account registry

Aliases map to provider logins. The server ships with one login per provider:

| Alias | Provider | Used by |
|-------|----------|---------|
| `connecteam:main` | connecteam | `connecteam_*` tools |
| `qbo:main` | qbo | `qbo_*` tools |
| `hubspot:main` | hubspot | `hubspot_*` tools |
| `microsoft:main` | microsoft | `sharepoint_*`, `outlook_*` tools |
| `google:main` | google | `gmail_*`, `gcal_*` tools |

Every tool takes an optional `account` argument. With one login per provider,
it defaults to that provider's single registered alias. When more logins are
added, the agent passes the alias to choose. Unknown alias → actionable error
listing valid aliases for that provider.

### Token store

Rotating OAuth refresh tokens (QBO, Microsoft Graph, Google) are stored in
Azure Table Storage via the user-assigned managed identity:

- **PartitionKey** = provider (`qbo`, `microsoft`, `google`)
- **RowKey** = alias (`main`, etc.)
- Fields: `refresh_token`, `access_token` (cached), `expires_at`, `realm_id` (QBO only), `updated_at`

For QBO, refresh tokens **rotate on every use** — the rotated token is persisted
immediately to Table Storage on each refresh.

---

## Environment variables

The app reads ALL static secrets from environment variables (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `INBOUND_TOKEN` | Static bearer token for inbound MCP auth |
| `STATUS_TOKEN` | Read-only bearer token for GET /status (separate from INBOUND_TOKEN) |
| `CONNECTEAM_KEY` | Connecteam API key (sent as `X-API-KEY` header) |
| `HUBSPOT_MAIN` | HubSpot private-app access token |
| `QBO_CLIENT_ID` | QuickBooks OAuth client ID |
| `QBO_CLIENT_SECRET` | QuickBooks OAuth client secret |
| `QBO_ENV` | `sandbox` or `production` (selects base URL) |
| `GRAPH_CLIENT_ID` | Entra app registration client ID (Graph only) |
| `GRAPH_CLIENT_SECRET` | Entra app registration client secret (Graph only) |
| `TENANT_ID` | Entra tenant ID |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `AZURE_CLIENT_ID` | User-assigned managed identity client ID (Table Storage only) |
| `TOKEN_STORE_ACCOUNT` | Azure Storage account name |
| `TOKEN_STORE_TABLE` | Table name (default: `oauthtokens`) |

The rotating refresh tokens live in Table Storage, NOT in env vars.

---

## Required OAuth scopes per provider

### Microsoft Graph (SharePoint + Outlook)
https://learn.microsoft.com/en-us/graph/permissions-reference

Delegated scopes (one Entra app for all three):
- `offline_access` — for refresh tokens
- `User.Read` — basic profile
- `Sites.ReadWrite.All` — SharePoint sites, lists, drive items
- `Files.ReadWrite.All` — OneDrive/SharePoint files
- `Mail.ReadWrite` — Outlook mail (read + write)
- `Mail.Send` — send mail
- `Calendars.ReadWrite` — Outlook calendar (read + write)

### Google (Gmail + Calendar)
https://developers.google.com/identity/protocols/oauth2

- `https://mail.google.com/` — full Gmail access (RESTRICTED scope)
- `https://www.googleapis.com/auth/calendar` — full Calendar access

### QuickBooks Online
https://developer.intuit.com/app/developer/qbo/docs/learn/scopes

- `com.intuit.quickbooks.accounting` — full accounting access

---

## Registering the Entra app (SharePoint + Outlook)

1. Go to [Azure Portal → Entra ID → App registrations → New registration](https://portal.azure.com).
2. Name it (e.g. "MCP Graph Server"), select **Accounts in this organizational directory only**.
3. Add a redirect URI: **Web** → `http://localhost:8765/callback` (for seeding).
4. Under **Certificates & secrets**, create a new client secret. Copy the value.
5. Under **API permissions**, add the delegated Microsoft Graph permissions listed above.
6. Grant admin consent for the permissions.
7. Copy the **Application (client) ID** and the **Directory (tenant) ID**.

Set these as env vars: `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `TENANT_ID`.

---

## Registering the Google OAuth client (Gmail + Calendar)

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials).
2. Create an OAuth 2.0 Client ID (Web application).
3. Add authorized redirect URI: `http://localhost:8765/callback`.
4. Under **OAuth consent screen**, add the scopes:
   - `https://mail.google.com/`
   - `https://www.googleapis.com/auth/calendar`
5. Add yourself as a test user (if in Testing mode).

Set these as env vars: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.

### ⚠️ Google restricted-scope verification caveat

`https://mail.google.com/` is a **RESTRICTED scope**. An unverified ("testing")
OAuth app issues refresh tokens that **expire after ~7 days**. After that, the
server will return an auth-expired error and you must re-run the seeding script.

Options to avoid periodic re-auth:
1. **Publish/verify the app** — submit the OAuth consent screen for verification
   (requires a security assessment for restricted scopes).
2. **Use narrower scopes** — e.g. `gmail.send` + `gmail.readonly` (sensitive, not
   restricted — no expiry for unverified apps, but less than full access).
3. **Accept periodic re-auth** — re-run `python scripts/seed_oauth.py google` weekly.

Reference: https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification

---

## Seeding OAuth refresh tokens

The seeding script runs **locally** (not on the deployed server). It opens a
browser for sign-in, exchanges the auth code, and writes the refresh token to
Azure Table Storage using your own Azure credentials (`az login`).

### Prerequisites
```bash
az login                          # Your own Azure credentials for Table Storage
pip install -r requirements.txt  # httpx, azure-identity, azure-data-tables
```

### Seed each provider
```bash
# Set env vars first (see .env.example)
export TOKEN_STORE_ACCOUNT=your_storage_account_name
export QBO_CLIENT_ID=... QBO_CLIENT_SECRET=... QBO_ENV=sandbox
export GRAPH_CLIENT_ID=... GRAPH_CLIENT_SECRET=... TENANT_ID=...
export GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=...

# Seed QuickBooks Online (captures realmId alongside refresh token)
python scripts/seed_oauth.py qbo

# Seed Microsoft Graph (SharePoint + Outlook)
python scripts/seed_oauth.py microsoft

# Seed Google (Gmail + Calendar)
python scripts/seed_oauth.py google
```

To seed a non-default alias: `python scripts/seed_oauth.py qbo --alias secondary`

---

## Local run

```bash
# 1. Set all environment variables (see .env.example)
cp .env.example .env
# Edit .env with your values

# 2. Seed OAuth tokens (see above)

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python -m src
# Server starts on http://localhost:8000
# MCP endpoint: http://localhost:8000/mcp
# Health check: http://localhost:8000/health
```

---

## Deploy to Azure Container Apps

### 1. Build and push the Docker image

```bash
# Create ACR (if not exists)
az acr create --name <registry> --resource-group <rg> --sku Basic

# Build and push
az acr build --registry <registry> --image multi-account-mcp:latest .
```

### 2. Create the Container App

```bash
# Create environment (if not exists)
az containerapp env create \
  --name mcp-env \
  --resource-group <rg> \
  --location <location>

# Create the container app
az containerapp create \
  --name multi-account-mcp \
  --resource-group <rg> \
  --environment mcp-env \
  --image <registry>.azurecr.io/multi-account-mcp:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 3 \
  --scale-rule-name http-scale \
  --scale-rule-type http \
  --scale-rule-metadata concurrentRequests=10
```

### 3. Wire up Key Vault secrets + managed identity

```bash
# Create user-assigned managed identity
az identity create --name mcp-identity --resource-group <rg>

# Assign it to the container app
az containerapp identity assign \
  --name multi-account-mcp \
  --resource-group <rg> \
  --user-assigned mcp-identity

# Grant the identity access to the storage table
# (Storage Table Data Contributor role on the storage account)
az role assignment create \
  --assignee <mcp-identity-principal-id> \
  --role "Storage Table Data Contributor" \
  --scope <storage-account-resource-id>

# Create Key Vault secrets
az keyvault secret set --vault-name <vault> --name INBOUND_TOKEN --value <your-token>
az keyvault secret set --vault-name <vault> --name CONNECTEAM_KEY --value <your-key>
# ... repeat for all env vars (see .env.example)

# Reference Key Vault secrets in the container app (ACA resolves them via managed identity)
az containerapp secret set \
  --name multi-account-mcp \
  --resource-group <rg> \
  --secrets \
    INBOUND_TOKEN="keyvault:https://<vault>.vault.azure.net/secrets/INBOUND_TOKEN" \
    STATUS_TOKEN="keyvault:https://<vault>.vault.azure.net/secrets/STATUS_TOKEN" \
    CONNECTEAM_KEY="keyvault:https://<vault>.vault.azure.net/secrets/CONNECTEAM_KEY" \
    HUBSPOT_MAIN="keyvault:https://<vault>.vault.azure.net/secrets/HUBSPOT_MAIN" \
    QBO_CLIENT_ID="keyvault:https://<vault>.vault.azure.net/secrets/QBO_CLIENT_ID" \
    QBO_CLIENT_SECRET="keyvault:https://<vault>.vault.azure.net/secrets/QBO_CLIENT_SECRET" \
    QBO_ENV="keyvault:https://<vault>.vault.azure.net/secrets/QBO_ENV" \
    GRAPH_CLIENT_ID="keyvault:https://<vault>.vault.azure.net/secrets/GRAPH_CLIENT_ID" \
    GRAPH_CLIENT_SECRET="keyvault:https://<vault>.vault.azure.net/secrets/GRAPH_CLIENT_SECRET" \
    TENANT_ID="keyvault:https://<vault>.vault.azure.net/secrets/TENANT_ID" \
    GOOGLE_CLIENT_ID="keyvault:https://<vault>.vault.azure.net/secrets/GOOGLE_CLIENT_ID" \
    GOOGLE_CLIENT_SECRET="keyvault:https://<vault>.vault.azure.net/secrets/GOOGLE_CLIENT_SECRET" \
    AZURE_CLIENT_ID="keyvault:https://<vault>.vault.azure.net/secrets/AZURE_CLIENT_ID" \
    TOKEN_STORE_ACCOUNT="keyvault:https://<vault>.vault.azure.net/secrets/TOKEN_STORE_ACCOUNT" \
    TOKEN_STORE_TABLE="keyvault:https://<vault>.vault.azure.net/secrets/TOKEN_STORE_TABLE"

# Bind secrets as environment variables
az containerapp update \
  --name multi-account-mcp \
  --resource-group <rg> \
  --set-env-vars \
    INBOUND_TOKEN=secretref:INBOUND_TOKEN \
    STATUS_TOKEN=secretref:STATUS_TOKEN \
    CONNECTEAM_KEY=secretref:CONNECTEAM_KEY \
    HUBSPOT_MAIN=secretref:HUBSPOT_MAIN \
    QBO_CLIENT_ID=secretref:QBO_CLIENT_ID \
    QBO_CLIENT_SECRET=secretref:QBO_CLIENT_SECRET \
    QBO_ENV=secretref:QBO_ENV \
    GRAPH_CLIENT_ID=secretref:GRAPH_CLIENT_ID \
    GRAPH_CLIENT_SECRET=secretref:GRAPH_CLIENT_SECRET \
    TENANT_ID=secretref:TENANT_ID \
    GOOGLE_CLIENT_ID=secretref:GOOGLE_CLIENT_ID \
    GOOGLE_CLIENT_SECRET=secretref:GOOGLE_CLIENT_SECRET \
    AZURE_CLIENT_ID=secretref:AZURE_CLIENT_ID \
    TOKEN_STORE_ACCOUNT=secretref:TOKEN_STORE_ACCOUNT \
    TOKEN_STORE_TABLE=secretref:TOKEN_STORE_TABLE
```

### 4. Configure health probe

ACA automatically detects the `HEALTHCHECK` in the Dockerfile. The `/health`
endpoint is unauthenticated and lightweight (no outbound calls), making it safe
for liveness probes under scale-to-zero.

### 5. Scale-to-zero

`--min-replicas 0` means the app scales to zero when idle. The server is
stateless (`stateless_http=True`), so cold starts work correctly — no
in-memory session state is expected to survive between requests.

---

## Single inbound-token model

The server is protected by a single static bearer token (`INBOUND_TOKEN`).
Every MCP request must include:

```
Authorization: Bearer <INBOUND_TOKEN>
```

The `/health` endpoint is EXEMPT from this check (for ACA liveness probes).

To add per-user tokens later, extend `BearerAuthMiddleware` to look up tokens
from a credential store instead of comparing against a single env var.

---

## Status endpoint (GET /status)

A live provider-status endpoint protected by a **separate read-only token**
(`STATUS_TOKEN`). This token unlocks ONLY `/status` — never the MCP tools at
`/mcp`. It is completely independent of `INBOUND_TOKEN`.

### What it returns

For each provider (connecteam, qbo, hubspot, microsoft, google):

| Field | Description |
|-------|-------------|
| `configured` | Credentials / registry entry present in env |
| `seeded` | For OAuth providers: refresh token exists in Table Storage |
| `reachable` | Result of a lightweight live auth ping |
| `scopes` | Granted scopes (Google via tokeninfo, Microsoft from JWT `scp`, HubSpot via token-info, QBO fixed, Connecteam `api_key`) |
| `expires_at` | Token expiry if applicable |
| `error` | Short message if the ping failed (never leaks secrets) |

Response shape:
```json
{
  "checked_at": "2025-01-15T12:00:00Z",
  "providers": {
    "connecteam": {"configured": true, "seeded": true, "reachable": true, "scopes": ["api_key"], "expires_at": null, "error": null},
    "qbo": {"configured": true, "seeded": true, "reachable": true, "scopes": ["com.intuit.quickbooks.accounting"], "expires_at": "...", "error": null}
  }
}
```

### CORS

The `/status` endpoint includes CORS headers (`Access-Control-Allow-Origin: *`,
`GET` + `OPTIONS` methods, `Authorization` header) so the status page can call
it from a different origin.

### Deployment

After adding `STATUS_TOKEN`:

1. **Store in Key Vault** (like the other secrets):
   ```bash
   az keyvault secret set --vault-name <vault> --name STATUS_TOKEN --value <your-status-token>
   ```

2. **Reference it in the container app** (add to the `--secrets` and `--set-env-vars` commands shown in the Deploy section above).

3. **Rebuild and redeploy** the server:
   ```bash
   az acr build --registry <registry> --image multi-account-mcp:latest .
   az containerapp update --name multi-account-mcp --resource-group <rg> \
     --image <registry>.azurecr.io/multi-account-mcp:latest
   ```

### curl example

```bash
curl -H "Authorization: Bearer $STATUS_TOKEN" \
  https://your-mcp-server.azurecontainerapps.io/status
```

---

## MCP Inspector testing

```bash
# Install MCP Inspector
npx @modelcontextprotocol/inspector

# Connect to: http://localhost:8000/mcp
# Add header: Authorization: Bearer <INBOUND_TOKEN>
```

### Read-only smoke test per provider

Use the `check_provider_connectivity` tool to verify all providers in one call,
or test individually:

| Provider | Read-only tool |
|----------|---------------|
| Connecteam | `connecteam_get_me` |
| QBO | `qbo_query` (entity=Customer, limit=1) |
| HubSpot | `hubspot_list_objects` (object_type=contacts, limit=1) |
| SharePoint | `sharepoint_list_sites` |
| Outlook mail | `outlook_list_messages` (limit=1) |
| Outlook calendar | `outlook_list_calendars` |
| Gmail | `gmail_list_messages` (max_results=1) |
| Google Calendar | `gcal_list_calendars` |

---

## Destructive tools

The following tools are destructive (require `confirm=true`):

| Tool | Provider |
|------|----------|
| `connecteam_delete_user` | Connecteam |
| `qbo_delete_entity` | QuickBooks Online |
| `hubspot_archive_object` | HubSpot |
| `outlook_delete_event` | Microsoft Graph (Calendar) |
| `gcal_delete_event` | Google Calendar |

All write tools support `dry_run=true` to validate without executing.

---

## Tool reference

### Typed tools (by provider)

**Connecteam** (12): `connecteam_get_me`, `connecteam_list_users`, `connecteam_get_user`,
`connecteam_create_user`, `connecteam_update_user`, `connecteam_delete_user`,
`connecteam_list_shifts`, `connecteam_create_shift`, `connecteam_list_time_clock`,
`connecteam_list_jobs`, `connecteam_list_forms`, `connecteam_list_tasks`

**QuickBooks Online** (7): `qbo_query`, `qbo_get_entity`, `qbo_create_entity`,
`qbo_update_entity`, `qbo_delete_entity`, `qbo_get_report`, `qbo_request`

**HubSpot** (12): `hubspot_list_objects`, `hubspot_get_object`, `hubspot_create_object`,
`hubspot_update_object`, `hubspot_archive_object`, `hubspot_search_objects`,
`hubspot_list_associations`, `hubspot_create_association`, `hubspot_create_note`,
`hubspot_list_properties`, `hubspot_list_pipelines`, `hubspot_request`

**SharePoint** (8): `sharepoint_list_sites`, `sharepoint_get_site`, `sharepoint_list_drives`,
`sharepoint_list_drive_items`, `sharepoint_upload_file`, `sharepoint_download_file`,
`sharepoint_list_lists`, `sharepoint_list_list_items`

**Outlook Mail** (9): `outlook_list_messages`, `outlook_get_message`, `outlook_send_mail`,
`outlook_create_draft`, `outlook_reply_to_message`, `outlook_forward_message`,
`outlook_list_mail_folders`, `outlook_list_categories`, `outlook_list_rules`

**Outlook Calendar** (7): `outlook_list_calendars`, `outlook_list_events`, `outlook_get_event`,
`outlook_create_event`, `outlook_update_event`, `outlook_delete_event`, `outlook_get_free_busy`

**Gmail** (10): `gmail_list_messages`, `gmail_get_message`, `gmail_send_message`,
`gmail_list_threads`, `gmail_get_thread`, `gmail_list_labels`, `gmail_create_label`,
`gmail_create_draft`, `gmail_list_filters`, `gmail_get_vacation_settings`

**Google Calendar** (7): `gcal_list_calendars`, `gcal_list_events`, `gcal_get_event`,
`gcal_create_event`, `gcal_update_event`, `gcal_delete_event`, `gcal_get_free_busy`

**Diagnostics** (1): `check_provider_connectivity`

### Escape-hatch tools (one per provider)

Every provider has a generic `*_request` tool that can call ANY endpoint:
`connecteam_request`, `qbo_request`, `hubspot_request`, `graph_request`, `google_request`.

Each takes `method`, `path`, `query`, `body` and authenticates with the resolved
account automatically. This guarantees full API coverage even without a typed tool.

### Tool conventions

- All tools take optional `account` (alias) and `response_format` ("json" | "markdown")
- Pagination: `limit` parameter; responses include `has_more`, `next_cursor`, `total_count`
- Annotations: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`
- Write tools support `dry_run=true`; destructive tools require `confirm=true`
- Errors are actionable (bad alias, wrong scope, expired token, 429) — never leak secrets