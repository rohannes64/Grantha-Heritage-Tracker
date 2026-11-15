"""Builds Grantha_Heritage_Tracker_SIH26096.pptx from the result files, with no hand-typed result.

    python scripts/build_deck.py
    powershell -File scripts/embed_fonts.ps1        # optional: embeds the fonts so any PC shows the deck as designed

Reads only:
  reports/deliverable_facts.json           every number written on a slide or in the notes
  web/data/study.json, reports/**/*.json   chart series and names the facts file does not hold
  reports/features/*.json                  feature evaluations, when present (slides show the tool without numbers if absent)
  web/data/galaxy.json, galaxy_umap.json   the archive map: each book's position, language and group. galaxy_umap.json is
                                           written by pipeline/galaxy.py when umap-learn is installed (the live app has it);
                                           without it the map slide falls back to the flat view in galaxy.json
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
ASSETS = Path(__file__).resolve().parents[1] / "docs" / "assets"


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
             [(f"{len(SLIDES)} of 10", S(size="mast", medium=True, color="muted", align=PP_ALIGN.RIGHT))], name="Slide number")
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
# SHARED FACTS FOR THE SLIDES
# ==============================================================================
classified = H["effects"]["classified_books"]          # from: deliverable_facts.json:hierarchical.effects.classified_books
usable = C["usable"]                                   # from: deliverable_facts.json:corpus.usable
no_class = 1 - classified / usable
langs = sorted(C["by_language"], key=lambda r: -r["usable"] / r["harvested"])   # from: corpus.by_language
worst = langs[-1]
t1, t1_target = TEST["t1_agreement"], TEST["targets"]["T1_page_agreement"]      # from: evaluation.test
t2_target = TEST["targets"]["T2_points_above_baseline"]
t3_target = TEST["targets"]["T3_bootstrap_ari"]
gain_t, gain_v = TEST["t2_points"], VAL["t2_points"]                          # from: evaluation.test/val.t2_points
hb, dbb = H["bootstrap"], DB["bootstrap"]                                     # from: hierarchical.bootstrap, dbscan.bootstrap
n_met = sum(MET.values())
CONTENT_W = SLIDE_W - 2 * MARGIN

# ==============================================================================
# 1. TITLE: the manuscript the project is named for
# ==============================================================================
s = new_slide(None, f"""
Good morning. We are Rohan, Rajith and Sai Pranav, and this is the Grantha Heritage Tracker, for Smart India Hackathon problem SIH26096.

A grantha is a palm-leaf manuscript, like the one on this slide: leaves cut from the palm, the text scratched in and darkened with soot, bound between two boards on a cord. The model on the slide is drawn by us; the lines on its leaves are the opening couplets of the Tirukkural.

Our books are the printed descendants of these: old Indian books, scanned into a digital library, in many scripts. We asked whether a computer can group them by subject without being told the subjects. Grantha is a working web app built on that idea.

Every number you will see comes from our result files. {"We set three targets before the results; where we missed one, we say so." if not all(MET.values()) else "We set three targets before the results, and we show each one beside its result."}
""")
fibre_band(s, 0, 0, SLIDE_W, SLIDE_H)
double_rule(s, MARGIN, 0.62, CONTENT_W)
text(s, MARGIN, 0.3, 6.0, 0.3, [("Smart India Hackathon, problem SIH26096", S(size="mast", bold=True, color="ink_2"))])
text(s, MARGIN, 0.95, 8.6, 1.35, [("Grantha Heritage Tracker", S(font="display", size="display", line=0.92))],
     anchor=MSO_ANCHOR.BOTTOM, name="Title")
text(s, MARGIN, 2.45, 7.2, 1.0,
     [(f"Grouping old Indian books by subject, across {C['languages']} languages and the scripts they are written in.",  # from: corpus.languages
       S(font="outlier", size="statement", line=1.02))])
img_w = 9.3
img_h = img_w * 688 / 2335                              # the render's own aspect (docs/assets/manuscript_model.png)
s.shapes.add_picture(str(ASSETS / "manuscript_model.png"), Inches(SLIDE_W - MARGIN - img_w + 0.35), Inches(3.55),
                     Inches(img_w), Inches(img_h)).name = "Palm-leaf manuscript model"
team = [("Vemuri Rohan", "12403675"), ("Rajith Kolappa Pillai Sundar", "12413353"), ("Etikala Sai Pranav", "12401062")]
for i, (who, roll) in enumerate(team):
    y = 4.05 + i * 0.78
    hline(s, MARGIN, y, 2.75, "ink" if i == 0 else "rule", 0.75)
    text(s, MARGIN, y + 0.1, 2.75, 0.6, [(who, S(size="small", bold=True)), (roll, S(size="small", color="muted", space=1))])
double_rule(s, MARGIN, 6.92, CONTENT_W)
text(s, MARGIN, 7.02, CONTENT_W, 0.3,
     [("The palm-leaf manuscript is a 3-D model drawn for this deck. Its leaves carry the opening couplets of the Tirukkural.",
       S(size="caption", color="muted"))])

# ==============================================================================
# 2. THE REAL-LIFE PROBLEM
# ==============================================================================
how_many = "About half" if 0.4 <= no_class <= 0.6 else "Most" if no_class > 0.6 else "Many"
s = new_slide(f"{how_many} of the books cannot be found by subject", f"""
Start with the problem a real archive has.

