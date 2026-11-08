"""Step 1: sampling frame -> stratified draw -> page downloads.

    python -m pipeline.harvest --stage pilot          # 50 documents per language
    python -m pipeline.harvest --stage full           # 375 per language (pilot docs are reused)
    python -m pipeline.harvest --stage pilot --langs eng,tam

Resumable: documents already harvested, skipped or failed are not fetched again.
"""
import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from . import config, db, sampling
from .ia import IAClient

FRAME_FIELDS = ["identifier", "date_raw", "year", "era"]
PAGE_THREADS = 3


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def build_frame(client: IAClient, lang: str) -> list[dict]:
    """Every in-scope item for one language (published <= MAX_YEAR or undated). Cached as CSV."""
    path = config.FRAME_DIR / f"{lang}.csv"
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    query = f"collection:{config.COLLECTION} AND language:{lang} AND mediatype:texts"
    rows, seen, total = [], set(), 0
    log(f"[{lang}] building sampling frame (one request per 10,000 items)...")
    for it in client.scrape(query, ["identifier", "date"]):
        total += 1
        if total % 10000 == 0:
            log(f"[{lang}]   {total} items listed")
        ident = it["identifier"]
        if ident in seen:
            continue
        seen.add(ident)
        year = sampling.parse_year(it.get("date"))
        era = sampling.era_of(year)
        if era is None:
            continue
        rows.append({"identifier": ident, "date_raw": sampling.first_str(it.get("date")) or "",
                     "year": year or "", "era": era})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, FRAME_FIELDS)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)
    log(f"[{lang}] frame: {total} items in collection, {len(rows)} in scope (<= {config.MAX_YEAR} or undated)")
    return rows


def harvest_one(client: IAClient, con, lang: str, rank: int, row: dict) -> str:
    """Fetch metadata and pages for one item. Returns the final status."""
    ident = row["identifier"]
    meta_all = client.metadata(ident)
    meta, files = meta_all["metadata"], meta_all["files"]
    dc = sampling.parse_dc(meta.get("description"))
    total = sampling.total_pages_of(dc, meta) or client.page_count_from_numbers(ident, files)
    names = [f["name"] for f in files]
    ia_ocr = {
        "searchtext": next((n for n in names if n.endswith("_hocr_searchtext.txt.gz")), None),
        "pageindex": next((n for n in names if n.endswith("_hocr_pageindex.json.gz")), None),
    }
    year = int(row["year"]) if row["year"] else None
    doc = {
        "identifier": ident, "lang_tag": lang, "era": row["era"], "sample_rank": rank,
        "title": sampling.first_str(meta.get("title")),
        "creator": sampling.first_str(meta.get("creator")),
        "date_raw": row["date_raw"] or None, "year": year,
        "publisher": "; ".join(dc.get("publisher", [])) or None,
        "source_library": "; ".join(dc.get("source.library", [])) or None,
        "scanning_centre": "; ".join(dc.get("description.scanningcentre", [])) or None,
        "subject_field": sampling.first_str(meta.get("subject")),
        "classification": " | ".join(dc.get("subject.classification", [])) or None,
        "total_pages": total,
        "ia_ocr_files": json.dumps(ia_ocr) if ia_ocr["searchtext"] and ia_ocr["pageindex"] else None,
        "status": "drawn", "note": None,
    }
    if total is None or total < config.MIN_PAGES:
        doc["status"], doc["note"] = "skipped", f"page count {total} (< {config.MIN_PAGES} or unknown)"
        _save_doc(con, doc)
        return doc["status"]

    def fetch(leaf_pos):
        leaf, pos = leaf_pos
        rel = f"data/pages/{ident}/{leaf:05d}.jpg"
        try:
            client.page_image(ident, leaf, config.ROOT / rel)
            return (ident, leaf, pos, rel)
        except Exception as e:  # one bad page should not sink the book
            log(f"  page {leaf} of {ident} failed: {e}")
            return None

    # Requests still start at most once per second (the client paces them); up to three overlap.
    with ThreadPoolExecutor(max_workers=PAGE_THREADS) as ex:
        pages = [p for p in ex.map(fetch, sampling.choose_leaves(total)) if p]
    if len(pages) < 3:
        doc["status"], doc["note"] = "failed", f"only {len(pages)} pages downloaded"
    else:
        doc["status"] = "harvested"
    _save_doc(con, doc)
    con.executemany("INSERT OR IGNORE INTO pages (identifier, leaf, position, image_path) VALUES (?,?,?,?)", pages)
    con.commit()
    if doc["status"] == "harvested":
        write_marker(ident, lang, [(leaf, rel) for _, leaf, _, rel in pages])
    return doc["status"]


