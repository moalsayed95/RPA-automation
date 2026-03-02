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