The Digital Library of India holds scans of old printed books. Of the {n(usable)} books we could use, {n(classified)} carry a library class, the subject code a librarian gives a book. The rest have none, so a subject search cannot find them. They are scanned, but in practice they are lost.

Three things make this hard to fix by hand. One: books in different scripts never meet, so a Tamil book and a Telugu book on the same subject sit in separate piles. Two: a loose page with no cover or title cannot be filed at all. Three: cataloguing needs a person who can read each language, and there are far more books than such people.

So our question: can a computer read the books and group them by subject on its own, across scripts?
""", source="reports/deliverable_facts.json: hierarchical.effects.classified_books, corpus.usable")
text(s, MARGIN, BODY_Y - 0.1, 7.4, 1.45,
     [[(n(classified), S(font="display", size="stat", color="accent", line=0.9)),     # from: hierarchical.effects.classified_books
       (f"  of {n(usable)}", S(font="outlier", size="statement"))]], anchor=MSO_ANCHOR.BOTTOM)  # from: corpus.usable
text(s, MARGIN, BODY_Y + 1.45, 7.4, 0.4, [("usable books have a library class from a librarian. The rest cannot be searched by subject.",
                                           S(size="body", color="muted"))])
swatch_key(s, 8.9, BODY_Y + 0.75, [("with a library class", "accent"), ("no class", "paper_3")])
cd = CategoryChartData()
cd.categories = ["books"]
cd.add_series("with a class", [classified])            # from: hierarchical.effects.classified_books
cd.add_series("without a class", [usable - classified])  # from: corpus.usable minus hierarchical.effects.classified_books
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED_100, Inches(MARGIN - 0.08), Inches(BODY_Y + 1.95),
                        Inches(CONTENT_W + 0.16), Inches(0.55), cd)
ch = gf.chart
plot = style_chart(ch, labels=False)
ch.category_axis.visible = False
ch.value_axis.visible = False
plot.gap_width = 10
plot.overlap = 100
color_series(ch.series[0], "accent")
color_series(ch.series[1], "paper_3")
w3 = (CONTENT_W - 2 * GAP) / 3
for i, (head_t, body_t) in enumerate((
        ("Scripts never meet", "A Tamil book and a Telugu book on one subject sit in separate piles."),
        ("Loose pages get lost", "A page with no cover or title has nowhere to go."),
        ("Too few readers", "Cataloguing by hand needs a person for every language."))):
    x = MARGIN + i * (w3 + GAP)
    hline(s, x, BODY_Y + 2.85, w3, "ink", 0.75)
    text(s, x, BODY_Y + 2.95, w3, 0.55, [(head_t, S(font="display", size="section", line=0.92))])
    text(s, x, BODY_Y + 3.55, w3, 0.9, [(body_t, S(size="body", color="muted"))])

# ==============================================================================
# 3. WHAT THE APP IS AND DOES
# ==============================================================================
rs = REL["knn_other_script_share"] if REL else None     # from: reports/features/related.json:knn_other_script_share
tools = [("Places a page", pct(t1),                                                         # from: evaluation.test.t1_agreement
          f"One scanned page lands in its own book's group; chance is {pct(TEST['t1_chance'])}.")]
if SUG:
    tools.append(("Suggests a class", pct(SUG["top3"]),                                     # from: reports/features/suggest.json:top3
                  f"The right class is in its first three suggestions, on {n(SUG['heldout_books'])} test books."))
if REL:
    tools.append(("Links scripts", pct(rs["centred"]),                                      # from: related.knn_other_script_share.centred
                  f"of a book's closest books are in another script; {pct(rs['uncentred'])} before our fix."))
tools.append(("Maps the archive", n(usable),                                                # from: corpus.usable
              "books, each one dot on a 3D map you can turn, colour and open."))
s = new_slide("Grantha tells an archivist where a book belongs", f"""
This is what we built: Grantha, a web app for the archivist. It is running live on a cloud server, and it does four things.

One, it places a page. The archivist uploads one scanned page, the app reads it, and shows the group it belongs to and the closest books in the archive. In our test a single page landed in its own book's group {pct(t1)} of the time; a random guess manages {pct(TEST['t1_chance'])}.

{f"Two, it suggests a class for a book that has none, by letting the nearest classed books vote. On {n(SUG['heldout_books'])} test books, the book's own class was among the first three suggestions {pct(SUG['top3'])} of the time; the top suggestion alone was right {pct(SUG['top1'])}, against {pct(SUG['baseline_most_common'])} for always naming the most common class." if SUG else ""}

{f"Three, it links books across scripts. After our fix, {pct(rs['centred'])} of a book's {REL['k']} closest books are in another script; before it, {pct(rs['uncentred'])}." if REL else ""}

Four, it draws the whole archive as a map, which you will see in a moment.

