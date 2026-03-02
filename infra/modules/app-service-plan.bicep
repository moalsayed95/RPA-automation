// App Service Plan — B1 Linux
// Consumption and Flex Consumption plans are blocked by the subscription policy
// (no shared key access on storage accounts = no file share for Consumption)

@description('App Service Plan name')
param name string

@description('Azure region')
param location string

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: name
  location: location
  kind: 'linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  properties: {
    reserved: true // required for Linux
  }
}

@description('App Service Plan resource ID')
output id string = plan.id
