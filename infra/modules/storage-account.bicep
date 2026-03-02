// Storage Account — identity-based access, no shared keys
// Matches subscription policy: allowSharedKeyAccess = false

@description('Storage account name (3-24 chars, lowercase alphanumeric only)')
@minLength(3)
@maxLength(24)
param name string

@description('Azure region')
param location string

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }
}

@description('Storage account name')
output name string = storageAccount.name

@description('Storage account resource ID')
output id string = storageAccount.id
