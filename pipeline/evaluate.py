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

from . import config, db, tags as tagging, text
from .catalogue import main_class
from .config import MIN_TOKENS_TO_ASSIGN
from .preprocess import MIN_DOC_CONF, MODEL_SCRIPT

PROCESSED = config.PROCESSED
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


def page_check_books(book_group: dict, docs: pd.DataFrame) -> tuple[dict, int]:
    """Books usable for T1. A book whose features were built from its own Tesseract pages (no archive
    text) would be compared with itself, which inflates agreement, so it is left out."""
    kept = {i: g for i, g in book_group.items() if docs.loc[i, "text_source"] != "tesseract_pages"}
    return kept, len(book_group) - len(kept)


def upload_check(fs, tf, centroids, metric, book_group: dict, con, spread=None) -> dict:
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
    D = pairwise_distances(transform(fs, tf, toks, langs), centroids, metric=metric)
    groups = D.argmin(axis=1)
    agree = np.array([g == book_group[i] for g, i in zip(groups, keep)])
    tagged = None
    if spread is not None:
        page_tags = tagging.tags(D, spread)
        hit = np.array([book_group[i] in t for t, i in zip(page_tags, keep)])
        tagged = {"agreement_tagged": float(hit.mean()), "tags_per_page": float(np.mean([len(t) for t in page_tags])),
                  "rule": f"main group + groups within their own {tagging.SPREAD_Q:.0%} spread, at most {tagging.MAX_TAGS}"}
    caution = np.array(caution)
    ci = None
    if len(agree):
        books = np.array(keep)
        uniq = np.unique(books)
        per_book = {b: agree[books == b] for b in uniq}
        ci_rng = np.random.default_rng(config.SEED + 2)
        means = []
        for _ in range(N_CI):        # resample books, not pages: pages of one book are not independent
            pick = ci_rng.choice(uniq, len(uniq))
            means.append(np.concatenate([per_book[b] for b in pick]).mean())
        ci = interval(means)
    return {"pages": int(len(pages)), "assigned": int(len(keep)), "abstained": int(len(pages) - len(keep)),
            "agreement_ci95": ci,
            "abstain_rate": float(1 - len(keep) / max(1, len(pages))),
            "agreement": float(agree.mean()) if len(agree) else None,
            "agreement_confident_pages": float(agree[~caution].mean()) if (~caution).any() else None,
            "agreement_caution_pages": float(agree[caution].mean()) if caution.any() else None,
            "caution_pages": int(caution.sum()), "tagged": tagged}


N_CI = 2000          # bootstrap resamples for confidence intervals