def write_marker(ident: str, lang: str, pages: list[tuple[int, str]]) -> None:
    """`_doc.json` beside the pages tells the OCR step a book is complete (no DB access needed)."""
    path = config.PAGES_DIR / ident / "_doc.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps({"identifier": ident, "lang_tag": lang, "pages": pages}), encoding="utf-8")
    tmp.replace(path)


def _save_doc(con, doc: dict) -> None:
    cols = ", ".join(doc)
    marks = ", ".join("?" for _ in doc)
    con.execute(f"INSERT OR REPLACE INTO documents ({cols}) VALUES ({marks})", list(doc.values()))
    con.commit()


def harvest_language(client: IAClient, con, lang: str, target: int) -> None:
    frame = build_frame(client, lang)
    order = sampling.stratified_order(frame)
    # Anything already in the table (any language, any status) is never fetched again.
    # A multi-language item counts only for the language that drew it first.
    done = {r["identifier"] for r in con.execute("SELECT identifier FROM documents")}
    have = con.execute("SELECT COUNT(*) FROM documents WHERE lang_tag=? AND status='harvested'",
                       (lang,)).fetchone()[0]
    log(f"[{lang}] target {target}, already harvested {have}")
    for rank, row in enumerate(order):
        if have >= target:
            break
        ident = row["identifier"]
        if ident in done:
            continue
        try:
            status = harvest_one(client, con, lang, rank, row)
        except Exception as e:
            status = "failed"
            con.execute("INSERT OR REPLACE INTO documents (identifier, lang_tag, era, sample_rank, status, note) "
                        "VALUES (?,?,?,?,?,?)", (ident, lang, row["era"], rank, status, str(e)[:300]))
            con.commit()
        done.add(ident)
        if status == "harvested":
            have += 1
            if have % 10 == 0:
                log(f"[{lang}] {have}/{target}")
    log(f"[{lang}] finished with {have} harvested")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=["pilot", "full"])
    ap.add_argument("--langs", default=",".join(config.LANGUAGES))
    ap.add_argument("--markers", action="store_true",
                    help="only (re)write _doc.json markers for books already harvested")
    args = ap.parse_args(argv)
    if args.markers:
        con = db.connect()
        n = 0
        for d in con.execute("SELECT identifier, lang_tag FROM documents WHERE status='harvested'").fetchall():
            pages = [(r["leaf"], r["image_path"]) for r in con.execute(
                "SELECT leaf, image_path FROM pages WHERE identifier=? ORDER BY leaf", (d["identifier"],))]
            write_marker(d["identifier"], d["lang_tag"], pages)
            n += 1
        log(f"wrote {n} markers")
        return
    if not args.stage:
        ap.error("--stage is required unless --markers is given")
    target = config.PILOT_PER_LANG if args.stage == "pilot" else config.FULL_PER_LANG
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    unknown = [l for l in langs if l not in config.LANGUAGES]
    if unknown:
        sys.exit(f"unknown language codes: {unknown}")
    client, con = IAClient(), db.connect()
    for lang in langs:
        harvest_language(client, con, lang, target)


if __name__ == "__main__":
    main()
