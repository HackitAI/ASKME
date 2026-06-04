import os, json, base64, io
import azure.functions as func
from azure.storage.blob import BlobServiceClient

CONTAINER = "courses"


def _client():
    cs = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    svc = BlobServiceClient.from_connection_string(cs)
    try:
        svc.create_container(CONTAINER)
    except Exception:
        pass
    return svc


def _chunks_from_text(text, max_len=900):
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if buf and len(buf) + len(p) > max_len:
            chunks.append(buf.strip()); buf = ""
        buf += (" " if buf else "") + p
    if buf.strip():
        chunks.append(buf.strip())
    chunks = [c for c in chunks if len(c) >= 40] or chunks
    return chunks


def _materials_from_pdf(pdf_bytes, name, start_idx=0):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    mats, idx = [], start_idx
    for pi, page in enumerate(reader.pages):
        txt = page.extract_text() or ""
        if not txt.strip():
            continue
        for c in _chunks_from_text(txt):
            mats.append({"id": f"m{idx}", "title": f"{name} — pag. {pi+1}",
                         "ref": f"pag. {pi+1}", "content": c})
            idx += 1
            if idx >= start_idx + 60:
                return mats
    return mats


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except Exception:
        return func.HttpResponse(json.dumps({"error": "invalid JSON"}),
                                 status_code=400, mimetype="application/json")

    course = body.get("course") or {}
    cid = course.get("id")
    if not cid or not (course.get("name") or "").strip():
        return func.HttpResponse(json.dumps({"error": "course id and name required"}),
                                 status_code=400, mimetype="application/json")

    try:
        mats = course.get("materials") or []
        pdf_b64 = body.get("pdf")
        pdf_bytes = None
        if pdf_b64:
            if "," in pdf_b64[:64]:
                pdf_b64 = pdf_b64.split(",", 1)[1]
            pdf_bytes = base64.b64decode(pdf_b64)
            mats = (mats + _materials_from_pdf(pdf_bytes, course.get("name"), len(mats)))[:120]
        course["materials"] = mats

        svc = _client()
        cc = svc.get_container_client(CONTAINER)
        cc.upload_blob(cid + ".json", json.dumps(course, ensure_ascii=False), overwrite=True)
        if pdf_bytes:
            cc.upload_blob(cid + ".pdf", pdf_bytes, overwrite=True)

        return func.HttpResponse(json.dumps(course, ensure_ascii=False),
                                 status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(json.dumps({"error": str(e)}),
                                 status_code=500, mimetype="application/json")