The site also lists scans that should be redone and looks for other editions of a book; both are early, and we say so on the limits slide. When a page has too few readable words, the app refuses to guess.
""", source="reports/deliverable_facts.json: evaluation.test.t1_agreement, t1_chance, corpus.usable"
            + ("; reports/features/suggest.json, related.json" if SUG and REL else ""))
fibre_band(s, 0, BODY_Y - 0.05, SLIDE_W, 3.85)
w4 = (CONTENT_W - (len(tools) - 1) * GAP) / len(tools)
for i, (head_t, stat, body_t) in enumerate(tools):
    x = MARGIN + i * (w4 + GAP)
    text(s, x, BODY_Y + 0.15, w4, 1.0, [(stat, S(font="display", size="figure", color="accent", line=0.9))],
         anchor=MSO_ANCHOR.BOTTOM)
    hline(s, x, BODY_Y + 1.35, w4, "ink", 0.75)
    text(s, x, BODY_Y + 1.5, w4, 0.4, [(head_t, S(size="lead", bold=True))])
    text(s, x, BODY_Y + 2.0, w4, 1.6, [(body_t, S(size="body", color="ink_2"))])
text(s, MARGIN, BODY_Y + 4.0, CONTENT_W, 0.5,
     [("Also on the site: the groups to browse, a list of scans to redo, an edition finder, and an API for other software.",
       S(size="body", color="muted"))])

# ==============================================================================
# 4. HOW IT WORKS
# ==============================================================================
s = new_slide("Five steps from a scanned page to a subject group", f"""
Here is the whole method in five steps.

One, read: OCR, software that turns a picture of a page into text. We downloaded {n(C['harvested'])} books in {C['languages']} languages, and {n(usable)} were read clearly enough to use.

Two, embed: an embedding is a list of numbers that stands for the meaning of a text, so books on similar topics get similar numbers. We use {F['encoder']['name']}, which reads all our languages.

Three, centre: we subtract each language's average list of numbers. {"Without this, the strongest signal is the language itself, not the subject; the next slide shows the measurement. This is our key step." if CENTRING_HELPS else "We do this so that language does not dominate; the next slide shows what it changed."}

Four, group, in two ways. Hierarchical clustering joins the closest books step by step into a tree, and we cut the tree into groups. DBSCAN looks for crowded regions of books and marks the rest as noise.

Five, check: we test the groups on books we kept aside, and compare with simple guesses.
""", source="method as built in pipeline/; reports/deliverable_facts.json: corpus.harvested, corpus.usable, encoder.name")
steps = [("Read", "OCR turns each page image into text."),
         ("Embed", "A model turns the text into numbers; similar topics get similar numbers."),
         ("Centre", "Subtract each language's average, so language stops leading."),
         ("Group", "Hierarchical clustering builds a tree of books; DBSCAN finds crowded regions."),
         ("Check", "Test on books kept aside, against simple guesses.")]
col_w = (CONTENT_W - 4 * GAP) / 5
for i, (head, body) in enumerate(steps):
    x = MARGIN + i * (col_w + GAP)
    key = head == "Centre" and CENTRING_HELPS
    if key:
        rect(s, x - 0.18, BODY_Y + 0.05, col_w + 0.36, 3.45, "accent_soft", name="The key step")
    text(s, x, BODY_Y + 0.2, col_w, 0.95, [(str(i + 1), S(font="display", size="figure", color="accent", line=0.9))],
         anchor=MSO_ANCHOR.BOTTOM)
    hline(s, x, BODY_Y + 1.3, col_w, "ink", 0.75)
    text(s, x, BODY_Y + 1.42, col_w, 0.55, [(head, S(font="display", size="section", line=0.92))])
    text(s, x, BODY_Y + 2.0, col_w, 1.5, [(body, S(size="body", color="ink_2"))])
hline(s, MARGIN, BODY_Y + 3.8, CONTENT_W, "rule")
text(s, MARGIN, BODY_Y + 3.92, CONTENT_W, 0.7, [
    [(f"{n(usable)} of {n(C['harvested'])}", S(size="body", bold=True)),                         # from: corpus.usable, harvested
     (f" downloaded books, in {C['languages']} languages, were clear enough to use. Embedding model: "  # from: corpus.languages
      f"{F['encoder']['name']}.", S(size="body", color="muted"))]])                             # from: encoder.name

# ==============================================================================
# 5. LANGUAGE FIRST, AND THE FIX
# ==============================================================================
word_groups = [v for k, v in sorted(NAMES["A_hier"].items(), key=lambda kv: int(kv[0]))]  # from: reports/cluster_names.json:A_hier
word_groups_by_language = all(v.endswith("books") or "(" in v for v in word_groups)
if CE:
    un, ce = CE["uncentred"], CE["centred"]                     # from: deliverable_facts.json:centring_effect
    language_first = un["knn10_same_script"] > 0.5
    title5 = ("Left alone, books group by language; centring removes it" if language_first and CENTRING_HELPS else
              "Left as they are, books group by language first" if language_first else
              "Even left as they are, books do not group mainly by language")
    notes5 = f"""
This is our main finding.

We take the {n(CE['train_books'])} training books and group them twice with the same model: once with the numbers as the model gives them, and once after subtracting each language's average.

The top chart uses NMI, a score of how much the groups follow language: 0 means not at all, 1 means each group is exactly one language. As the model gives them, NMI is {f2(un['nmi_script'])}; after centring it is {f2(ce['nmi_script'])}. {"So centring takes language out of the groups." if CENTRING_HELPS else "So centring did not lower it."}

The bottom chart asks a simpler question: of each book's 10 closest books, how many are written in the same script? As given, {pct(un['knn10_same_script'], 0)}. After centring, {pct(ce['knn10_same_script'], 0)}. {"Left alone, a book's neighbours are mostly books in its own language, whatever the subject." if language_first else "Even before centring, most neighbours are in other scripts."}

