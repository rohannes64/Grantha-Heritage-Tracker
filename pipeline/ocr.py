"""Step 2: OCR every harvested page with Tesseract.

    python -m pipeline.ocr                 # all pages without text yet
    python -m pipeline.ocr --workers 10

Per page: orientation/script detection (OSD), rotation fix, then OCR with the model for the
document's script. The catalogue language tag is trusted only when OSD agrees with its script,
because some tags are wrong (e.g. English books tagged Sanskrit).
"""
import argparse
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
    out = []
    for leaf, _ in pages:
        d = pytesseract.image_to_data(images[leaf], lang=model, config="--oem 1 --psm 3",
                                      output_type=pytesseract.Output.DICT)
        text, mean_conf, n_words = _lines_from_data(d)
        out.append({"identifier": identifier, "leaf": leaf, "ocr_model": model, "osd_script": osd[leaf],
                    "text": text, "mean_conf": mean_conf, "n_words": n_words,
                    "script_ratio": script_ratio(text, script)})
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args(argv)
    con = db.connect()
    rows = con.execute("""
        SELECT p.identifier, d.lang_tag, p.leaf, p.image_path FROM pages p
        JOIN documents d USING (identifier)
        WHERE d.status='harvested' AND p.text IS NULL ORDER BY d.lang_tag, d.sample_rank, p.leaf""").fetchall()
    docs: dict[str, tuple[str, list]] = {}
    for r in rows:
        docs.setdefault(r["identifier"], (r["lang_tag"], []))[1].append((r["leaf"], r["image_path"]))
    print(f"OCR: {len(docs)} documents, {len(rows)} pages, {args.workers} workers", flush=True)
    t0, n = time.time(), 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(ocr_document, ident, lang, pages): ident for ident, (lang, pages) in docs.items()}
        for fut in as_completed(futs):
            try:
                results = fut.result()
            except Exception as e:
                print(f"  {futs[fut]} failed: {e}", flush=True)
                continue
            con.executemany("""UPDATE pages SET ocr_model=:ocr_model, osd_script=:osd_script, text=:text,
                               mean_conf=:mean_conf, n_words=:n_words, script_ratio=:script_ratio
                               WHERE identifier=:identifier AND leaf=:leaf""", results)
            con.commit()
            n += 1
            if n % 20 == 0 or n == len(docs):
                rate = (time.time() - t0) / n
                print(f"  {n}/{len(docs)} documents, {rate:.1f}s each, ~{rate * (len(docs) - n) / 60:.0f} min left",
                      flush=True)


if __name__ == "__main__":
    main()
