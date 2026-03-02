# RPA - Logic App Deployment Agent
## Complete Vision & Technical Reference

---

## 1. Customer Problem

The RPA team operates a fully event-driven automation landscape using **UiPath** and **Azure Logic Apps**. Every automation (email-triggered, SharePoint-triggered, etc.) requires a **dedicated Logic App per country/organization** (e.g., Japan, Italy, Spain).

Because the process must scale to **100+ organizations**, the current manual setup is slow, repetitive, and error-prone.

### General Pain Points
- For every new country/org, the team must manually:
  - Clone a Logic App template from the `templates-rg` resource group.
  - Fill in mailbox or SharePoint parameters.
  - Configure trigger specifics (email folder, subject filter, underlying event type).
  - Retrieve secrets from Key Vault and map headers for UiPath.
  - Insert correct UiPath queue names, folder paths, and environment (DEV/PROD) URLs.
  - **Move the Logic App** from `templates-rg` into the correct target resource group (e.g., `finance-rg`).
  - Validate connectors and dependencies.
- These steps take time, require high attention, and are repeated dozens of times.

---

## 2. Azure Infrastructure Context

### Resource Groups
| Resource Group | Purpose |
|---|---|
| `templates-rg` | Contains the **source Logic App templates** that get cloned |
| `finance-rg` | Target resource group for finance-related Logic Apps |
| `rpa-dev-rg` | Dev environment RPA resource group |
| *(others)* | Additional target resource groups per department/function |

### Logic App Tier
- **Consumption tier** (not Standard)

### Region
- **West Europe** (default)

---

## 3. Logic App Template Patterns

There are **two main trigger patterns**, but the downstream steps are identical.

### Pattern A: Email Trigger
**Trigger**: "When a new email arrives in a shared mailbox (V2)"
- Shared mailbox address (e.g., `rpa-japan@contoso.com`)
- Specific folder (e.g., `/invoices`)
- Subject filter (optional, per use case)

### Pattern B: SharePoint Trigger
**Trigger**: "When a file is created in a folder" (or similar)
- SharePoint site URL
- Document library / folder path
- File type filter (optional)

### Common Steps (Both Patterns)
After the trigger fires, the Logic App executes the same sequence:

#### Step 1 - Get Secret: Client ID
- **Action**: Get secret from Azure Key Vault
- **Secret name**: UiPath Client ID (varies by environment)

#### Step 2 - Get Secret: Client Secret
- **Action**: Get secret from Azure Key Vault
- **Secret name**: UiPath Client Secret (varies by environment)

#### Step 3 - HTTP Authenticate
- **Action**: HTTP POST to UiPath Identity endpoint
- **URL**: `https://cloud.uipath.com/identity/connect/token`
- **Body**: `grant_type=client_credentials&client_id={clientId}&client_secret={clientSecret}&scope=OR.Queues`
- **Response**: Bearer token for subsequent API calls

#### Step 4 - Parse JSON
- Parse the auth response to extract the `access_token`

#### Step 5 - Initialize Variable
- Store the bearer token or other runtime data

#### Step 6 - HTTP Create Queue Item
- **Action**: HTTP POST to UiPath Orchestrator
- **URL**: `https://cloud.uipath.com/{TENANT}/{ENV}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem`
  - `{TENANT}` = your UiPath Cloud tenant name
  - `{ENV}` = `DEV` or `PROD`
- **Method**: POST
- **Headers**:
  - `Authorization`: `Bearer {access_token}`
  - `Content-Type`: `application/json`
  - `X-UIPATH-FolderPath`: e.g., `Finance/HQ` (varies per department/country)
- **Body**:
  ```json
  {
    "itemData": {
      "Name": "{QUEUE_NAME}",
      "Priority": "Normal",
      "SpecificContent": {
        "Attribute1": "{PLACEHOLDER}",
        "Attribute 2": "{PLACEHOLDER}"
      }
    }
  }
  ```
  - `Name`: The UiPath queue name (e.g., `invoices_emails_japan`)
  - `SpecificContent`: Variable attributes passed to the robot (e.g., Subject, MessageID, file path - depends on the trigger and use case)

