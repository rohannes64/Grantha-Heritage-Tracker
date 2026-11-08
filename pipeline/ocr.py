"""Step 2: OCR every harvested page with Tesseract.

    python -m pipeline.ocr                 # OCR every complete book without output yet
    python -m pipeline.ocr --workers 10
    python -m pipeline.ocr --ingest        # load the OCR files into SQLite (no other writer running)

Per page: orientation/script detection (OSD), rotation fix, then OCR with the model for the
document's script. The catalogue language tag is trusted only when OSD agrees with its script,
because some tags are wrong (e.g. English books tagged Sanskrit).
"""
import argparse
import json
import os
import time
import unicodedata
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

from . import config, db

os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # one Tesseract thread per worker process


def script_ratio(text: str, script: str) -> float | None:
    """Share of letters/marks in `text` that belong to `script`'s Unicode blocks."""
    ranges = config.SCRIPT_RANGES.get(script)
    letters = [c for c in text if unicodedata.category(c)[0] in "LM"]
    if not ranges or not letters:
        return None
    inside = sum(1 for c in letters if any(lo <= ord(c) <= hi for lo, hi in ranges))
    return inside / len(letters)


def choose_model(lang_tag: str, osd_scripts: list[str]) -> tuple[str, str]:
    """(tesseract model, script) for a document, from its tag and the per-page OSD scripts."""
    tag = config.LANGUAGES[lang_tag]
    if not osd_scripts:
        return tag["tess"], tag["script"]
    detected, _ = Counter(osd_scripts).most_common(1)[0]
    if detected == tag["script"]:
        return tag["tess"], detected  # keeps Hindi vs Sanskrit apart (both Devanagari)
    if detected in config.SCRIPT_MODEL:
        return config.SCRIPT_MODEL[detected], detected
    return tag["tess"], tag["script"]


def _osd(img):
    import pytesseract
    try:
        d = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT, config="--psm 0")
    except pytesseract.TesseractError:
        return None, 0, 0.0
    return config.OSD_SCRIPT.get(d.get("script")), int(d.get("rotate", 0)), float(d.get("script_conf", 0))


def _lines_from_data(d: dict) -> tuple[str, float | None, int]:
    lines, confs, current, key = [], [], [], None
    for i, word in enumerate(d["text"]):
        k = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        if k != key and current:
            lines.append(" ".join(current))
            current = []
        key = k
        w = (word or "").strip()
        conf = float(d["conf"][i])
        if w and conf >= 0:
            current.append(w)
            confs.append(conf)
    if current:
        lines.append(" ".join(current))
    mean = sum(confs) / len(confs) if confs else None
    return "\n".join(lines), mean, len(confs)


def ocr_document(identifier: str, lang_tag: str, pages: list[tuple[int, str]]) -> list[dict]:
    """Worker: OSD on each page, pick one model for the document, OCR every page."""
    import pytesseract
    from PIL import Image, ImageOps

    images, osd = {}, {}
    for leaf, rel in pages:
        img = ImageOps.grayscale(Image.open(config.ROOT / rel))
        script, rotate, sconf = _osd(img)
        if rotate and sconf >= 2:
            img = img.rotate(-rotate, expand=True)  # OSD 'rotate' is clockwise degrees to fix
        images[leaf], osd[leaf] = img, (script if sconf >= 1 else None)
    model, script = choose_model(lang_tag, [s for s in osd.values() if s])
    tag = config.LANGUAGES[lang_tag]
    if model != tag["tess"]:
        # Script detection overrode the catalogue tag. OSD is unreliable on some scripts (it called
        # most Gujarati pages Bengali or Latin in the pilot), so read the middle page with both
        # models and keep the one that reads with higher confidence.
        mid = pages[len(pages) // 2][0]
        trial = {}
        for m in (tag["tess"], model):
            d = pytesseract.image_to_data(images[mid], lang=m, config="--oem 1 --psm 3",
                                          output_type=pytesseract.Output.DICT)
            trial[m] = _lines_from_data(d)[1] or 0.0
        if trial[tag["tess"]] >= trial[model]:
            model, script = tag["tess"], tag["script"]
    out = []
    for leaf, _ in pages:
        d = pytesseract.image_to_data(images[leaf], lang=model, config="--oem 1 --psm 3",
                                      output_type=pytesseract.Output.DICT)
        text, mean_conf, n_words = _lines_from_data(d)
        out.append({"identifier": identifier, "leaf": leaf, "ocr_model": model, "osd_script": osd[leaf],
                    "text": text, "mean_conf": mean_conf, "n_words": n_words,
                    "script_ratio": script_ratio(text, script)})
    return out


OCR_DIR = config.DATA / "ocr"


def pending_documents() -> list[dict]:
    """Books whose pages are complete (`_doc.json` marker) and that have no OCR output yet."""
    out = []
    for marker in sorted(config.PAGES_DIR.glob("*/_doc.json")):
        doc = json.loads(marker.read_text(encoding="utf-8"))
        if not (OCR_DIR / f"{doc['identifier']}.json").exists():
            out.append(doc)
    return out


def run_ocr(workers: int) -> None:
    """OCR every pending book; one JSON file per book, written atomically. Never touches SQLite,
    so it can run in Docker while the harvest (on the host) is still writing the database."""
    docs = pending_documents()
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    print(f"OCR: {len(docs)} documents, {workers} workers", flush=True)
    t0, n = time.time(), 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(ocr_document, d["identifier"], d["lang_tag"], [tuple(p) for p in d["pages"]]):
                d["identifier"] for d in docs}
        for fut in as_completed(futs):
            ident = futs[fut]
            try:
                results = fut.result()
            except Exception as e:
                print(f"  {ident} failed: {e}", flush=True)
                continue
            tmp = OCR_DIR / f"{ident}.part"
            tmp.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
            tmp.replace(OCR_DIR / f"{ident}.json")
            n += 1
            if n % 20 == 0 or n == len(docs):
                rate = (time.time() - t0) / n
                print(f"  {n}/{len(docs)} documents, {rate:.1f}s each, ~{rate * (len(docs) - n) / 60:.0f} min left",
                      flush=True)


def ingest() -> None:
    """Load OCR JSON files into SQLite. Run only when nothing else is writing the database."""
    con = db.connect()
    n = 0
    for path in sorted(OCR_DIR.glob("*.json")):
        results = json.loads(path.read_text(encoding="utf-8"))
        con.executemany("""UPDATE pages SET ocr_model=:ocr_model, osd_script=:osd_script, text=:text,
                           mean_conf=:mean_conf, n_words=:n_words, script_ratio=:script_ratio
                           WHERE identifier=:identifier AND leaf=:leaf""", results)
        n += 1
    con.commit()
    print(f"ingested OCR for {n} documents", flush=True)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--ingest", action="store_true", help="load OCR files into SQLite instead of running OCR")
    ap.add_argument("--watch", type=int, default=0, metavar="MINUTES",
                    help="keep picking up newly harvested books; stop after this many idle minutes")
    args = ap.parse_args(argv)
    if args.ingest:
        ingest()
        return
    idle_since = time.time()
    while True:
        if pending_documents():
            run_ocr(args.workers)
            idle_since = time.time()
        if not args.watch or time.time() - idle_since > args.watch * 60:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
