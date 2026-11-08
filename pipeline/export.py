"""Step 6: package the final models and study results for the web app.

    python -m pipeline.export

Writes
  data/model/bundle.joblib   everything the app needs to check a new document (no retraining)
  web/data/study.json        all study results the Study page shows (both feature sets)
  web/data/corpus.json       the clustered books, their groups and PCA positions (Browse page)
Cluster names: reports/cluster_names.json ({"A": {"0": "name", ...}, "B": {...}}) if present,
otherwise the three most distinctive terms.
"""
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.metrics import pairwise_distances

from . import config, preprocess
from .study import clean_json

PROCESSED = config.DATA / "processed"
MODEL_DIR = config.DATA / "model"
WEB_DATA = config.ROOT / "web" / "data"


def archive_url(ident: str) -> str:
    return f"https://archive.org/details/{ident}"


def names_for(fs, profiles):
    path = config.REPORTS / "cluster_names.json"
    given = json.loads(path.read_text(encoding="utf-8")).get(fs, {}) if path.exists() else {}
    out = {}
    for p in profiles:
        c = str(p["cluster"])
        auto = ", ".join(t["term"] for t in p["terms"][:3]) or "mixed"
        out[c] = given.get(c, auto)
    return out


def downsample(curve, n=200):
    idx = np.linspace(0, len(curve) - 1, min(n, len(curve))).round().astype(int)
    return [curve[i] for i in idx]


def main() -> None:
    feats = joblib.load(PROCESSED / "features.joblib")
    st = joblib.load(PROCESSED / "study.joblib")
    ids = feats["ids"]
    docs = pd.read_csv(PROCESSED / "docs.csv").set_index("identifier")
    fs = st["selection"]["chosen"]
    res = st["results"][fs]
    Z = feats[fs]["Z"].astype(np.float64)
    hmetric = res["hierarchical"]["final"]["metric"]
    dmetric = res["distance"]["chosen"]
    hl = np.array(res["hierarchical"]["labels"])
    dl = np.array(res["dbscan"]["labels"])

    clusters = sorted(set(hl))
    centroids = np.vstack([Z[hl == c].mean(axis=0) for c in clusters])
    own = pairwise_distances(Z, centroids, metric=hmetric)[np.arange(len(Z)), hl]
    spread = {int(c): {"p50": float(np.quantile(own[hl == c], 0.5)), "p90": float(np.quantile(own[hl == c], 0.9)),
                       "max": float(own[hl == c].max())} for c in clusters}
    dfin = res["dbscan"]["final"]
    D = pairwise_distances(Z, metric=dmetric)
    db = DBSCAN(eps=dfin["eps"], min_samples=dfin["min_pts"], metric="precomputed").fit(D)
    assert (db.labels_ == dl).all(), "DBSCAN refit differs from the study labels"

    hnames = names_for(f"{fs}_hier", res["hierarchical"]["profiles"])
    dnames = names_for(f"{fs}_dbscan", res["dbscan"]["profiles"])
    meta_cols = ["title", "creator", "year", "era", "lang_tag", "script", "mean_conf", "classification", "total_pages"]
    display = docs.loc[ids, meta_cols].reset_index()
    display["url"] = display["identifier"].map(archive_url)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "feature_set": fs, "feature_name": res["name"],
        "transform": feats[fs]["transform"], "lsa": feats["A"]["transform"], "Xw": feats["A"]["Xw"],
        "ids": ids, "Z": Z.astype(np.float32),
        "hier": {"labels": hl, "metric": hmetric, "linkage": res["hierarchical"]["final"]["linkage"],
                 "k": res["hierarchical"]["final"]["k"], "centroids": centroids, "spread": spread, "names": hnames},
        "dbscan": {"labels": dl, "metric": dmetric, "eps": dfin["eps"], "min_pts": dfin["min_pts"],
                   "core_idx": db.core_sample_indices_, "names": dnames},
        "pca": st["models"][fs]["pca"],
        "docs": display.to_dict("records"),
        "thresholds": {"min_conf": preprocess.MIN_DOC_CONF, "min_tokens": preprocess.MIN_DOC_TOKENS},
    }, MODEL_DIR / "bundle.joblib")

    # ---- web data
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    all_docs = pd.read_csv(PROCESSED / "docs.csv")
    pilot_path = config.REPORTS / "pilot_ocr_quality.json"
    web = {"selection": st["selection"], "final": fs, "sets": {},
           "corpus": {"harvested": int(len(all_docs)), "usable": int(all_docs["usable"].sum()),
                      "by_language": [{"lang": l, "name": config.LANGUAGES[l]["name"], "harvested": int(len(g)),
                                       "usable": int(g["usable"].sum()),
                                       "median_conf": float(g["mean_conf"].median())}
                                      for l, g in all_docs.groupby("lang_tag")],
                      "tag_mismatch": int((all_docs["tag_matches_script"] == 0).sum())},
           "pilot": json.loads(pilot_path.read_text()) if pilot_path.exists() else None,
           "relevance": pd.read_csv(config.REPORTS / "variable_relevance.csv").to_dict("records")}
    for f, r in st["results"].items():
        r = dict(r)
        r["dbscan"] = dict(r["dbscan"], kdist={k: downsample(v) for k, v in r["dbscan"]["kdist"].items()})
        r["hierarchical"] = {k: v for k, v in r["hierarchical"].items() if k != "labels"}
        r["dbscan"] = {k: v for k, v in r["dbscan"].items() if k != "labels"}
        r["hierarchical"]["names"] = names_for(f"{f}_hier", r["hierarchical"]["profiles"])
        r["dbscan"]["names"] = names_for(f"{f}_dbscan", r["dbscan"]["profiles"])
        r["labels"] = {"hierarchical": st["results"][f]["hierarchical"]["labels"],
                       "dbscan": st["results"][f]["dbscan"]["labels"]}
        web["sets"][f] = r
    (WEB_DATA / "study.json").write_text(json.dumps(clean_json(web)), encoding="utf-8")
    corpus = {"ids": ids, "feature_set": fs, "hier_names": hnames, "dbscan_names": dnames,
              "docs": [dict(d, hier=int(h), dbscan=int(b), x=float(c[0]), y=float(c[1]))
                       for d, h, b, c in zip(display.to_dict("records"), hl, dl, res["pca"]["coords"])]}
    (WEB_DATA / "corpus.json").write_text(json.dumps(clean_json(corpus), ensure_ascii=False), encoding="utf-8")
    print(f"exported model ({fs}: {res['name']}) and web data for {len(ids)} books")


if __name__ == "__main__":
    main()