---

## 4. Variable Parts Per Deployment

Every new Logic App deployment requires these values to be customized:

| Parameter | Example | Varies By |
|---|---|---|
| Trigger type | Email / SharePoint | Use case |
| Shared mailbox | `rpa-japan@contoso.com` | Country |
| Mail folder | `/invoices` | Use case |
| Subject filter | *(optional)* | Use case |
| SharePoint site URL | `https://contoso.sharepoint.com/sites/finance` | Department |
| SharePoint folder | `/Invoices/Japan` | Country |
| Key Vault name | `kv-rpa-dev` | Environment |
| UiPath Client ID secret name | `UiPathClientId-DEV` | Environment |
| UiPath Client Secret secret name | `UiPathClientSecret-DEV` | Environment |
| UiPath environment | `DEV` / `PROD` | Environment |
| UiPath Orchestrator URL | `https://cloud.uipath.com/{TENANT}/DEV/orchestrator_/...` | Environment |
| UiPath folder path | `Finance/HQ` | Department/Country |
| UiPath queue name | `invoices_emails_japan` | Country/Use case |
| Queue attributes (SpecificContent) | Subject, MessageID, file name | Use case |
| Target resource group | `finance-rg` | Department |
| Logic App name | `rpa-999-test-d` | Convention |

---

## 5. The Desired Solution

### Architecture

```
User (Teams) --> Copilot Studio Agent --> Azure Function --> ARM Deployment --> Logic App in target RG
```

### Agent Capabilities

The agent (Copilot Studio, deployed to Microsoft Teams) will:

1. **Collect inputs** from the user via conversation:
   - Trigger type (Email / SharePoint)
   - Country/Organization
   - Trigger-specific parameters (mailbox, folder, subject OR SharePoint site, library)
   - UiPath queue name
   - UiPath folder path (e.g., `Finance/HQ`)
   - Queue attributes to pass (e.g., Subject, MessageID)
   - Environment (DEV / PROD)
   - Target resource group (e.g., `finance-rg`)

2. **Generate a fully parameterized Logic App** by injecting inputs into a base ARM template

3. **Deploy directly to the target resource group** - no cloning from `templates-rg`, no manual move

4. **Return results** including:
   - Success/failure status
   - Logic App name
   - **Clickable Azure Portal URL** for immediate validation by IT staff

### Key Design Decision: No Clone-and-Move
The current manual workflow clones a template from `templates-rg` and then moves it to the target resource group. The agent approach **eliminates this entirely** by deploying directly to the target resource group from the start via ARM template.

### Managed Identity & Key Vault Access
Each deployed Logic App requires:
1. **System-assigned managed identity** enabled on the Logic App
2. **Key Vault Secrets User** role assigned to that identity on the Key Vault (e.g., `kv-rpa-dev`)

This allows the Logic App to read UiPath Client ID and Client Secret from Key Vault without storing credentials. The agent automates both steps:
- The ARM template enables the managed identity at deployment time
- The Azure Function assigns the Key Vault role post-deployment using the identity's principal ID


### Access Control
- Only **IT staff** will have access to the agent
- IT staff are responsible for validating the deployed Logic App via the portal link

---

## 6. Technical Implementation

### Components

| Component | Technology | Purpose |
|---|---|---|
| Agent UI | Copilot Studio (Teams) | Conversational input collection |
| Backend API | Azure Function (Python) | Template parameterization & ARM deployment |
| Templates | ARM JSON | Base Logic App definitions (email & SharePoint variants) |
| Identity | Managed Identity | Azure Function authenticates to ARM with Contributor role |
| Role Assignment | Azure RBAC | Post-deployment: assign Key Vault Secrets User to Logic App identity |
| Deployment | Azure Resource Manager | Creates Logic App in target resource group |

