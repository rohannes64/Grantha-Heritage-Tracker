"""Step 3: from OCR'd pages to a clean, documented study table.

    python -m pipeline.preprocess

Outputs (data/processed/):
  docs.csv            one row per harvested book: metadata, OCR quality, usability flag
  tokens.jsonl        cleaned tokens per usable book
  metadata.joblib     fitted encoder/scaler for the metadata block + the encoded matrix
Report: reports/preprocessing_log.md (every decision, with counts).
"""
import json
import math
from collections import Counter

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import config, db, text

OUT = config.DATA / "processed"

# Usability thresholds (see preprocessing log for the reasoning and the counts they exclude).
MIN_DOC_CONF = 50.0      # word-weighted mean Tesseract confidence across the book's pages
MIN_DOC_TOKENS = 100     # clean tokens left after filtering

NUMERIC = ["year", "log_pages", "mean_conf", "log_tokens"]
CATEGORICAL = ["script"]

MODEL_SCRIPT = {m: s for s, m in config.SCRIPT_MODEL.items()} | {"san": "Devanagari"}


def load(con) -> pd.DataFrame:
    docs = pd.read_sql_query("SELECT * FROM documents WHERE status='harvested'", con)
    pages = pd.read_sql_query("SELECT identifier, leaf, ocr_model, text, mean_conf, n_words, script_ratio "
                              "FROM pages", con)
    return docs, pages


def doc_level(docs: pd.DataFrame, pages: pd.DataFrame) -> pd.DataFrame:
    ocrd = pages[pages["text"].notna()]
    rows = []
    for ident, g in ocrd.groupby("identifier"):
        words = g["n_words"].fillna(0)
        conf = (g["mean_conf"].fillna(0) * words).sum() / words.sum() if words.sum() else None
        model = g["ocr_model"].mode().iat[0]
        script = MODEL_SCRIPT.get(model, "Latin")
        tokens = text.remove_stopwords(
            [t for page in g.sort_values("leaf")["text"] for t in text.clean_tokens(page, script)])
        rows.append({"identifier": ident, "ocr_model": model, "script": script, "pages_ocrd": len(g),
                     "mean_conf": conf, "ocr_words": int(words.sum()),
                     "script_ratio": g["script_ratio"].mean(), "n_tokens": len(tokens), "tokens_list": tokens})
    lvl = pd.DataFrame(rows)
    out = docs.merge(lvl, on="identifier", how="inner")
    out["log_pages"] = np.log10(out["total_pages"].astype(float))
    out["log_tokens"] = np.log10(out["n_tokens"].clip(lower=1).astype(float))
    out["year_missing"] = out["year"].isna().astype(int)
    out["tag_script"] = out["lang_tag"].map(lambda l: config.LANGUAGES[l]["script"])
    out["tag_matches_script"] = (out["tag_script"] == out["script"]).astype(int)
    out["usable"] = ((out["mean_conf"].fillna(0) >= MIN_DOC_CONF) &
                     (out["n_tokens"] >= MIN_DOC_TOKENS)).astype(int)
    return out


def relevance_table(df: pd.DataFrame) -> pd.DataFrame:
    """Variable relevance review: missing share, distinct values, decision and reason."""
    decisions = {
        "year": ("keep (numeric)", "publication era shapes vocabulary and spelling; median-imputed with a missing flag"),
        "total_pages": ("keep as log10 (numeric)", "book length; heavy right tail, so log-transformed"),
        "mean_conf": ("keep (numeric)", "OCR quality; needed to study whether noise drives clusters"),
        "n_tokens": ("keep as log10 (numeric)", "amount of usable text"),
        "script": ("keep (one-hot)", "detected script; the only categorical field encoded"),
        "lang_tag": ("drop", "catalogue tag; replaced by detected script because some tags are wrong"),
        "era": ("drop from features", "derived from year (redundant); kept for profiles and sampling"),
        "title": ("drop from features", "not available for a new scan; used only to display results"),
        "creator": ("drop from features", "free text, mostly unique; display only"),
        "publisher": ("drop from features", "free text, high cardinality; display only"),
        "source_library": ("drop", "provenance, not content"),
        "scanning_centre": ("drop", "provenance; would let clusters form by scanning site (leakage)"),
        "subject_field": ("drop", "mostly the scanning centre, not a topic (checked on real records)"),
        "classification": ("drop from features", "sparse real subject labels; used only as a weak outside check"),
    }
    rows = []
    for col, (decision, reason) in decisions.items():
        s = df[col] if col in df else pd.Series(dtype=object)
        missing = s.isna() | (s.astype(str).str.strip() == "")
        rows.append({"field": col, "missing_pct": round(100 * missing.mean(), 1),
                     "distinct": int(s[~missing].nunique()), "decision": decision, "reason": reason})
    return pd.DataFrame(rows)


