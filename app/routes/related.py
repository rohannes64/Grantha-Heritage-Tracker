"""Feature 1: related books in other scripts (docs/superpowers/specs/api-contract.md)."""
import numpy as np
from fastapi import APIRouter, HTTPException
from sklearn.metrics import pairwise_distances

router = APIRouter()
FIELDS = ("identifier", "title", "lang_tag", "script", "url")


def _neighbours(checker, dist: np.ndarray, script: str, k: int, other_scripts: bool, skip: int | None) -> list[dict]:
    rows = [i for i in np.argsort(dist, kind="stable") if i != skip
            and (not other_scripts or checker.docs[i]["script"] != script)]
    return [{f: checker.docs[i].get(f) for f in FIELDS} | {"distance": float(dist[i])} for i in rows[:k]]


def related(checker, i: int, k: int = 10, other_scripts: bool = True) -> list[dict]:
    """The k nearest books to row i (itself excluded), by the bundle's metric; only other scripts if asked."""
    dist = pairwise_distances(checker.Z[i:i + 1], checker.Z, metric=checker.b["hier"]["metric"])[0]
    return _neighbours(checker, dist, checker.docs[i]["script"], k, other_scripts, i)


@router.get("/api/related/{identifier}")
def get_related(identifier: str, k: int = 10, other_scripts: bool = True) -> dict:
    import app.main as m
    c = m.checker()
    if identifier not in c.index:
        raise HTTPException(404, "no such document in the study sample")
    if not 1 <= k <= 50:
        raise HTTPException(400, "k must be between 1 and 50")
    i = c.index[identifier]
    return {"identifier": identifier, "script": c.docs[i]["script"], "k": k, "other_scripts": other_scripts,
            "neighbours": related(c, i, k, other_scripts)}


def enrich_check(checker, result: dict, vector) -> dict:
    """Up to 5 nearest archive books in scripts other than the page's."""
    dist = pairwise_distances(np.asarray(vector).reshape(1, -1), checker.Z, metric=checker.b["hier"]["metric"])[0]
    return {"related_other_scripts": _neighbours(checker, dist, result["script"], 5, True, None)}
