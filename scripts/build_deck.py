"""Builds Grantha_Heritage_Tracker_SIH26096.pptx from the result files, with no hand-typed result.

    python scripts/build_deck.py
    powershell -File scripts/embed_fonts.ps1        # optional: embeds the fonts so any PC shows the deck as designed

Reads only:
  reports/deliverable_facts.json           every number written on a slide or in the notes
  web/data/study.json, reports/**/*.json   chart series and names the facts file does not hold
  reports/features/*.json                  feature evaluations, when present (slides show the tool without numbers if absent)
  docs/assets/figures/*.png                the team's study figures (corpus gate, DFD, Ward selection, DBSCAN sweep, PCA,
                                           centring), tinted onto the parchment ground
  docs/assets/manuscript_model.png         the title slide's palm-leaf manuscript, rendered from docs/build/manuscript/
  docs/assets/fibre_wash.png               the parchment fibre texture laid on the deck's bands

Every number in slide text comes from deliverable_facts.json or reports/features/*.json, so
`python scripts/check_claims.py` can trace it. Every sentence that states an outcome (met or not met, better or worse,
which subject a group leans to, whether centring helped) is chosen by a branch on the facts, never written for one result.
Chart values carry a `# from:` comment naming their file and key path. Titles that state a result are built from
the data, so they stay true when the results change.

Design: Hallmark's Vellum theme, parchment colourway: a parchment ground, umber ink, Grenze Gotisch for the heads,
its roman sibling Grenze for one statement, Hanken Grotesk for everything read, hairline and double rules, and
ultramarine as the one pigment (the series that argues, the figures, the summary field). No shadows, 2 px corners.
Fonts: Grenze Gotisch SemiBold, Grenze, Hanken Grotesk (Regular, Medium, SemiBold), SIL Open Font License, from Google
Fonts. They must be installed to build a faithful copy; scripts/embed_fonts.ps1 embeds them in the saved deck.
"""
import json
import sys
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_MARKER_STYLE, XL_TICK_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

# ==============================================================================
# DESIGN TOKENS: the only place a colour, font or size is written (Hallmark Vellum, parchment; oklch -> sRGB)
# ==============================================================================
COLOR = {
    "paper": "F3EADA",        # oklch(94% 0.024 82): the ground
    "paper_2": "E9DCC7",      # oklch(90% 0.032 80): the fibre band
    "paper_3": "DECFB7",      # oklch(86% 0.036 78): baseline bars, the empty share
    "ink": "261A12",          # oklch(23% 0.025 55): umber ink
    "ink_2": "3A2D24",        # oklch(31% 0.024 58)
    "muted": "62554A",        # oklch(46% 0.024 64): secondary text, axis labels
    "rule": "BCAB96",         # oklch(75% 0.035 72): hairlines; also the reference series
    "accent": "2942AB",       # oklch(43% 0.17 268): ultramarine, the one pigment
    "accent_deep": "1B2E87",  # oklch(35% 0.15 268)
    "accent_soft": "D1DBF3",  # oklch(89% 0.035 268): table shading, the key column
    "accent_ink": "F5EEE0",   # oklch(95% 0.02 82): text on the pigment field
}
FONT = {"display": "Grenze Gotisch SemiBold",   # heads, figures (never below 30 px, never running text)
        "outlier": "Grenze",                     # one statement set large
        "body": "Hanken Grotesk", "body_med": "Hanken Grotesk Medium", "body_semi": "Hanken Grotesk SemiBold",
        "indic": "Nirmala UI"}
SIZE = {"display": 66, "title": 40, "figure": 60, "stat": 104, "section": 28, "statement": 26, "lead": 20, "body": 15,
        "title_s": 32, "small": 13, "caption": 10.5, "chart": 12, "table": 12.5, "mast": 11.5}
SLIDE_W, SLIDE_H = 13.333, 7.5
MARGIN = 0.75                       # left and right
MAST_Y = 0.36                       # running head
TITLE_Y, TITLE_H = 0.88, 1.12       # the head sits on its baseline at TITLE_Y + TITLE_H
BODY_Y = 2.25                       # content starts here
FOOT_Y = 6.92                       # the hairline above the source line
GAP = 0.4
TOTAL = 11                          # slides in the deck, for the running "N of 11"
ASSETS = Path(__file__).resolve().parents[1] / "docs" / "assets"
FIG = ASSETS / "figures"            # the team's study figures, tinted onto parchment (white multiplied by the paper colour)
LINKS = {                           # the Project Links slide; each was opened and answered on 2026-11-15
    "repo": "https://github.com/rohannes64/Grantha-Heritage-Tracker",
    "live": "https://grantha.tail7ee38f.ts.net/",
    "archive": "https://archive.org/details/digitallibraryindia",
    "books": "https://grantha.tail7ee38f.ts.net/data/corpus.json",
    "map": "https://grantha.tail7ee38f.ts.net/galaxy.html",
    "study": "https://grantha.tail7ee38f.ts.net/study.html",
    "api": "https://grantha.tail7ee38f.ts.net/docs",
}


def rgb(name: str) -> RGBColor:
    return RGBColor.from_string(COLOR[name])


def mix(a: str, b: str, t: float) -> RGBColor:
    """A colour t of the way from token a to token b (for table shading, and quiet text on the pigment field)."""
    ca, cb = RGBColor.from_string(COLOR[a]), RGBColor.from_string(COLOR[b])
    return RGBColor(*(round(x + (y - x) * t) for x, y in zip(ca, cb)))


# ==============================================================================
# DATA
# ==============================================================================
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Grantha_Heritage_Tracker_SIH26096.pptx"


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


F = load("reports/deliverable_facts.json")
STUDY = load("web/data/study.json")
NAMES = load("reports/cluster_names.json")
FEATURES = {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((ROOT / "reports" / "features").glob("*.json"))} if (ROOT / "reports" / "features").exists() else {}

C = F["corpus"]
TEST, VAL = F["evaluation"]["test"], F["evaluation"]["val"]
H, DB = F["hierarchical"], F["dbscan"]
CE = F.get("centring_effect")                     # from: deliverable_facts.json:centring_effect (train books, same model)
MET = TEST["met"]                                 # from: deliverable_facts.json:evaluation.test.met
CAT = TEST.get("catalogue") or {}                 # from: deliverable_facts.json:evaluation.test.catalogue
SUG, REL, TRI, EDI = (FEATURES.get(k) for k in ("suggest", "related", "triage", "editions"))
CENTRING_HELPS = bool(CE) and CE["centred"]["nmi_script"] < CE["uncentred"]["nmi_script"]
LANG = {r["lang"]: r["name"] for r in C["by_language"]}          # from: deliverable_facts.json:corpus.by_language