def metadata_encoder() -> ColumnTransformer:
    num = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    cat = Pipeline([("impute", SimpleImputer(strategy="constant", fill_value="unknown")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    return ColumnTransformer([("num", num, NUMERIC), ("flag", "passthrough", ["year_missing"]),
                              ("cat", cat, CATEGORICAL)])


def write_log(df: pd.DataFrame, rel: pd.DataFrame, enc: ColumnTransformer) -> None:
    usable = df[df["usable"] == 1]
    L = ["# Preprocessing log", "",
         "Every choice made between OCR output and the clustering features, with counts.", "",
         "## 1. Documents", "",
         f"- Harvested books with OCR: {len(df)}",
         f"- Usable for clustering: {len(usable)} "
         f"(rule: word-weighted mean OCR confidence >= {MIN_DOC_CONF:.0f} and >= {MIN_DOC_TOKENS} clean tokens)",
         f"- Excluded as unreadable OCR: {len(df) - len(usable)}. They stay in the table and are used in the "
         "OCR-noise analysis; they are not silently dropped.", "",
         "| Language tag | Harvested | Usable | Usable % | Median conf | Tag matches detected script |",
         "|---|---|---|---|---|---|"]
    for lang, g in df.groupby("lang_tag"):
        L.append(f"| {config.LANGUAGES[lang]['name']} | {len(g)} | {int(g['usable'].sum())} | "
                 f"{100 * g['usable'].mean():.0f}% | {g['mean_conf'].median():.1f} | {100 * g['tag_matches_script'].mean():.0f}% |")
    L += ["", "## 2. Text cleaning", "",
          "1. Unicode NFC normalisation (one code-point sequence per character).",
          "2. Tokens are runs of letters and combining marks (`\\p{L}\\p{M}`); the default `\\w+` pattern "
          "would split Indian-script words at vowel signs.",
          f"3. Tokens shorter than {text.MIN_TOKEN_CHARS} characters, starting with a stray vowel sign, or mixing "
          "scripts are dropped as OCR noise; tokens in the book's own script or in Latin are kept.",
          "4. Latin tokens lower-cased; English function words removed. Function words of every language are "
          "removed in the feature step by a per-language document-frequency cap (a term in more than 30% of the "
          "books of its own language), not by hand-written lists.",
          "5. Digits, numerals and punctuation removed (not letters).", "",
          "## 3. Variable relevance review", "",
          "| Field | Missing % | Distinct | Decision | Reason |", "|---|---|---|---|---|"]
    for r in rel.itertuples():
        L.append(f"| {r.field} | {r.missing_pct} | {r.distinct} | {r.decision} | {r.reason} |")
    year_med = enc.named_transformers_["num"].named_steps["impute"].statistics_[0]
    L += ["", "## 4. Missing values", "",
          f"- `year`: {int(usable['year_missing'].sum())} of {len(usable)} usable books undated "
          f"({100 * usable['year_missing'].mean():.0f}%). Imputed with the median ({year_med:.0f}) and a "
          "`year_missing` flag, so undated books are not mistaken for typical-year books.",
          "- `script`: never missing (always detected); unknown categories at prediction time are ignored "
          "by the encoder rather than raising an error.",
          "- Text: books whose OCR is unusable are flagged, not imputed (there is no sensible text to impute).",
          "", "## 5. Encoding and scaling", "",
          f"- Numeric fields {NUMERIC} are standardised (zero mean, unit variance) so year (hundreds) "
          "does not outweigh confidence (tens) in distance calculations.",
          f"- Categorical {CATEGORICAL} is one-hot encoded: categories "
          f"{list(enc.named_transformers_['cat'].named_steps['onehot'].categories_[0])}.",
          "- The metadata block is used in a sensitivity check (`python -m pipeline.sensitivity`, "
          "`reports/study/sensitivity.json`): appended to the text features at weights 0.25, 0.5 and 1. The main "
          "study clusters text alone, so groups reflect content, not script or era.", ""]
    config.REPORTS.mkdir(exist_ok=True)
    (config.REPORTS / "preprocessing_log.md").write_text("\n".join(L), encoding="utf-8")
    rel.to_csv(config.REPORTS / "variable_relevance.csv", index=False)


def main() -> None:
    con = db.connect()
    docs, pages = load(con)
    df = doc_level(docs, pages)
    if df.empty:
        raise SystemExit("no OCR'd documents yet; run pipeline.ocr --ingest first")
    OUT.mkdir(parents=True, exist_ok=True)
    usable = df[df["usable"] == 1].copy()
    enc = metadata_encoder().fit(usable)
    X_meta = enc.transform(usable)
    joblib.dump({"encoder": enc, "X": X_meta, "identifiers": usable["identifier"].tolist(),
                 "columns": list(enc.get_feature_names_out())}, OUT / "metadata.joblib")
    with (OUT / "tokens.jsonl").open("w", encoding="utf-8") as f:
        for r in usable.itertuples():
            f.write(json.dumps({"identifier": r.identifier, "tokens": r.tokens_list}, ensure_ascii=False) + "\n")
    df.drop(columns=["tokens_list"]).to_csv(OUT / "docs.csv", index=False)
    rel = relevance_table(df)
    write_log(df, rel, enc)
    print(f"{len(df)} books, {len(usable)} usable; wrote {OUT} and reports/preprocessing_log.md")


if __name__ == "__main__":
    main()
