# RPA Logic App Deployer — Progress Update

**Date:** 2 March 2026 | **Subscription:** `<your-subscription-id>`

---

## Status: IaC Complete — Single-Command Deploy ✅

| Phase | Status | Summary |
|-------|--------|---------|
| 0 — Prerequisites | ✅ | Azure CLI 2.76, Func Tools 4.2.1, Python 3.12.10, azd 1.20.1 |
| 1 — ARM Template | ✅ | Validated `logic-app-email-trigger.json` via direct `az deployment` |
| 2 — Local Function | ✅ | Runs on localhost, deploys Logic Apps with SystemAssigned identity |
| 3 — Azure Deploy | ✅ | `rpa-poc-func` live on B1 Linux, HTTP 200 end-to-end |
| 3b — Cross-RG | ✅ | Deployed to `templates-rg` (Sweden Central) with auto-detected location |
| **4 — Bicep IaC** | **✅** | **`azd up` provisions all infra + deploys code in one command** |

---

## Quick Start (for customer)

```bash
# One-time setup
az login
azd init
azd env new <env-name>
azd env set AZURE_LOCATION westeurope
azd env set AZURE_SUBSCRIPTION_ID <sub-id>

# Deploy everything
azd up
```

---

## Fixes Applied

| # | Issue | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | `deployments` property missing | `azure-mgmt-resource` v25 breaking change | Pinned to v23.2.0 |
| 2 | Cryptography module crash on Linux | `--no-build` shipped Windows binaries | Switched to remote build |
| 3 | Function routes not registered | v1-style `function.json` conflicting with v2 model | Removed the file |
| 4 | HTTP 404 — files missing on server | `templates/` was outside `function_app/` directory | Moved inside + fixed path |
| 5 | HTTP 404 — routes not discovered | `EnableWorkerIndexing` feature flag missing | Set in Bicep app settings |
| 6 | Key Vault role assignment target wrong | `KEY_VAULT_RESOURCE_ID` pointed to wrong RG | Updated `config.py` |
| 7 | `InvalidResourceGroupLocation` on cross-RG deploy | Defaulted to West Europe for Sweden Central RG | Added `_resolve_location()` auto-detect |
| **8** | **`azd deploy` — `No module named 'azure.identity'`** | **azd zip push skipped pip install** | **Added `WEBSITE_RUN_FROM_PACKAGE=0` to Bicep** |
| **9** | **`azd deploy` — can't find service** | **Function App missing azd tags** | **Added `azd-service-name: api` tag to Bicep** |

---

## Bicep Infrastructure (infra/)

| File | Purpose |
|------|---------|
| `main.bicep` | Subscription-scoped orchestrator, wires all modules |
| `main.parameters.json` | Customer-editable params (env name, location, cross-RG targets) |
| `modules/storage-account.bicep` | StorageV2, identity-based (no shared keys), TLS 1.2 |
| `modules/app-service-plan.bicep` | B1 Linux, reserved |
| `modules/monitoring.bicep` | Log Analytics + Application Insights |
| `modules/function-app.bicep` | Python 3.12, SystemAssigned identity, all app settings |
| `modules/rbac-storage.bicep` | Blob Data Owner + Queue + Table Data Contributor |
| `modules/rbac-target-rg.bicep` | Contributor on each target RG (loop) |
| `modules/rbac-keyvault.bicep` | User Access Administrator on Key Vault |

Key design decisions:
- `WEBSITE_RUN_FROM_PACKAGE=0` — forces filesystem deploy so Oryx runs `pip install`
- `allowSharedKeyAccess: false` — subscription policy compliance
- `azd-service-name: api` tag — maps Function App to azd service for deployment

---

## Azure Resources (rg-rpa-poc)

| Resource | Type |
|----------|------|
| `rpapocstor` | Storage Account (Standard_LRS) |
| `rpa-poc-plan` | App Service Plan (B1 Linux) |
| `rpa-poc-func` | Function App (Python 3.12) |
| `rpa-poc-appi` | Application Insights |
| `rpa-poc-log` | Log Analytics Workspace |

## RBAC — Function Identity `<principal-id>`

| Role | Scope |
|------|-------|
| Contributor | `rg-rpa-poc` RG |
| Storage Blob Data Owner | `rpapocstor` |
| Storage Queue Data Contributor | `rpapocstor` |
| Storage Table Data Contributor | `rpapocstor` |

## Key Values

| Item | Value |
|------|-------|
| Function URL | `https://<env-name>-func.azurewebsites.net/api/deploy-logic-app` |
| Function Key | _(retrieve with `az functionapp keys list`)_ |

---

## Known Issue

Key Vault role assignment skipped — `KEY_VAULT_RESOURCE_ID` is empty because `templates-rg` RG doesn't exist in this subscription. Once customer provides target RGs/KV, update `main.parameters.json` and re-run `azd provision`.

---

## Next Steps

1. **Cross-RG Params** — Set `targetResourceGroups`, `keyVaultName`, `keyVaultResourceGroup` in `main.parameters.json` when target RGs exist, re-provision
2. **Email Trigger Template** — Get JSON export of real email-trigger Logic App, parameterize ARM template (mailbox, folder, subject filter, KV secrets, UiPath config), extend Function API, handle API connections
3. **Production RBAC** — Grant User Access Administrator on target Key Vault
4. **Copilot Studio** — Build topic flow for parameter collection, HTTP action to call Function, deploy to Teams
