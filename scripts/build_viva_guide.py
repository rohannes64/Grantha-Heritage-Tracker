"""Grantha_Heritage_Tracker_Viva_Voce_Master_Guide.pdf: the viva questions and honest answers, as a printable PDF.

    python scripts/build_viva_guide.py                      # temporary HTML in the system temp folder
    python scripts/build_viva_guide.py --workdir D:/tmp/x   # temporary HTML (and the browser profile) there
    python scripts/build_viva_guide.py --html out.html      # also keep the HTML

Ported from scratch/generate_viva_guide_pdf.py, with the same approach: the guide is written as HTML with
print CSS and printed to PDF by headless Microsoft Edge or Google Chrome (--print-to-pdf). The questions are
in scripts/viva_content.py (shared with docs/viva_notes.md) and every number comes from the result files
through scripts/doc_results.py, where each one carries its `# from: <file>:<key path>` comment.
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_results import ROOT  # noqa: E402
from viva_content import SECTIONS, SUBTITLE, TITLE  # noqa: E402

OUT_PDF = ROOT / "Grantha_Heritage_Tracker_Viva_Voce_Master_Guide.pdf"

CSS = """<style>
  @page { size: A4; margin: 18mm 16mm 20mm 16mm;
    @bottom-right { content: "Page " counter(page) " of " counter(pages); font-family: 'Segoe UI', system-ui, sans-serif; font-size: 8pt; color: #64748B; }
    @bottom-left { content: "Grantha Heritage Tracker (SIH26096) · Viva voce guide"; font-family: 'Segoe UI', system-ui, sans-serif; font-size: 8pt; color: #64748B; } }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1E293B; line-height: 1.55; font-size: 9.8pt; background: #FFFFFF; margin: 0; }
  .doc-header { border-bottom: 2.5px solid #0F172A; padding-bottom: 12px; margin-bottom: 22px; }
  .doc-meta-badge { display: inline-block; background: #0F172A; color: #F8FAFC; font-size: 8pt; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; padding: 3px 8px; border-radius: 3px; margin-bottom: 8px; }
  .doc-title { font-family: Georgia, serif; font-size: 21pt; font-weight: 700; color: #0F172A; margin: 4px 0 6px 0; line-height: 1.2; }
  .doc-subtitle { font-size: 10.5pt; color: #475569; font-weight: 500; }
  .summary { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 5px; padding: 10px 14px; margin-top: 12px; font-size: 9.2pt; }
  .section-title { font-family: Georgia, serif; font-size: 13.5pt; color: #0F172A; border-bottom: 1.5px solid #CBD5E1; padding-bottom: 4px; margin: 20px 0 14px 0; }
  .section-number { background: #B45309; color: #FFFFFF; font-family: sans-serif; font-size: 8.5pt; font-weight: 700; padding: 2px 7px; border-radius: 3px; margin-right: 8px; }
  .qa-card { border: 1px solid #E2E8F0; border-radius: 5px; margin-bottom: 14px; page-break-inside: avoid; }
  .qa-header { background: #F1F5F9; border-bottom: 1px solid #E2E8F0; padding: 8px 12px; font-weight: 700; color: #0F172A; font-size: 9.6pt; }
  .q-badge { background: #0284C7; color: #FFFFFF; font-size: 7.5pt; font-weight: 700; padding: 1px 5px; border-radius: 3px; margin-right: 8px; white-space: nowrap; }
  .qa-body { padding: 10px 14px; font-size: 9.3pt; }
  .core-thesis { background: #FEF3C7; border-left: 3.5px solid #D97706; padding: 6px 10px; margin-bottom: 8px; font-size: 9pt; color: #78350F; font-weight: 600; }
  .formula-box { background: #F8FAFC; border: 1px dashed #94A3B8; border-radius: 4px; padding: 8px 12px; margin: 8px 0; font-family: Consolas, monospace; font-size: 8.6pt; color: #0F172A; }
  .trap-alert { background: #FEE2E2; border-left: 3.5px solid #EF4444; padding: 6px 10px; margin-top: 8px; font-size: 8.6pt; color: #991B1B; }
  .trap-alert strong { color: #7F1D1D; text-transform: uppercase; font-size: 8pt; letter-spacing: 0.5px; }
  table.data-table { width: 100%; border-collapse: collapse; font-size: 8.5pt; margin: 10px 0; }
  table.data-table th, table.data-table td { border: 1px solid #CBD5E1; padding: 5px 8px; text-align: left; }
  table.data-table th { background: #0F172A; color: #F8FAFC; font-weight: 600; }
  table.data-table tr:nth-child(even) { background: #F8FAFC; }
  ul { margin: 4px 0 8px 18px; padding: 0; } li { margin-bottom: 3px; }
  code { font-family: Consolas, monospace; font-size: 8.6pt; }
</style>"""


def inline(text: str) -> str:
    """Escape, then turn **bold**, *italic* and `code` into HTML."""
    s = escape(str(text), quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<em>\1</em>", s)


def card_html(num: str, c: dict) -> str:
    body = [f'<div class="core-thesis">{inline(c["a"])}</div>']
    if c.get("formula"):
        body.append(f'<div class="formula-box">{inline(c["formula"])}</div>')
    if c.get("table"):
        head, rows = c["table"]
        th = "".join(f"<th>{inline(h)}</th>" for h in head)
        trs = "".join("<tr>" + "".join(f"<td>{inline(x)}</td>" for x in r) + "</tr>" for r in rows)
        body.append(f'<table class="data-table"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>')
    if c.get("points"):
        body.append("<ul>" + "".join(f"<li>{inline(p)}</li>" for p in c["points"]) + "</ul>")
    for q, a in c.get("asks", []):
        body.append(f'<div class="trap-alert"><strong>If an examiner asks:</strong> <em>{inline(q)}</em> {inline(a)}</div>')
    return (f'<div class="qa-card"><div class="qa-header"><span class="q-badge">Q {num}</span>{inline(c["q"])}</div>'
            f'<div class="qa-body">{"".join(body)}</div></div>')


def build_html() -> str:
    parts = [f"""<div class="doc-header"><div class="doc-meta-badge">Viva voce guide · built from the result files</div>
<h1 class="doc-title">{inline(TITLE)}</h1><div class="doc-subtitle">{inline(SUBTITLE)}</div></div>"""]
    for i, (title, cards) in enumerate(SECTIONS, 1):
        parts.append(f'<div class="section-title"><span class="section-number">{i}</span>{inline(title)}</div>')
        parts += [card_html(f"{i}.{j}", c) for j, c in enumerate(cards, 1)]
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Grantha viva guide (SIH26096)</title>'
            f'{CSS}</head><body>{"".join(parts)}</body></html>')


def find_browser() -> str | None:
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              shutil.which("msedge"), shutil.which("chromium"), shutil.which("google-chrome")):
        if p and Path(p).exists():
            return p
    return None


def print_pdf(html: str, workdir: Path, out: Path) -> None:
    browser = find_browser()
    if not browser:
        sys.exit("no Edge/Chrome found to print the PDF")
    src = workdir / "viva_guide.html"
    src.write_text(html, encoding="utf-8")
    res = subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                          f"--user-data-dir={workdir / 'browser-profile'}", f"--print-to-pdf={out}", src.as_uri()],
                         capture_output=True, text=True, timeout=180)
    if res.returncode != 0 or not out.exists():
        sys.exit(f"PDF export failed: {res.stderr}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", help="folder for the temporary HTML and browser profile (default: a temp folder)")
    ap.add_argument("--html", help="also write the HTML here")
    args = ap.parse_args(argv)
    html = build_html()
    if args.html:
        Path(args.html).write_text(html, encoding="utf-8")
    if args.workdir:
        Path(args.workdir).mkdir(parents=True, exist_ok=True)
    before = OUT_PDF.stat().st_mtime if OUT_PDF.exists() else None
    with tempfile.TemporaryDirectory(dir=args.workdir) as tmp:
        print_pdf(html, Path(tmp), OUT_PDF)
    if before is not None and OUT_PDF.stat().st_mtime == before:
        sys.exit("PDF export did not rewrite the guide")
    print(f"wrote {OUT_PDF}")


if __name__ == "__main__":
    main()
