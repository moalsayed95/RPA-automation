"""Logic App deployer service - handles ARM template deployment to Azure."""
import json
import logging
import uuid
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.authorization import AuthorizationManagementClient

from .config import DEFAULT_LOCATION, KEY_VAULT_RESOURCE_ID, KEY_VAULT_SECRETS_USER_ROLE_ID, FUNCTION_APP_HOSTNAME

logger = logging.getLogger(__name__)

# Path to ARM templates (inside function_app/templates/)
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


class LogicAppDeployer:
    """Deploys a blank Azure Logic App using an ARM template."""

    def __init__(self):
        self.credential = DefaultAzureCredential()

    def _get_resource_client(self, subscription_id: str) -> ResourceManagementClient:
        return ResourceManagementClient(self.credential, subscription_id)

    def _get_auth_client(self, subscription_id: str) -> AuthorizationManagementClient:
        return AuthorizationManagementClient(self.credential, subscription_id)

    def _build_logic_app_name(self, country: str) -> str:
        """Generate a standardized Logic App name."""
        country_clean = country.lower().replace(" ", "-")
        return f"la-rpa-{country_clean}"

    def _resolve_location(self, client: ResourceManagementClient, resource_group: str, fallback: str) -> str:
        """Get the location of an existing resource group, or use the fallback for new ones."""
        try:
            rg = client.resource_groups.get(resource_group)
            logger.info(f"Resource group '{resource_group}' exists in '{rg.location}'")
            return rg.location
        except Exception:
            logger.info(f"Resource group '{resource_group}' not found, using fallback location '{fallback}'")
            return fallback

    def _load_template(self) -> dict:
        """Load the ARM template."""
        template_path = TEMPLATE_DIR / "logic-app-email-trigger.json"
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        with open(template_path, "r") as f:
            return json.load(f)

    def _build_mock_url(self, path: str) -> str:
        """Build a mock UiPath URL using the Function App's own hostname."""
        return f"https://{FUNCTION_APP_HOSTNAME}/api/mock/uipath/{path}"

    def deploy(self, params: dict) -> dict:
        """
        Deploy a Logic App with UiPath workflow to Azure.

        Expects:
            - country: str
            - resourceGroup: str
            - subscriptionId: str
            - uipathFolderPath: str (e.g. 'Finance/HQ')
            - queueItemName: str (e.g. 'RPA-822: Invoices Emails')
            - uipathEnvironment: str (optional, 'dev' or 'prod')

        Returns a dict with deployment status and resource details.
        """
        subscription_id = params["subscriptionId"]
        resource_group = params["resourceGroup"]
        country = params["country"]

        logic_app_name = self._build_logic_app_name(country)
        # Truncate to 80 chars (Azure resource name limit)
        logic_app_name = logic_app_name[:80]

        logger.info(f"Starting deployment for {country} to {resource_group}")

        # Resolve location: use existing RG's location, fall back to default
        client = self._get_resource_client(subscription_id)
        location = self._resolve_location(client, resource_group, params.get("location", DEFAULT_LOCATION))

        # Load template
        template = self._load_template()

        # Build parameters for ARM template
        arm_parameters = {
            "logicAppName": {"value": logic_app_name},
            "location": {"value": location},
            "uipathAuthUrl": {"value": params.get("uipathAuthUrl", self._build_mock_url("auth"))},
            "uipathQueueUrl": {"value": params.get("uipathQueueUrl", self._build_mock_url("queue"))},
            "uipathFolderPath": {"value": params.get("uipathFolderPath", "Finance/HQ")},
            "queueItemName": {"value": params.get("queueItemName", "RPA-Queue-Item")},
        }

        # Generate a unique deployment name
        deployment_name = f"deploy-{logic_app_name}-{uuid.uuid4().hex[:8]}"

        # Ensure resource group exists (uses the resolved location)
        client.resource_groups.create_or_update(
            resource_group,
            {"location": location}
        )

        # Start deployment
        logger.info(f"Deploying {logic_app_name} as {deployment_name}")
        deployment = client.deployments.begin_create_or_update(
            resource_group,
            deployment_name,
            {
                "properties": {
                    "template": template,
                    "parameters": arm_parameters,
                    "mode": "Incremental",
                }
            }
        )

        # Wait for completion
        result = deployment.result()
        logger.info(f"Deployment completed: {result.properties.provisioning_state}")

        # Extract outputs
        outputs = result.properties.outputs or {}
        resource_id = outputs.get("logicAppResourceId", {}).get("value", "")
        principal_id = outputs.get("principalId", {}).get("value", "")
        trigger_url = outputs.get("triggerUrl", {}).get("value", "")

        # Assign Key Vault Secrets User role to the Logic App's managed identity
        role_assignment_status = "skipped"
        if principal_id and KEY_VAULT_RESOURCE_ID:
            role_assignment_status = self._assign_keyvault_role(
                subscription_id, principal_id
            )

        # Build Azure Portal URL for quick validation
        portal_url = (
            f"https://portal.azure.com/#/resource"
            f"/subscriptions/{subscription_id}"
            f"/resourceGroups/{resource_group}"
            f"/providers/Microsoft.Logic/workflows/{logic_app_name}/logicApp"
        )

        return {
            "status": "success",
            "provisioningState": result.properties.provisioning_state,
            "deploymentName": deployment_name,
            "logicAppName": logic_app_name,
            "logicAppResourceId": resource_id,
            "resourceGroup": resource_group,
            "country": country,
            "portalUrl": portal_url,
            "triggerUrl": trigger_url,
            "keyVaultRoleAssignment": role_assignment_status,
            "message": (
                f"Logic App '{logic_app_name}' deployed successfully to "
                f"resource group '{resource_group}'. "
                f"Key Vault role assignment: {role_assignment_status}. "
                f"Trigger URL: {trigger_url}. "
                f"Validate here: {portal_url}"
            ),
        }

    def _assign_keyvault_role(self, subscription_id: str, principal_id: str) -> str:
        """
        Assign Key Vault Secrets User role to the Logic App's managed identity
        on the Key Vault resource.
        """
        try:
            auth_client = self._get_auth_client(subscription_id)
            role_assignment_name = str(uuid.uuid4())

            # Role definition ID for Key Vault Secrets User
            role_definition_id = (
                f"/subscriptions/{subscription_id}"
                f"/providers/Microsoft.Authorization/roleDefinitions"
                f"/{KEY_VAULT_SECRETS_USER_ROLE_ID}"
            )

            auth_client.role_assignments.create(
                scope=KEY_VAULT_RESOURCE_ID,
                role_assignment_name=role_assignment_name,
                parameters={
                    "properties": {
                        "role_definition_id": role_definition_id,
                        "principal_id": principal_id,
                        "principal_type": "ServicePrincipal",
                    }
                },
            )
            logger.info(f"Key Vault role assigned to principal {principal_id}")
            return "success"
        except Exception as e:
            logger.error(f"Key Vault role assignment failed: {str(e)}")
            return f"failed: {str(e)}"
