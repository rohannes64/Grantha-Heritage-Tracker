"""Catalogue class suggestion (docs/superpowers/specs/api-contract.md, Feature 2)."""
import numpy as np
from fastapi import APIRouter, HTTPException
from sklearn.metrics import pairwise_distances

from pipeline.catalogue import main_class
from pipeline.suggest_eval import K, vote

router = APIRouter()


def suggest(checker, z: np.ndarray, k: int = K, exclude: int | None = None) -> dict:
    """Top 3 catalogue main classes for vector `z` among the model's coded books (not book `exclude`)."""
    d = pairwise_distances(np.asarray(z).reshape(1, -1), checker.Z, metric=checker.b["hier"]["metric"])[0]
    classes = [main_class(doc["classification"]) for doc in checker.docs]
    if exclude is not None:
        classes[exclude] = None
    return vote(d, classes, k)


@router.get("/api/suggest/{identifier}")
def suggest_for(identifier: str, k: int = K):
    import app.main as m
    c = m.checker()
    i = c.index.get(identifier)
    if i is None:
        raise HTTPException(404, "no such document in the study sample")
    k = max(1, min(k, 200))
    return ({"identifier": identifier, "catalogue_class": main_class(c.docs[i]["classification"]), "k": k}
            | suggest(c, c.Z[i], k, exclude=i)
            | {"basis": "nearest coded books in the model"})


def enrich_check(checker, result, vector) -> dict:
    return {"suggested_classes": suggest(checker, vector)["suggestions"]}
