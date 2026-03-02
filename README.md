# RPA Logic App Deployer

Azure Function that deploys parameterized Logic Apps via a REST API. Designed to be called from **Microsoft Copilot Studio** in Teams — a user provides a country name and the function creates a pre-configured Logic App in the target resource group.

---

## Architecture Overview

```
┌────────────────────┐     HTTP POST      ┌──────────────────────┐     ARM deploy     ┌─────────────────┐
│  Copilot Studio    │ ──────────────────► │  Azure Function      │ ──────────────────► │  Logic App      │
│  (Teams agent)     │     + function key  │  (<env>-func)        │     via managed     │  (la-rpa-<cc>)  │
│                    │ ◄────────────────── │  Python 3.12         │     identity        │                 │
│  Shows result      │     JSON response   │                      │                     │  + Key Vault    │
└────────────────────┘                     └──────────────────────┘     RBAC            └─────────────────┘
```

**Flow:** User says _"Deploy RPA for Japan"_ in Teams → Copilot Studio asks for the country → sends HTTP POST to the Azure Function → function deploys an ARM template to create `la-rpa-japan` → returns success result → Copilot shows confirmation.

---

## Part 1 — Azure Infrastructure

### What gets created

Running `azd up` provisions all of the following automatically:

| Resource | Naming | Purpose |
|----------|--------|---------|
| Resource Group | `rg-<env-name>` | Contains all resources |
| Storage Account | `<env-name>stor` | Function App backing storage |
| App Service Plan | `<env-name>-plan` (B1 Linux) | Hosts the Function App |
| Function App | `<env-name>-func` (Python 3.12) | REST API for Logic App deployment |
| Application Insights | `<env-name>-appi` | Monitoring & telemetry |
| Log Analytics Workspace | `<env-name>-log` | Log aggregation |
| RBAC role assignments | — | Contributor, Storage Blob/Queue/Table roles |

The Function App uses a **system-assigned managed identity** — no passwords or connection strings stored anywhere.

### Prerequisites

- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) (v2.50+)
- [Azure Developer CLI (azd)](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd) (v1.20+)
- **Owner** or **Contributor + User Access Administrator** on the target subscription

### Deploy — Step by Step

#### 1. Log in

```bash
az login
azd auth login
```

#### 2. Create an environment

```bash
azd env new <env-name>
```

Pick a short name (e.g. `rpa-prod`). This name drives all resource naming:

| env-name | Resource Group | Function App | Storage |
|----------|---------------|-------------|---------|
| `rpa-poc` | `rg-rpa-poc` | `rpa-poc-func` | `rpapocstor` |
| `rpa-prod` | `rg-rpa-prod` | `rpa-prod-func` | `rpaprodstor` |

#### 3. Set required variables

```bash
azd env set AZURE_LOCATION <region>            # e.g. westeurope, swedencentral
azd env set AZURE_SUBSCRIPTION_ID <sub-id>     # your subscription GUID
```

#### 4. (Optional) Configure cross-resource-group access

Edit `infra/main.parameters.json` if the function needs to deploy Logic Apps into **other** resource groups or assign Key Vault roles:

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `targetResourceGroups` | RGs where Logic Apps will be deployed (function gets Contributor) | `["templates-rg", "rg-production"]` |
| `keyVaultResourceId` | Full resource ID of the Key Vault | `/subscriptions/.../vaults/my-kv` |
| `keyVaultName` | Key Vault name | `my-kv` |
| `keyVaultResourceGroup` | RG containing the Key Vault | `templates-rg` |

Leave these empty if you only need to deploy Logic Apps into the same resource group as the function.

##### Adding more resource groups later

Append new names to `targetResourceGroups` and run:

```bash
azd provision
```

This only updates RBAC — your function app, code, and existing Logic Apps are untouched. Existing role assignments are idempotent and won't duplicate. Any request targeting a resource group **not** in the list will fail with an authorization error (by design — this is a security boundary).

#### 5. Deploy everything

```bash
azd up
```

This provisions all infrastructure and deploys the function code in one command (~5 min).