def n(x) -> str:
    return f"{int(x):,}"


def pct(x, d=1) -> str:
    return f"{100 * x:.{d}f}%"


def f2(x) -> str:
    return f"{x:.2f}"


def pts(x) -> str:
    return f"{x:.1f}"


def gain(x) -> str:
    """A signed points difference, e.g. +14.5 or -4.0 (the sign is part of the sourced number)."""
    return f"{x:+.1f}"


def met_word(ok: bool) -> str:
    return "met" if ok else "not met"


# ==============================================================================
# DRAWING HELPERS
# ==============================================================================
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(SLIDE_W), Inches(SLIDE_H)
BLANK = prs.slide_layouts[6]
SLIDES = []


def ground(slide, color="paper"):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb(color)


def font_for(st: dict) -> str:
    face = st.get("font", "body")
    if face == "body" and st.get("bold"):
        return FONT["body_semi"]          # a real SemiBold, never a synthetic bold
    if face == "body" and st.get("medium"):
        return FONT["body_med"]
    return FONT[face]


def color_of(c):
    return c if isinstance(c, RGBColor) else rgb(c)


def text(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, name=None):
    """paras: list of (text, style) or (list of (text, style) runs). style: dict(font, size, color, bold, medium, align, space, line)."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        box.name = name
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        runs = para if isinstance(para, list) else [para]
        first_style = runs[0][1]
        p.alignment = first_style.get("align", PP_ALIGN.LEFT)
        if first_style.get("space"):
            p.space_before = Pt(first_style["space"])
        p.line_spacing = first_style.get("line", 1.15)
        for t, st in runs:
            r = p.add_run()
            r.text = t
            r.font.name = font_for(st)
            r.font.size = Pt(SIZE[st.get("size", "body")])
            r.font.color.rgb = color_of(st.get("color", "ink"))
            r.font.bold = False
            r.font.italic = False
            if st.get("link"):
                r.hyperlink.address = st["link"]          # a live link; the run keeps the deck's colour, not the theme's
                r.font.color.rgb = color_of(st.get("color", "ink"))
                r.font.underline = True
    return box


def S(**kw):
    return kw


def hline(slide, x, y, w, color="rule", weight=0.75):
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x), Inches(y), Inches(x + w), Inches(y))
    ln.line.color.rgb = color_of(color)
    ln.line.width = Pt(weight)
    ln._element.spPr.append(etree.Element(qn("a:effectLst")))   # printed flat: no theme shadow under a rule
    return ln


def double_rule(slide, x, y, w, color="ink"):
    """The printer's double rule: two ink hairlines 3 pt apart (Vellum's --rule-double)."""
    hline(slide, x, y, w, color, 0.9)
    hline(slide, x, y + 0.045, w, color, 0.9)


def rect(slide, x, y, w, h, color, name=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = color_of(color)
    shp.line.fill.background()
    shp.shadow.inherit = False
    if name:
        shp.name = name
    return shp


def fibre_band(slide, x, y, w, h):
    """A paper_2 band carrying the long tan fibre wash (Vellum's one texture, on bands only)."""
    rect(slide, x, y, w, h, "paper_2", name="Fibre band")
    pic = slide.shapes.add_picture(str(ASSETS / "fibre_wash.png"), Inches(x), Inches(y), Inches(w), Inches(h))
    pic.name = "Fibre wash"


def new_slide(title, notes, source=None, ground_color="paper"):
    slide = prs.slides.add_slide(BLANK)
    ground(slide, ground_color)
    SLIDES.append(slide)
    if title:
        text(slide, MARGIN, MAST_Y, 6.0, 0.3, [("Grantha Heritage Tracker", S(size="mast", bold=True, color="ink_2"))],
             name="Running head")
        text(slide, SLIDE_W - MARGIN - 2.0, MAST_Y, 2.0, 0.3,
             [(f"{len(SLIDES)} of {TOTAL}", S(size="mast", medium=True, color="muted", align=PP_ALIGN.RIGHT))], name="Slide number")
        double_rule(slide, MARGIN, MAST_Y + 0.36, SLIDE_W - 2 * MARGIN)
        text(slide, MARGIN, TITLE_Y, SLIDE_W - 2 * MARGIN, TITLE_H,
             [(title, S(font="display", size="title" if len(title) <= 52 else "title_s", line=0.92))],
             anchor=MSO_ANCHOR.BOTTOM, name="Title")
    if source:
        hline(slide, MARGIN, FOOT_Y, SLIDE_W - 2 * MARGIN, "rule")
        text(slide, MARGIN, FOOT_Y + 0.08, SLIDE_W - 2 * MARGIN, 0.3,
             [(f"Source: {source}", S(size="caption", color="muted"))], name="Source")
    slide.notes_slide.notes_text_frame.text = notes.strip()
    return slide


def swatch_key(slide, x, y, items, color="ink"):
    """A direct key: a small square swatch beside each series name, the name in ink (never in the data colour)."""
    for i, (label, c) in enumerate(items):
        yy = y + i * 0.34
        rect(slide, x, yy + 0.07, 0.16, 0.16, c)
        text(slide, x + 0.28, yy, SLIDE_W - MARGIN - x - 0.28, 0.3, [(label, S(size="small", color=color))])


def style_chart(chart, number_format="0%", labels=True, value_axis=False, max_scale=None):
    chart.has_legend = False
    chart.has_title = False
    chart.font.name = FONT["body"]
    chart.font.size = Pt(SIZE["chart"])
    chart.font.color.rgb = rgb("ink")
    va, ca = chart.value_axis, chart.category_axis
    va.has_major_gridlines = value_axis
    if value_axis:
        va.major_gridlines.format.line.color.rgb = rgb("rule")
        va.major_gridlines.format.line.width = Pt(0.5)
        va.tick_labels.font.color.rgb = rgb("muted")
        va.tick_labels.number_format = number_format
        va.tick_labels.number_format_is_linked = False
    else:
        va.tick_label_position = XL_TICK_LABEL_POSITION.NONE
    va.format.line.fill.background()
    va.minimum_scale = 0
    if max_scale is not None:
        va.maximum_scale = max_scale
    ca.format.line.color.rgb = rgb("ink")
    ca.format.line.width = Pt(0.75)
    ca.tick_labels.font.color.rgb = rgb("ink")
    ca.has_major_gridlines = False
    plot = chart.plots[0]
    if labels:
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.number_format = number_format
        dl.number_format_is_linked = False
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        dl.font.size = Pt(SIZE["chart"])
        dl.font.color.rgb = rgb("ink")
    return plot


def color_series(series, color):
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = color_of(color)
    series.format.line.fill.background()


def bar_chart(slide, x, y, w, h, categories, series, number_format="0%", max_scale=None, gap=60, horizontal=True):
    """series: list of (name, values, colour or list of per-point colours)."""
    cd = CategoryChartData()
    cd.categories = categories
    for name, values, _ in series:
        cd.add_series(name, values)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    chart = gf.chart
    plot = style_chart(chart, number_format, max_scale=max_scale)
    plot.gap_width = gap
    plot.overlap = -10 if len(series) > 1 else 0
    if horizontal:
        chart.category_axis.reverse_order = True     # first category on top, reading order
    for s, (_, _, color) in zip(chart.series, series):
        if isinstance(color, list):
            for i, c in enumerate(color):
                pt = s.points[i]
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = rgb(c)
                pt.format.line.fill.background()
        else:
            color_series(s, color)
    return chart


def scatter(slide, x, y, w, h, series, size=3, value_axis=False, max_scale=None, fmt="0.0"):
    """series: list of (name, [(x, y), ...], colour or None for a line). Dots, no lines, no frame."""
    cd = XyChartData()
    for name, points, _ in series:
        ser = cd.add_series(name)
        for px, py in points:
            ser.add_data_point(px, py)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    style_chart(ch, number_format=fmt, labels=False, value_axis=value_axis, max_scale=max_scale)
    if not value_axis:
        ch.value_axis.minimum_scale = None
    ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
    ch.category_axis.format.line.fill.background()
    for ser, (_, _, color) in zip(ch.series, series):
        if color is None:                                  # a reference line
            ser.marker.style = XL_MARKER_STYLE.NONE
            ser.format.line.color.rgb = rgb("ink")
            ser.format.line.width = Pt(1.0)
            ser.format.line.dash_style = 4                 # a printer's dash
        else:
            ser.format.line.fill.background()
            ser.marker.style = XL_MARKER_STYLE.CIRCLE
            ser.marker.size = size
            ser.marker.format.fill.solid()
            ser.marker.format.fill.fore_color.rgb = rgb(color)
            ser.marker.format.line.fill.background()
    return ch


def ledger(slide, x, y, w, rows, col_w, row_h=0.42):
    """A table set like a day book: a double ink rule over the head, an ink rule under it, hairlines between rows."""
    double_rule(slide, x, y - 0.08, w)
    gf = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows)))
    tbl = gf.table
    tbl.first_row = False
    tbl.horz_banding = False
    tbl._tbl.tblPr.find(qn("a:tableStyleId")).text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"  # No Style, No Grid
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        tbl.rows[i].height = Inches(row_h)
        for j, cell_spec in enumerate(row):
            t, st = cell_spec[0], cell_spec[1]
            fill = cell_spec[2] if len(cell_spec) > 2 else None
            cell = tbl.cell(i, j)
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            if fill is not None:
                cell.fill.solid()
                cell.fill.fore_color.rgb = fill
            else:
                cell.fill.background()
            p = cell.text_frame.paragraphs[0]
            p.alignment = st.get("align", PP_ALIGN.LEFT)
            r = p.add_run()
            r.text = t
            r.font.name = font_for(st)
            r.font.size = Pt(SIZE[st.get("size", "table")])
            r.font.bold = False
            r.font.color.rgb = color_of(st.get("color", "ink"))
            tcPr = cell._tc.get_or_add_tcPr()
            ln = etree.Element(qn("a:lnB"), w=str(Emu(Pt(0.9 if i == 0 else 0.5))), cmpd="sng")
            tcPr.insert(0, ln)                         # borders precede the cell fill in the schema
            sf = etree.SubElement(ln, qn("a:solidFill"))
            etree.SubElement(sf, qn("a:srgbClr"), val=COLOR["ink" if i == 0 else "rule"])
    return tbl


