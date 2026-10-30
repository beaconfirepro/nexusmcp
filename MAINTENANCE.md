# Maintaining the NexusMCP Server — Operations & Security Guide

This is the multi-account MCP server that gives an AI agent read/write access to nine business
services (Connecteam, QuickBooks, HubSpot, Helm, SharePoint, Outlook Mail, Outlook Calendar, Gmail,
Google Calendar) through one endpoint. This document is how you keep it running and what you must
stay careful about.

---

## 1. What lives where

| Piece | Name / value | Purpose |
|---|---|---|
| Container App | `multi-mcp` (resource group `mcp-rg`) | The running server |
| Public URL | `https://multi-mcp.gentleplant-1d0fa284.eastus.azurecontainerapps.io` | Stable; `/mcp` is the endpoint, `/health` is open, `/status` is read-only |
| Container Registry | `mcpacrbeacon01` | Holds the built image |
| Key Vault | `mcp-kv-beacon01` | All static secrets (tokens, client secrets, inbound + status tokens) |
| Token store | Storage account `mcpstorebeacon01`, table `oauthtokens` | The rotating OAuth refresh tokens (QBO / Microsoft / Google) |
| Managed identity | `mcp-identity` | The app's identity for reading the token table + resolving Key Vault secrets |
| Entra app | client id `539c8f00-2a08-4e23-9022-108124681a93`, tenant `f5d93f40-76aa-4dc8-b3db-469f219b8e75` | Delegated Microsoft Graph login (SharePoint + Outlook) |
| Repo | `github.com/beaconfirepro/nexusmcp` (Python server under `mcp_server/`) | Source code |

The two things that make it work: **static secrets** are injected from Key Vault as environment
variables; **rotating OAuth tokens** live in Table Storage and are refreshed automatically.

---

## 2. Routine maintenance

### Redeploy after a code change
```bash
cd ~ && rm -rf nexusmcp
git clone https://github.com/beaconfirepro/nexusmcp.git
cd nexusmcp/mcp_server
az acr build -r mcpacrbeacon01 -t multi-mcp:latest .
az containerapp update -n multi-mcp -g mcp-rg --image mcpacrbeacon01.azurecr.io/multi-mcp:latest
```
Deploying does **not** change the URL. After it finishes, quit Claude from the system tray and reopen
so it reconnects.

### Change a secret (e.g. rotate the inbound token, update an API key)
```bash
az keyvault secret set --vault-name mcp-kv-beacon01 -n <secret-name> --value "<new-value>"
# then bounce a new revision so it picks up the new version:
az containerapp update -n multi-mcp -g mcp-rg --revision-suffix rot$(date +%s)
```
Secret names: `inbound-token`, `status-token`, `connecteam-key`, `hubspot-main`, `helm-api-key`, `nexus-bridge-secret`,
`qbo-client-secret`, `graph-client-secret`, `google-client-secret`.

### Connect Helm (once, before the first deploy that carries the Helm provider)
The server refuses to start without `HELM_API_KEY` and `HELM_BASE_URL`, so set both before that
deploy. Make the key in Helm under Tenant Admin > API keys; its scopes decide what the `helm_*`
tools may read and write.
```bash
az keyvault secret set --vault-name mcp-kv-beacon01 -n helm-api-key --value "helm_..."
az containerapp secret set -n multi-mcp -g mcp-rg \
  --secrets "helm-api-key=keyvaultref:https://mcp-kv-beacon01.vault.azure.net/secrets/helm-api-key,identityref:$(az identity show -n mcp-identity -g mcp-rg --query id -o tsv)"
az containerapp update -n multi-mcp -g mcp-rg \
  --set-env-vars HELM_API_KEY=secretref:helm-api-key HELM_BASE_URL=https://helm.beaconfire.co
```
Check it with the `helm_ping` tool or `GET /status`.

### Sign-in and "Add an API" (once, before the first deploy that carries them)
The owner password is gone: the server now sends the owner to the Nexus web app to sign in (invite-only,
admin role) and approve, and reads APIs added there. It refuses to start without `NEXUS_APP_URL` and
`NEXUS_BRIDGE_SECRET`. Use one new random value for the secret, in both places:
```bash
SECRET=$(openssl rand -hex 32)
az keyvault secret set --vault-name mcp-kv-beacon01 -n nexus-bridge-secret --value "$SECRET"
az containerapp secret set -n multi-mcp -g mcp-rg \
  --secrets "nexus-bridge-secret=keyvaultref:https://mcp-kv-beacon01.vault.azure.net/secrets/nexus-bridge-secret,identityref:$(az identity show -n mcp-identity -g mcp-rg --query id -o tsv)"
az containerapp update -n multi-mcp -g mcp-rg \
  --set-env-vars NEXUS_BRIDGE_SECRET=secretref:nexus-bridge-secret NEXUS_APP_URL=https://nexus-beacon.base44.app
echo "$SECRET"   # paste into the Base44 app's secrets as NEXUS_BRIDGE_SECRET, then clear your terminal
```
Keep `OWNER_LOGIN_PASSWORD` until the new code is live: the running revision still needs it to
start. Once the deploy has rolled out and sign-in through the web app works, remove it:
```bash
az containerapp update -n multi-mcp -g mcp-rg --remove-env-vars OWNER_LOGIN_PASSWORD
```
then delete the old owner-password secret from Key Vault.

