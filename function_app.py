import azure.functions as func
import logging
from binance.client import Client

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="trigger_bot")
def http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. this is after CI/CD",
             status_code=200
        )