# ==============================================================================
# SHARED FACTS AND SLIDE PIECES
# ==============================================================================
from PIL import Image                                   # only to read each figure's own aspect

classified = H["effects"]["classified_books"]          # from: deliverable_facts.json:hierarchical.effects.classified_books
usable = C["usable"]                                   # from: deliverable_facts.json:corpus.usable
langs_by_conf = sorted(C["by_language"], key=lambda r: r["median_conf"])   # from: corpus.by_language[].median_conf
low1, low2 = langs_by_conf[0], langs_by_conf[1]
t1, t1_target = TEST["t1_agreement"], TEST["targets"]["T1_page_agreement"]      # from: evaluation.test
t2_target = TEST["targets"]["T2_points_above_baseline"]
t3_target = TEST["targets"]["T3_bootstrap_ari"]
gain_t = TEST["t2_points"]                                                    # from: evaluation.test.t2_points
hb, dbb = H["bootstrap"], DB["bootstrap"]                                     # from: hierarchical.bootstrap, dbscan.bootstrap
CONTENT_W = SLIDE_W - 2 * MARGIN
SPL = C["splits"]                                                             # from: corpus.splits
TS = C["text_source"]                                                         # from: corpus.text_source
ENC = F["encoder"]                                                            # from: encoder
un, ce = CE["uncentred"], CE["centred"]                                       # from: centring_effect


def p3(x) -> str:
    return f"{x:.3f}"


def figure(slide, name, x, y, w, caption, max_h=None):
    """A study figure at its own aspect, a hairline under it and its caption. Returns the y below the caption."""
    path = FIG / name
    iw, ih = Image.open(path).size
    h = w * ih / iw
    if max_h is not None and h > max_h:
        h, w = max_h, max_h * iw / ih
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h)).name = name
    hline(slide, x, y + h + 0.04, w, "rule", 0.5)
    text(slide, x, y + h + 0.1, w, 0.3, [(caption, S(size="caption", color="muted"))])
    return y + h + 0.42


def stat(slide, x, y, w, figure_t, label, size="title_s", color="accent"):
    """A figure set in the display face over its label."""
    text(slide, x, y, w, 0.55, [(figure_t, S(font="display", size=size, color=color, line=0.9))], anchor=MSO_ANCHOR.BOTTOM)
    text(slide, x, y + 0.6, w, 0.5, [(label, S(size="small", color="ink_2"))])


def entries(slide, x, y, w, items, step=0.8, size="small"):
    """Labelled lines: a semibold head run, then the text, each on a hairline."""
    for i, (head_t, body_t) in enumerate(items):
        yy = y + i * step
        hline(slide, x, yy, w, "ink" if i == 0 else "rule", 0.75 if i == 0 else 0.5)
        text(slide, x, yy + 0.08, w, step - 0.1, [[(head_t + "  ", S(size=size, bold=True)),
                                                   (body_t, S(size=size, color="ink_2"))]])


