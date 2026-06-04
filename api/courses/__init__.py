import os, json
import azure.functions as func
from azure.storage.blob import BlobServiceClient

CONTAINER = "courses"

def main(req: func.HttpRequest) -> func.HttpResponse:
    cs = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not cs:
        # storage not configured yet -> behave as empty (front end uses built-in demo courses)
        return func.HttpResponse("[]", status_code=200, mimetype="application/json")
    try:
        svc = BlobServiceClient.from_connection_string(cs)
        try:
            svc.create_container(CONTAINER)
        except Exception:
            pass
        cc = svc.get_container_client(CONTAINER)
        out = []
        for b in cc.list_blobs():
            if b.name.endswith(".json"):
                try:
                    data = cc.download_blob(b.name).readall()
                    out.append(json.loads(data))
                except Exception:
                    pass
        out.sort(key=lambda c: c.get("createdAt", 0))
        return func.HttpResponse(json.dumps(out, ensure_ascii=False),
                                 status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(json.dumps({"error": str(e)}),
                                 status_code=500, mimetype="application/json")