{"On the left, for comparison: an earlier study that grouped books by counting words found one group per language." if word_groups_by_language else ""}
"""
    source5 = "reports/deliverable_facts.json: centring_effect.uncentred, centring_effect.centred; reports/cluster_names.json: A_hier"
else:
    title5 = "Counting words, books group by language first"
    notes5 = f"""
When we grouped books by counting their words, in an earlier study, the groups followed language. NMI, a score of how much groups follow language (0 none, 1 fully), is {f2(H['nmi_script'])} for the final groups.
"""
    source5 = "reports/cluster_names.json: A_hier; reports/deliverable_facts.json: hierarchical.nmi_script"
s = new_slide(title5, notes5, source=source5)
text(s, MARGIN, BODY_Y, 3.4, 0.6, [("Groups from counting words, in an earlier study", S(size="body", bold=True))])
for i, g in enumerate(word_groups):
    y = BODY_Y + 0.7 + i * 0.5
    hline(s, MARGIN, y, 3.4, "ink" if i == 0 else "rule", 0.75 if i == 0 else 0.5)
    text(s, MARGIN, y + 0.1, 3.4, 0.35, [(g, S(size="body", color="ink_2"))])
if CE:
    for j, (label, key, fmt) in enumerate((("How much the groups follow language (NMI: 0 none, 1 fully)", "nmi_script", "0.00"),
                                           ("Share of a book's 10 closest books in the same script", "knn10_same_script", "0%"))):
        y = BODY_Y + j * 2.3
        text(s, 4.75, y, 7.8, 0.4, [(label, S(size="body", bold=True))])
        bar_chart(s, 4.65, y + 0.4, 7.95, 1.7, ["as the model gives them", "after centring"],
                  [(key, [un[key], ce[key]], ["rule", "accent"])],    # from: centring_effect.uncentred/centred.<key>
                  number_format=fmt, gap=40, max_scale=1.15)      # headroom so a label near 1 is not clipped
else:
    text(s, 4.75, BODY_Y, 7.8, 0.5, [("How much the final groups follow language (NMI: 0 none, 1 fully)", S(size="body", bold=True))])
    bar_chart(s, 4.65, BODY_Y + 0.45, 7.95, 1.6, [f"{F['encoder']['name']}, centred"],
              [("NMI", [H["nmi_script"]], ["accent"])], number_format="0.00", gap=50, max_scale=1)  # from: hierarchical.nmi_script

# ==============================================================================
# 6. THE ARCHIVE MAP (UMAP layout from the live app, or the flat PCA view when it is absent)
# ==============================================================================
GALAXY = load("web/data/galaxy.json")
UMAP = load("web/data/galaxy_umap.json") if (ROOT / "web/data/galaxy_umap.json").exists() else None
if UMAP and UMAP["n"] != GALAXY["n"]:
    UMAP = None                                                 # a layout of other books cannot be coloured by these
tags = [b["lang_tag"] for b in GALAXY["books"]]                 # from: web/data/galaxy.json:books[].lang_tag
grp = [b["group"] for b in GALAXY["books"]]                     # from: web/data/galaxy.json:books[].group
coords = UMAP["coords"] if UMAP else GALAXY["views"]["centred"]  # from: web/data/galaxy_umap.json:coords
step = max(1, len(tags) // 1800)                                # a light, even sample keeps the chart quick to open


def apartness(pts_, labels) -> dict:
    """Per label: how far its books' middle sits from the middle of all books, in units of the overall spread."""
    cx, cy = sum(p[0] for p in pts_) / len(pts_), sum(p[1] for p in pts_) / len(pts_)
    spread = (sum((p[0] - cx) ** 2 + (p[1] - cy) ** 2 for p in pts_) / len(pts_)) ** 0.5
    out = {}
    for lab in set(labels):
        own = [p for p, t in zip(pts_, labels) if t == lab]
        lx, ly = sum(p[0] for p in own) / len(own), sum(p[1] for p in own) / len(own)
        out[lab] = ((lx - cx) ** 2 + (ly - cy) ** 2) ** 0.5 / spread
    return out


raw_apart = apartness(GALAXY["views"]["uncentred"], tags)
star = max(raw_apart, key=raw_apart.get)                        # the language that sits furthest apart before centring
lang_apart, group_apart = apartness(coords, tags), apartness(coords, grp)
apart_langs = sorted(l for l, a in lang_apart.items() if a > 1)   # middle more than one overall spread from everyone's middle
if apart_langs:
    star = max(apart_langs, key=lang_apart.get)                 # show the language that stands furthest apart on this map
star_name = LANG.get(star, star)
apart_names = " and ".join(LANG.get(l, l) for l in apart_langs)
lang_mixed = not apart_langs
n_lang = len(set(tags))
groups_regional = max(group_apart.values()) > 1
cross = (f" This matches the measurement: after centring, {pct(REL['knn_other_script_share']['centred'])} of a book's closest books "
         f"are in another script, up from {pct(REL['knn_other_script_share']['uncentred'])}, which is a real change and still a minority."
         if REL else "")