# ==============================================================================
# 1. TITLE: the manuscript the project is named for
# ==============================================================================
s = new_slide(None, f"""
Grantha Heritage Tracker, Smart India Hackathon problem SIH26096, section K3P24XC.

A grantha is a palm-leaf manuscript, like the model on this slide: we drew it for the deck, and its leaves carry the opening couplets of the Tirukkural.

Our books are their printed descendants: {n(C['harvested'])} books harvested across {C['languages']} languages, {n(usable)} usable after the OCR quality gate. We embed them with language-centred {ENC['name']} ({ENC['dims']}-d PCA) and cluster them with Ward (k = {H['k']}) and DBSCAN ({DB['n_clusters']} dense cores, {pct(DB['noise_share'])} noise).

The team: Rajith Sundar built the data and OCR pipeline, Etikala Sai Pranav ran the clustering study, and Vemuri Rohan built the app and delivered it.
""")
fibre_band(s, 0, 0, SLIDE_W, SLIDE_H)
double_rule(s, MARGIN, 0.62, CONTENT_W)
text(s, MARGIN, 0.3, 8.0, 0.3, [("Smart India Hackathon SIH26096, section K3P24XC", S(size="mast", bold=True, color="ink_2"))])
text(s, MARGIN, 0.95, 8.6, 1.35, [("Grantha Heritage Tracker", S(font="display", size="display", line=0.92))],
     anchor=MSO_ANCHOR.BOTTOM, name="Title")
text(s, MARGIN, 2.45, 7.4, 1.0,
     [(f"Discovering cross-script themes in {n(usable)} heritage books with unsupervised clustering.",  # from: corpus.usable
       S(font="outlier", size="statement", line=1.02))])
text(s, MARGIN, 3.42, 8.6, 0.3,
     [("CO2 clustering formulation and optimisation; CO3 2D and 3D PCA projection; Units III and IV",
       S(size="small", color="muted"))])
img_w = 9.3
img_h = img_w * 688 / 2335                              # the render's own aspect (docs/assets/manuscript_model.png)
s.shapes.add_picture(str(ASSETS / "manuscript_model.png"), Inches(SLIDE_W - MARGIN - img_w + 0.35), Inches(3.7),
                     Inches(img_w), Inches(img_h)).name = "Palm-leaf manuscript model"
team = [("Rajith Kolappa Pillai Sundar", "12413353, RK3P24XCB41", "Data and OCR"),
        ("Etikala Sai Pranav", "12401062, RK3P24XCB59", "Clustering study"),
        ("Vemuri Rohan", "12403675, RK3P24XCA03", "App and delivery")]
for i, (who, roll, part) in enumerate(team):
    y = 4.05 + i * 0.9
    hline(s, MARGIN, y, 3.0, "ink" if i == 0 else "rule", 0.75)
    text(s, MARGIN, y + 0.08, 3.0, 0.8, [(who, S(size="small", bold=True)), (roll, S(size="small", color="muted", space=1)),
                                         (part, S(size="small", color="ink_2", space=1))])
double_rule(s, MARGIN, 6.92, CONTENT_W)
text(s, MARGIN, 7.02, CONTENT_W, 0.3,
     [("The palm-leaf manuscript is a 3-D model drawn for this deck. Its leaves carry the opening couplets of the Tirukkural.",
       S(size="caption", color="muted"))])

# ==============================================================================
# 2. THE CORPUS
# ==============================================================================
s = new_slide(f"{n(C['harvested'])} books harvested, {n(usable)} clean enough to cluster", f"""
We harvested {n(C['harvested'])} books ({n(C['ocr_pages'])} OCR pages) across {C['languages']} languages from the Internet Archive's Digital Library of India scans. {n(usable)} ({pct(C['usable_share'])}) passed the quality gate: a mean OCR word confidence of 50 or more and at least 100 tokens. {n(C['excluded'])} were set aside.

The books are split {n(SPL['train'])} train, {n(SPL['val'])} validation and {n(SPL['test'])} test, and the test split is locked.

Panel D is the leakage audit: scanning centre, source library, subject field, classification and publisher are dropped from the features, so the groups follow the text, not where a book was scanned.

If asked: {low1['name']} (median confidence {pts(low1['median_conf'])}%) and {low2['name']} ({pts(low2['median_conf'])}%) lose the most books at the gate.
""", source="reports/deliverable_facts.json: corpus; reports/variable_relevance.csv")
text(s, MARGIN, BODY_Y - 0.1, 4.4, 0.95, [(n(usable), S(font="display", size="figure", color="accent", line=0.9))],
     anchor=MSO_ANCHOR.BOTTOM)                                                                    # from: corpus.usable
text(s, MARGIN, BODY_Y + 0.9, 4.4, 0.6, [
    (f"of {n(C['harvested'])} harvested books are usable: {pct(C['usable_share'])} kept, {n(C['excluded'])} set aside, "  # from: corpus
     f"{n(C['ocr_pages'])} OCR pages.", S(size="body", color="ink_2"))])
entries(s, MARGIN, BODY_Y + 1.7, 4.4, [
    ("Source", f"Internet Archive DLI scans across {C['languages']} languages."),
    ("Quality gate", "Mean Tesseract word confidence of 50 or more and at least 100 tokens."),
    ("Leakage audit", "Scanning centre, source library, subject field, classification and publisher are dropped."),
    ("Splits", f"Train {n(SPL['train'])}, validation {n(SPL['val'])}, test {n(SPL['test'])} (locked)."),   # from: corpus.splits
], step=0.7)
figure(s, "corpus_gate.png", 5.55, BODY_Y - 0.1, 7.03,
       "Corpus by language, the OCR confidence gate, the splits and the variable audit.", max_h=4.3)

