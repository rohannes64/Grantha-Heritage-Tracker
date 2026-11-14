"""Catalogue class suggestion: the vote, and its held-out evaluation.

A book's class is suggested from its nearest coded books: each neighbour votes for its catalogue main class
(`pipeline.catalogue.main_class`) with weight 1 / (distance + 1e-9), and a class's score is its share of the
total weight. The evaluation fits nothing: neighbours are coded *train* books only, the test is on coded
held-out books, and the baseline is "always the most common class among coded train books".
Writes reports/features/suggest.json.

    python -m pipeline.suggest_eval [--split test]
"""
import argparse
import json
from collections import Counter

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import pairwise_distances

from . import config
from .catalogue import main_class
from .evaluate import N_CI, interval

K = 25
METHOD = ("distance-weighted vote of the k nearest coded train books; top-1 / top-3 = the held-out book's own "
          "catalogue class is the first / among the first three suggestions; CI by resampling held-out books")


def vote(dist, classes, k: int = K) -> dict:
    """Weighted vote of the k nearest entries whose class is not None (`dist[i]` pairs with `classes[i]`)."""
    ok = np.array([c is not None for c in classes], dtype=bool)
    near = np.flatnonzero(ok)[np.argsort(np.asarray(dist, dtype=float)[ok], kind="stable")[:k]]
    w = 1 / (np.asarray(dist, dtype=float)[near] + 1e-9)
    score: dict[str, float] = {}
    for i, wi in zip(near, w):
        score[classes[i]] = score.get(classes[i], 0.0) + wi / w.sum()
    top = sorted(score.items(), key=lambda kv: -kv[1])[:3]
    return {"suggestions": [{"class": c, "score": float(s)} for c, s in top], "neighbours_used": int(len(near))}


def evaluate(Z_train, y_train, Z_held, y_held, k: int = K, metric: str = "euclidean") -> dict:
    """Top-1 / top-3 accuracy on the coded held-out books, neighbours from the coded train books only."""
    tr = [i for i, c in enumerate(y_train) if c is not None]
    te = [i for i, c in enumerate(y_held) if c is not None]
    if not tr or not te:
        raise ValueError(f"need coded books on both sides (train {len(tr)}, held-out {len(te)})")
    Ztr, ytr = np.asarray(Z_train)[tr], [y_train[i] for i in tr]
    D = pairwise_distances(np.asarray(Z_held)[te], Ztr, metric=metric)
    truth = [y_held[i] for i in te]
    ranks = [[s["class"] for s in vote(D[j], ytr, k)["suggestions"]] for j in range(len(te))]
    hit1 = np.array([r[:1] == [t] for r, t in zip(ranks, truth)], dtype=float)
    hit3 = np.array([t in r for r, t in zip(ranks, truth)], dtype=float)
    counts = Counter(ytr)
    common = min(counts, key=lambda c: (-counts[c], c))   # most common; ties by name, so it is deterministic
    rng = np.random.default_rng(config.SEED)
    boots = [(hit1[ix].mean(), hit3[ix].mean()) for ix in (rng.integers(0, len(te), len(te)) for _ in range(N_CI))]
    boots = np.array(boots)
    return {"top1": float(hit1.mean()), "top3": float(hit3.mean()),
            "top1_ci95": interval(boots[:, 0]), "top3_ci95": interval(boots[:, 1]),
            "baseline_most_common": float(np.mean([t == common for t in truth])),
            "k": k, "metric": metric, "heldout_books": len(te), "train_coded_books": len(tr), "method": METHOD}


def from_study(feats: dict, st: dict, docs: pd.DataFrame, split: str) -> dict:
    """Evaluate on one split of a train-only fit: `feats` is features.joblib, `st` study.joblib, `docs` indexed by id.
    Train books are `feats["ids"]` / `feats[fs]["Z"]`; held-out books are in `feats["holdout"]` (as in evaluate.py)."""
    fs = st["selection"]["chosen"]
    metric = st["results"][fs]["hierarchical"]["final"]["metric"]
    hold = feats["holdout"]
    want = [k for k, i in enumerate(hold["ids"]) if docs.loc[i, "split"] == split]
    classes = lambda ids: [main_class(docs.loc[i, "classification"]) for i in ids]
    out = evaluate(np.asarray(feats[fs]["Z"], dtype=np.float64), classes(feats["ids"]),
                   np.asarray(hold[fs], dtype=np.float64)[want], classes([hold["ids"][k] for k in want]),
                   metric=metric)
    return out | {"split": split, "feature_set": fs}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["val", "test"], default="test")
    a = ap.parse_args()
    feats = joblib.load(config.PROCESSED / "features.joblib")
    st = joblib.load(config.PROCESSED / "study.joblib")
    if feats.get("fit") != "train" or st.get("fit") != "train":
        raise SystemExit("needs the train-only fit: run features --fit train, then study")
    docs = pd.read_csv(config.PROCESSED / "docs.csv").set_index("identifier")
    out = from_study(feats, st, docs, a.split)
    path = config.REPORTS / "features" / "suggest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