map_word = "UMAP map" if UMAP else "map"
s = new_slide(("On the map, languages mix and the groups take their own regions" if lang_mixed and groups_regional else
               "On the map, languages mix after centring" if lang_mixed else
               f"On the map, {n_lang - len(apart_langs)} of {n_lang} languages mix; {apart_names} stands apart"), f"""
This is the archive map from the app. Each dot is one book.

{"The layout is made by UMAP, a method that draws many-dimensional points on a flat page while keeping each book next to its closest neighbours. So nearby dots are books the model reads as similar. Distances between far-apart clumps mean little." if UMAP else "The layout keeps the two directions that spread the books most."} It is drawn after centring, the step from the last slide.

Both panels show the same dots. On the left, the blue dots are {star_name} books. {"They are spread through the whole map, among books of every other language: no language keeps a corner to itself." if lang_mixed else f"The tan dots, every other language, share one large body, so those languages have mixed. The {star_name} books have not: they keep their own islands. Centring removes the average difference between languages, but a book's closest neighbours are still often in its own language, and a neighbour map shows exactly that." + cross + " We have not tested why " + apart_names + " stands apart, so we only report it."}

On the right, the same map coloured by the {H['k']} groups that hierarchical clustering found. {"Each group holds its own region of the map, so the groups follow what the books say, not which language they are in." if groups_regional else "The groups overlap on the map: they are broad, and the borders between them are soft."}

The slide shows a sample of the {n(usable)} books in two dimensions. In the app the map is in 3-D with every book: you can turn it, switch the colour between language and group, and open sample books. A picture explains; the measurements prove.
""", source=("web/data/galaxy_umap.json: coords (from the live app); " if UMAP else "web/data/galaxy.json: views.centred; ")
            + "web/data/galaxy.json: books[].lang_tag, books[].group")
group_ids = sorted(set(grp))
group_colors = dict(zip(group_ids, ("accent", "ink", "rule", "muted", "accent_soft")))
panels = [(f"{'UMAP map' if UMAP else 'Map'} by language: {star_name} in blue", [("other languages", lambda i: tags[i] != star, "rule"),
                                                (star_name, lambda i: tags[i] == star, "accent")]),
          (f"{'UMAP map' if UMAP else 'Map'} by hierarchical group", [(f"Group {g + 1}", (lambda i, g=g: grp[i] == g), group_colors.get(g, "rule"))
                                     for g in reversed(group_ids)])]
for j, (label, series) in enumerate(panels):
    x = MARGIN + j * 4.3
    text(s, x, BODY_Y, 4.0, 0.4, [(label, S(size="body", bold=True))])
    hline(s, x, BODY_Y + 0.42, 4.0, "ink", 0.75)
    scatter(s, x - 0.1, BODY_Y + 0.5, 4.1, 4.1,
            [(name, [(coords[i][0], coords[i][1]) for i in range(0, len(coords), step) if keep(i)], color)  # from: coords[][0..1]
             for name, keep, color in series])
swatch_key(s, 9.45, BODY_Y, [(f"Group {g + 1}", group_colors.get(g, "rule")) for g in group_ids])
text(s, 9.45, BODY_Y + 0.34 * len(group_ids) + 0.4, 3.15, 3.0, [
    ("Each dot is one book; nearby dots are similar books.", S(size="lead")),
    ((f"UMAP layout, drawn after centring. A sample of the {n(usable)} books." if UMAP else           # from: corpus.usable
      f"A flat view after centring. A sample of the {n(usable)} books."), S(size="body", color="muted", space=12)),
    ("In the app the map is 3D and shows every book.", S(size="body", color="muted", space=8)),
])

# ==============================================================================
# 7. HIERARCHICAL CLUSTERING: THE GROUPS
# ==============================================================================
groups = F["groups"]                                         # from: deliverable_facts.json:groups
lang_codes = [r["lang"] for r in C["by_language"]]
top_share = max(g["top_language_share"] for g in groups)    # from: groups[].top_language_share
all_mixed = all(all(g["languages"].get(l, 0) > 0 for l in lang_codes) for g in groups)
subject_count = {}
for g in groups:                                             # from: groups[].majority_subject
    subj = g["majority_subject"] or "no labelled books"
    subject_count[subj] = subject_count.get(subj, 0) + 1
lean = "; ".join(f"{'one group leans' if c == 1 else f'{c} groups lean'} to {subj}"
                 for subj, c in sorted(subject_count.items(), key=lambda kv: -kv[1]))
pci = TEST.get("t2_points_ci95")                             # from: evaluation.test.t2_points_ci95
significant = TEST["t2_p"] is not None and TEST["t2_p"] < 0.05
best_name = "guessing from the script alone" if TEST["t2_baseline_script"] >= TEST["t2_baseline_common"] else \
    "always guessing the most common subject"
