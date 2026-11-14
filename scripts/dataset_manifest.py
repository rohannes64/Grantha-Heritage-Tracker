"""Freeze what a study run used, so the results can be traced and reproduced.

Writes
  reports/manifest/books.csv        one row per harvested book: identifier, language, script, usable, split,
                                    text source, OCR confidence, tokens (the exact book list and splits)
  reports/manifest/manifest.json    SHA-256 of every input and result file, counts, git commit, Python and
                                    package versions
Run on the machine with data/, after the protocol run:  python scripts/dataset_manifest.py
"""
import hashlib
import json
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from pipeline import config  # noqa: E402

OUT = config.REPORTS / "manifest"
PACKAGES = ["numpy", "scipy", "scikit-learn", "pandas", "joblib", "requests", "fastapi", "pytesseract",
            "pymupdf", "rapidfuzz", "sentence-transformers", "torch"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=BASE, capture_output=True, text=True, timeout=20).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    docs = pd.read_csv(config.PROCESSED / "docs.csv", low_memory=False)
    cols = [c for c in ("identifier", "lang_tag", "script", "usable", "split", "text_source", "mean_conf",
                        "n_tokens", "year", "title") if c in docs]
    docs[cols].sort_values("identifier").to_csv(OUT / "books.csv", index=False)

    files = {}
    for rel in ["data/processed/docs.csv", "data/processed/tokens.jsonl", "data/processed/features.joblib",
                "data/processed/study.joblib", "data/model/bundle.joblib", "reports/eval/subject_labels.csv",
                "reports/eval/evaluation_val.json", "reports/eval/evaluation_test.json",
                "reports/study/selection.json", "reports/study/selection_train.json",
                "reports/deliverable_facts.json", "web/data/study.json"]:
        p = BASE / rel
        if p.exists():
            files[rel] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    for p in sorted((config.PROCESSED).glob("embeddings_*")) + sorted((config.STUDY).glob("results_*.json")):
        files[str(p.relative_to(BASE)).replace("\\", "/")] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    fulltext = config.DATA / "fulltext"
    ft = sorted(fulltext.glob("*.json")) if fulltext.exists() else []
    agg = hashlib.sha256()
    for p in ft:
        agg.update(p.name.encode())
        agg.update(sha256(p).encode())

    usable = docs[docs["usable"] == 1]
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    manifest = {
        "git_commit": git("rev-parse", "HEAD"), "git_dirty_files": (git("status", "--porcelain") or "").count("\n") + 1
        if git("status", "--porcelain") else 0,
        "python": platform.python_version(), "platform": platform.platform(), "packages": versions,
        "seed": config.SEED,
        "counts": {"harvested": int(len(docs)), "usable": int(len(usable)),
                   "splits": {k: int(v) for k, v in usable["split"].value_counts().items()},
                   "text_source": {k: int(v) for k, v in usable["text_source"].value_counts().items()},
                   "fulltext_files": len(ft)},
        "fulltext_sha256_of_hashes": agg.hexdigest() if ft else None,
        "files": files,
        "books_csv_sha256": sha256(OUT / "books.csv"),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {OUT / 'books.csv'} ({len(docs)} books) and {OUT / 'manifest.json'} ({len(files)} files hashed)")


if __name__ == "__main__":
    main()
