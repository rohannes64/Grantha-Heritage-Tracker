"""Which sentence encoder carries the most topic information? (docs/accuracy_plan.md, fix 2)

    python -m pipeline.encoders

For every encoder whose raw embeddings are cached (pipeline.features), on the labelled train and
validation books only (test books are never used): the share of books whose subject matches the
majority of their 7 nearest neighbours (cosine), 5-fold cross-validated, seed 2026, before and after
per-language centring. This is the most topic information the numbers carry: no unsupervised grouping
of them can match subjects better. The labels measure; they never fit or choose clusters.

Rule (fixed before the run): highest centred score wins; within 2 points the smaller model wins.
Writes reports/study/encoder_comparison.json.
"""
import json

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import normalize

from . import config
from .features import MODELS, SET_NAMES

PROCESSED = config.DATA / "processed"
LABELS = config.REPORTS / "eval" / "subject_labels.csv"
OUT = config.REPORTS / "study" / "encoder_comparison.json"
PARAMS_M = {"B": 471, "C": 238, "D": 568}   # model size, millions of parameters (model cards)
TIE_POINTS = 2.0


def centred(E: np.ndarray, langs: np.ndarray) -> np.ndarray:
    """Subtract each language's mean over these books (uses no subject labels)."""
    E = normalize(E).copy()
    for l in np.unique(langs):
        E[langs == l] -= E[langs == l].mean(axis=0)
    return normalize(E)


def knn_cv(E: np.ndarray, y: np.ndarray) -> float:
    accs = []
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=config.SEED).split(E, y):
        k = KNeighborsClassifier(7, metric="cosine").fit(E[tr], y[tr])
        accs.append(float(np.mean(k.predict(E[te]) == y[te])))
    return float(np.mean(accs))


def main() -> None:
    docs = pd.read_csv(PROCESSED / "docs.csv").set_index("identifier")
    lab = pd.read_csv(LABELS).set_index("identifier")["subject"]
    rows = {}
    for fs, name in MODELS.items():
        cache, ids_path = PROCESSED / f"embeddings_raw_{fs}.npy", PROCESSED / f"embeddings_ids_{fs}.json"
        # an encoder that was only benchmarked has vectors for the labelled books alone (same order as keep)
        bench = config.DATA / "logs" / f"exp_{name.replace('/', '__')}.npy"
        if cache.exists():
            ids = json.loads(ids_path.read_text())
        elif bench.exists():
            ids = json.loads((PROCESSED / "embeddings_ids_B.json").read_text())
        else:
            continue
        keep = [i for i in ids if i in lab.index and docs.loc[i, "split"] in ("train", "val")]
        if cache.exists():
            pos = {d: k for k, d in enumerate(ids)}
            E = np.load(cache)[[pos[i] for i in keep]]
        else:
            E = np.load(bench)
            if len(E) != len(keep):
                continue
        y, langs = lab[keep].values, docs.loc[keep, "ocr_model"].values
        rows[fs] = {"model": name, "name": SET_NAMES[fs], "params_m": PARAMS_M.get(fs), "books": len(keep),
                    "knn_plain": knn_cv(normalize(E), y), "knn_centred": knn_cv(centred(E, langs), y)}
        print(f"{fs} {name}: {len(keep)} books, 7-NN subject accuracy {rows[fs]['knn_plain']:.3f} plain, "
              f"{rows[fs]['knn_centred']:.3f} centred", flush=True)
    best = max(rows, key=lambda f: rows[f]["knn_centred"])
    near = [f for f in rows if rows[best]["knn_centred"] - rows[f]["knn_centred"] < TIE_POINTS / 100]
    chosen = min(near, key=lambda f: rows[f]["params_m"] or 1e9)
    out = {"encoders": rows, "chosen": chosen,
           "rule": f"highest centred 7-NN subject accuracy; within {TIE_POINTS:g} points the smaller model",
           "subjects": sorted(set(lab.values)), "note": "labelled train+validation books only; test books unused"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"chosen encoder: {chosen} ({rows[chosen]['model']})")


if __name__ == "__main__":
    main()