best_base = max(TEST["t2_baseline_script"], TEST["t2_baseline_common"])
s = new_slide(f"The tree cuts into {len(groups)} broad groups, each mixing "
              f"{'all ' + str(len(lang_codes)) if all_mixed else 'many'} languages", f"""
Hierarchical clustering starts with every book alone, joins the two closest, then the next closest, and so on, until all the books hang on one tree. We cut the tree into {H['k']} groups, using {H['linkage']} linkage; the number of groups was chosen on the training books by a rule we fixed beforehand.

Each row is a group. The columns show what share of the group comes from each language: the darker the cell, the bigger the share. No language holds more than {pct(top_share, 0)} of any group{", so the groups are not language piles" if top_share < 0.5 else ", so one language still dominates at least one group"}.

The subject column is the most common subject among the hand-labelled training books in that group: {lean}. These are broad shelves, not a catalogue.

How good are they? On {n(TEST['t2_labelled_heldout'])} labelled books kept aside, each group predicts its most common subject and is right {pct(TEST['t2_accuracy'])} of the time. The best simple guess, {best_name}, is right {pct(best_base)}. So the groups {"lead" if gain_t > 0 else "trail"} by {pts(abs(gain_t))} points against a target of {gain(t2_target)}: {met_word(MET['T2'])}.{f" The likely range is {gain(pci[0])} to {gain(pci[1])} points, and the validation books gave {gain(gain_v)}, so we hold this result with care." if pci else ""} {"Random shuffles of the labels almost never give a gain this big." if significant else "Random shuffles of the labels often give a gain this big, so it may be luck."}

One honest number: the silhouette, a score of how cleanly groups separate, from 0 for overlapping to 1 for clean, is {f2(H['silhouette'])}. The groups overlap a great deal.
""", source="reports/deliverable_facts.json: groups[], hierarchical.linkage, k, silhouette; evaluation.test.t2_accuracy, t2_points, targets, met")
max_cell = max(max(g["languages"].values()) for g in groups)
head = [("Group", S(medium=True)), ("Books", S(medium=True, align=PP_ALIGN.RIGHT)), ("Most common subject", S(medium=True))] + \
       [(LANG[l], S(medium=True, align=PP_ALIGN.RIGHT)) for l in lang_codes]
rows = [head]
for g in groups:
    rows.append([(f"{g['group'] + 1}", S(font="display", size="section", color="accent")),     # from: groups[].group
                 (n(g["books"]), S(align=PP_ALIGN.RIGHT)),                              # from: groups[].books
                 (g["majority_subject"] or "no labelled books", S(bold=True))] +        # from: groups[].majority_subject
                [(pct(g["languages"].get(l, 0), 0), S(align=PP_ALIGN.RIGHT),            # from: groups[].languages
                  mix("paper", "accent_soft", g["languages"].get(l, 0) / max_cell)) for l in lang_codes])
ledger(s, MARGIN, BODY_Y + 0.35, CONTENT_W, rows,
       [0.85, 0.95, 2.5] + [(CONTENT_W - 4.3) / len(lang_codes)] * len(lang_codes), row_h=0.58)
text(s, MARGIN, BODY_Y - 0.12, CONTENT_W, 0.3, [("Hierarchical clustering: every book joins a tree, and the tree is cut into groups",
                                                S(size="small", bold=True, color="ink_2"))])
text(s, MARGIN, BODY_Y + 2.85, 8.2, 1.7, [
    (f"On test books the groups guess the subject {pts(abs(gain_t))} points {'better' if gain_t > 0 else 'worse'} than the best "  # from: t2_points
     f"simple guess. Target {gain(t2_target)}: {met_word(MET['T2'])}.", S(font="outlier", size="statement", line=1.02)),   # from: targets, met.T2
])
text(s, 9.3, BODY_Y + 2.85, 3.3, 1.7, [
    (f"A tree of books joined closest first ({H['linkage']} linkage), cut into {H['k']} groups.",        # from: hierarchical.linkage, k
     S(size="body", color="ink_2")),
    (f"Silhouette {f2(H['silhouette'])}: the groups are broad and overlap.", S(size="body", color="muted", space=8)),  # from: hierarchical.silhouette
])

# ==============================================================================
# 8. DBSCAN, AND HOW STEADY EACH METHOD IS
# ==============================================================================
stable = hb["median"] >= t3_target
db_steadier = dbb["median"] > hb["median"]
agree = F["hier_vs_dbscan"]["ari_non_noise"]                # from: deliverable_facts.json:hier_vs_dbscan.ari_non_noise
s = new_slide(f"A density search finds {DB['n_clusters']} crowded regions; {pct(DB['noise_share'], 0)} of books are noise", f"""
Our second method, DBSCAN, asks a different question. It does not cut the books into shelves. It looks for crowded regions, places where many books sit close together, and calls every book outside them noise.

It finds {DB['n_clusters']} crowded regions and marks {pct(DB['noise_share'])} of the books as noise. Noise here is not an error: it means the book has no close crowd, so any group we give it deserves less trust. The app shows this verdict beside every answer.

The chart shows how steady each method is. We re-ran each one {len(hb['values'])} times on a random part of the books and compared the result with the full run, using ARI, a score of how much two groupings agree: 1 is identical, 0 is chance.

The blue dots are DBSCAN: around {f2(dbb['median'])}, {"very steady" if dbb['median'] >= 0.8 else "fairly steady"}. The brown dots are the hierarchical groups: the middle value is {f2(hb['median'])}, against our target of {t3_target}. {'We met it.' if stable else 'We did not meet it: the hierarchical groups shift when the books change.'}

The two methods also {"barely agree with each other" if agree < 0.2 else "partly agree with each other"}: their ARI is {f2(agree)}. So we use them for different jobs. Hierarchical clustering gives every book a shelf; DBSCAN says how sure we can be.
""", source="reports/deliverable_facts.json: dbscan.n_clusters, noise_share, bootstrap.values; hierarchical.bootstrap.values; hier_vs_dbscan")
text(s, MARGIN, BODY_Y - 0.12, CONTENT_W, 0.3, [("DBSCAN: a density search for crowded regions of books; each dot is one re-run",
                                                S(size="small", bold=True, color="ink_2"))])
