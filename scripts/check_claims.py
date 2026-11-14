"""No number without a source: every number in the deliverables must come from a result file or the code.

Allowed numbers are built from
  1. reports/deliverable_facts.json (written from the pipeline's result files), in every way they are printed
     (raw, rounded to 0-4 decimals, as a percentage with 0-1 decimals, with thousands separators), and
  2. constants imported from the pipeline and app (thresholds, chunk sizes, bootstrap settings, targets),
  3. a short explicit list of numbers that are not results (team roll numbers, the problem code, units).
Structural numbers (slide/section/figure/question numbers, dates, years in prose) are skipped by pattern.

    python scripts/check_claims.py            # checks the default deliverables; exit 1 if anything is unsourced
    python scripts/check_claims.py FILE ...   # check given files (.md, .pptx, .pdf, .txt)
    python scripts/check_claims.py --explain  # also list each sourced number and the fact it matched
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

DEFAULT_FILES = ["README.md", "docs/viva_notes.md", "docs/Grantha_Speaker_Script.md",
                 "Grantha_Heritage_Tracker_SIH26096.pptx", "Grantha_Heritage_Tracker_Viva_Voce_Master_Guide.pdf"]
WEB_GLOBS = ["web/*.html", "web/js/*.js"]          # the website's visible text and script strings

# Not results: identifiers and course facts given by the team, and units of the method stated in prose.
EXPLICIT = {
    "12403675", "12413353", "12401062",          # roll numbers
    "26096",                                      # SIH26096 problem code
    "768",                                        # dimension of text-multilingual-embedding-002 (model card)
    "1960",                                       # sampling frame: books published up to 1960 (docs/evaluation_plan.md)
    "-1",                                         # DBSCAN's noise label
}

NUMBER = re.compile(r"(?<![\w.:/-])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?(?![\w])")
SKIP_CONTEXT = re.compile(
    r"(?:slide|figure|fig\.|section|q|step|unit|co|t|table|panel|group|g|page|round|tranche|level|pc|presenter|col(?:umn)?"
    r"|python|tesseract|version|v)\s*$",
    re.IGNORECASE)
DATE = re.compile(r"\b(19|20)\d\d-\d\d-\d\d\b")


def variants(x) -> set[str]:
    """The printed forms of a number."""
    out = set()
    if isinstance(x, bool) or x is None:
        return out
    if isinstance(x, int) or (isinstance(x, float) and x.is_integer() and abs(x) >= 1):
        i = int(x)
        out |= {str(i), f"{i:,}"}
    if isinstance(x, (int, float)):
        f = float(x)
        for d in range(0, 5):
            out.add(f"{f:.{d}f}")
            out.add(f"{f:,.{d}f}")
        if -1.5 <= f <= 1.5:                       # shares printed as percentages
            for d in (0, 1, 2):
                out.add(f"{100 * f:.{d}f}%")
                out.add(f"{100 * f:.{d}f}")
        out |= {v.lstrip("+") for v in out} | {"+" + v for v in out if not v.startswith("-")}
    return out


def walk(obj, path="facts"):
    """(path, number) for every number in the facts, e.g. ('facts.evaluation.test.t2_accuracy', 0.475)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield path, obj


def code_constants() -> list[tuple[str, float]]:
    from pipeline import config, evaluate, features, preprocess, study, tags
    from app import checker, ocr_input
    named = {"config.SEED": config.SEED, "config.MIN_TOKENS_TO_ASSIGN": config.MIN_TOKENS_TO_ASSIGN,
             "features.CHUNK_TOKENS": features.CHUNK_TOKENS, "features.MAX_CHUNKS": features.MAX_CHUNKS,
             "features.N_COMPONENTS": features.N_COMPONENTS, "preprocess.MIN_DOC_CONF": preprocess.MIN_DOC_CONF,
             "study.N_BOOT": study.N_BOOT, "study.BOOT_FRAC": study.BOOT_FRAC, "study.MIN_BOOT_ARI": study.MIN_BOOT_ARI,
             "study.MAX_SCRIPT_NMI": study.MAX_SCRIPT_NMI, "study.K_RANGE.min": min(study.K_RANGE),
             "study.K_RANGE.max": max(study.K_RANGE), "study.HIGH_CONF": study.HIGH_CONF,
             "checker.MIN_TOKENS_CONFIDENT": checker.MIN_TOKENS_CONFIDENT, "ocr_input.MAX_PAGES": ocr_input.MAX_PAGES,
             "tags.MAX_TAGS": tags.MAX_TAGS, "tags.SPREAD_Q": tags.SPREAD_Q, "len(config.LANGUAGES)": len(config.LANGUAGES),
             "evaluate.permutations": 2000, "features.LANG_DF_CAP": features.LANG_DF_CAP}
    named |= {f"config.PAGE_POSITIONS[{i}]": v for i, v in enumerate(config.PAGE_POSITIONS)}
    named |= {f"evaluate.TARGETS.{k}": v for k, v in evaluate.TARGETS.items()}
    named |= {f"preprocess.SPLITS.{n}": s for n, s in preprocess.SPLITS}
    return [(k, v) for k, v in named.items() if isinstance(v, (int, float))]


