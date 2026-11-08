"""Step 5: the clustering study, run identically on feature sets A and B.

    python -m pipeline.study

1. Euclidean vs Manhattan, measured four ways; the winner is used for every non-Ward model.
2. Hierarchical clustering: Ward, average and complete linkage, k = 2..15, silhouette for each.
3. DBSCAN: k-distance curves, then a grid of MinPts x eps (eps from k-distance quantiles + knee).
4. Final configuration per method by the selection rules below (fixed before seeing results).
5. Stability: bootstrap resamples and neighbouring parameter settings.
6. Direct comparison of the two methods (ARI, NMI, cross-table) and PCA to 2-D.
7. Interpretation: cluster profiles, distinctive terms, PCA loadings, language and OCR effects.

Selection rules
- Hierarchical: highest silhouette among settings with k >= 3 and every cluster >= max(10, 1% of books).
- DBSCAN: highest silhouette (non-noise points) among settings with >= 2 clusters and <= 50% noise.
- Final feature set for the app: the one whose final hierarchical grouping depends least on script
  (lower NMI with detected script), provided its silhouette > 0 and median bootstrap ARI >= 0.5;
  otherwise the other set.
"""
import json
import math

import joblib
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cophenet, dendrogram, fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score, pairwise_distances,
                             roc_auc_score, silhouette_score)

from . import config

PROCESSED = config.DATA / "processed"
STUDY = config.REPORTS / "study"
METRICS = {"euclidean": "Euclidean", "cityblock": "Manhattan"}
LINKAGES = ["ward", "average", "complete"]
K_RANGE = range(2, 16)
MINPTS = [5, 10, 15, 20]
EPS_QUANTILES = [0.10, 0.25, 0.40, 0.55, 0.70]
N_BOOT, BOOT_FRAC = 20, 0.8
MAX_NOISE = 0.5
FEATURE_NAMES = {"A": "TF-IDF + LSA", "B": "LaBSE embeddings"}


def top_class(series: pd.Series) -> pd.Series:
    """First (top-level) value of the ' | '-joined classification field; None when missing."""
    return series.map(lambda x: x.split(" | ")[0].strip() if isinstance(x, str) and x.strip() else None)


