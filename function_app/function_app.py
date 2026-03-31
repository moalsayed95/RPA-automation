import azure.functions as func
import json
import logging

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="deploy-logic-app", methods=["POST"])
def deploy_logic_app(req: func.HttpRequest) -> func.HttpResponse:
    """
    Deploys a blank Logic App to Azure.
    Called by Copilot Studio agent via HTTP action.

    Expected JSON body:
    {
        "country": "japan",
        "resourceGroup": "rg-rpa-japan",
        "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    }
    """
    logging.info("Deploy Logic App function triggered.")

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json"
        )

    # Validate required fields
    required_fields = ["country", "resourceGroup", "subscriptionId"]
    missing = [f for f in required_fields if f not in req_body or not req_body[f]]
    if missing:
        return func.HttpResponse(
            json.dumps({"error": f"Missing required fields: {', '.join(missing)}"}),
            status_code=400,
            mimetype="application/json"
        )

    try:
        from services.deployer import LogicAppDeployer
        deployer = LogicAppDeployer()
        result = deployer.deploy(req_body)

        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Deployment failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Deployment failed: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )


# ──────────────────────────────────────────────
# Mock UiPath endpoints — simulate UiPath Cloud
# Orchestrator for demo purposes. Replace with
# real UiPath URLs when going to production.
# ──────────────────────────────────────────────

@app.route(route="mock/uipath/auth", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def mock_uipath_auth(req: func.HttpRequest) -> func.HttpResponse:
    """Mock UiPath authentication endpoint. Returns a fake bearer token."""
    logging.info("Mock UiPath auth endpoint called.")
    return func.HttpResponse(
        json.dumps({
            "access_token": "mock-bearer-token-for-demo-only",
            "token_type": "Bearer",
            "expires_in": 3600
        }),
        status_code=200,
        mimetype="application/json"
    )


@app.route(route="mock/uipath/queue", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def mock_uipath_queue(req: func.HttpRequest) -> func.HttpResponse:
    """Mock UiPath Add Queue Item endpoint. Accepts the payload and returns success."""
    logging.info("Mock UiPath queue endpoint called.")

    # Try to read the request body for realistic response
    try:
        body = req.get_json()
        item_name = body.get("itemData", {}).get("Name", "Unknown")
    except (ValueError, AttributeError):
        item_name = "Unknown"

    return func.HttpResponse(
        json.dumps({
            "Id": 12345,
            "Status": "New",
            "Priority": "Normal",
            "Name": item_name,
            "message": "Mock queue item created successfully"
        }),
        status_code=201,
        mimetype="application/json"
    )