def allowed(facts: dict) -> dict[str, list[str]]:
    """Every printable form of every sourced number -> where it comes from."""
    ok: dict[str, list[str]] = {t: ["explicit"] for t in EXPLICIT}

    def add(source, value):
        for t in variants(value):
            ok.setdefault(t, []).append(source)

    for src, v in list(walk(facts)) + code_constants():
        add(src, v)
    for key in ("pca_Z_3d", "pca_embedder_pc123"):
        xs = facts.get("figures", {}).get(key, [])
        if len(xs) >= 3:
            add(f"sum(figures.{key}[:2])", xs[0] + xs[1])
            add(f"sum(figures.{key}[:3])", sum(xs[:3]))
    ev = facts.get("evaluation", {})
    labelled = [ev.get("test", {}).get("t2_labelled_train"), ev.get("test", {}).get("t2_labelled_heldout"),
                ev.get("val", {}).get("t2_labelled_heldout")]
    if all(isinstance(x, int) for x in labelled):
        add("labelled train+val+test", sum(labelled))
    for r in facts.get("corpus", {}).get("by_language", []):
        add(f"usable share {r['name']}", r["usable"] / r["harvested"])
    for g in facts.get("groups", []):
        add("group number", g["group"] + 1)
    c = facts.get("corpus", {})
    if c.get("harvested") and c.get("usable"):
        add("excluded share", 1 - c["usable"] / c["harvested"])
        add("usable share", c["usable"] / c["harvested"])
        add("excluded books", c["harvested"] - c["usable"])
    add("books with archive text", sum(v for k, v in c.get("text_source", {}).items() if k != "tesseract_pages"))
    return ok


def html_text(src: str) -> list[str]:
    """Visible text of a page: scripts, styles, comments and attribute values are not text a reader sees."""
    from html import unescape
    src = re.sub(r"(?is)<(script|style)\b.*?</\1>|<!--.*?-->", " ", src)
    return [unescape(line).strip() for line in re.sub(r"(?s)<[^>]+>", "\n", src).split("\n") if line.strip()]


def js_strings(src: str) -> list[str]:
    """The string literals of a script (what it can put on screen); ${...} inside templates is code, not text."""
    src = re.sub(r"(?m)//[^\n]*$", " ", src)
    src = re.sub(r"(?s)/\*.*?\*/", " ", src)
    out = []
    literal = re.compile(r"`((?:\\.|[^`\\])*)`|'((?:\\.|[^'\\\n])*)'|\"((?:\\.|[^\"\\\n])*)\"")
    for m in literal.finditer(src):
        lit = next(g for g in m.groups() if g is not None)
        lit = re.sub(r"\$\{[^}]*\}", " ", lit)
        lit = re.sub(r"\b[a-zA-Z]+\([^()]*\)", " ", lit)   # SVG/CSS functions such as rotate(-90) are code
        if re.search(r"[A-Za-z]", lit):          # skip bare numeric/format strings such as "0.5" or "%"
            out.append(lit)
    return out


def read_text(path: Path) -> list[str]:
    if path.suffix == ".pptx":
        from pptx import Presentation
        lines = []
        for i, s in enumerate(Presentation(path).slides, 1):
            for sh in s.shapes:
                if sh.has_text_frame:
                    lines += [f"[slide {i}] {p}" for p in sh.text_frame.text.split("\n")]
                if getattr(sh, "has_table", False) and sh.has_table:
                    lines += [f"[slide {i}] " + " | ".join(c.text for c in r.cells) for r in sh.table.rows]
            if s.has_notes_slide:
                lines += [f"[slide {i} notes] {p}" for p in s.notes_slide.notes_text_frame.text.split("\n")]
        return lines
    if path.suffix in (".html", ".htm"):
        return html_text(path.read_text(encoding="utf-8"))
    if path.suffix == ".js":
        return js_strings(path.read_text(encoding="utf-8"))
    if path.suffix == ".pdf":
        import fitz
        return [f"[page {i}] {line}" for i, page in enumerate(fitz.open(path), 1) for line in page.get_text().split("\n")]
    return path.read_text(encoding="utf-8").split("\n")


def unsourced(lines: list[str], ok: set[str]) -> list[tuple[int, str, str]]:
    bad = []
    in_code = False
    for n, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        text = DATE.sub(" ", line)
        for m in NUMBER.finditer(text):
            tok = m.group(0)
            before = text[max(0, m.start() - 12):m.start()]
            if SKIP_CONTEXT.search(before) or re.search(r"(slide|page) \d+(?: notes)?\]\s*$", text[:m.start()]):
                continue
            if re.fullmatch(r"(19|20)\d\d", tok.rstrip("%")):   # years in prose (e.g. "printed in 1923")
                continue
            if tok in ok or tok.rstrip("%") in ok:
                continue
            if re.fullmatch(r"\d", tok):                        # single digits: list counts, "5 pages", "3 of us"
                continue
            bad.append((n, tok, line.strip()[:140]))
    return bad


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    facts = json.loads((BASE / "reports" / "deliverable_facts.json").read_text(encoding="utf-8"))
    ok = allowed(facts)
    explain = "--explain" in argv
    argv = [a for a in argv if a != "--explain"]
    files = [Path(a) for a in argv] or ([BASE / f for f in DEFAULT_FILES]
                                        + sorted(p for g in WEB_GLOBS for p in BASE.glob(g)))
    if explain:   # every sourced number and what it matched, so a reviewer can spot coincidental matches
        for f in files:
            for line in read_text(f):
                for m in NUMBER.finditer(DATE.sub(" ", line)):
                    tok = m.group(0)
                    srcs = ok.get(tok) or ok.get(tok.rstrip("%"))
                    if srcs:
                        print(f"{f.name}: {tok:>10} <- {', '.join(sorted(set(srcs))[:3])}")
    total = 0
    for f in files:
        if not f.exists():
            print(f"MISSING {f}")
            total += 1
            continue
        bad = unsourced(read_text(f), ok)
        total += len(bad)
        for n, tok, line in bad:
            print(f"{f.relative_to(BASE) if f.is_absolute() else f}:{n}: unsourced {tok!r}: {line}")
    print(f"{total} unsourced number(s) in {len(files)} file(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
