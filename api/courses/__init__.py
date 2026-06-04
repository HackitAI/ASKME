import os, json
import azure.functions as func
from azure.storage.blob import BlobServiceClient

CONTAINER = "courses"


def _svc():
    cs = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not cs:
        return None
    svc = BlobServiceClient.from_connection_string(cs)
    try:
        svc.create_container(CONTAINER)
    except Exception:
        pass
    return svc


def main(req: func.HttpRequest) -> func.HttpResponse:
    svc = _svc()
    if svc is None:
        if req.method == "DELETE":
            return func.HttpResponse(json.dumps({"error": "storage not configured"}),
                                     status_code=500, mimetype="application/json")
        return func.HttpResponse("[]", status_code=200, mimetype="application/json")

    cc = svc.get_container_client(CONTAINER)

    if req.method == "DELETE":
        cid = req.params.get("id")
        if not cid:
            return func.HttpResponse(json.dumps({"error": "id required"}),
                                     status_code=400, mimetype="application/json")
        for blob in (cid + ".json", cid + ".pdf"):
            try:
                cc.delete_blob(blob)
            except Exception:
                pass
        return func.HttpResponse(json.dumps({"deleted": cid}),
                                 status_code=200, mimetype="application/json")

    try:
        out = []
        for b in cc.list_blobs():
            if b.name.endswith(".json"):
                try:
                    out.append(json.loads(cc.download_blob(b.name).readall()))
                except Exception:
                    pass
        out.sort(key=lambda c: c.get("createdAt", 0))
        return func.HttpResponse(json.dumps(out, ensure_ascii=False),
                                 status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(json.dumps({"error": str(e)}),
                                 status_code=500, mimetype="application/json")