> **Note:** The first request after deployment may take up to ~90 seconds (cold start — container image pull + Python worker initialization). Subsequent requests are fast.

### After Deployment

#### Get the function key

```bash
az functionapp keys list \
  --name <env-name>-func \
  --resource-group rg-<env-name> \
  --query "functionKeys.default" -o tsv
```

Save this key — you will need it for Copilot Studio configuration in Part 2.

#### Test via curl

```bash
curl -X POST "https://<env-name>-func.azurewebsites.net/api/deploy-logic-app?code=<FUNCTION_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"country":"japan","resourceGroup":"rg-<env-name>","subscriptionId":"<sub-id>"}'
```

A successful response:

```json
{
  "status": "success",
  "provisioningState": "Succeeded",
  "deploymentName": "deploy-la-rpa-japan-a1b2c3d4",
  "logicAppName": "la-rpa-japan",
  "logicAppResourceId": "/subscriptions/.../workflows/la-rpa-japan",
  "resourceGroup": "rg-rpa-poc",
  "country": "japan",
  "portalUrl": "https://portal.azure.com/#/resource/.../logicApp",
  "keyVaultRoleAssignment": "success",
  "message": "Logic App 'la-rpa-japan' deployed successfully..."
}
```

#### Verify in Azure Portal

```bash
az resource list --resource-group rg-<env-name> \
  --resource-type Microsoft.Logic/workflows \
  --query "[].name" -o tsv
```

### Day-2 Operations

| Task | Command |
|------|---------|
| Update Python code only | `azd deploy` |
| Update infrastructure only | `azd provision` |
| Update both | `azd up` |
| Tear down everything | `azd down --purge` |
| Restart function (if cold) | `az functionapp restart --name <env>-func --resource-group rg-<env>` |
| Check logs | Azure Portal → `<env>-func` → Monitor → Log stream |

---

## Part 2 — Copilot Studio (Teams Agent)

This section walks through creating a Microsoft Copilot Studio agent that lets users deploy Logic Apps by chatting in Teams.

### Prerequisites