### Azure Function Endpoints
- **POST `/api/deploy-logic-app`** - Takes deployment parameters, deploys Logic App, returns portal URL
- Auth: Function key (called by Copilot Studio HTTP action)

### Agent Topic Flow
1. Trigger phrases: "Deploy a logic app", "Onboard a new country", etc.
2. Question nodes collect all required parameters
3. Confirmation message shows summary
4. HTTP action calls Azure Function
5. Response message shows status + clickable portal link

---

## 7. Phased Delivery

### Phase 1 - PoC (Current)
- Blank Logic App deployment (no triggers, no UiPath steps)
- Agent asks: Country, Resource Group, Subscription ID
- Validates the full pipeline: Teams --> Agent --> Function --> ARM --> Azure
- Returns portal URL for validation

### Phase 2 - Email Template
- Full email trigger Logic App with all UiPath steps
- Agent asks all parameters (mailbox, folder, queue, environment, attributes, etc.)
- ARM template includes: trigger --> Key Vault --> auth --> queue item creation

### Phase 3 - SharePoint Template
- SharePoint trigger variant
- Same downstream steps as email template

### Phase 4 - Enhancements
- List existing Logic Apps ("Show me all Logic Apps in Japan")
- Status checking ("What's the status of the Italy deployment?")
- Bulk onboarding (deploy multiple countries at once)
- Approval workflow before deployment
- Tagging resources (environment, country, team)

---

## 8. UiPath Integration Details

### Orchestrator URLs
- **DEV**: `https://cloud.uipath.com/{TENANT}/DEV/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem`
- **PROD**: `https://cloud.uipath.com/{TENANT}/PROD/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem`

### Identity URL
- `https://cloud.uipath.com/identity/connect/token`

### Folder Path Convention
- `X-UIPATH-FolderPath` header, e.g., `Finance/HQ`

### Queue Item Structure
```json
{
  "itemData": {
    "Name": "{queue_name}",
    "Priority": "Normal",
    "SpecificContent": {
      "{attribute_key}": "{attribute_value}"
    }
  }
}
```

### Robot Side
- Robot picks up the queue item
- Uses the passed attributes (e.g., MessageID) to fetch the source data
- Processes the item (extract attachments, metadata, etc.)

---

## 9. Open Questions for Customer

- [ ] Exact Key Vault names for DEV and PROD
- [ ] Key Vault secret naming convention (e.g., `UiPathClientId-DEV` or `UiPathClientId`)
- [ ] Full list of target resource groups (beyond `finance-rg`)
- [ ] Logic App naming convention (e.g., `rpa-{number}-{process}-d`)
- [ ] Azure AD tenant domain (for portal URL: `contoso.com` or `contoso.onmicrosoft.com`)
- [ ] SharePoint trigger details (site URL pattern, library structure)
- [ ] List of standard queue attributes per use case
- [ ] Do shared API connections (Office 365, Key Vault) already exist or need to be created per deployment?
- [x] Key Vault name: `kv-rpa-dev` (confirmed from screenshot)
- [x] Subscription name: _(confirmed from screenshot)_
- [x] Logic Apps use system-assigned managed identity with Key Vault Secrets User role (confirmed from screenshot)
- [ ] Should tags be applied to deployed Logic Apps?
- [ ] JSON export of an existing working Logic App (Code View) for exact template matching

---

## 10. Why This Matters

### Current State (Manual)
- Does not scale to 100+ organizations
- Slow and repetitive (hours per country)
- High risk of human error
- Clone --> Move --> Modify --> Validate per deployment
- Consumes time that could be used for innovation

### Future State (Agent-Driven)
- Standardized Logic App creation
- Deploys directly to target resource group (no clone-and-move)
- Consistency enforced across all countries
- Minutes per deployment instead of hours
- IT staff validates via clickable portal link
- Foundation for expanded agent capabilities (status, troubleshooting, bulk ops)