scatter(s, MARGIN - 0.1, BODY_Y + 0.25, 8.5, 4.3,
        [("DBSCAN", list(enumerate(dbb["values"], 1)), "accent"),                     # from: dbscan.bootstrap.values
         ("Hierarchical groups", list(enumerate(hb["values"], 1)), "muted"),           # from: hierarchical.bootstrap.values
         ("target", [(1, t3_target), (len(hb["values"]), t3_target)], None)],          # from: evaluation.test.targets.T3_bootstrap_ari
        size=9, value_axis=True, max_scale=1, fmt="0.0")
swatch_key(s, 9.25, BODY_Y, [("DBSCAN, one dot per re-run", "accent"), ("hierarchical groups", "muted"),
                             (f"target {t3_target}", "ink")])                                     # from: evaluation.test.targets
text(s, 9.25, BODY_Y + 1.3, 3.35, 3.3, [
    ("DBSCAN looks for crowded regions; a book outside them is noise.", S(size="lead")),
    (f"Steadiness on re-runs (ARI, 1 is identical): DBSCAN {f2(dbb['median'])}, hierarchical {f2(hb['median'])}.",  # from: bootstrap.median
     S(size="body", space=12)),
    ("The app shows the DBSCAN verdict beside every answer, as a measure of trust.", S(size="body", color="muted", space=8)),
])

# ==============================================================================
# 9. RESULTS AND LIMITS
# ==============================================================================
cat_gain = CAT.get("points_above_best_baseline")
tri_chance = bool(TRI) and TRI["auc_ci95"][0] <= 0.5 <= TRI["auc_ci95"][1]
limit_lines = [f"{worst['name']} keeps only {pct(worst['usable'] / worst['harvested'], 0)} of its books."]   # from: corpus.by_language
if cat_gain is not None and cat_gain <= 0:
    limit_lines.append(f"Against the librarians' own classes the groups score {gain(cat_gain)} "
                       "points from the best simple guess.")                                  # from: evaluation.test.catalogue
if tri_chance:
    limit_lines.append(f"Scan triage is no better than chance (AUC {TRI['auc']:.2f}).")        # from: reports/features/triage.json
limit_lines.append("Test labels were made with an AI assistant and checked by us.")
limit_lines.append("The embedding model is an online Google service.")
cat_sentence = (f"Against the librarians' own catalogue classes, rather than our subject labels, the groups score {gain(cat_gain)} "
                f"points from the best simple guess, so they {'do not beat' if cat_gain <= 0 else 'beat'} it there. "
                if cat_gain is not None else "")
tri_sentence = (f"The score behind the list of scans to redo separates good and bad scans with an AUC of {TRI['auc']:.2f}, where "
                f"0.5 is chance, {'so it is no better than chance' if tri_chance else 'so it does better than chance'}. " if TRI else "")
edi_sentence = (f"The edition finder made no false report but found {pct(EDI['recall'])} of known editions, in only "
                f"{EDI['groups_heldout']} test groups, so that number is very uncertain. " if EDI and EDI["precision"] >= 0.995 else
                f"The edition finder found {pct(EDI['recall'])} of known editions in only {EDI['groups_heldout']} test groups, "
                "so that number is very uncertain. " if EDI else "")
s = new_slide(f"We met {n_met} of our 3 targets; here is what it does not do yet", f"""
Our results and limits, plainly.

We set three targets before seeing any results, and this study met {n_met} of them. A page lands with its book {pct(t1)} of the time against a target of {pct(t1_target, 0)}: {met_word(MET['T1'])}. The subject gain is {gain(gain_t)} points against {gain(t2_target)}: {met_word(MET['T2'])}{f", though the validation books gave {gain(gain_v)}" if MET['T2'] and not VAL['met']['T2'] else ""}. Stability, measured on the training books, is {f2(TEST['t3_bootstrap'])} against {t3_target}: {met_word(MET['T3'])}.

{cat_sentence}{tri_sentence}{edi_sentence}

The groups are broad: {H['k']} groups for a whole library. Hard-to-read languages are under-represented; {worst['name']} keeps only {pct(worst['usable'] / worst['harvested'], 0)} of its books. The subject labels we test with were made with an AI assistant and checked by us; they are a measuring tool, not expert cataloguing. And the embedding model is an online Google service, so checking a page sends its text to Google.

So we offer this as a helper that shows its evidence, not as a catalogue.
""", source="reports/deliverable_facts.json: evaluation.test.targets, met, t1_agreement, t2_points, t3_bootstrap, catalogue"
            + ("; reports/features/triage.json" if TRI else ""))


def verdict_cell(ok: bool):
    return (met_word(ok), S(bold=ok, color="accent" if ok else "muted"))


rows = [[("Target set before the results", S(medium=True)), ("Needed", S(medium=True, align=PP_ALIGN.RIGHT)),
         ("Got", S(medium=True, align=PP_ALIGN.RIGHT)), ("", S())],
        [("A page lands with its book", S()), (pct(t1_target, 0), S(align=PP_ALIGN.RIGHT)),                 # from: targets.T1_page_agreement
         (pct(t1), S(align=PP_ALIGN.RIGHT)), verdict_cell(MET["T1"])],                                         # from: t1_agreement, met.T1
        [("Subject gain over the best simple guess", S()), (f"{gain(t2_target)} points", S(align=PP_ALIGN.RIGHT)),  # from: targets.T2
         (f"{gain(gain_t)} points", S(align=PP_ALIGN.RIGHT)), verdict_cell(MET["T2"])],                     # from: t2_points, met.T2
        [("Groups hold on re-runs (ARI, train books)", S()), (str(t3_target), S(align=PP_ALIGN.RIGHT)),     # from: targets.T3
         (f2(TEST["t3_bootstrap"]), S(align=PP_ALIGN.RIGHT)), verdict_cell(MET["T3"])]]                    # from: t3_bootstrap, met.T3
