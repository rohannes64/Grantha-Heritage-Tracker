"""Feature 5: other editions and translations of a book (docs/superpowers/specs/api-contract.md)."""
from fastapi import APIRouter, HTTPException
from sklearn.metrics import pairwise_distances

from pipeline import editions

router = APIRouter()


@router.get("/api/editions/{identifier}")
def get_editions(identifier: str) -> dict:
    import app.main as m
    c = m.checker()
    if identifier not in c.index:
        raise HTTPException(404, "no such document in the study sample")
    i = c.index[identifier]
    threshold = c.b.get("editions_threshold")
    method = c.b.get("editions_method") or "Not calibrated: this model bundle predates the edition finder."
    body = {"identifier": identifier, "threshold": threshold, "method": method, "candidates": []}
    if threshold is None or threshold <= 0:   # missing, or no same-title pair was found to calibrate on
        body["threshold"] = None
        return body
    dist = pairwise_distances(c.Z[i:i + 1], c.Z, metric=c.b["hier"]["metric"])[0]
    dist[i] = float("inf")
    mine = editions.key(c.docs[i])
    for j in editions.candidates(dist, threshold):
        d = c.docs[j]
        body["candidates"].append({"identifier": d.get("identifier"), "title": d.get("title"),
                                   "lang_tag": d.get("lang_tag"), "script": d.get("script"),
                                   "distance": float(dist[j]),
                                   "same_title_author": mine is not None and editions.key(d) == mine,
                                   "url": d.get("url")})
    return body