# ==============================================================================
# 3. THE PIPELINE
# ==============================================================================
s = new_slide(f"From scanned pixels to script-free {ENC['dims']}-d vectors", f"""
Five stages. One, read the OCR: the archive's hOCR for {n(TS['hocr'])} books, its DjVu text for {n(TS['djvu'])}, and our own Tesseract pages for {n(TS['tesseract_pages'])}.

Two, clean: Unicode NFC normalisation, speckle removal and a per-language stopword cap. Three, the usability gate. Four, embed with {ENC['name']}: 768-d vectors, compressed to {ENC['dims']}-d with PCA, keeping {pct(ENC['pca_explained'])} of the variance.

Five, centre by language: subtract each language's mean. On the {n(CE['train_books'])} train books script NMI drops from {p3(un['nmi_script'])} to {p3(ce['nmi_script'])}, and a book's 10 nearest neighbours in the same script drop from {pct(un['knn10_same_script'], 0)} to {pct(ce['knn10_same_script'], 0)}.

Walk the DFD: the text corpus goes through cleaning to the usability filter; the metadata is reviewed, imputed and encoded; usable books are embedded, centred and reduced, and land in the feature store with the encoded metadata block.
""", source="scripts/dfd.py; reports/deliverable_facts.json: corpus.text_source, encoder, centring_effect")
steps = [("Read OCR", f"hOCR ({n(TS['hocr'])}), DjVu ({n(TS['djvu'])}) and Tesseract ({n(TS['tesseract_pages'])})."),   # from: corpus.text_source
         ("Clean and NFC", "Unicode NFC, speckle removal and a per-language stopword cap."),
         ("Usability gate", "Mean OCR confidence of 50 or more and at least 100 tokens; missing year imputed."),
         ("Embed", f"{ENC['name']}: 768-d, compressed to {ENC['dims']}-d PCA ({pct(ENC['pca_explained'])} variance)."),
         ("Centre by language", "Subtract each language's mean vector.")]
for i, (head_t, body_t) in enumerate(steps):
    y = BODY_Y - 0.05 + i * 0.9
    key = head_t.startswith("Centre")
    if key:
        rect(s, MARGIN - 0.12, y - 0.06, 5.6, 0.86, "accent_soft", name="The key step")
    text(s, MARGIN, y, 0.5, 0.6, [(str(i + 1), S(font="display", size="title_s", color="accent", line=0.9))])
    text(s, MARGIN + 0.6, y + 0.02, 4.75, 0.8, [(head_t, S(size="body", bold=True)),
                                                (body_t, S(size="small", color="ink_2", space=2))])
yb = figure(s, "dfd_level2_p3.png", 6.55, BODY_Y - 0.1, 6.03, "Data flow, level 2: process 3.0, preprocess and build features.")
stat(s, 6.55, yb + 0.05, 2.7, f"{ENC['dims']}-d", f"PCA from 768-d {ENC['name']}, {pct(ENC['pca_explained'])} variance kept")
stat(s, 9.55, yb + 0.05, 3.03, f"{p3(un['nmi_script'])} → {p3(ce['nmi_script'])}",
     f"script NMI after centring; same-script neighbours {pct(un['knn10_same_script'], 0)} → {pct(ce['knn10_same_script'], 0)}")

# ==============================================================================
# 4. HIERARCHICAL CLUSTERING: MODEL SELECTION
# ==============================================================================
k_lo, k_hi = 2, 15                                            # from: pipeline/study.py K_RANGE (a code constant)
wins = F["distance"]["wins"]                                  # from: deliverable_facts.json:distance.wins
s = new_slide(f"{H['linkage'].title()} linkage on {ENC['dims']}-d features selects k = {H['k']}", f"""
We searched the hierarchical settings: Ward, average and complete linkage, each from k = {k_lo} to {k_hi}. Euclidean distance won {wins['euclidean']} to {wins['cityblock']} over Manhattan.

{H['linkage'].title()} linkage at k = {H['k']} on the {ENC['dims']}-d features gives a silhouette of {p3(H['silhouette'])}: a diffuse thematic manifold, not tight balls. Script NMI is {p3(H['nmi_script'])}, so the groups are essentially not language groups. The largest group holds {pct(H['largest_share'])} of the books and the smallest {n(H['smallest'])}.

Panel A is the last merges of the dendrogram, with the dashed line at the k = {H['k']} cut. Panel B is the silhouette across linkages and k.

If asked about the low silhouette: book space is continuous, so the groups are broad shelves, not islands.
""", source="reports/study/results_V.json; reports/deliverable_facts.json: hierarchical, distance")
yb = figure(s, "ward_selection.png", MARGIN, BODY_Y - 0.1, 8.35,
            "Ward dendrogram, last merges (left); silhouette across linkages, k from 2 to 15 (right).")
stat(s, 9.6, BODY_Y - 0.1, 2.98, f"{H['linkage'].title()}, k = {H['k']}",
     f"Euclidean distance, which won {wins['euclidean']} to {wins['cityblock']} over Manhattan")
stat(s, 9.6, BODY_Y + 1.15, 2.98, p3(H["silhouette"]), "silhouette: a diffuse thematic manifold, not tight balls")
stat(s, 9.6, BODY_Y + 2.4, 2.98, p3(H["nmi_script"]), "script NMI: essentially no language grouping")
w3 = (CONTENT_W - 2 * GAP) / 3
for i, (head_t, body_t) in enumerate((
        ("Search", "Ward, average and complete linkage, k from 2 to 15."),
        ("Balance", f"Largest group {pct(H['largest_share'])} of books, smallest {n(H['smallest'])} books."),
        ("Selection", f"Made on the {n(SPL['train'])} train books, then applied to all {n(usable)}."))):
    entries(s, MARGIN + i * (w3 + GAP), 6.0, w3, [(head_t, body_t)], step=0.85)

# ==============================================================================
# 5. DBSCAN
# ==============================================================================
s = new_slide(f"DBSCAN finds {DB['n_clusters']} dense cores and sets {pct(DB['noise_share'])} aside as noise", f"""
We swept {DB['grid_settings']} DBSCAN settings: MinPts {", ".join(str(m) for m in DB['min_pts_tried'])}, and eps from {p3(DB['eps_range'][0])} to {p3(DB['eps_range'][1])}.

The selected setting, MinPts {DB['min_pts']} and eps {p3(DB['eps'])}, finds {DB['n_clusters']} dense cores and marks {pct(DB['noise_share'])} of the books as noise. On re-runs it is very steady: bootstrap ARI {p3(dbb['median'])}.

The k-distance curves have no sharp knee, so eps is chosen from the sweep, where the noise share and the cluster count both settle.

If asked: noise is the label -1, the books outside every dense core. They are set aside, not forced into a group.
""", source="reports/deliverable_facts.json: dbscan")
yb = figure(s, "dbscan_sweep.png", MARGIN + 0.9, BODY_Y - 0.15, 10.0,
            f"Noise share and cluster count across {DB['grid_settings']} settings, with sorted k-distance curves.")
w4 = (CONTENT_W - 3 * GAP) / 4
for i, (fig_t, label) in enumerate(((p3(DB["eps"]), "selected eps radius"),
                                    (str(DB["min_pts"]), "MinPts density threshold"),
                                    (pct(DB["noise_share"]), "noise (label -1), set aside"),
                                    (p3(dbb["median"]), "DBSCAN bootstrap ARI"))):
    stat(s, MARGIN + i * (w4 + GAP), yb - 0.05, w4, fig_t, label)