def clean_json(obj):
    """NaN/inf -> None and numpy scalars -> Python, so browsers can JSON.parse the results."""
    if isinstance(obj, dict):
        return {str(k): clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return None if not np.isfinite(obj) else float(obj)
    return obj


def min_cluster_size(n: int) -> int:
    return max(10, math.ceil(0.01 * n))


# ---------------------------------------------------------------- 1. distance metric study
def relative_contrast(D: np.ndarray) -> float:
    """Median over points of (farthest - nearest) / nearest. Higher = distances discriminate better."""
    D = D.copy()
    np.fill_diagonal(D, np.nan)
    near, far = np.nanmin(D, axis=1), np.nanmax(D, axis=1)
    ok = near > 0
    return float(np.median((far[ok] - near[ok]) / near[ok]))


def knn_agreement(D: np.ndarray, labels: np.ndarray, k: int = 10) -> float | None:
    """Share of each point's k nearest neighbours carrying the same (non-missing) label."""
    have = pd.notna(labels)
    if have.sum() < 30:
        return None
    D = D.copy()
    np.fill_diagonal(D, np.inf)
    hits = []
    for i in np.where(have)[0]:
        order = np.argsort(D[i])
        nb = [j for j in order if have[j]][:k]
        hits.append(np.mean(labels[nb] == labels[i]))
    return float(np.mean(hits))


def distance_study(Z, scripts, classes) -> dict:
    res = {}
    for m in METRICS:
        D = pairwise_distances(Z, metric=m)
        cond = squareform(D, checks=False)
        r = {"relative_contrast": relative_contrast(D)}
        for method in ["average", "complete"]:
            L = linkage(cond, method=method)
            r[f"cophenetic_{method}"] = float(cophenet(L, cond)[0])
            sils = [silhouette_score(D, fcluster(L, k, "maxclust"), metric="precomputed")
                    for k in K_RANGE if len(set(fcluster(L, k, "maxclust"))) > 1]
            r[f"best_silhouette_{method}"] = float(max(sils)) if sils else None
        r["knn_same_script"] = knn_agreement(D, scripts)
        r["knn_same_classification"] = knn_agreement(D, classes)
        res[m] = r
    criteria = ["relative_contrast", "cophenetic_average", "cophenetic_complete", "best_silhouette_average"]
    wins = {m: 0 for m in METRICS}
    for c in criteria:
        a, b = res["euclidean"][c], res["cityblock"][c]
        if a is None or b is None:
            continue
        wins["euclidean" if a >= b else "cityblock"] += 1
    chosen = "cityblock" if wins["cityblock"] > wins["euclidean"] else "euclidean"  # tie -> Euclidean
    return {"metrics": res, "criteria": criteria, "wins": wins, "chosen": chosen,
            "rule": "metric winning most of the four criteria; a tie goes to Euclidean (needed by Ward)"}


# ---------------------------------------------------------------- 2. hierarchical
def hierarchical_grid(D_by_metric, chosen) -> tuple[list[dict], dict]:
    n = D_by_metric["euclidean"].shape[0]
    rows, linkages = [], {}
    for method in LINKAGES:
        metric = "euclidean" if method == "ward" else chosen
        D = D_by_metric[metric]
        L = linkage(squareform(D, checks=False), method=method)
        linkages[method] = L
        for k in K_RANGE:
            lab = fcluster(L, k, "maxclust")
            sizes = np.bincount(lab)[1:]
            sizes = sizes[sizes > 0]
            sil = silhouette_score(D, lab, metric="precomputed") if len(sizes) > 1 else None
            rows.append({"linkage": method, "metric": metric, "k": k, "k_actual": int(len(sizes)),
                         "silhouette": None if sil is None else float(sil),
                         "largest_share": float(sizes.max() / n), "smallest": int(sizes.min()),
                         "valid": bool(k >= 3 and len(sizes) == k and sizes.min() >= min_cluster_size(n))})
    return rows, linkages


def pick(rows, key="silhouette"):
    valid = [r for r in rows if r["valid"] and r[key] is not None]
    if valid:
        return max(valid, key=lambda r: r[key]), True
    usable = [r for r in rows if r[key] is not None]
    return (max(usable, key=lambda r: r[key]) if usable else None), False


# ---------------------------------------------------------------- 3. DBSCAN
def knee(values: np.ndarray) -> float:
    """Point of the sorted curve farthest from the straight line between its ends."""
    y = np.sort(values)
    x = np.linspace(0, 1, len(y))
    yn = (y - y[0]) / (y[-1] - y[0] + 1e-12)
    return float(y[np.argmax(x - yn)]) if len(y) > 2 else float(y[-1])


def dbscan_grid(D) -> tuple[list[dict], dict]:
    n = D.shape[0]
    Ds = np.sort(D, axis=1)  # column 0 is the point itself (distance 0)
    rows, curves = [], {}
    for mp in MINPTS:
        kd = Ds[:, mp - 1]   # distance to the (MinPts-1)-th other point: core-point threshold
        curves[mp] = np.sort(kd)[::-1].tolist()
        eps_list = sorted({round(float(np.quantile(kd, q)), 6) for q in EPS_QUANTILES} | {round(knee(kd), 6)})
        for eps in eps_list:
            lab = DBSCAN(eps=eps, min_samples=mp, metric="precomputed").fit_predict(D)
            clusters = sorted(set(lab) - {-1})
            noise = float(np.mean(lab == -1))
            sil = None
            mask = lab != -1
            if len(clusters) >= 2 and mask.sum() > len(clusters):
                sil = float(silhouette_score(D[np.ix_(mask, mask)], lab[mask], metric="precomputed"))
            sizes = [int(np.sum(lab == c)) for c in clusters]
            rows.append({"min_pts": mp, "eps": eps, "eps_is_knee": eps == round(knee(kd), 6),
                         "n_clusters": len(clusters), "noise_share": noise, "silhouette": sil,
                         "largest_share": (max(sizes) / n) if sizes else None,
                         "valid": bool(len(clusters) >= 2 and noise <= MAX_NOISE)})
    return rows, curves


# ---------------------------------------------------------------- 5. stability
def bootstrap_hier(D, method, k, ref, rng):
    n = D.shape[0]
    aris = []
    for _ in range(N_BOOT):
        idx = np.sort(rng.choice(n, int(BOOT_FRAC * n), replace=False))
        L = linkage(squareform(D[np.ix_(idx, idx)], checks=False), method=method)
        aris.append(adjusted_rand_score(ref[idx], fcluster(L, k, "maxclust")))
    return aris


def bootstrap_dbscan(D, eps, mp, ref, rng):
    n = D.shape[0]
    aris = []
    for _ in range(N_BOOT):
        idx = np.sort(rng.choice(n, int(BOOT_FRAC * n), replace=False))
        lab = DBSCAN(eps=eps, min_samples=mp, metric="precomputed").fit_predict(D[np.ix_(idx, idx)])
        aris.append(adjusted_rand_score(ref[idx], lab))
    return aris


def summary(xs):
    xs = np.asarray(xs, float)
    return {"median": float(np.median(xs)), "p10": float(np.quantile(xs, 0.1)),
            "p90": float(np.quantile(xs, 0.9)), "values": xs.round(4).tolist()}


# ---------------------------------------------------------------- 7. interpretation
def distinctive_terms(Xw, vocab_inv, mask, top=12):
    mean_in = np.asarray(Xw[mask].mean(axis=0)).ravel()
    mean_all = np.asarray(Xw.mean(axis=0)).ravel()
    score = mean_in - mean_all
    order = np.argsort(score)[::-1][:top]
    return [{"term": vocab_inv[i], "score": round(float(score[i]), 5)} for i in order if score[i] > 0]


def profiles(labels, Z, Xw, vocab_inv, docs, metric):
    out = []
    for c in sorted(set(labels)):
        mask = labels == c
        sub = docs[mask]
        centroid = Z[mask].mean(axis=0, keepdims=True)
        dist = pairwise_distances(Z[mask], centroid, metric=metric).ravel()
        typical = sub.iloc[np.argsort(dist)[:5]]
        cls = top_class(sub["classification"]).dropna().value_counts().head(5)
        out.append({
            "cluster": int(c), "size": int(mask.sum()), "share": float(mask.mean()),
            "terms": distinctive_terms(Xw, vocab_inv, mask),
            "script_mix": sub["script"].value_counts(normalize=True).round(3).to_dict(),
            "era_mix": sub["era"].value_counts(normalize=True).round(3).to_dict(),
            "median_year": None if sub["year"].isna().all() else float(sub["year"].median()),
            "median_conf": float(sub["mean_conf"].median()),
            "classification_top": cls.to_dict(), "classified_share": float(sub["classification"].notna().mean()),
            "typical": typical[["identifier", "title", "year", "script"]].to_dict("records"),
        })
    return out


def label_effects(labels, docs) -> dict:
    cls = top_class(docs["classification"])
    have = cls.notna().to_numpy()
    return {
        "nmi_script": float(normalized_mutual_info_score(docs["script"], labels)),
        "ari_script": float(adjusted_rand_score(docs["script"], labels)),
        "nmi_era": float(normalized_mutual_info_score(docs["era"], labels)),
        "nmi_classification": float(normalized_mutual_info_score(cls[have], labels[have])) if have.sum() >= 30 else None,
        "classified_books": int(have.sum()),
    }


def pca_view(Z, feature_set, bundle):
    p = PCA(2, random_state=config.SEED).fit(Z)
    view = {"explained": p.explained_variance_ratio_.round(4).tolist(), "coords": p.transform(Z).round(4).tolist()}
    if feature_set == "A":   # map PCs back to words: PCA axes -> SVD axes -> TF-IDF terms
        lsa = bundle["A"]["transform"]
        n_word = len(lsa.word.vocabulary_)
        term_w = p.components_ @ lsa.svd.components_[:, :n_word]
        inv = {i: t for t, i in lsa.word.vocabulary_.items()}
        view["loadings"] = [{"pc": j + 1,
                             "positive": [inv[i] for i in np.argsort(term_w[j])[::-1][:10]],
                             "negative": [inv[i] for i in np.argsort(term_w[j])[:10]]} for j in range(2)]
    return p, view


# ---------------------------------------------------------------- run
def run_feature_set(fs, bundle, docs, rng) -> dict:
    Z = bundle[fs]["Z"].astype(np.float64)
    n = len(Z)
    scripts = docs["script"].to_numpy()
    classes = top_class(docs["classification"]).to_numpy()
    print(f"[{fs}] {FEATURE_NAMES[fs]}: {n} books x {Z.shape[1]} dims", flush=True)

    dist = distance_study(Z, scripts, classes)
    chosen = dist["chosen"]
    print(f"[{fs}] distance: chosen {METRICS[chosen]} (wins {dist['wins']})", flush=True)
    D = {m: pairwise_distances(Z, metric=m) for m in METRICS}

    hrows, linkages = hierarchical_grid(D, chosen)
    hbest, h_ok = pick(hrows)
    hmetric = hbest["metric"]
    hlab = fcluster(linkages[hbest["linkage"]], hbest["k"], "maxclust") - 1
    print(f"[{fs}] hierarchical: {hbest['linkage']} k={hbest['k']} silhouette={hbest['silhouette']:.3f}"
          f"{'' if h_ok else ' (NO setting met the validity rule; best overall shown)'}", flush=True)

    drows, curves = dbscan_grid(D[chosen])
    dbest, d_ok = pick(drows)
    if dbest is None:  # every setting gave <= 1 cluster: report the setting with least noise
        dbest = min(drows, key=lambda r: r["noise_share"])
    dlab = DBSCAN(eps=dbest["eps"], min_samples=dbest["min_pts"], metric="precomputed").fit_predict(D[chosen])
    print(f"[{fs}] DBSCAN: MinPts={dbest['min_pts']} eps={dbest['eps']:.4f} clusters={dbest['n_clusters']} "
          f"noise={dbest['noise_share']:.1%} silhouette={dbest['silhouette']}"
          f"{'' if d_ok else ' (NO setting met the validity rule)'}", flush=True)

    # stability
    h_boot = bootstrap_hier(D[hmetric], hbest["linkage"], hbest["k"], hlab, rng)
    d_boot = bootstrap_dbscan(D[chosen], dbest["eps"], dbest["min_pts"], dlab, rng)
    h_neighbours = []
    for k in (hbest["k"] - 1, hbest["k"] + 1):
        if k >= 2:
            other = fcluster(linkages[hbest["linkage"]], k, "maxclust") - 1
            h_neighbours.append({"k": k, "ari": float(adjusted_rand_score(hlab, other))})
    same_mp = sorted(r["eps"] for r in drows if r["min_pts"] == dbest["min_pts"])
    i = same_mp.index(dbest["eps"])
    d_neighbours = []
    for eps in same_mp[max(0, i - 1):i] + same_mp[i + 1:i + 2]:
        other = DBSCAN(eps=eps, min_samples=dbest["min_pts"], metric="precomputed").fit_predict(D[chosen])
        d_neighbours.append({"eps": eps, "min_pts": dbest["min_pts"], "ari": float(adjusted_rand_score(dlab, other))})
    for mp in MINPTS:
        if mp != dbest["min_pts"] and abs(MINPTS.index(mp) - MINPTS.index(dbest["min_pts"])) == 1:
            other = DBSCAN(eps=dbest["eps"], min_samples=mp, metric="precomputed").fit_predict(D[chosen])
            d_neighbours.append({"eps": dbest["eps"], "min_pts": mp, "ari": float(adjusted_rand_score(dlab, other))})

    # comparison of the two methods
    core = dlab != -1
    cross = pd.crosstab(pd.Series(hlab, name="hierarchical"), pd.Series(np.where(core, dlab, -1), name="dbscan"))
    comparison = {
        "ari_non_noise": float(adjusted_rand_score(hlab[core], dlab[core])) if core.sum() > 1 else None,
        "nmi_non_noise": float(normalized_mutual_info_score(hlab[core], dlab[core])) if core.sum() > 1 else None,
        "ari_all_noise_as_group": float(adjusted_rand_score(hlab, dlab)),
        "crosstab": {"rows": [int(x) for x in cross.index], "cols": [int(x) for x in cross.columns],
                     "values": cross.to_numpy().tolist()},
    }

    # OCR quality vs DBSCAN noise
    conf = docs["mean_conf"].to_numpy()
    noise = (dlab == -1).astype(int)
    ocr_noise = {"noise_share": float(noise.mean()),
                 "median_conf_noise": float(np.median(conf[noise == 1])) if noise.any() else None,
                 "median_conf_clustered": float(np.median(conf[noise == 0])) if (noise == 0).any() else None,
                 "auc_low_conf_predicts_noise": float(roc_auc_score(noise, -conf)) if 0 < noise.sum() < n else None}

    L = linkages[hbest["linkage"]]
    dg = dendrogram(L, truncate_mode="lastp", p=30, no_plot=True)
    k = hbest["k"]
    heights = L[:, 2]
    cut = float((heights[-k] + heights[-(k - 1)]) / 2) if k >= 2 else None
    dendro = {"icoord": np.round(dg["icoord"], 3).tolist(), "dcoord": np.round(dg["dcoord"], 4).tolist(),
              "ivl": dg["ivl"], "cut": cut}

    p, view = pca_view(Z, fs, bundle)
    lsa = bundle["A"]["transform"]
    Xw = bundle["A"]["Xw"]
    inv = np.empty(len(lsa.word.vocabulary_), dtype=object)
    for t, j in lsa.word.vocabulary_.items():
        inv[j] = t
    res = {
        "feature_set": fs, "name": FEATURE_NAMES[fs], "n": n, "dims": int(Z.shape[1]),
        "explained_variance": bundle[fs]["explained_variance"],
        "distance": dist,
        "hierarchical": {"grid": hrows, "final": hbest, "rule_met": h_ok,
                         "labels": hlab.tolist(), "bootstrap_ari": summary(h_boot), "neighbours": h_neighbours,
                         "dendrogram": dendro,
                         "effects": label_effects(hlab, docs),
                         "profiles": profiles(hlab, Z, Xw, inv, docs, hmetric)},
        "dbscan": {"grid": drows, "kdist": {str(k): v for k, v in curves.items()}, "final": dbest, "rule_met": d_ok,
                   "labels": dlab.tolist(), "bootstrap_ari": summary(d_boot), "neighbours": d_neighbours,
                   "effects": label_effects(dlab, docs), "ocr_noise": ocr_noise,
                   "profiles": profiles(dlab, Z, Xw, inv, docs, chosen)},
        "comparison": comparison, "pca": view,
    }
    res["_models"] = {"pca": p, "linkage": linkages[hbest["linkage"]]}
    return res


def choose_feature_set(results) -> dict:
    ok = {}
    for fs, r in results.items():
        h = r["hierarchical"]
        ok[fs] = (h["final"]["silhouette"] or 0) > 0 and h["bootstrap_ari"]["median"] >= 0.5
    candidates = [fs for fs in results if ok[fs]] or list(results)
    best = min(candidates, key=lambda fs: results[fs]["hierarchical"]["effects"]["nmi_script"])
    return {"chosen": best, "meets_quality_bar": ok,
            "nmi_script": {fs: r["hierarchical"]["effects"]["nmi_script"] for fs, r in results.items()},
            "rule": "lowest NMI with script among sets with silhouette > 0 and median bootstrap ARI >= 0.5"}


def main() -> None:
    bundle = joblib.load(PROCESSED / "features.joblib")
    docs = pd.read_csv(PROCESSED / "docs.csv").set_index("identifier").loc[bundle["ids"]].reset_index()
    rng = np.random.default_rng(config.SEED)
    STUDY.mkdir(parents=True, exist_ok=True)
    results = {fs: run_feature_set(fs, bundle, docs, rng) for fs in ("A", "B") if fs in bundle}
    selection = choose_feature_set(results)
    print(f"final feature set: {selection['chosen']} ({FEATURE_NAMES[selection['chosen']]})", flush=True)
    models = {fs: r.pop("_models") for fs, r in results.items()}
    for fs, r in results.items():
        (STUDY / f"results_{fs}.json").write_text(json.dumps(clean_json(r)), encoding="utf-8")
    (STUDY / "selection.json").write_text(json.dumps(clean_json(selection), indent=2), encoding="utf-8")
    joblib.dump({"results": results, "models": models, "selection": selection, "ids": bundle["ids"]},
                PROCESSED / "study.joblib")


if __name__ == "__main__":
    main()
