import os, json, base64, io, time, random
import azure.functions as func
from azure.storage.blob import BlobServiceClient

CONTAINER = "courses"
PALETTE = [["#1E2761","#3CBEE1"],["#26305C","#5B7FB9"],["#3A2E5C","#8E7CC3"],
           ["#7A2E3B","#E0707E"],["#1E5C57","#4FB6A8"],["#14324A","#2BA3C4"],["#6B3E1E","#D9A05B"]]


def _client():
    cs = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    svc = BlobServiceClient.from_connection_string(cs)
    try:
        svc.create_container(CONTAINER)
    except Exception:
        pass
    return svc


def _chunks_from_text(text, max_len=900):
    """Group paragraphs into ~max_len-char chunks."""
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if buf and len(buf) + len(p) > max_len:
            chunks.append(buf.strip()); buf = ""
        buf += (" " if buf else "") + p
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def _materials_from_pdf(pdf_bytes, name):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    mats, idx = [], 0
    for pi, page in enumerate(reader.pages):
        txt = page.extract_text() or ""
        if not txt.strip():
            continue
        for c in _chunks_from_text(txt):
            mats.append({"id": f"m{idx}", "title": f"{name} — pag. {pi+1}",
                         "ref": f"pag. {pi+1}", "content": c})
            idx += 1
            if idx >= 60:
                return mats
    return mats


def _materials_from_text(text, name):
    return [{"id": f"m{i}", "title": f"{name} — fragment {i+1}",
             "ref": f"fragment {i+1}", "content": c}
            for i, c in enumerate(_chunks_from_text(text)[:40])]


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except Exception:
        return func.HttpResponse(json.dumps({"error": "invalid JSON"}),
                                 status_code=400, mimetype="application/json")

    name = (body.get("name") or "").strip()
    if not name:
        return func.HttpResponse(json.dumps({"error": "name required"}),
                                 status_code=400, mimetype="application/json")
    tag = (body.get("tag") or "General").strip()
    desc = (body.get("description") or "").strip()
    text = (body.get("text") or "").strip()
    pdf_b64 = body.get("pdf")

    try:
        svc = _client()
        cc = svc.get_container_client(CONTAINER)

        materials, pdf_bytes = [], None
        if pdf_b64:
            if "," in pdf_b64[:64]:           # strip "data:application/pdf;base64,"
                pdf_b64 = pdf_b64.split(",", 1)[1]
            pdf_bytes = base64.b64decode(pdf_b64)
            materials = _materials_from_pdf(pdf_bytes, name)
        if not materials and text:
            materials = _materials_from_text(text, name)
        if not materials:
            materials = [{"id": "m0", "title": name, "ref": "descriere",
                          "content": desc or name}]

        count = sum(1 for b in cc.list_blobs() if b.name.endswith(".json"))
        col = PALETTE[count % len(PALETTE)]
        cid = "c" + str(int(time.time() * 1000)) + str(random.randint(10, 99))
        course = {
            "id": cid, "name": name, "tag": tag, "progress": 0,
            "c1": col[0], "c2": col[1],
            "description": desc or "Curs încărcat de profesor.",
            "materials": materials,
            "docs": [["Document încărcat", "PDF" if pdf_bytes else "text"]],
            "createdAt": int(time.time()),
        }
        cc.upload_blob(cid + ".json", json.dumps(course, ensure_ascii=False), overwrite=True)
        if pdf_bytes:
            cc.upload_blob(cid + ".pdf", pdf_bytes, overwrite=True)

        return func.HttpResponse(json.dumps(course, ensure_ascii=False),
                                 status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(json.dumps({"error": str(e)}),
                                 status_code=500, mimetype="application/json")