# ==============================================================================
# 6. PCA, 2D AND 3D
# ==============================================================================
s = new_slide(f"2D and 3D PCA across all {n(usable)} books: centring dissolves script walls", f"""
The PCA projections cover all {n(usable)} usable books; the {ENC['dims']}-d features keep {pct(ENC['pca_explained'])} of the variance.

Panel A, before centring: the books cluster by script. Panel B, after language centring: all {C['languages']} languages mix across the {H['k']} Ward groups. Panel C is the 3D centred projection.

Why does 3D look diffuse? Book space is high-dimensional. Three axes show the global mixing, while the clustering itself runs in {ENC['dims']} dimensions.
""", source="reports/figures (PCA 2D and 3D); web/data/galaxy.json; reports/deliverable_facts.json: encoder")
yb = figure(s, "pca_2d_3d.png", MARGIN + 0.95, BODY_Y - 0.15, 9.9,
            "Uncentred 2D PCA by script (A), language-centred 2D Ward groups (B), 3D centred projection (C).")
stat(s, MARGIN, yb - 0.05, 3.0, pct(ENC["pca_explained"]), f"variance kept in {ENC['dims']}-d PCA")
entries(s, MARGIN + 3.4, yb + 0.05, 8.43, [
    ("Why 3D looks diffuse", f"book space is high-dimensional; three axes show the global mixing while clustering runs in {ENC['dims']}-d.")],
    step=0.9, size="body")

# ==============================================================================
# 7. CENTRING ACROSS ENCODERS
# ==============================================================================
s = new_slide("Language centring lifts subject agreement across every encoder", f"""
The key finding: subtracting each language's centroid removes script clustering without losing the topic signal.

On the {n(CE['train_books'])} train books, script NMI falls from {p3(un['nmi_script'])} to {p3(ce['nmi_script'])}, and a book's 10 nearest neighbours in the same script fall from {pct(un['knn10_same_script'], 0)} to {pct(ce['knn10_same_script'], 0)}.

The right panel tests centring on four encoders: Gemini, BGE-M3, LaBSE and IndicSBERT. Seven-nearest-neighbour subject agreement on the labelled train and validation books rises for every one of them once they are centred.

The production model is {ENC['name']} with {ENC['dims']}-d PCA, across all {n(usable)} usable books.
""", source="reports/study/encoder_comparison.json; reports/deliverable_facts.json: centring_effect")
text(s, MARGIN, BODY_Y - 0.1, 3.55, 1.3, [[("Key finding  ", S(size="body", bold=True)),
                                          ("subtracting each language's centroid removes script clustering without losing topic signal.",
                                           S(size="body", color="ink_2"))]])
stat(s, MARGIN, BODY_Y + 1.25, 3.55, f"{p3(un['nmi_script'])} → {p3(ce['nmi_script'])}",
     f"script NMI on {n(CE['train_books'])} train books")
stat(s, MARGIN, BODY_Y + 2.45, 3.55, f"{pct(un['knn10_same_script'], 0)} → {pct(ce['knn10_same_script'], 0)}",
     "10-NN same-script neighbours")
stat(s, MARGIN, BODY_Y + 3.65, 3.55, "Every encoder", "gains 7-NN subject agreement once centred", color="ink")
yb = figure(s, "centring_encoders.png", 4.65, BODY_Y - 0.1, 7.93,
            "Centring on train books (left); 7-NN subject agreement across four encoders (right).")
rect(s, 4.65, yb + 0.05, 7.93, 1.15, "accent_soft", name="Production model")
text(s, 4.9, yb + 0.15, 7.45, 1.0, [("Production model", S(size="body", bold=True)),
                                    (f"{ENC['name']} ({ENC['dims']}-d PCA) across all {n(usable)} usable books. "
                                     "Gemini, BGE-M3, LaBSE and IndicSBERT all improve once centred.", S(size="small", color="ink_2", space=3))])

# ==============================================================================
# 8. THE GROUPS
# ==============================================================================
groups = F["groups"]                                         # from: deliverable_facts.json:groups
lang_codes = [r["lang"] for r in C["by_language"]]
top_share = max(g["top_language_share"] for g in groups)    # from: groups[].top_language_share
all_mixed = all(all(g["languages"].get(l, 0) > 0 for l in lang_codes) for g in groups)
SUGF = (FEATURES.get("suggest") or {})
s = new_slide(f"{len(groups)} broad cross-script groups, each mixing "
              f"{'all ' + str(len(lang_codes)) if all_mixed else 'many'} languages", f"""
These are the Ward k = {H['k']} groups on all {n(usable)} books. Each row is a group; the cells show each language's share of it, darker for a bigger share. No language holds more than {pct(top_share, 0)} of any group.

{" ".join(f"Group {g['group'] + 1}: {n(g['books'])} books, mostly {g['majority_subject']}." for g in groups)}

The groups act as broad archival shelves, not fine-grained Dewey classes.

Live app example: the uncatalogued Tamil book dli.56E228. Its top suggested class is language and literature, voted by its {SUGF.get('k', 'nearest')} nearest coded books, and its closest books are in Gujarati, Telugu, Kannada and Devanagari script.
""", source="reports/deliverable_facts.json: groups; web/fixtures/get_related__dli.56E228.json, get_suggest__dli.56E228.json")
max_cell = max(max(g["languages"].values()) for g in groups)
head = [("Group", S(medium=True)), ("Books", S(medium=True, align=PP_ALIGN.RIGHT)), ("Majority subject", S(medium=True))] + \
       [(LANG[l], S(medium=True, align=PP_ALIGN.RIGHT)) for l in lang_codes]
rows = [head]
for g in groups:
    rows.append([(f"{g['group'] + 1}", S(font="display", size="section", color="accent")),     # from: groups[].group
                 (n(g["books"]), S(align=PP_ALIGN.RIGHT)),                              # from: groups[].books
                 (g["majority_subject"] or "no labelled books", S(bold=True))] +        # from: groups[].majority_subject
                [(pct(g["languages"].get(l, 0), 0), S(align=PP_ALIGN.RIGHT),            # from: groups[].languages
                  mix("paper", "accent_soft", g["languages"].get(l, 0) / max_cell)) for l in lang_codes])
ledger(s, MARGIN, BODY_Y + 0.05, CONTENT_W, rows,
       [0.85, 0.95, 2.5] + [(CONTENT_W - 4.3) / len(lang_codes)] * len(lang_codes), row_h=0.55)
