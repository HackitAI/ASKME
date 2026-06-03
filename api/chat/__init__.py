import os, json, urllib.request, urllib.error
import azure.functions as func

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        endpoint   = os.environ["AOAI_ENDPOINT"].rstrip("/")
        deployment = os.environ["AOAI_DEPLOYMENT"]
        key        = os.environ["AOAI_KEY"]
    except KeyError as e:
        return func.HttpResponse(
            json.dumps({"error": f"Missing app setting: {e}"}),
            status_code=500, mimetype="application/json")
    ver = os.environ.get("AOAI_API_VERSION", "2024-08-01-preview")
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={ver}"

    body = req.get_body()  # the {messages, max_completion_tokens} payload from the page
    r = urllib.request.Request(url, data=body, method="POST")
    r.add_header("Content-Type", "application/json")
    r.add_header("api-key", key)
    try:
        with urllib.request.urlopen(r) as resp:
            data, code = resp.read(), resp.status
    except urllib.error.HTTPError as e:
        data, code = e.read(), e.code
    except Exception as e:
        data, code = json.dumps({"error": str(e)}).encode(), 502
    return func.HttpResponse(data, status_code=code, mimetype="application/json")
