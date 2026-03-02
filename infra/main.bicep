// main.bicep — Subscription-scoped orchestrator
// Provisions all infrastructure for the RPA Logic App Deployer
//
// Usage: azd up (or az deployment sub create)
// Creates: RG, Storage, App Service Plan, Function App, Monitoring, RBAC

targetScope = 'subscription'

// ──────────────────────────────────────────────
// Parameters
// ──────────────────────────────────────────────

@description('Name of the azd environment (used as prefix for all resource names)')
@minLength(1)
@maxLength(20)
param environmentName string

@description('Primary Azure region for all resources')
param location string

@description('Existing resource groups where the Function will deploy Logic Apps. Contributor role is assigned on each.')
param targetResourceGroups array = []

@description('Full resource ID of the Key Vault for Logic App RBAC assignments. Leave empty to skip.')
param keyVaultResourceId string = ''

@description('Name of the Key Vault (used for RBAC scope). Leave empty to skip.')
param keyVaultName string = ''

@description('Resource group containing the Key Vault. Leave empty to skip.')
param keyVaultResourceGroup string = ''

// ──────────────────────────────────────────────
// Derived names
// ──────────────────────────────────────────────

var resourceGroupName = 'rg-${environmentName}'
// Storage: 3-24 chars, lowercase alphanumeric only
var rawStorageName = toLower(replace('${environmentName}stor', '-', ''))
var storageAccountName = take(rawStorageName, 24)
var functionAppName = '${environmentName}-func'
var appServicePlanName = '${environmentName}-plan'
var logAnalyticsName = '${environmentName}-log'
var appInsightsName = '${environmentName}-appi'

// Tags for azd service mapping
var tags = {
  'azd-env-name': environmentName
}

// ──────────────────────────────────────────────
// 1. Resource Group
// ──────────────────────────────────────────────

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
}

// ──────────────────────────────────────────────
// 2. Storage Account
// ──────────────────────────────────────────────

module storage 'modules/storage-account.bicep' = {
  name: 'storage'
  scope: rg
  params: {
    #disable-next-line BCP334 // environmentName @minLength(1) guarantees >= 5 chars ('Xstor')
    name: storageAccountName
    location: location
  }
}

// ──────────────────────────────────────────────
// 3. Monitoring (Log Analytics + App Insights)
// ──────────────────────────────────────────────

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    logAnalyticsName: logAnalyticsName
    appInsightsName: appInsightsName
    location: location
  }
}

// ──────────────────────────────────────────────
// 4. App Service Plan (B1 Linux)
// ──────────────────────────────────────────────

module plan 'modules/app-service-plan.bicep' = {
  name: 'plan'
  scope: rg
  params: {
    name: appServicePlanName
    location: location
  }
}

// ──────────────────────────────────────────────
// 5. Function App
// ──────────────────────────────────────────────

module functionApp 'modules/function-app.bicep' = {
  name: 'functionApp'
  scope: rg
  params: {
    name: functionAppName
    location: location
    appServicePlanId: plan.outputs.id
    storageAccountName: storage.outputs.name
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    keyVaultResourceId: keyVaultResourceId
    defaultLocation: location
    defaultResourceGroup: length(targetResourceGroups) > 0 ? string(targetResourceGroups[0]) : resourceGroupName
    tags: union(tags, { 'azd-service-name': 'api' })
  }
}

// ──────────────────────────────────────────────
// 6. RBAC — Storage roles for Function identity
// ──────────────────────────────────────────────

module storageRbac 'modules/rbac-storage.bicep' = {
  name: 'storageRbac'
  scope: rg
  params: {
    storageAccountName: storage.outputs.name
    principalId: functionApp.outputs.principalId
  }
}

// ──────────────────────────────────────────────
// 7. RBAC — Contributor on the infra RG itself
//    (so the Function can deploy Logic Apps to its own RG too)
// ──────────────────────────────────────────────

module infraRgRbac 'modules/rbac-target-rg.bicep' = {
  name: 'infraRgRbac'
  scope: rg
  params: {
    principalId: functionApp.outputs.principalId
  }
}

// ──────────────────────────────────────────────
// 8. RBAC — Contributor on each target resource group
//    (these RGs must already exist)
// ──────────────────────────────────────────────

module targetRgRbac 'modules/rbac-target-rg.bicep' = [for (rgName, i) in targetResourceGroups: {
  name: 'targetRgRbac-${i}'
  scope: resourceGroup(string(rgName))
  params: {
    principalId: functionApp.outputs.principalId
  }
}]

// ──────────────────────────────────────────────
// 9. RBAC — User Access Administrator on Key Vault
//    (optional — enables auto-assign KV Secrets User to Logic Apps)
// ──────────────────────────────────────────────

module keyVaultRbac 'modules/rbac-keyvault.bicep' = if (!empty(keyVaultName) && !empty(keyVaultResourceGroup)) {
  name: 'keyVaultRbac'
  scope: resourceGroup(keyVaultResourceGroup)
  params: {
    principalId: functionApp.outputs.principalId
    keyVaultName: keyVaultName
  }
}

// ──────────────────────────────────────────────
// Outputs — consumed by azd for code deployment
// ──────────────────────────────────────────────

@description('Function App name (used by azd deploy)')
output SERVICE_API_NAME string = functionApp.outputs.name

@description('Resource group for the Function App')
output SERVICE_API_RESOURCE_GROUP string = rg.name

@description('Function App URL')
output AZURE_FUNCTION_URL string = functionApp.outputs.url

@description('Function App managed identity principal ID')
output AZURE_FUNCTION_PRINCIPAL_ID string = functionApp.outputs.principalId
