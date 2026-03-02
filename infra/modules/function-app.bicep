// Function App — Python 3.12, Linux, system-assigned managed identity
// All app settings wired here so nothing needs manual configuration

@description('Function App name (must be globally unique)')
param name string

@description('Azure region')
param location string

@description('App Service Plan resource ID')
param appServicePlanId string

@description('Storage account name for identity-based connection')
param storageAccountName string

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('Key Vault resource ID for Logic App role assignments')
param keyVaultResourceId string = ''

@description('Default Azure region for Logic App deployments')
param defaultLocation string

@description('Default resource group for Logic App deployments')
param defaultResourceGroup string

@description('Tags to apply (includes azd-service-name for deployment mapping)')
param tags object = {}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: name
  location: location
  kind: 'functionapp,linux'
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlanId
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      pythonVersion: '3.12'
      minTlsVersion: '1.2'
      appSettings: [
        // --- Functions runtime ---
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'AzureWebJobsFeatureFlags', value: 'EnableWorkerIndexing' }

        // --- Identity-based storage connection (no shared keys) ---
        { name: 'AzureWebJobsStorage__accountName', value: storageAccountName }

        // --- Monitoring ---
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }

        // --- Remote build (required for Python pip install on Linux) ---
        // WEBSITE_RUN_FROM_PACKAGE=0 forces filesystem deploy so Oryx can pip install
        { name: 'WEBSITE_RUN_FROM_PACKAGE', value: '0' }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'ENABLE_ORYX_BUILD', value: 'true' }

        // --- App-specific config (read by services/config.py) ---
        { name: 'DEFAULT_LOCATION', value: defaultLocation }
        { name: 'DEFAULT_RESOURCE_GROUP', value: defaultResourceGroup }
        { name: 'KEY_VAULT_RESOURCE_ID', value: keyVaultResourceId }
      ]
    }
  }
}

@description('Function App name')
output name string = functionApp.name

@description('Function App default hostname')
output hostname string = functionApp.properties.defaultHostName

@description('Function App URL')
output url string = 'https://${functionApp.properties.defaultHostName}'

@description('System-assigned managed identity principal ID')
output principalId string = functionApp.identity.principalId
