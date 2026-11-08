"""Pilot OCR quality report, per catalogue language and per detected script.

    python -m pipeline.quality

Metrics (stated in the report):
- mean word confidence from Tesseract (0-100),
- script ratio: share of letters in the expected script's Unicode blocks,
- OSD agreement: share of documents whose detected script matches the catalogue tag,
- agreement with the Internet Archive's own OCR of the same page (normalised Indel similarity,
  0-100), where the archive has per-page OCR. The archive's OCR is not ground truth; high
  agreement means two independent runs read the same thing, low agreement flags a problem.
"""
import json
import re
import statistics as st
from collections import defaultdict

from rapidfuzz import fuzz

from . import config, db
from .ia import IAClient

# Usability rule fixed before looking at results.
MIN_MEDIAN_CONF = 60.0
MIN_MEDIAN_SCRIPT_RATIO = 0.80


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def fill_ia_similarity(con, client: IAClient) -> None:
    docs = con.execute("""SELECT identifier, ia_ocr_files FROM documents
                          WHERE status='harvested' AND ia_ocr_files IS NOT NULL""").fetchall()
    for d in docs:
        todo = con.execute("""SELECT leaf, text FROM pages WHERE identifier=? AND text IS NOT NULL
                              AND ia_similarity IS NULL""", (d["identifier"],)).fetchall()
        if not todo:
            continue
        files = json.loads(d["ia_ocr_files"])
        try:
            ia_pages = client.ia_page_texts(d["identifier"], files["searchtext"], files["pageindex"])
        except Exception as e:
            print(f"  IA OCR unavailable for {d['identifier']}: {e}", flush=True)
            continue
        for p in todo:
            if p["leaf"] >= len(ia_pages):
                continue
            ia = _norm(ia_pages[p["leaf"]])
            ours = _norm(p["text"])
            sim = fuzz.ratio(ours, ia) if (ours or ia) else None
            con.execute("UPDATE pages SET ia_text=?, ia_similarity=? WHERE identifier=? AND leaf=?",
                        (ia, sim, d["identifier"], p["leaf"]))
        con.commit()


def _med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 2) if xs else None


def summarise(con) -> list[dict]:
    rows = con.execute("""SELECT d.identifier, d.lang_tag, p.ocr_model, p.osd_script, p.mean_conf, p.n_words,
                                 p.script_ratio, p.ia_similarity
                          FROM pages p JOIN documents d USING (identifier)
                          WHERE d.status='harvested' AND p.text IS NOT NULL""").fetchall()
    by_lang = defaultdict(list)
    for r in rows:
        by_lang[r["lang_tag"]].append(r)
    out = []
    for lang, rs in sorted(by_lang.items(), key=lambda kv: list(config.LANGUAGES).index(kv[0])):
        expected = config.LANGUAGES[lang]["tess"]
        doc_models = {r["identifier"]: r["ocr_model"] for r in rs}
        agree = sum(1 for m in doc_models.values() if m == expected) / len(doc_models)
        confs = [r["mean_conf"] for r in rs]
        ratios = [r["script_ratio"] for r in rs]
        sims = [r["ia_similarity"] for r in rs if r["ia_similarity"] is not None]
        med_conf, med_ratio = _med(confs), _med(ratios)
        usable = (med_conf or 0) >= MIN_MEDIAN_CONF and (med_ratio or 0) >= MIN_MEDIAN_SCRIPT_RATIO
        out.append({
            "lang": lang, "name": config.LANGUAGES[lang]["name"], "documents": len(doc_models), "pages": len(rs),
            "tag_matches_script_pct": round(100 * agree, 1),
            "models_used": dict(sorted({m: list(doc_models.values()).count(m) for m in set(doc_models.values())}.items())),
            "median_conf": med_conf,
            "pages_conf_ge_70_pct": round(100 * sum(1 for c in confs if c and c >= 70) / len(rs), 1),
            "median_script_ratio": med_ratio,
            "median_words_per_page": _med([r["n_words"] for r in rs]),
            "empty_pages_pct": round(100 * sum(1 for r in rs if not r["n_words"]) / len(rs), 1),
            "ia_pages_compared": len(sims), "median_ia_similarity": _med(sims),
            "usable": usable,
        })
    return out


def write_report(con, summary: list[dict]) -> None:
    config.REPORTS.mkdir(exist_ok=True)
    (config.REPORTS / "pilot_ocr_quality.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    counts = {r["status"]: r["n"] for r in con.execute(
        "SELECT status, COUNT(*) n FROM documents GROUP BY status")}
    L = ["# Pilot OCR quality", "",
         f"Documents drawn and tried: {sum(counts.values())} "
         f"(harvested {counts.get('harvested', 0)}, skipped {counts.get('skipped', 0)}, failed {counts.get('failed', 0)}).",
         "",
         f"Usability rule (fixed before the run): median word confidence >= {MIN_MEDIAN_CONF:.0f} "
         f"and median script ratio >= {MIN_MEDIAN_SCRIPT_RATIO:.2f}.",
         "Agreement with the Internet Archive's OCR is a consistency check, not ground truth.", "",
         "| Language | Docs | Pages | Tag matches script | Median conf | Pages conf>=70 | Median script ratio "
         "| Words/page | Empty pages | IA pages compared | Median IA agreement | Usable |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in summary:
        L.append(f"| {s['name']} | {s['documents']} | {s['pages']} | {s['tag_matches_script_pct']}% | {s['median_conf']} "
                 f"| {s['pages_conf_ge_70_pct']}% | {s['median_script_ratio']} | {s['median_words_per_page']} "
                 f"| {s['empty_pages_pct']}% | {s['ia_pages_compared']} | {s['median_ia_similarity']} "
                 f"| {'yes' if s['usable'] else 'NO'} |")
    L += ["", "Models used per language (documents re-routed when OSD found a different script):", ""]
    for s in summary:
        L.append(f"- {s['name']}: {s['models_used']}")
    (config.REPORTS / "pilot_ocr_quality.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    con = db.connect()
    fill_ia_similarity(con, IAClient())
    summary = summarise(con)
    write_report(con, summary)
    print((config.REPORTS / "pilot_ocr_quality.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
