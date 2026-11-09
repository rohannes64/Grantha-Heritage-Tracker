"""Out-of-sample evaluation (docs/evaluation_plan.md, section 5).

    python -m pipeline.features --fit train && python -m pipeline.study    # fitted on train books only
    python -m pipeline.evaluate --split val       # look at the validation books
    python -m pipeline.evaluate --split test      # the final numbers; run once

T1  Upload check: each held-out book's own Tesseract pages go through the same steps as an upload
    (clean, transform, nearest group centre). The page's group is compared with the group of the
    book's whole text. Target >= 0.80 agreement on pages the checker does not abstain on.
T2  Subject: books labelled with a broad subject (reports/eval/subject_labels.csv; labels are never
    used to fit or choose). Each group takes the majority subject of its labelled train books; the
    map is applied to the labelled held-out books. Target: >= 10 points above the better of
    "most common subject" and "subject guessed from the script alone".
T3  Stability: median bootstrap ARI of the chosen hierarchical groups >= 0.60 (from the study).

Writes reports/eval/evaluation_<split>.json and appends a line to docs/evaluation_log.md.
"""
import argparse
import json
from collections import Counter
from datetime import date

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import normalized_mutual_info_score, pairwise_distances

from app.checker import MIN_TOKENS_TO_ASSIGN
from . import config, db, text
from .preprocess import MIN_DOC_CONF, MODEL_SCRIPT

PROCESSED = config.DATA / "processed"
EVAL = config.REPORTS / "eval"
LABELS = EVAL / "subject_labels.csv"
LOG = config.ROOT / "docs" / "evaluation_log.md"
TARGETS = {"T1_page_agreement": 0.80, "T2_points_above_baseline": 10.0, "T3_bootstrap_ari": 0.60}


def transform(fs, tf, token_lists, langs=None):
    if fs == "A":
        return tf.transform(token_lists)[0]
    return tf.transform(token_lists, langs=langs)


def nearest(Z, centroids, metric):
    return np.argmin(pairwise_distances(Z, centroids, metric=metric), axis=1)


def upload_check(fs, tf, centroids, metric, book_group: dict, con) -> dict:
    """T1: every Tesseract page of every held-out book, read exactly as an upload would be."""
    ids = list(book_group)
    q = f"SELECT identifier, leaf, text, mean_conf, ocr_model FROM pages WHERE identifier IN ({','.join('?' * len(ids))})"
    pages = pd.read_sql_query(q, con, params=ids)
    pages = pages[pages["text"].notna()]
    toks, keep, caution, langs = [], [], [], []
    for r in pages.itertuples():
        script = MODEL_SCRIPT.get(r.ocr_model, "Latin")
        t = text.remove_stopwords(text.clean_tokens(r.text, script))
        if len(t) < MIN_TOKENS_TO_ASSIGN:
            continue
        toks.append(t)
        keep.append(r.identifier)
        langs.append(r.ocr_model)
        caution.append(bool((r.mean_conf or 0) < MIN_DOC_CONF or len(t) < 100))
    groups = nearest(transform(fs, tf, toks, langs), centroids, metric)
    agree = np.array([g == book_group[i] for g, i in zip(groups, keep)])
    caution = np.array(caution)
    return {"pages": int(len(pages)), "assigned": int(len(keep)), "abstained": int(len(pages) - len(keep)),
            "abstain_rate": float(1 - len(keep) / max(1, len(pages))),
            "agreement": float(agree.mean()) if len(agree) else None,
            "agreement_confident_pages": float(agree[~caution].mean()) if (~caution).any() else None,
            "agreement_caution_pages": float(agree[caution].mean()) if caution.any() else None,
            "caution_pages": int(caution.sum())}


