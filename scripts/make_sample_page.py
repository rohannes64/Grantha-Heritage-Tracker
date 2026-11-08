"""Prepare the landing page's demo: one page from a book outside the study sample, OCR'd.

    python scripts/make_sample_page.py --lang tam      (run in the pipeline container: needs Tesseract)

The book is taken from rank 3000 onward of the language's seeded draw order, which the harvest
never reaches (it stops near rank 400), so the demo is never checked against itself.
"""
import argparse
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app.ocr_input import ocr_images  # noqa: E402
from pipeline import config, harvest, sampling, text  # noqa: E402
from pipeline.ia import IAClient  # noqa: E402

HTML_LANG = {"eng": "en", "hin": "hi", "san": "sa", "ben": "bn", "guj": "gu", "tel": "te", "kan": "kn", "tam": "ta"}
OUT = config.ROOT / "web" / "data" / "sample_page.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="tam", choices=list(config.LANGUAGES))
    ap.add_argument("--start", type=int, default=3000)
    args = ap.parse_args()
    client = IAClient()
    order = sampling.stratified_order(harvest.build_frame(client, args.lang))
    script = config.LANGUAGES[args.lang]["script"]
    for row in order[args.start:args.start + 40]:
        ident = row["identifier"]
        meta = client.metadata(ident)
        dc = sampling.parse_dc(meta["metadata"].get("description"))
        total = sampling.total_pages_of(dc, meta["metadata"]) or client.page_count_from_numbers(ident, meta["files"])
        if not total or total < config.MIN_PAGES:
            continue
        leaf = round(0.5 * (total - 1))
        url = config.IA_PAGE.format(id=ident, leaf=leaf, width=config.PAGE_WIDTH)
        img = Image.open(io.BytesIO(client._get(url).content))
        ocr = ocr_images([img], args.lang)
        toks = text.clean_tokens(ocr["text"], script)
        print(f"{ident} leaf {leaf}: conf {ocr['ocr_conf']:.0f}, {len(toks)} tokens", flush=True)
        if ocr["ocr_conf"] < 65 or len(toks) < 150:
            continue
        lines = [l for l in ocr["text"].splitlines() if len(text.clean_tokens(l, script)) >= 3][:3]
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({
            "identifier": ident, "leaf": leaf, "lang": args.lang, "html_lang": HTML_LANG[args.lang],
            "title": sampling.first_str(meta["metadata"].get("title")), "year": row["year"] or None,
            "image_url": url, "text": ocr["text"], "excerpt": "\n".join(lines),
            "ocr_conf": round(ocr["ocr_conf"], 1), "model": ocr["model"],
            "archive_url": f"https://archive.org/details/{ident}",
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")
        return
    raise SystemExit("no suitable page found in this range; try --start 3040")


if __name__ == "__main__":
    main()
