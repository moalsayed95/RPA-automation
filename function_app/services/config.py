"""Environment configuration for Logic App deployment."""
import os


# Azure location for Logic Apps
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "westeurope")

# Default resource group for Logic App deployments
DEFAULT_RESOURCE_GROUP = os.getenv("DEFAULT_RESOURCE_GROUP", "")

# Key Vault resource ID for role assignment
# The Logic App's managed identity needs Key Vault Secrets User on this resource
KEY_VAULT_RESOURCE_ID = os.getenv(
    "KEY_VAULT_RESOURCE_ID",
    ""  # Set via app setting, e.g. /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<name>
)

# Built-in role definition ID for "Key Vault Secrets User"
# This is a fixed Azure GUID: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles
KEY_VAULT_SECRETS_USER_ROLE_ID = "4633458b-17de-408a-b874-0445c86b69e6"
