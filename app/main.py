"""Grantha web app (FastAPI). Serves the API and the static site in web/.

    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import json
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pipeline import config

from .checker import Checker
from .ocr_input import OCRInputError, images_from_upload, ocr_images

WEB = config.ROOT / "web"
BUNDLE = Path(os.environ.get("HERITAGE_BUNDLE", config.DATA / "model" / "bundle.joblib"))
MAX_UPLOAD = 20 * 1024 * 1024
MAX_TEXT = 200_000

@lru_cache(maxsize=1)
def checker() -> Checker:
    return Checker.load(BUNDLE)


@lru_cache(maxsize=1)
def study() -> dict:
    return json.loads((WEB / "data" / "study.json").read_text(encoding="utf-8"))


@asynccontextmanager
async def lifespan(_app):
    if BUNDLE.exists():
        checker()          # load models once, so the first check is not slow
        if checker().b["feature_set"] == "B":
            checker().b["transform"].model  # load the embedding model too
    yield


app = FastAPI(title="Grantha", version="1.0", lifespan=lifespan,
              description="Check a heritage document against topic groups learned from Digital Library of India scans.")


@app.get("/api/health")
def health():
    ok = BUNDLE.exists()
    return {"status": "ok" if ok else "no-model", "documents": len(checker().docs) if ok else 0}


def _final():
    s = study()
    return s["sets"][s["final"]]


@app.get("/api/clusters")
def clusters(method: str = "hierarchical"):
    if method not in ("hierarchical", "dbscan"):
        raise HTTPException(400, "method must be hierarchical or dbscan")
    r = _final()[method]
    return [{"cluster": p["cluster"], "name": r["names"][str(p["cluster"])], "size": p["size"],
             "share": p["share"], "terms": [t["term"] for t in p["terms"][:8]], "script_mix": p["script_mix"],
             "median_year": p["median_year"]} for p in r["profiles"]]


@app.get("/api/clusters/{cluster_id}")
def cluster(cluster_id: int, method: str = "hierarchical"):
    if method not in ("hierarchical", "dbscan"):
        raise HTTPException(400, "method must be hierarchical or dbscan")
    r = _final()[method]
    for p in r["profiles"]:
        if p["cluster"] == cluster_id:
            return p | {"name": r["names"][str(cluster_id)]}
    raise HTTPException(404, "no such group")


@app.get("/api/documents/{identifier}")
def document(identifier: str):
    c = checker()
    i = c.index.get(identifier)
    if i is None:
        raise HTTPException(404, "no such document in the study sample")
    return c.docs[i] | {"hier": int(c.b["hier"]["labels"][i]), "dbscan": int(c.b["dbscan"]["labels"][i])}


@app.get("/api/study")
def study_results():
    return FileResponse(WEB / "data" / "study.json", media_type="application/json")


@app.post("/api/check")
async def check(file: UploadFile | None = File(None), text: str | None = Form(None),
                lang: str | None = Form(None)):
    if lang in ("", "auto"):
        lang = None
    if lang is not None and lang not in config.LANGUAGES:
        raise HTTPException(400, f"unknown language; use one of {list(config.LANGUAGES)} or auto")
    if file is None and not (text and text.strip()):
        raise HTTPException(400, "send a scan (image or PDF) or paste some text")
    ocr = None
    if file is not None:
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "file is larger than 20 MB")
        try:
            ocr = ocr_images(images_from_upload(data, file.filename or ""), lang)
        except OCRInputError as e:
            raise HTTPException(400, str(e)) from e
        raw, script, conf = ocr["text"], ocr["script"], ocr["ocr_conf"]
    else:
        raw = text[:MAX_TEXT]
        script = config.LANGUAGES[lang]["script"] if lang else None
        conf = None
    result = checker().check_text(raw, script=script, ocr_conf=conf)
    result["input"] = "scan" if file is not None else "text"
    if ocr:
        result["ocr"] = {k: ocr[k] for k in ("model", "pages", "script_detected")} | {"preview": ocr["text"][:1200]}
    return result


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
