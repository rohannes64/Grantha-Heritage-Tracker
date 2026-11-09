"""Whole-book text from the Internet Archive's own OCR, for every harvested book.

    python -m pipeline.fulltext [--langs hin,ben] [--workers 8]

For each harvested book, in order of preference:
  1. hOCR search text + page index (page by page). The pages we read ourselves with Tesseract
     (our 5 sampled leaves) are left out, so they stay unseen test material for the upload check.
  2. The full `_djvu.txt` (one block, no page breaks).
  3. Nothing: the book keeps only our 5 Tesseract pages.

Writes data/fulltext/<identifier>.json = {"source": "hocr"|"djvu"|"none", "text": str,
"pages_used": int, "held_out_leaves": [...]}. Resumable: books already written are skipped.
Polite: one IAClient (one request start per second) per worker process.
"""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor

from . import config, db
from .ia import IAClient

OUT = config.DATA / "fulltext"


def djvu_name(meta: dict) -> str | None:
    names = [f["name"] for f in meta.get("files", []) if f["name"].endswith("_djvu.txt")]
    return sorted(names, key=len)[0] if names else None


def fetch_one(client: IAClient, ident: str, ocr_files: str | None, leaves: list[int]) -> dict:
    files = json.loads(ocr_files) if ocr_files else {}
    if files.get("searchtext") and files.get("pageindex"):
        try:
            pages = client.ia_page_texts(ident, files["searchtext"], files["pageindex"])
            held = set(leaves)
            kept = [p for i, p in enumerate(pages) if i not in held]
            return {"source": "hocr", "text": "\n".join(kept), "pages_used": len(kept), "held_out_leaves": sorted(held)}
        except Exception as e:  # fall through to djvu
            print(f"  hOCR failed for {ident}: {e}", flush=True)
    meta = client.metadata(ident)
    name = djvu_name(meta)
    if name:
        cache = config.CACHE_DIR / "ia_djvu" / f"{ident}.txt"
        if not cache.exists():
            r = client._get(config.IA_DOWNLOAD.format(id=ident, name=name))
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(r.content.decode("utf-8", errors="replace"), encoding="utf-8")
        return {"source": "djvu", "text": cache.read_text(encoding="utf-8"), "pages_used": None, "held_out_leaves": []}
    return {"source": "none", "text": "", "pages_used": 0, "held_out_leaves": []}


def run_language(lang: str) -> str:
    con = db.connect()
    rows = con.execute("SELECT identifier, ia_ocr_files FROM documents WHERE status='harvested' AND lang_tag=?",
                       (lang,)).fetchall()
    client = IAClient()
    OUT.mkdir(parents=True, exist_ok=True)
    done = failed = 0
    for r in rows:
        dest = OUT / f"{r['identifier']}.json"
        if dest.exists():
            continue
        leaves = [x[0] for x in con.execute("SELECT leaf FROM pages WHERE identifier=?", (r["identifier"],))]
        try:
            res = fetch_one(client, r["identifier"], r["ia_ocr_files"], leaves)
        except Exception as e:
            failed += 1
            print(f"  {lang} {r['identifier']}: {e}", flush=True)
            continue
        tmp = dest.with_suffix(".part")
        tmp.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        tmp.replace(dest)
        done += 1
        if done % 50 == 0:
            print(f"{lang}: {done} written", flush=True)
    return f"{lang}: {done} written, {failed} failed"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs", default=",".join(config.LANGUAGES))
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    langs = a.langs.split(",")
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for msg in ex.map(run_language, langs):
            print(msg, flush=True)


if __name__ == "__main__":
    from pipeline.fulltext import main as _main
    _main()
