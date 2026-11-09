"""Sensitivity check: what happens when the encoded, scaled metadata is added to the text features.

    python -m pipeline.sensitivity      ->  reports/study/sensitivity.json

The main study clusters text alone. Here the metadata block from preprocessing (standardised year,
log pages, OCR confidence, log tokens, year-missing flag, one-hot script) is appended to each feature
set at several weights, and the chosen hierarchical setting (same linkage, same k) is refitted.
The block is divided by the square root of its width, so at weight w its typical row length is about w,
against 1 for the unit-length text rows.
"""
import json

import joblib
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score

from . import config
from .study import PROCESSED, STUDY, clean_json

WEIGHTS = [0.0, 0.25, 0.5, 1.0]


def run() -> dict:
    feats = joblib.load(PROCESSED / "features.joblib")
    meta = joblib.load(PROCESSED / "metadata.joblib")
    st = joblib.load(PROCESSED / "study.joblib")
    ids = feats["ids"]
    pos = {d: i for i, d in enumerate(meta["identifiers"])}
    M = np.asarray(meta["X"], dtype=np.float64)[[pos[d] for d in ids]]
    M = M / np.sqrt(M.shape[1])
    docs = pd.read_csv(PROCESSED / "docs.csv").set_index("identifier").loc[ids]
    out = {"weights": WEIGHTS, "columns": meta["columns"], "feature_sets": {}}
    for fs in ("A", "B", "C"):
        if fs not in feats:
            continue
        fin = st["results"][fs]["hierarchical"]["final"]
        Z = feats[fs]["Z"].astype(np.float64)
        base = None
        rows = []
        for w in WEIGHTS:
            X = np.hstack([Z, w * M]) if w else Z
            labels = fcluster(linkage(X, method=fin["linkage"], metric="euclidean"), fin["k"], "maxclust")
            if base is None:
                base = labels
            rows.append({
                "weight": w,
                "silhouette": float(silhouette_score(X, labels)),
                "silhouette_text_space": float(silhouette_score(Z, labels)),
                "nmi_script": float(normalized_mutual_info_score(docs["script"], labels)),
                "nmi_era": float(normalized_mutual_info_score(docs["era"], labels)),
                "ari_vs_text_only": float(adjusted_rand_score(base, labels)),
                "largest_share": float(np.bincount(labels).max() / len(labels)),
            })
            print(f"[{fs}] w={w}: " + ", ".join(f"{k}={v:.3f}" for k, v in rows[-1].items() if k != "weight"), flush=True)
        out["feature_sets"][fs] = {"linkage": fin["linkage"], "k": fin["k"], "rows": rows}
    return out


def main() -> None:
    res = run()
    STUDY.mkdir(parents=True, exist_ok=True)
    (STUDY / "sensitivity.json").write_text(json.dumps(clean_json(res), indent=2), encoding="utf-8")
    print(f"wrote {STUDY / 'sensitivity.json'}")


if __name__ == "__main__":
    from pipeline.sensitivity import main as _main
    _main()
