"""Finding other editions and translations of a book.

Two books are "the same work" when their normalised title+author keys match. A book's candidate editions are
the books within a distance threshold of it in the final vector space (at most CAP, nearest first). The
threshold is calibrated on train books only: the distance that maximises F1 of "same key" among each train
book's K nearest neighbours. Held-out (test split) books are used only to evaluate it.

Evaluation: each held-out book's candidates come from the held-out pool only, so the numbers measure how well
the threshold generalises to unseen books; the API ranks a book against every book in the bundle. Books of one
edition group are not independent, so the bootstrap 95% intervals resample held-out groups (clusters), with a
book in no group counting as a cluster of its own.

Limitation: the key is a string match after NFKC, case folding and punctuation stripping. A transliteration
variant or a translated title ("Ramayana" / "Ramayan" / the Devanagari form) does not share a key, so it is
neither counted as a true edition in the calibration nor in the evaluation; the vectors may still bring such
books close, and they then appear as candidates with same_title_author false. No transliteration is attempted.

    python -m pipeline.editions
"""
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import pairwise_distances

from . import config
from .evaluate import N_CI, interval

K = 10      # neighbours examined per book when calibrating
CAP = 10    # candidates returned per book
MIN_TITLE_WORDS = 3   # a title alone (no creator) is a key only when it is at least this long
OUT = config.REPORTS / "features" / "editions.json"


def _norm(s) -> str:
    if s is None or s is pd.NA or (isinstance(s, float) and np.isnan(s)):
        return ""
    s = unicodedata.normalize("NFKC", str(s)).casefold()
    s = "".join(" " if unicodedata.category(c).startswith(("P", "S")) else c for c in s)
    return re.sub(r"\s+", " ", s).strip()


def key(doc: dict) -> str | None:
    """Normalised title+author key, or None when the book has no usable key."""
    title, creator = _norm(doc.get("title")), _norm(doc.get("creator"))
    if not title:
        return None
    if creator:
        return f"{title} | {creator}"
    return title if len(title.split()) >= MIN_TITLE_WORDS else None


def _records(docs) -> list[dict]:
    if isinstance(docs, pd.DataFrame):
        d = docs.reset_index() if "identifier" not in docs.columns else docs
        return d.to_dict("records")
    return list(docs)


def groups(docs) -> dict[str, list[str]]:
    """key -> identifiers, only keys shared by two or more books. `docs`: list of dicts or a DataFrame."""
    out: dict[str, list[str]] = {}
    for d in _records(docs):
        k = key(d)
        if k is not None:
            out.setdefault(k, []).append(d["identifier"])
    return {k: v for k, v in out.items() if len(v) >= 2}


def _group_numbers(ids, groups_) -> np.ndarray:
    """Group number per row (-1 = in no group)."""
    row = {i: r for r, i in enumerate(ids)}
    g = np.full(len(ids), -1)
    for n, members in enumerate(groups_.values()):
        for m in members:
            if m in row:
                g[row[m]] = n
    return g


def calibrate(Z_train, groups_train: dict, ids=None, metric: str = "cosine") -> float:
    """The distance threshold maximising F1 of "same key" among each train book's K nearest neighbours.
    `groups_train` lists identifiers (`ids`, one per row of Z_train) or, with ids=None, row numbers.
    The returned value is midway to the next larger neighbour distance, so it does not sit on a training pair.
    0.0 when no neighbour pair shares a key."""
    Z = np.asarray(Z_train)
    if len(Z) < 2:
        return 0.0
    ids = list(range(len(Z))) if ids is None else list(ids)
    g = _group_numbers(ids, groups_train)
    D = pairwise_distances(Z, metric=metric)
    np.fill_diagonal(D, np.inf)
    nn = np.argsort(D, axis=1, kind="stable")[:, :min(K, len(Z) - 1)]
    dist = np.take_along_axis(D, nn, axis=1).ravel()
    same = ((g[:, None] == g[nn]) & (g[:, None] >= 0)).ravel()
    if not same.any():
        return 0.0
    order = np.argsort(dist, kind="stable")
    d, s = dist[order], same[order]
    tp = np.cumsum(s)
    f1 = 2 * tp / (np.arange(1, len(d) + 1) + s.sum())   # 2PR/(P+R) with P=tp/predicted, R=tp/positives
    last = np.r_[d[1:] != d[:-1], True]                  # thresholds sit after a run of equal distances
    best = int(np.flatnonzero(last)[np.argmax(f1[last])])
    return float(d[best] if best + 1 >= len(d) else (d[best] + d[best + 1]) / 2)