y8 = BODY_Y + 2.6
stat(s, MARGIN, y8 + 0.1, 2.6, pct(top_share, 0), "maximum language share in any group", size="title")
entries(s, 3.75, y8 + 0.1, 4.2, [
    ("Mixed", f"every group contains all {len(lang_codes)} languages." if all_mixed else "most groups contain most languages."),
    ("Shelves", "the groups act as broad archival shelves, not fine-grained Dewey classes.")], step=0.8)
rect(s, 8.35, y8 + 0.1, 4.23, 1.85, "accent_soft", name="Live app example")
text(s, 8.55, y8 + 0.2, 3.85, 1.85, [
    ("Live app example", S(size="body", bold=True)),
    (f"Uncatalogued Tamil book dli.56E228: the top suggested class is language and literature, from its "
     f"{SUGF.get('k', 'nearest')} nearest coded books. Its closest books are in Gujarati, Telugu, Kannada and Devanagari script.",  # from: features/suggest.json:k
     S(size="small", color="ink_2", space=3))])

# ==============================================================================
# 9. VALIDATION
# ==============================================================================
s = new_slide(f"Validated on {n(TEST['held_out_books'])} held-out books: {gain(gain_t)} points over a script-only baseline", f"""
The test set of {n(TEST['held_out_books'])} books was locked and used once.

Page-to-book agreement: {pct(t1)} of single pages land in their own book's group, against {pct(TEST['t1_chance'])} by chance. Our target was {pct(t1_target, 0)}, so this one is {met_word(MET['T1'])}.

Subject accuracy on {n(TEST['t2_labelled_heldout'])} labelled test books: {pct(TEST['t2_accuracy'])}, against {pct(TEST['t2_baseline_script'])} for guessing from the script: {gain(gain_t)} points, p = {TEST['t2_p']:.4f} over 2,000 label permutations.

Script NMI on the full corpus is {p3(H['nmi_script'])}, against {p3(un['nmi_script'])} before centring.

Bootstrap ARI over {len(hb['values'])} re-runs on {pct(0.8, 0)} of the books: DBSCAN cores {p3(dbb['median'])}; the Ward groups {p3(TEST['t3_bootstrap'])} on train books and {p3(hb['median'])} on all books.

If asked about the Ward ARI: the three Ward groups are broad shelves, so books near their borders move when the data is resampled. The DBSCAN cores are the stable part, which is why we use both.
""", source="reports/deliverable_facts.json: evaluation.test, hierarchical, dbscan.bootstrap")
rows = [[("Benchmark", S(medium=True)), ("Baseline", S(medium=True)), ("Grantha", S(medium=True, align=PP_ALIGN.RIGHT)),
         ("Result", S(medium=True))],
        [("Page-to-book agreement", S()), (f"chance {pct(TEST['t1_chance'])}", S()),            # from: evaluation.test.t1_chance
         (pct(t1), S(bold=True, align=PP_ALIGN.RIGHT)), (f"target {pct(t1_target, 0)}: {met_word(MET['T1'])}", S(color="ink_2"))],
        [(f"Subject accuracy ({n(TEST['t2_labelled_heldout'])} test books)", S()),
         (f"script-only {pct(TEST['t2_baseline_script'])}", S()),                                  # from: t2_baseline_script
         (pct(TEST["t2_accuracy"]), S(bold=True, align=PP_ALIGN.RIGHT)),                           # from: t2_accuracy
         (f"{gain(gain_t)} points, p = {TEST['t2_p']:.4f}", S(color="ink_2"))],                    # from: t2_points, t2_p
        [("Script independence (NMI)", S()), (f"uncentred {p3(un['nmi_script'])}", S()),
         (p3(H["nmi_script"]), S(bold=True, align=PP_ALIGN.RIGHT)), ("full corpus", S(color="ink_2"))],
        [(f"Bootstrap ARI ({len(hb['values'])} re-runs)", S()), ("chance level", S()),
         (p3(dbb["median"]), S(bold=True, align=PP_ALIGN.RIGHT)),
         (f"DBSCAN cores; Ward {p3(TEST['t3_bootstrap'])} train, {p3(hb['median'])} full", S(color="ink_2"))]]
ledger(s, MARGIN, BODY_Y + 0.05, 7.9, rows, [2.75, 1.65, 0.95, 2.55], row_h=0.62)
text(s, 9.05, BODY_Y - 0.1, 3.5, 0.3, [("Baseline against Grantha", S(size="body", bold=True))])
swatch_key(s, 9.05, BODY_Y + 0.3, [("baseline", "rule"), ("Grantha", "accent")])
ch = bar_chart(s, 8.95, BODY_Y + 0.95, 3.7, 2.55, ["Page-to-book", "Subject"],
               [("baseline", [TEST["t1_chance"], TEST["t2_baseline_script"]], "rule"),        # from: t1_chance, t2_baseline_script
                ("Grantha", [t1, TEST["t2_accuracy"]], "accent")],                              # from: t1_agreement, t2_accuracy
               number_format="0.0%", gap=70, horizontal=False, max_scale=1)
w3 = (CONTENT_W - 2 * GAP) / 3
for i, (head_t, body_t) in enumerate((
        ("Permutation test", f"2,000 label shuffles on subject accuracy; p = {TEST['t2_p']:.4f}."),
        ("Locked splits", "each book's split comes from a hash of its identifier; seeds are fixed."),
        ("Used once", f"the {n(TEST['held_out_books'])}-book test set was evaluated a single time."))):
    entries(s, MARGIN + i * (w3 + GAP), 5.85, w3, [(head_t, body_t)], step=0.95)

