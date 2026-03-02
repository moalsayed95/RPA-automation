// RBAC — User Access Administrator on Key Vault
// Allows the Function App to assign "Key Vault Secrets User" to Logic App identities
//
// This module is deployed at the scope of the RG containing the Key Vault.
// The deploying user must have Owner or User Access Administrator on that RG.

@description('Principal ID of the Function App managed identity')
param principalId string

@description('Name of the Key Vault resource')
param keyVaultName string

// Built-in User Access Administrator role GUID
var userAccessAdminRoleId = '18d7d88d-d35e-4fb5-a5c3-7773c20a72d9'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource userAccessAdmin 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, principalId, userAccessAdminRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', userAccessAdminRoleId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