def calibrate_for_bundle(Z, ids, docs, metric: str) -> tuple[float, str]:
    """Threshold and a plain-words method for a bundle. `docs`: rows aligned with `ids`, with a `split` column
    when known; train rows only are used, or all rows (said so in the method) when there is no split."""
    recs = _records(docs)
    has_split = bool(recs) and all(r.get("split") in ("train", "val", "test") for r in recs)
    rows = [i for i, r in enumerate(recs) if r["split"] == "train"] if has_split else list(range(len(recs)))
    sub = [dict(recs[i], identifier=ids[i]) for i in rows]
    t = calibrate(np.asarray(Z)[rows], groups(sub), ids=[ids[i] for i in rows], metric=metric)
    scope = (f"the {len(rows)} train books" if has_split
             else f"all {len(rows)} books (the data has no train/test split column)")
    method = (f"Distance ({metric}) at which, among each book's {K} nearest neighbours in {scope}, "
              f"'same normalised title and author' is best predicted (maximum F1). "
              f"Candidates are books within that distance, at most {CAP}, nearest first.")
    return t, method


def candidates(dist_row: np.ndarray, threshold: float) -> np.ndarray:
    order = np.argsort(dist_row, kind="stable")
    return order[dist_row[order] <= threshold][:CAP]


def evaluate(Z, docs, metric: str = "cosine", out: Path = OUT) -> dict:
    """Threshold from train books; precision/recall on held-out (test) books' title+author groups, with
    cluster-bootstrap 95% intervals (resampling edition groups). `docs` rows align with Z and have identifier, title, creator, split."""
    recs = _records(docs)
    Z = np.asarray(Z)
    split = np.array([r["split"] for r in recs])
    ids = [r["identifier"] for r in recs]
    tr, te = np.flatnonzero(split == "train"), np.flatnonzero(split == "test")
    threshold = calibrate(Z[tr], groups([recs[i] for i in tr]), ids=[ids[i] for i in tr], metric=metric)
    held = [recs[i] for i in te]
    g = _group_numbers([ids[i] for i in te], groups(held))
    D = pairwise_distances(Z[te], metric=metric) if len(te) else np.zeros((0, 0))
    np.fill_diagonal(D, np.inf)
    rows = []   # per held-out book: candidates returned, correct candidates, true editions present
    for r in range(len(te)):
        c = candidates(D[r], threshold)
        true = int((g == g[r]).sum() - 1) if g[r] >= 0 else 0
        rows.append((len(c), int(((g[c] == g[r]) & (g[r] >= 0)).sum()), true))
    a = np.array(rows, dtype=float).reshape(-1, 3)

    cluster = np.where(g >= 0, g, g.max() + 1 + np.arange(len(g))) if len(g) else g   # ungrouped book = own cluster
    _, cluster = np.unique(cluster, return_inverse=True)
    sums = np.zeros((cluster.max() + 1 if len(a) else 0, 3))
    if len(a):
        np.add.at(sums, cluster, a)
    rng = np.random.default_rng(config.SEED)

    def ratio(tot, num, den):
        return float(tot[num] / tot[den]) if tot[den] else float("nan")

    def stat(num, den):
        v = np.array([ratio(sums[rng.integers(0, len(sums), len(sums))].sum(axis=0), num, den)
                      for _ in range(N_CI)]) if len(sums) else np.array([])
        v = v[~np.isnan(v)]
        p = ratio(a.sum(axis=0), num, den) if len(a) else float("nan")
        return (None if np.isnan(p) else p), (interval(v) if len(v) else [None, None])

    (p, p_ci), (r_, r_ci) = stat(1, 0), stat(1, 2)
    res = {"precision": p, "recall": r_, "precision_ci95": p_ci, "recall_ci95": r_ci,
           "groups_heldout": len(groups(held)), "threshold": threshold,
           "heldout_books": int(len(te)), "train_books": int(len(tr)), "metric": metric, "split": "test"}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2))
    return res


def from_study(feats: dict, st: dict, docs: pd.DataFrame, out: Path = OUT) -> dict:
    """Evaluate a train-only fit: train books are feats["ids"] / feats[fs]["Z"]; the test-split books are in
    feats["holdout"] (as in suggest_eval.from_study). `docs` is indexed by identifier."""
    fs = st["selection"]["chosen"]
    metric = st["results"][fs]["hierarchical"]["final"]["metric"]
    hold = feats["holdout"]
    keep = [k for k, i in enumerate(hold["ids"]) if docs.loc[i, "split"] == "test"]
    ids = list(feats["ids"]) + [hold["ids"][k] for k in keep]
    Z = np.vstack([np.asarray(feats[fs]["Z"], dtype=np.float64), np.asarray(hold[fs], dtype=np.float64)[keep]])
    d = docs.loc[ids, ["title", "creator"]].reset_index()
    d["split"] = ["train"] * len(feats["ids"]) + ["test"] * len(keep)
    return evaluate(Z, d, metric=metric, out=out) | {"feature_set": fs}


def main() -> None:
    import joblib
    feats = joblib.load(config.PROCESSED / "features.joblib")
    st = joblib.load(config.PROCESSED / "study.joblib")
    if feats.get("fit") != "train" or st.get("fit") != "train":
        raise SystemExit("needs the train-only fit: run features --fit train, then study")
    docs = pd.read_csv(config.PROCESSED / "docs.csv", low_memory=False).set_index("identifier")
    print(json.dumps(from_study(feats, st, docs), indent=2))


if __name__ == "__main__":
    main()
