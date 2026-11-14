"""Feature 3: scan quality triage (docs/superpowers/specs/api-contract.md). Rules live in pipeline/triage.py.

Covers every harvested book (bundle key `triage_books`), not only the model's books; `dbscan_noise` is null
for books that are not in the model.
"""
from fastapi import APIRouter, HTTPException

from app.checker import MIN_TOKENS_CONFIDENT
from pipeline import triage

router = APIRouter()
MAX_LIMIT = 500


def _books(c) -> list[dict]:
    books = c.b.get("triage_books")
    if books is None:   # a bundle exported before triage existed: the model's own books only
        books = [{"identifier": d["identifier"], "title": d.get("title"), "lang_tag": d.get("lang_tag"),
                  "mean_conf": d.get("mean_conf"), "text_source": d.get("text_source"),
                  "n_tokens": d.get("n_tokens"), "usable": True} for d in c.docs]
    return books


def _assess(c, book: dict) -> dict:
    i = c.index.get(book["identifier"])
    noise = None if i is None else bool(c.b["dbscan"]["labels"][i] == -1)
    signals = {"mean_conf": book.get("mean_conf"), "text_source": book.get("text_source"),
               "n_tokens": book.get("n_tokens"), "dbscan_noise": noise}
    v = triage.verdict(signals["mean_conf"], signals["text_source"], signals["n_tokens"], noise,
                       min_tokens=MIN_TOKENS_CONFIDENT)
    return {"identifier": book["identifier"], **v, "signals": signals}


@router.get("/api/triage/{identifier}")
def triage_one(identifier: str):
    import app.main as m
    c = m.checker()
    for b in _books(c):
        if b["identifier"] == identifier:
            return _assess(c, b)
    raise HTTPException(404, "no such document in the study sample")


@router.get("/api/triage")
def triage_all(lang: str | None = None, verdict: str | None = None, limit: int = 100, offset: int = 0):
    import app.main as m
    if not 1 <= limit <= MAX_LIMIT:
        raise HTTPException(400, f"limit must be between 1 and {MAX_LIMIT}")
    if offset < 0:
        raise HTTPException(400, "offset must be 0 or more")
    if verdict is not None and verdict not in triage.VERDICTS:
        raise HTTPException(400, f"verdict must be one of {list(triage.VERDICTS)}")
    c = m.checker()
    rows = []
    for b in _books(c):
        if lang is not None and b.get("lang_tag") != lang:
            continue
        r = _assess(c, b)
        if verdict is not None and r["verdict"] != verdict:
            continue
        rows.append(r | {"title": b.get("title"), "lang_tag": b.get("lang_tag")})
    counts = {v: 0 for v in triage.VERDICTS}
    by_language: dict[str, dict] = {}
    for r in rows:
        counts[r["verdict"]] += 1
        by_language.setdefault(r["lang_tag"], {v: 0 for v in triage.VERDICTS})[r["verdict"]] += 1
    return {"total": len(rows), "counts": counts, "by_language": by_language, "rows": rows[offset:offset + limit]}