def subject_scores(train_groups: dict, held_groups: dict, docs: pd.DataFrame, labels: pd.DataFrame, rng) -> dict:
    """T2: group -> majority subject (learned on labelled train books), tested on labelled held-out books."""
    lab = labels.set_index("identifier")["subject"]
    tr = [i for i in train_groups if i in lab.index]
    te = [i for i in held_groups if i in lab.index]
    if len(tr) < 30 or len(te) < 30:
        return {"labelled_train": len(tr), "labelled_heldout": len(te), "note": "too few labelled books"}
    overall = Counter(lab[tr]).most_common(1)[0][0]
    by_group = {}
    for g in set(train_groups[i] for i in tr):
        subs = [lab[i] for i in tr if train_groups[i] == g]
        by_group[g] = Counter(subs).most_common(1)[0][0]
    by_script = {}
    for sc in set(docs.loc[tr, "script"]):
        subs = [lab[i] for i in tr if docs.loc[i, "script"] == sc]
        by_script[sc] = Counter(subs).most_common(1)[0][0]
    truth = np.array([lab[i] for i in te])
    pred_group = np.array([by_group.get(held_groups[i], overall) for i in te])
    pred_major = np.array([overall] * len(te))
    pred_script = np.array([by_script.get(docs.loc[i, "script"], overall) for i in te])
    acc = lambda p: float(np.mean(p == truth))
    a_g, a_m, a_s = acc(pred_group), acc(pred_major), acc(pred_script)
    # permutation test: how often do shuffled labels do as well as the groups?
    perm = [np.mean(pred_group == rng.permutation(truth)) for _ in range(2000)]
    best_base = max(a_m, a_s)
    return {"labelled_train": len(tr), "labelled_heldout": len(te),
            "accuracy_groups": a_g, "baseline_most_common": a_m, "baseline_script_only": a_s,
            "points_above_best_baseline": 100 * (a_g - best_base),
            "permutation_p": float((np.sum(np.array(perm) >= a_g) + 1) / (len(perm) + 1)),
            "nmi_groups_subjects_heldout": float(normalized_mutual_info_score(truth, [held_groups[i] for i in te])),
            "group_to_subject": {str(k): v for k, v in sorted(by_group.items())},
            "subject_counts_heldout": dict(Counter(truth.tolist()))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["val", "test"], required=True)
    a = ap.parse_args()
    feats = joblib.load(PROCESSED / "features.joblib")
    st = joblib.load(PROCESSED / "study.joblib")
    if feats.get("fit") != "train" or st.get("fit") != "train":
        raise SystemExit("evaluation needs the train-only fit: run features --fit train, then study")
    docs = pd.read_csv(PROCESSED / "docs.csv").set_index("identifier")
    fs = st["selection"]["chosen"]
    res = st["results"][fs]
    hl = np.asarray(res["hierarchical"]["labels"])
    metric = res["hierarchical"]["final"]["metric"]
    Z = feats[fs]["Z"].astype(np.float64)
    centroids = np.vstack([Z[hl == c].mean(axis=0) for c in sorted(set(hl))])
    train_groups = dict(zip(feats["ids"], hl.tolist()))

    hold = feats["holdout"]
    want = [i for i in hold["ids"] if docs.loc[i, "split"] == a.split]
    pos = {i: k for k, i in enumerate(hold["ids"])}
    Zh = hold[fs][[pos[i] for i in want]].astype(np.float64)
    held_groups = dict(zip(want, nearest(Zh, centroids, metric).tolist()))

    shares = np.bincount(hl) / len(hl)
    t1 = upload_check(fs, feats[fs]["transform"], centroids, metric, held_groups, db.connect())
    t1["chance"] = float(np.sum(shares ** 2))
    labels = pd.read_csv(LABELS) if LABELS.exists() else pd.DataFrame(columns=["identifier", "subject"])
    t2 = subject_scores(train_groups, held_groups, docs, labels, np.random.default_rng(config.SEED))
    t3 = res["hierarchical"]["bootstrap_ari"]["median"]
    verdict = {
        "T1": t1["agreement"] is not None and t1["agreement"] >= TARGETS["T1_page_agreement"],
        "T2": t2.get("points_above_best_baseline", -1e9) >= TARGETS["T2_points_above_baseline"],
        "T3": t3 >= TARGETS["T3_bootstrap_ari"],
    }
    out = {"split": a.split, "date": str(date.today()), "feature_set": fs, "feature_name": res["name"],
           "setting": {k: res["hierarchical"]["final"][k] for k in ("linkage", "metric", "k", "silhouette", "nmi_script")},
           "held_out_books": len(want), "targets": TARGETS, "T1_upload_check": t1, "T2_subject": t2,
           "T3_bootstrap_median": t3, "met": verdict}
    EVAL.mkdir(parents=True, exist_ok=True)
    (EVAL / f"evaluation_{a.split}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    line = (f"| {date.today()} | {a.split} | {fs} {res['hierarchical']['final']['linkage']} k={res['hierarchical']['final']['k']} "
            f"| {t1['agreement']:.3f} (chance {t1['chance']:.2f}, abstain {t1['abstain_rate']:.0%}) "
            f"| {t2.get('accuracy_groups', float('nan')):.3f} vs {max(t2.get('baseline_most_common', 0), t2.get('baseline_script_only', 0)):.3f} "
            f"| {t3:.2f} | {' '.join(k + ('✓' if v else '✗') for k, v in verdict.items())} |")
    if not LOG.exists():
        LOG.write_text("# Evaluation log\n\nOne line per evaluation run (docs/evaluation_plan.md).\n\n"
                       "| Date | Split | Setting | T1 page agreement | T2 subject accuracy vs best baseline | T3 bootstrap | Targets |\n"
                       "|---|---|---|---|---|---|---|\n", encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