ledger(s, MARGIN, BODY_Y + 0.1, 7.3, rows, [3.9, 1.25, 1.25, 0.9], row_h=0.58)
text(s, 8.55, BODY_Y, 4.05, 0.4, [("What it does not do yet", S(size="body", bold=True))])
for i, line in enumerate(limit_lines):
    y = BODY_Y + 0.45 + i * 0.76
    hline(s, 8.55, y, 4.05, "ink" if i == 0 else "rule", 0.75 if i == 0 else 0.5)
    text(s, 8.55, y + 0.08, 4.05, 0.66, [(line, S(size="small", color="ink_2"))])
text(s, MARGIN, BODY_Y + 2.75, 7.3, 1.2,
     [("A helper that shows its evidence, not a catalogue.", S(font="outlier", size="statement", line=1.02))])

# ==============================================================================
# 10. SUMMARY: the one ultramarine field
# ==============================================================================
if CENTRING_HELPS and gain_t > 0:
    title10 = "Take away the language, and subject starts to show"
elif CENTRING_HELPS:
    title10 = "Taking away the language is not enough on its own"
else:
    title10 = "Grouping by subject across scripts is still open"
if gain_t <= 0:
    p2_head, p2_tail = "The groups do not beat simple guesses.", f"{gain(gain_t)} points against a target of {gain(t2_target)}"
elif MET["T2"]:
    p2_head = "The groups beat simple guesses and reach the subject target on test books."
    p2_tail = f"{gain(gain_t)} points on test books against {gain(t2_target)}" + \
        (f"; validation gave {gain(gain_v)}" if not VAL["met"]["T2"] else "")
else:
    p2_head, p2_tail = "The groups beat simple guesses, by less than we aimed.", f"{gain(gain_t)} points against a target of {gain(t2_target)}"
p2_tail += "; not yet stable." if not MET["T3"] else "; stable on re-runs."
p1_head = "Books group by language first." if CE and CE["uncentred"]["knn10_same_script"] > 0.5 else "Language shapes the groups."
p1_tail = ("Subtracting each language's average lets subject come through." if CENTRING_HELPS else
           "Subtracting each language's average did not remove it.")
s = new_slide(None, f"""
To sum up in three sentences.

One: {p1_head[:-1].lower()}; {p1_tail[0].lower() + p1_tail[1:]}

Two: {p2_head[0].lower() + p2_head[1:-1]}: {p2_tail}

Three: Grantha is a working app that helps an archivist today: it places a new page, suggests a class for an uncatalogued book, links books across scripts, and draws the whole archive as one map, always with its evidence.

Thank you. We are happy to take your questions.
""", ground_color="accent")
quiet = mix("accent", "accent_ink", 0.72)
faint = mix("accent", "accent_ink", 0.35)
text(s, MARGIN, MAST_Y, 6.0, 0.3, [("Grantha Heritage Tracker", S(size="mast", bold=True, color="accent_ink"))])
text(s, SLIDE_W - MARGIN - 2.0, MAST_Y, 2.0, 0.3, [("10 of 10", S(size="mast", medium=True, color=quiet, align=PP_ALIGN.RIGHT))])
double_rule(s, MARGIN, MAST_Y + 0.36, CONTENT_W, "accent_ink")
text(s, MARGIN, TITLE_Y, CONTENT_W, TITLE_H, [(title10, S(font="display", size="title", color="accent_ink", line=0.92))],
     anchor=MSO_ANCHOR.BOTTOM, name="Title")
points = [(p1_head, p1_tail),                                                                 # from: centring_effect
          (p2_head, p2_tail),                                                                 # from: evaluation.test.t2_points, targets, met
          ("A working app for the archivist.", "It places pages, suggests classes, links scripts and maps the archive.")]
w3 = (CONTENT_W - 2 * GAP) / 3
for i, (head_t, body_t) in enumerate(points):
    x = MARGIN + i * (w3 + GAP)
    text(s, x, BODY_Y + 0.55, w3, 0.6, [(str(i + 1), S(font="display", size="figure", color="accent_ink", line=0.9))],
         anchor=MSO_ANCHOR.BOTTOM)
    hline(s, x, BODY_Y + 1.3, w3, faint, 0.75)
    text(s, x, BODY_Y + 1.45, w3, 2.4, [(head_t, S(size="lead", bold=True, color="accent_ink")),
                                        (body_t, S(size="body", color=quiet, space=8))])
double_rule(s, MARGIN, 6.3, CONTENT_W, "accent_ink")
text(s, MARGIN, 6.48, CONTENT_W, 0.5, [("Thank you. Questions are welcome.", S(font="outlier", size="statement", color="accent_ink"))])

prs.save(OUT)
print(f"saved {OUT.relative_to(ROOT)} ({len(prs.slides)} slides)")
