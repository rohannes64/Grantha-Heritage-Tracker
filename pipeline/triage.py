"""Scan quality triage: does a book need to be re-OCRed or re-scanned?

    python -m pipeline.triage          # evaluation on the VM: writes reports/features/triage.json

The rules reuse the usability gate's own thresholds (nothing new is invented):

  low_conf     our OCR confidence is missing or below `preprocess.MIN_DOC_CONF`, and the archive supplied no
               text of its own (so our OCR is the only text there is).
  few_tokens   fewer than `MIN_TOKENS` readable words (`preprocess.MIN_DOC_TOKENS`, the same bar as
               `app.checker.MIN_TOKENS_CONFIDENT`). Unknown token counts do not fire this rule.
  dbscan_noise the book is DBSCAN noise in the topic model. It only adds a reason and raises the score;
               it never changes a verdict by itself. `None` (book not in the model) does not fire.

Verdict:
  archive text present (text_source not in {"tesseract_pages", "none"}) and enough tokens -> "fine",
      never "re-scan" (the archive's own text is usable whatever our OCR scored);
  low_conf (so no archive text)                                                  -> "re-scan";
  few_tokens (with or without archive text)                                      -> "re-ocr";
  otherwise                                                                      -> "fine".

Missing confidence (None/NaN) with no archive text counts as low_conf, hence "re-scan": there is no text at all
to trust. A missing or non-string text_source means no archive text.

Score in [0, 1], higher = worse: the sum of the weights of the rules that fired (weights add up to 1), so it
only grows as more rules fire. The WEIGHTS are design choices that order books, not measured results; the
AUC written by evaluate() / main() is what tests how well that ordering tracks OCR agreement with the archive.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from . import config, db
from .evaluate import N_CI, interval
from .preprocess import MIN_DOC_CONF, MIN_DOC_TOKENS

MIN_CONF = MIN_DOC_CONF
MIN_TOKENS = MIN_DOC_TOKENS          # equals app.checker.MIN_TOKENS_CONFIDENT (the route passes that one in)
NO_ARCHIVE_TEXT = ("tesseract_pages", "none")
WEIGHTS = {"low_conf": 0.5, "few_tokens": 0.3, "dbscan_noise": 0.2}
VERDICTS = ("fine", "re-ocr", "re-scan")
OUT = config.REPORTS / "features" / "triage.json"


def verdict(mean_conf, text_source, n_tokens, dbscan_noise, min_tokens: int = MIN_TOKENS) -> dict:
    # anything that is not a non-empty string (None, NaN, "") means no archive text
    has_archive_text = isinstance(text_source, str) and text_source.strip() != "" and text_source not in NO_ARCHIVE_TEXT
    low_conf = (not has_archive_text) and (mean_conf is None or mean_conf != mean_conf or mean_conf < MIN_CONF)
    few_tokens = n_tokens is not None and n_tokens < min_tokens
    noise = bool(dbscan_noise)

    reasons = []
    if low_conf:
        shown = "missing" if mean_conf is None or mean_conf != mean_conf else f"{mean_conf:.1f}"
        reasons.append(f"our OCR confidence is {shown} (below {MIN_CONF:g}) and the archive has no text of its own")
    if few_tokens:
        reasons.append(f"only {n_tokens} readable words (fewer than {min_tokens})")
    if noise:
        reasons.append("the topic model treats this book as noise (it matches no dense group)")

    if low_conf:
        v = "re-scan"
    elif few_tokens:
        v = "re-ocr"
    else:
        v = "fine"
    score = sum(WEIGHTS[k] for k, fired in (("low_conf", low_conf), ("few_tokens", few_tokens),
                                            ("dbscan_noise", noise)) if fired)
    return {"verdict": v, "score": float(min(1.0, score)), "reasons": reasons}


def row_score(row: dict, min_tokens: int = MIN_TOKENS) -> float:
    return verdict(row.get("mean_conf"), row.get("text_source"), row.get("n_tokens"),
                   row.get("dbscan_noise"), min_tokens)["score"]


def evaluate(rows, sims) -> dict:
    """AUC of the triage score against "our OCR agrees with the archive's OCR less than the pilot median".

    rows: per-book signal dicts (identifier, mean_conf, text_source, n_tokens, dbscan_noise).
    sims: {identifier: median ia_similarity} for pilot books. Only books in both are used.
    """
    from sklearn.metrics import roc_auc_score
    by_id = {r["identifier"]: r for r in rows}
    ids = [i for i in sims if i in by_id and sims[i] is not None]
    out = {"books": len(ids), "signal": "agreement of our OCR with the archive's OCR",
           "rule_thresholds": {"min_conf": MIN_CONF, "min_tokens": MIN_TOKENS, "weights": WEIGHTS},
           "auc": None, "auc_ci95": None}
    if len(ids) < 2:
        return out
    sim = np.array([sims[i] for i in ids], dtype=float)
    y = (sim < np.median(sim)).astype(int)        # 1 = low agreement
    score = np.array([row_score(by_id[i]) for i in ids])
    if y.min() == y.max():
        return out
    out["auc"] = float(roc_auc_score(y, score))
    rng = np.random.default_rng(config.SEED)
    boots = []
    for _ in range(N_CI):                          # resample books
        ix = rng.integers(0, len(ids), len(ids))
        if y[ix].min() == y[ix].max():
            continue
        boots.append(roc_auc_score(y[ix], score[ix]))
    if boots:
        out["auc_ci95"] = interval(boots)
    return out


def main() -> None:
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    docs = pd.read_csv(config.PROCESSED / "docs.csv")
    noise = {}
    bundle_path = config.DATA / "model" / "bundle.joblib"
    if bundle_path.exists():
        import joblib
        b = joblib.load(bundle_path)
        noise = {i: bool(l == -1) for i, l in zip(b["ids"], b["dbscan"]["labels"])}
    rows = [{"identifier": r.identifier, "mean_conf": None if pd.isna(r.mean_conf) else float(r.mean_conf),
             "text_source": r.text_source if isinstance(getattr(r, "text_source", None), str) else None,
             "n_tokens": None if pd.isna(getattr(r, "n_tokens", np.nan)) else int(r.n_tokens),
             "dbscan_noise": noise.get(r.identifier)} for r in docs.itertuples()]
    con = db.connect()
    per_book = {}
    for ident, s in con.execute("SELECT identifier, ia_similarity FROM pages WHERE ia_similarity IS NOT NULL"):
        per_book.setdefault(ident, []).append(s)
    med = {i: float(np.median(v)) for i, v in per_book.items()}
    res = evaluate(rows, med)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