- [Microsoft Copilot Studio](https://copilotstudio.microsoft.com) access (requires a license — usually included with Microsoft 365)
- The **function URL** and **function key** from Part 1
- The Azure Function must be deployed and responding (test with curl first)

### Step 1 — Create the Agent

1. Go to [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com)
2. Click **Create** → **New agent**
3. Set:
   - **Name:** `RPA Logic App Deployer`
   - **Description:** _Deploys country-specific Logic Apps to Azure via REST API_
4. Click **Create**

### Step 2 — Create the Topic

Topics define conversation flows. You need one topic: **Create Logic App**.

1. Go to the **Topics** tab
2. Click **+ Add a topic** → **From blank**
3. Name it: `Create Logic App`

### Step 3 — Configure the Trigger

1. In the trigger node, set **"The agent chooses"** (lets the AI decide when to invoke this topic)
2. Under **"Describe what the topic does"**, enter:
   ```
   Create a new Logic App
   ```
   The agent will route users here when they say things like _"Deploy RPA for a country"_, _"Create a Logic App"_, etc.

### Step 4 — Add a Question Node

1. Click the **+** below the trigger → **Ask a question**
2. Set the question text:
   ```
   Which country would you like to deploy the Logic App for?
   ```
3. Set **Identify** to: **User's entire response**
4. Under **Save user response as**, create a variable:
   - Name: `TopicCountry`
   - Type: `string`

### Step 5 — Add the HTTP Request Node

This is the core step — the agent calls your Azure Function.

#### Build your Function URL

You need the full URL from Part 1. It follows this pattern:

```
https://<env-name>-func.azurewebsites.net/api/deploy-logic-app?code=<FUNCTION_KEY>
```

Replace the two placeholders:
- **`<env-name>`** — the environment name you chose during `azd env new` (e.g., `rpa-poc`)
- **`<FUNCTION_KEY>`** — the key you retrieved with `az functionapp keys list` in the "After Deployment" section

**Example (if your environment is `rpa-poc` and your key is `abc123...`):**
```
https://rpa-poc-func.azurewebsites.net/api/deploy-logic-app?code=abc123...
```

Copy this full URL — you will paste it into Copilot Studio next.

#### Configure the HTTP Request

1. Click **+** → **Advanced** → **Send HTTP request**
2. Paste your full Function URL (including the `?code=...` part) into the **URL** field
3. Configure:

| Setting | Value |
|---------|-------|
| **URL** | Your full Function URL from above (including `?code=...`) |
| **Method** | `Post` |

4. **Headers** — Click **+ Add**:

| Key | Value |
|-----|-------|
| `Content-Type` | `application/json` |

4. **Body** — Select **JSON content**, then switch to **Edit formula** (click the `</> Edit formula` dropdown) and enter:

```
{
  country: Topic.TopicCountry,
  resourceGroup: "rg-<env-name>",
  subscriptionId: "<your-subscription-id>"
}
```

> **Important:** This is a **Power Fx record expression**, not JSON. Property names have no quotes, and `Topic.TopicCountry` is a variable reference (no quotes around it). String values still get quotes.

5. **Response data type** — Select **Record**, then click **Edit schema** → **Get schema from sample JSON** and paste:

```json
{
  "status": "success",
  "provisioningState": "Succeeded",
  "deploymentName": "deploy-la-rpa-japan-a1b2c3d4",
  "logicAppName": "la-rpa-japan",
  "logicAppResourceId": "/subscriptions/xxx/resourceGroups/rg-rpa-poc/providers/Microsoft.Logic/workflows/la-rpa-japan",
  "resourceGroup": "rg-rpa-poc",
  "country": "japan",
  "portalUrl": "https://portal.azure.com/#/resource/subscriptions/xxx/resourceGroups/rg-rpa-poc/providers/Microsoft.Logic/workflows/la-rpa-japan/logicApp",
  "keyVaultRoleAssignment": "success",
  "message": "Logic App 'la-rpa-japan' deployed successfully to resource group 'rg-rpa-poc'. Key Vault role assignment: success. Validate here: https://portal.azure.com/..."
}
```

6. **Save response as** — Create a variable:
   - Name: `TopicDeployResult`
   - Type: `record`

7. **Request timeout** — Set to `120000` (120 seconds). The function can take ~90s on cold start.

8. **Latency Message** (optional but recommended) — Check **Send a message** and enter:
   ```
   Deploying your Logic App, this may take a minute...
   ```
   This keeps the user informed while waiting.

### Step 6 — Add the Response Message

1. Click **+** below the HTTP Request → **Send a message**
2. In the message box, type and insert variables using the **{x}** button:

```
Logic App Created Successfully!

Name: {x} Topic.TopicDeployResult.logicAppName
Status: {x} Topic.TopicDeployResult.provisioningState
Portal: {x} Topic.TopicDeployResult.portalUrl
```

To insert each variable:
- Type the label (e.g., "Name: ")
- Click **{x}** in the toolbar
- Select **TopicDeployResult** → pick the property (e.g., `logicAppName`)

### Step 7 — Save and Test

1. Click **Save** (top right)
2. In the **Test your agent** panel (top right), type:
   ```
   Create a new Logic App
   ```
3. The agent will ask: _"Which country would you like to deploy..."_
4. Type a country: `germany`
5. Wait up to ~90 seconds (on first request / cold start)
6. The agent should respond with the Logic App name, status, and portal link

After testing, verify the Logic App was created:

```bash
az resource list --resource-group rg-<env-name> \
  --resource-type Microsoft.Logic/workflows \
  --query "[].name" -o tsv
```

### Step 8 — Publish to Teams (Optional)

Once testing is successful:

1. Click **Publish** (top right) → confirm
2. Go to **Channels** tab → click **Microsoft Teams**
3. Click **Turn on Teams** → **Open agent**
4. The agent appears as a chat bot in Teams
5. Share with your team by clicking **Availability options** and adding users/groups

### (Optional) Error Handling

For a better user experience, change **Error handling** from "Raise an error" to **Continue on error** in the HTTP Request properties. Then add a **Condition** node after the HTTP request:

- **If** `Topic.TopicDeployResult.status` equals `"success"` → show success message
- **Else** → show a friendly error: _"Something went wrong. Please try again or contact support."_

### Topic Flow Summary

```
Trigger ("The agent chooses" — Create a new Logic App)
    │
    ▼
Question: "Which country would you like to deploy the Logic App for?"
    │  Save → Topic.TopicCountry (string)
    ▼
HTTP Request: POST to Azure Function
    │  Body: { country: Topic.TopicCountry, resourceGroup: "...", subscriptionId: "..." }
    │  Save → Topic.TopicDeployResult (record)
    ▼
Message: "Logic App Created Successfully!"
    Name: Topic.TopicDeployResult.logicAppName
    Status: Topic.TopicDeployResult.provisioningState
    Portal: Topic.TopicDeployResult.portalUrl
```

---

## API Reference

### `POST /api/deploy-logic-app`

Deploys a parameterized Logic App to Azure.

**Authentication:** Function key via query parameter `?code=<KEY>`

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `country` | string | Yes | Country name — becomes part of the Logic App name (`la-rpa-<country>`) |
| `resourceGroup` | string | Yes | Target resource group for the Logic App |
| `subscriptionId` | string | Yes | Azure subscription ID |

**Response (200 OK):**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"success"` |
| `provisioningState` | string | `"Succeeded"` |
| `logicAppName` | string | e.g. `"la-rpa-japan"` |
| `resourceGroup` | string | Target resource group |
| `country` | string | Country passed in the request |
| `portalUrl` | string | Direct link to the Logic App in Azure Portal |
| `keyVaultRoleAssignment` | string | `"success"`, `"skipped"`, or `"failed: <reason>"` |
| `deploymentName` | string | Unique ARM deployment name |
| `logicAppResourceId` | string | Full Azure resource ID |
| `message` | string | Human-readable summary |

**Error responses:**

| Code | Cause |
|------|-------|
| 400 | Missing or invalid JSON body / missing required fields |
| 500 | ARM deployment failed (e.g., authorization error, template issue) |

---

## Project Structure

```
├── azure.yaml                  # azd project config
├── README.md                   # This file
├── test-payload.json           # Sample request for curl testing
├── infra/
│   ├── main.bicep              # Orchestrator (subscription-scoped)
│   ├── main.parameters.json    # Customer parameters (cross-RG, Key Vault)
│   └── modules/
│       ├── storage-account.bicep
│       ├── app-service-plan.bicep
│       ├── monitoring.bicep
│       ├── function-app.bicep
│       ├── rbac-storage.bicep
│       ├── rbac-target-rg.bicep
│       └── rbac-keyvault.bicep
└── function_app/
    ├── function_app.py         # HTTP endpoint (POST /api/deploy-logic-app)
    ├── requirements.txt        # Python dependencies
    ├── host.json               # Function runtime config
    ├── services/
    │   ├── config.py           # Environment config (location, Key Vault)
    │   └── deployer.py         # ARM deployment logic + RBAC assignment
    └── templates/
        └── logic-app-email-trigger.json  # ARM template for Logic Apps
```

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| 404 on first request | Function cold start (~90s) | Wait 1-2 minutes after deploy, or restart: `az functionapp restart` |
| 502 Bad Gateway | Python worker still initializing | Wait 60-90 seconds and retry |
| `No module named 'azure.identity'` | pip install didn't run during deploy | Ensure `WEBSITE_RUN_FROM_PACKAGE=0` is set (already in Bicep) |
| Authorization error when deploying Logic App | Function identity lacks Contributor on target RG | Add the RG to `targetResourceGroups` and run `azd provision` |
| Copilot Studio "Name isn't valid" error | Wrong variable reference in Power Fx body | Use exact variable name from "Save user response as" (e.g., `Topic.TopicCountry` not `Topic.Country`) |
| Copilot Studio timeout | Default timeout is 30s, cold start needs more | Set HTTP Request timeout to `120000` (120s) |
| Copilot Studio body not sent | Using "Edit JSON" instead of "Edit formula" | Switch to **Edit formula** for Power Fx expressions with variables |
