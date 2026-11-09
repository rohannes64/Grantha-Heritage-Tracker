"""T4 (docs/evaluation_plan.md): every path of the running app gives the documented response.

    python scripts/check_app.py [--base http://localhost:8000]

Uses real page scans of test-split books (data/pages, never redistributed) for each language,
uploaded with the language left on detect and with it chosen; a two-page PDF; pasted text; and the
error paths. Prints one line per check and writes reports/eval/app_checks.json.
"""
import argparse
import io
import json
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import config  # noqa: E402

PAGES = config.DATA / "pages"


def jpg_bytes(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=90)
    return b.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--per-lang", type=int, default=3)
    a = ap.parse_args()
    url = a.base.rstrip("/")
    docs = pd.read_csv(config.DATA / "processed" / "docs.csv")
    con = sqlite3.connect(config.DB_PATH)
    results = []

    def record(name, ok, detail=""):
        results.append({"check": name, "ok": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)

    def post(files=None, data=None):
        return requests.post(f"{url}/api/check", files=files, data=data or {}, timeout=300)

    # endpoints
    r = requests.get(f"{url}/api/health", timeout=30)
    record("health", r.status_code == 200 and r.json().get("status") == "ok", r.text[:80])
    for m in ("hierarchical", "dbscan"):
        r = requests.get(f"{url}/api/clusters", params={"method": m}, timeout=30)
        ok = r.status_code == 200 and len(r.json()) >= 1
        record(f"clusters ({m})", ok, f"{len(r.json()) if ok else r.status_code} groups")
        if ok:
            c = r.json()[0]["cluster"]
            r2 = requests.get(f"{url}/api/clusters/{c}", params={"method": m}, timeout=30)
            record(f"one group ({m})", r2.status_code == 200 and "typical" in r2.json())
    record("unknown group is 404", requests.get(f"{url}/api/clusters/9999", timeout=30).status_code == 404)
    record("unknown method is 400", requests.get(f"{url}/api/clusters", params={"method": "x"}, timeout=30).status_code == 400)
    record("unknown document is 404", requests.get(f"{url}/api/documents/nope", timeout=30).status_code == 404)
    record("study results", requests.get(f"{url}/api/study", timeout=30).status_code == 200)

    # each language, real scans of test books, detect and chosen
    test = docs[(docs["split"] == "test") & (docs["usable"] == 1) & (docs["tag_matches_script"] == 1)]
    for lang, g in test.groupby("lang_tag"):
        tess = config.LANGUAGES[lang]["tess"]
        for ident in g.sort_values("identifier")["identifier"].head(a.per_lang):
            leaves = [x[0] for x in con.execute("SELECT leaf FROM pages WHERE identifier=? AND mean_conf IS NOT NULL ORDER BY mean_conf DESC", (ident,))]
            files = sorted((PAGES / ident).glob("*.jpg"))
            if not leaves or not files:
                continue
            page = PAGES / ident / f"{leaves[0]:05d}.jpg"
            if not page.exists():
                page = files[len(files) // 2]
            data = page.read_bytes()
            model = con.execute("SELECT ocr_model FROM pages WHERE identifier=? LIMIT 1", (ident,)).fetchone()[0]
            for mode in ("auto", lang):
                r = post(files={"file": (page.name, data, "image/jpeg")}, data={"lang": mode})
                if r.status_code != 200:
                    record(f"{lang} scan ({mode})", False, f"HTTP {r.status_code} {r.text[:100]}")
                    continue
                j = r.json()
                got = j.get("ocr", {}).get("model")
                want = model if mode == "auto" else tess
                ok = j["status"] in ("ok", "caution", "abstain") and (got == want or mode == "auto" and got in (model, tess))
                record(f"{lang} scan ({mode})", ok,
                       f"{ident}: read as {got}, conf {j.get('ocr_conf') or 0:.0f}, status {j['status']}, "
                       f"group {j.get('hierarchical', {}).get('name')}")

    # wrong language chosen: must not crash, should caution or abstain
    tam = test[test["lang_tag"] == "tam"]["identifier"].head(1).tolist()
    if tam:
        page = sorted((PAGES / tam[0]).glob("*.jpg"))[2]
        r = post(files={"file": (page.name, page.read_bytes(), "image/jpeg")}, data={"lang": "eng"})
        j = r.json() if r.status_code == 200 else {}
        record("Tamil page with English chosen", r.status_code == 200 and j.get("status") in ("caution", "abstain"),
               f"status {j.get('status')}, conf {j.get('ocr_conf') or 0:.0f}")

    # two-page PDF
    some = test[test["lang_tag"] == "hin"]["identifier"].head(1).tolist()
    if some:
        imgs = [Image.open(p).convert("RGB") for p in sorted((PAGES / some[0]).glob("*.jpg"))[1:3]]
        b = io.BytesIO()
        imgs[0].save(b, "PDF", save_all=True, append_images=imgs[1:], resolution=200)
        r = post(files={"file": ("two.pdf", b.getvalue(), "application/pdf")}, data={"lang": "auto"})
        j = r.json() if r.status_code == 200 else {}
        record("two-page PDF", r.status_code == 200 and j.get("ocr", {}).get("pages") == 2,
               f"pages {j.get('ocr', {}).get('pages')}, status {j.get('status')}")

    # pasted text, a real page's OCR
    ident = test["identifier"].iloc[0]
    txt = con.execute("SELECT text FROM pages WHERE identifier=? AND text IS NOT NULL ORDER BY n_words DESC", (ident,)).fetchone()[0]
    r = post(data={"text": txt, "lang": "auto"})
    record("pasted text", r.status_code == 200 and r.json().get("input") == "text" and r.json()["status"] != "abstain",
           f"status {r.json().get('status') if r.status_code == 200 else r.status_code}")

    # abstain paths
    blank = jpg_bytes(Image.new("L", (1200, 1700), 255))
    r = post(files={"file": ("blank.jpg", blank, "image/jpeg")}, data={"lang": "auto"})
    record("blank page abstains", r.status_code == 200 and r.json()["status"] == "abstain")
    r = post(data={"text": "राम सीता", "lang": "hin"})
    record("too little text abstains", r.status_code == 200 and r.json()["status"] == "abstain")

    # error paths
    r = post(files={"file": ("notes.docx", os.urandom(4000), "application/octet-stream")})
    record("unsupported file is 400", r.status_code == 400, r.text[:80])
    r = post(files={"file": ("big.jpg", b"\xff" * (21 * 1024 * 1024), "image/jpeg")})
    record("file over 20 MB is 413", r.status_code == 413)
    record("nothing sent is 400", post(data={}).status_code == 400)
    record("unknown language is 400", post(data={"text": "hello world " * 30, "lang": "xx"}).status_code == 400)

    out = config.REPORTS / "eval" / "app_checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"base": url, "passed": sum(r["ok"] for r in results), "total": len(results),
                               "checks": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{sum(r['ok'] for r in results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()