### Read logs when something breaks
```bash
az containerapp logs show -n multi-mcp -g mcp-rg --tail 80
```

### Check health / status
- `GET /health` — is the process up (no auth needed).
- `GET /status` — per-provider auth + scopes (needs the read-only `STATUS_TOKEN`).

### Re-seed a provider (token expired or revoked)
OAuth tokens (QBO / Microsoft / Google) sometimes need re-seeding — see the sign-in + code-exchange
process you used during setup. Triggers: you revoked access, a refresh token went unused too long, or
(Google) the OAuth app is in "Testing" mode so the token expires ~weekly. Static providers
(Connecteam, HubSpot, Helm) never need re-seeding — just update the key in Key Vault if it changes.

### Add another account for a provider
Add a new alias (e.g. `google:personal1`) to the registry config, then run the sign-in + seeding for
that account so its refresh token lands in the token table under the new alias.

---

## 3. Costs

Scale-to-zero means you pay almost nothing while idle; a single-user load stays inside the Azure free
grant, so expect roughly **$0–5/month**. First request after idle has a ~1–3s cold start. The
provider APIs themselves don't meter-bill on your plans (confirm Connecteam's plan includes API
access).

---

## 4. Security — read this part carefully

This server is powerful, and that power cuts both ways. Treat the following as real risks, not
theoretical ones.

**One key unlocks everything.** A single bearer token (`INBOUND_TOKEN`) is the *only* thing standing
between the public URL and full read/write/delete access to your accounting, every email, your files,
and your CRM. If that token leaks, whoever has it can read your books, send email as you, delete
records, and download files — from anywhere. Treat it like a master password: store it somewhere safe,
never paste it into a public place or a shipped web page, and rotate it immediately if you suspect
exposure. (This matters more because the server's DNS-rebinding protection was turned off to run behind
Azure — the token is genuinely the sole gate.)

**The agent can destroy things, not just read them.** You granted full write and delete scopes. The
server can delete invoices, send and delete emails, remove calendar events, and delete files. An LLM
mistake, an ambiguous instruction, or a bad automation can do real, hard-to-undo damage. Be deliberate
about when you let the agent act autonomously versus asking it to confirm first.

**Prompt injection is the big one.** The agent both *reads untrusted content* (incoming emails, shared
files, web pages) and *has write access to your systems*. A malicious email or document can contain
hidden instructions that trick the agent into doing something harmful — forwarding sensitive data,
sending emails, changing records. This is the single most serious risk of a broad-access MCP server
wired to an LLM. Be cautious about pointing the agent at untrusted inbound content while it also holds
write tools, and don't run it fully unattended on that kind of material.

**It acts as you.** Microsoft and Google use delegated auth, so every action the agent takes is
recorded as *you* in the audit logs. There's no separate "bot" identity to trace — good and bad
actions alike look like Deb did them.

**Keep the repo clean and consider making it private.** The repo is currently public. That's fine only
because no secrets live in it — everything sensitive is in Key Vault. Never commit a token, client
secret, or `.env` with real values. Once things are stable, consider switching the repo back to
private to avoid leaking operational detail about your setup.

**Protect the token store and secrets.** The Table Storage account holds long-lived refresh tokens;
Key Vault holds every secret. Only the managed identity and you should have access. Don't hand out
those roles.

**Rotating tokens are fragile if shared.** QuickBooks refresh tokens rotate on every use. Let *only*
the server use them — if you run a second process against the same QBO token, the two will invalidate
each other and you'll have to re-seed.

**Least privilege is worth revisiting.** You wired full read/write everywhere because you wanted
maximum capability. If in practice you only need read access for some providers, scoping those down
later meaningfully shrinks the blast radius if the token ever leaks.

### A short security checklist
- Inbound token stored safely, rotated on any suspicion of exposure.
- Repo has zero secrets committed; consider private.
- Be wary of the agent acting on untrusted email/files while holding write tools.
- Add an IP allow-list on the Azure ingress if only you/known machines should reach it.
- Watch the `/status` page and each provider's own audit log for anything unexpected.
- Re-seed / revoke tokens promptly if a device or account is compromised.

---

*This server can do almost anything you can do across your business systems. That's the point — and
also the reason to treat its one access token, and the content you let it act on, with real care.*