def interval(values) -> list[float]:
    """Central 95% bootstrap interval."""
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def subject_scores(train_groups: dict, held_groups: dict, docs: pd.DataFrame, labels: pd.DataFrame, rng,
                   held_tags: dict | None = None) -> dict:
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
    ci_rng = np.random.default_rng(config.SEED + 1)     # separate stream: the permutation test above is unchanged
    boots = []
    for _ in range(N_CI):
        ix = ci_rng.integers(0, len(te), len(te))
        g, m, sc = (np.mean(pred_group[ix] == truth[ix]), np.mean(pred_major[ix] == truth[ix]),
                    np.mean(pred_script[ix] == truth[ix]))
        boots.append((g, 100 * (g - max(m, sc))))
    boots = np.array(boots)
    tagged = None
    if held_tags is not None:
        subj = [[by_group.get(g, overall) for g in held_tags[i]] for i in te]
        tagged = {"accuracy_tagged": float(np.mean([t in s for s, t in zip(subj, truth)])),
                  "tags_per_book": float(np.mean([len(s) for s in subj])),
                  "distinct_subjects_per_book": float(np.mean([len(set(s)) for s in subj])),
                  "tag_precision": float(np.sum([sum(x == t for x in s) for s, t in zip(subj, truth)]) / sum(len(s) for s in subj))}
    return {"labelled_train": len(tr), "labelled_heldout": len(te), "tagged": tagged,
            "accuracy_groups": a_g, "baseline_most_common": a_m, "baseline_script_only": a_s,
            "points_above_best_baseline": 100 * (a_g - best_base),
            "accuracy_groups_ci95": interval(boots[:, 0]), "points_above_best_baseline_ci95": interval(boots[:, 1]),
            "ci_method": f"{N_CI} bootstrap resamples of the held-out labelled books, percentile interval",
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
    own = pairwise_distances(Z, centroids, metric=metric)[np.arange(len(Z)), hl]
    spread = tagging.group_spread(own, hl, sorted(set(hl)))
    held_tags = dict(zip(want, tagging.tags(pairwise_distances(Zh, centroids, metric=metric), spread)))

    shares = np.bincount(hl) / len(hl)
    t1_books, left_out = page_check_books(held_groups, docs)
    t1 = upload_check(fs, feats[fs]["transform"], centroids, metric, t1_books, db.connect(), spread)
    t1["books"], t1["left_out_own_pages"] = len(t1_books), left_out
    t1["chance"] = float(np.sum(shares ** 2))
    labels = pd.read_csv(LABELS) if LABELS.exists() else pd.DataFrame(columns=["identifier", "subject"])
    t2 = subject_scores(train_groups, held_groups, docs, labels, np.random.default_rng(config.SEED), held_tags)
    # exploratory (added 2026-11-14, after the plan): librarians' classification codes as a second ground truth
    cat = docs["classification"].map(main_class) if "classification" in docs else pd.Series(dtype=object)
    cat_labels = cat.dropna().rename("subject").rename_axis("identifier").reset_index()
    t2_cat = subject_scores(train_groups, held_groups, docs, cat_labels, np.random.default_rng(config.SEED))
    t2_cat |= {"exploratory": True, "labels": "catalogue classification -> main class (pipeline/catalogue.py)",
               "books_with_a_code": int(docs["classification"].notna().sum()) if "classification" in docs else 0,
               "books_mapped": int(cat.notna().sum())}
    t3 = res["hierarchical"]["bootstrap_ari"]["median"]
    verdict = {
        "T1": t1["agreement"] is not None and t1["agreement"] >= TARGETS["T1_page_agreement"],
        "T2": t2.get("points_above_best_baseline", -1e9) >= TARGETS["T2_points_above_baseline"],
        "T3": t3 >= TARGETS["T3_bootstrap_ari"],
    }
    out = {"split": a.split, "date": str(date.today()), "feature_set": fs, "feature_name": res["name"],
           "setting": {k: res["hierarchical"]["final"][k] for k in ("linkage", "metric", "k", "silhouette", "nmi_script")},
           "held_out_books": len(want), "targets": TARGETS, "T1_upload_check": t1, "T2_subject": t2,
           "T2_catalogue_exploratory": t2_cat,
           "T3_bootstrap_median": t3, "met": verdict}
    EVAL.mkdir(parents=True, exist_ok=True)
    (EVAL / f"evaluation_{a.split}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    line = (f"| {date.today()} | {a.split} | {fs} {res['hierarchical']['final']['linkage']} k={res['hierarchical']['final']['k']} "
            + (f"| {t1['agreement']:.3f} (chance {t1['chance']:.2f}, abstain {t1['abstain_rate']:.0%})"
               if t1["agreement"] is not None else "| n/a (no held-out book has archive text) ")
            + (f"; tagged {t1['tagged']['agreement_tagged']:.3f} at {t1['tagged']['tags_per_page']:.2f} tags " if t1.get("tagged") else " ")
            + f"| {t2.get('accuracy_groups', float('nan')):.3f} vs {max(t2.get('baseline_most_common', 0), t2.get('baseline_script_only', 0)):.3f}"
            + (f"; tagged {t2['tagged']['accuracy_tagged']:.3f} at {t2['tagged']['tags_per_book']:.2f} tags, precision {t2['tagged']['tag_precision']:.2f} "
               if t2.get("tagged") else " ")
            +
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