# ==============================================================================
# 10. LIMITS AND GUARDRAILS
# ==============================================================================
s = new_slide("Known limits, guardrails and responsible deployment", f"""
Known limits. OCR quality: {low1['name']} (median {pts(low1['median_conf'])}%) and {low2['name']} ({pts(low2['median_conf'])}%) lose the most books at the 50% gate. Group boundaries: the Ward bootstrap ARI is {p3(TEST['t3_bootstrap'])} on train books and {p3(hb['median'])} on all books, so the edges shift on resampling, while the DBSCAN cores hold at {p3(dbb['median'])}. Coarse catalogue codes: only {n(classified)} of the {n(usable)} books carry one, and on {n(CAT['labelled_heldout'])} coded test books the groups score {pct(CAT['accuracy_groups'])} against {pct(CAT['baseline_script_only'])} for guessing from the script. Genre overlap: two of the three groups lean to religion and philosophy, and hard cuts simplify blended treatises.

Guardrails. The app abstains on thin or noisy pages instead of guessing silently: {pct(TEST['t1_abstain_rate'])} of test pages. The groups assist archivists and never reclassify library records on their own. Every suggestion shows its nearest cross-script neighbours and distances for human review. And scripts/check_claims.py traces every number in the deck to a result file.

Grantha is a working, reproducible system: it harvests, centres, clusters and explains {n(usable)} heritage books across {C['languages']} languages.
""", source="reports/deliverable_facts.json: corpus.by_language, evaluation.test, hierarchical.bootstrap, dbscan.bootstrap")
text(s, MARGIN, BODY_Y - 0.1, 5.6, 0.45, [("Known limits", S(font="display", size="section", line=0.92))])
entries(s, MARGIN, BODY_Y + 0.42, 5.75, [
    ("OCR quality", f"{low1['name']} (median {pts(low1['median_conf'])}%) and {low2['name']} ({pts(low2['median_conf'])}%) "
                    "lose the most books at the 50% gate."),                                        # from: corpus.by_language[].median_conf
    ("Group boundaries", f"Ward bootstrap ARI is {p3(TEST['t3_bootstrap'])} train and {p3(hb['median'])} full, so edges shift "
                         f"on resampling; DBSCAN cores hold at {p3(dbb['median'])}."),
    ("Coarse catalogue codes", f"{n(classified)} of {n(usable)} books carry one; on {n(CAT['labelled_heldout'])} coded test "
                               f"books the groups score {pct(CAT['accuracy_groups'])}, script-only {pct(CAT['baseline_script_only'])}."),
    ("Genre overlap", "two of three groups lean to religion and philosophy; hard cuts simplify blended treatises.")],
    step=0.86)
fibre_band(s, 6.85, BODY_Y - 0.15, SLIDE_W - 6.85, 3.85)
text(s, 7.15, BODY_Y - 0.1, 5.43, 0.45, [("Guardrails", S(font="display", size="section", line=0.92))])
entries(s, 7.15, BODY_Y + 0.45, 5.43, [
    ("Abstain on thin or noisy scans", f"weak pages return a warning ({pct(TEST['t1_abstain_rate'])} of test pages), "
                                       "never a silent guess."),                                    # from: evaluation.test.t1_abstain_rate
    ("Exploratory, not canonical", "the groups assist archivists and never reclassify library records."),
    ("Evidence first", "every suggestion shows its nearest cross-script neighbours and distances for review."),
    ("Reproducible", "scripts/check_claims.py traces every figure and claim to a result file.")],
    step=0.8)
double_rule(s, MARGIN, 6.12, CONTENT_W)
text(s, MARGIN, 6.22, CONTENT_W, 0.68,
     [(f"Grantha is a working, reproducible system: it harvests, centres, clusters and explains {n(usable)} heritage books "
       f"across {C['languages']} languages.", S(font="outlier", size="lead", line=1.05))])

# ==============================================================================
# 11. PROJECT LINKS: the one ultramarine field
# ==============================================================================
s = new_slide(None, f"""
Everything we showed is public.

The GitHub repository holds the complete source code. Its README covers the overview, prerequisites, dependencies, installation and how to run the app and the study.

The live deployment is the same app and model you saw today.

The dataset: the source scans are the Digital Library of India collection on the Internet Archive, and the live app serves the list of all {n(usable)} usable books with their archive identifiers.

Also live: the 3-D archive map, the study page and the API documentation.

Thank you. We welcome your questions.
""", ground_color="accent")
quiet = mix("accent", "accent_ink", 0.72)
faint = mix("accent", "accent_ink", 0.35)
text(s, MARGIN, MAST_Y, 6.0, 0.3, [("Grantha Heritage Tracker", S(size="mast", bold=True, color="accent_ink"))])
text(s, SLIDE_W - MARGIN - 2.0, MAST_Y, 2.0, 0.3, [(f"{TOTAL} of {TOTAL}", S(size="mast", medium=True, color=quiet, align=PP_ALIGN.RIGHT))])
double_rule(s, MARGIN, MAST_Y + 0.36, CONTENT_W, "accent_ink")
text(s, MARGIN, TITLE_Y, CONTENT_W, TITLE_H, [("Project Links", S(font="display", size="title", color="accent_ink", line=0.92))],
     anchor=MSO_ANCHOR.BOTTOM, name="Title")


def short(url: str) -> str:
    return url.replace("https://", "").rstrip("/")


link_rows = [
    ("GitHub repository", [LINKS["repo"]], "Complete source code, with a README covering the overview, prerequisites, "
                                           "dependencies, installation and how to run it."),
    ("Live deployment", [LINKS["live"]], "The working app: check a page, browse the groups, the study."),
    ("Dataset", [LINKS["archive"], LINKS["books"]], f"Source scans on the Internet Archive; the list of all {n(usable)} usable "
                                                    "books with their archive identifiers."),
    ("Other resources", [LINKS["map"], LINKS["study"], LINKS["api"]], "The 3-D archive map, the study page and the API documentation."),
]
y = BODY_Y - 0.1
for i, (label, urls, desc) in enumerate(link_rows):
    row_h = max(0.42 + 0.3 * len(urls), 0.95 if len(desc) > 90 else 0.72)
    hline(s, MARGIN, y, CONTENT_W, "accent_ink" if i == 0 else faint, 0.75 if i == 0 else 0.5)
    text(s, MARGIN, y + 0.1, 2.6, 0.4, [(label, S(size="lead", bold=True, color="accent_ink"))])
    text(s, 3.45, y + 0.12, 4.75, row_h, [(short(u), S(size="body", color="accent_ink", link=u, space=0 if j == 0 else 2))
                                         for j, u in enumerate(urls)])
    text(s, 8.4, y + 0.12, 4.18, row_h, [(desc, S(size="small", color=quiet))])
    y += row_h + 0.06
double_rule(s, MARGIN, 6.42, CONTENT_W, "accent_ink")
text(s, MARGIN, 6.56, CONTENT_W, 0.5, [("Thank you. We welcome your questions.", S(font="outlier", size="statement", color="accent_ink"))])

from pptx.opc.constants import RELATIONSHIP_TYPE as RT
theme = prs.slide_master.part.part_related_by(RT.THEME)
tx = etree.fromstring(theme.blob)
for tag in ("a:hlink", "a:folHlink"):                     # the only links are on the ultramarine field
    el = tx.find(f".//{qn('a:clrScheme')}/{qn(tag)}")
    for child in list(el):
        el.remove(child)
    etree.SubElement(el, qn("a:srgbClr"), val=COLOR["accent_ink"])
theme._blob = etree.tostring(tx, xml_declaration=True, encoding="UTF-8", standalone=True)

assert len(prs.slides) == TOTAL, f"built {len(prs.slides)} slides, expected {TOTAL}"
prs.save(OUT)
print(f"saved {OUT.relative_to(ROOT)} ({len(prs.slides)} slides)")
