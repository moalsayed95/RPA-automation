// RBAC — Contributor on a target resource group
// Allows the Function App to create/manage Logic Apps in this RG
//
// This module is deployed at the scope of the TARGET resource group.
// The target RG must already exist.

@description('Principal ID of the Function App managed identity')
param principalId string

// Built-in Contributor role GUID
var contributorRoleId = 'b24988ac-6180-42a0-ab88-20f7382dd24c'

resource contributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, principalId, contributorRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', contributorRoleId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
