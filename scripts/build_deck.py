"""Builds Grantha_Heritage_Tracker_SIH26096.pptx from the result files, with no hand-typed result.

    python scripts/build_deck.py

Reads only:
  reports/deliverable_facts.json           every number written on a slide or in the notes
  web/data/study.json, reports/**/*.json   chart series and names the facts file does not hold
  reports/features/*.json                  feature evaluations, when present (slides show the tool without numbers if absent)
  web/fixtures/*.json                      real example outputs of the app (catalogue card, related books, page check)

Every number in slide text comes from deliverable_facts.json or reports/features/*.json, so
`python scripts/check_claims.py` can trace it. Every sentence that states an outcome (met or not met, better or worse,
which subject a group leans to, whether centring helped) is chosen by a branch on the facts, never written for one result.
Chart values carry a `# from:` comment naming their file and key path. Titles that state a result are built from
the data, so they stay true when the results change.

Fonts: Georgia (headings) and Segoe UI (body) ship with every Windows install and with Office, so the deck renders
the same on any Windows PowerPoint without embedding. Book titles in Indian scripts use Nirmala UI, the Windows
font that covers Bengali, Devanagari, Gujarati, Kannada, Tamil and Telugu.
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
# DESIGN TOKENS: the only place a colour, font or size is written
# ==============================================================================
COLOR = {
    "paper": "FFFFFF",       # content slide ground
    "ink": "1C1A17",         # text and the dark ground
    "muted": "6A645B",       # secondary text, axis labels
    "rule": "E3DFD8",        # hairlines and gridlines
    "tint": "F4F2EE",        # one panel surface
    "accent": "A63A1F",      # laterite red: the one series that argues
    "accent_soft": "E7B9AA",  # light end of the accent ramp (table shading)
    "neutral": "B9B3AA",     # reference and baseline series
    "on_dark": "F4F2EE",     # text on the dark ground
    "on_dark_muted": "B5AEA3",
}
FONT = {"head": "Georgia", "body": "Segoe UI", "indic": "Nirmala UI"}
SIZE = {"display": 54, "title": 32, "stat": 88, "lead": 22, "body": 16, "small": 14, "caption": 11, "chart": 13,
        "table": 13, "step": 40}
SLIDE_W, SLIDE_H = 13.333, 7.5
MARGIN = 0.75                       # left and right
TITLE_Y, TITLE_H = 0.55, 1.25
BODY_Y = 2.05                       # content starts here
FOOT_Y = 6.92                       # source line and slide number
GAP = 0.4


def rgb(name: str) -> RGBColor:
    return RGBColor.from_string(COLOR[name])


def mix(a: str, b: str, t: float) -> RGBColor:
    """A colour t of the way from token a to token b (for table shading)."""
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
ENCODERS = load("reports/study/encoder_comparison.json")
NAMES = load("reports/cluster_names.json")
FEATURES = {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((ROOT / "reports" / "features").glob("*.json"))} if (ROOT / "reports" / "features").exists() else {}
EXAMPLE_BOOK = "dli.56E228"                  # an uncatalogued Tamil book with a recorded suggestion and related list
CHECK_FIXTURE = "post_check__in.ernet.dli.2015.294941"


def fixture(name: str) -> dict:
    return load(f"web/fixtures/{name}.json")["body"]


C = F["corpus"]
TEST, VAL = F["evaluation"]["test"], F["evaluation"]["val"]
H, DB = F["hierarchical"], F["dbscan"]
CMP = F.get("comparison_study")
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


def ground(slide, dark=False):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb("ink" if dark else "paper")


def text(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, name=None):
    """paras: list of (text, style) or (list of (text, style) runs). style: dict(font, size, color, bold, italic, align, space)."""
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
        p.line_spacing = first_style.get("line", 1.1)
        for t, st in runs:
            r = p.add_run()
            r.text = t
            r.font.name = FONT[st.get("font", "body")]
            r.font.size = Pt(SIZE[st.get("size", "body")])
            r.font.color.rgb = rgb(st.get("color", "ink"))
            r.font.bold = st.get("bold", False)
            r.font.italic = st.get("italic", False)
    return box


def S(**kw):
    return kw


def new_slide(title, notes, source=None, dark=False):
    slide = prs.slides.add_slide(BLANK)
    ground(slide, dark)
    SLIDES.append(slide)
    if title:
        text(slide, MARGIN, TITLE_Y, SLIDE_W - 2 * MARGIN, TITLE_H,
             [(title, S(font="head", size="title", color="on_dark" if dark else "ink", line=1.0))],
             anchor=MSO_ANCHOR.BOTTOM, name="Title")
    if source:
        text(slide, MARGIN, FOOT_Y, 10.5, 0.3, [(f"Source: {source}", S(size="caption", color="muted"))], name="Source")
    if not dark:
        text(slide, SLIDE_W - MARGIN - 0.8, FOOT_Y, 0.8, 0.3,
             [(str(len(SLIDES)), S(size="caption", color="muted", align=PP_ALIGN.RIGHT))], name="Slide number")
    slide.notes_slide.notes_text_frame.text = notes.strip()
    return slide


def rect(slide, x, y, w, h, color, name=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(color) if isinstance(color, str) else color
    shp.line.fill.background()
    shp.shadow.inherit = False
    if name:
        shp.name = name
    return shp


def hline(slide, x, y, w, color="rule", weight=1.0):
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x), Inches(y), Inches(x + w), Inches(y))
    ln.line.color.rgb = rgb(color)
    ln.line.width = Pt(weight)
    return ln


def swatch_key(slide, x, y, items):
    """A direct key: a small swatch beside each series name, text in ink (never in the data colour)."""
    for i, (label, color) in enumerate(items):
        yy = y + i * 0.34
        rect(slide, x, yy + 0.06, 0.18, 0.18, color)
        text(slide, x + 0.3, yy, SLIDE_W - MARGIN - x - 0.3, 0.3, [(label, S(size="small"))])


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
        va.major_gridlines.format.line.width = Pt(0.75)
        va.tick_labels.font.color.rgb = rgb("muted")
        va.tick_labels.number_format = number_format
        va.tick_labels.number_format_is_linked = False
    else:
        va.tick_label_position = XL_TICK_LABEL_POSITION.NONE
    va.format.line.fill.background()
    va.minimum_scale = 0
    if max_scale is not None:
        va.maximum_scale = max_scale
    ca.format.line.color.rgb = rgb("rule")
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
    series.format.fill.fore_color.rgb = rgb(color)
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


def plain_table(slide, x, y, w, rows, col_w, row_h=0.42, header=True):
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
            r.font.name = FONT[st.get("font", "body")]
            r.font.size = Pt(SIZE[st.get("size", "table")])
            r.font.bold = st.get("bold", False)
            r.font.color.rgb = rgb(st.get("color", "ink"))
            if header and i == 0:
                tcPr = cell._tc.get_or_add_tcPr()
                ln = etree.Element(qn("a:lnB"), w=str(Emu(Pt(1))), cmpd="sng")
                tcPr.insert(0, ln)                     # borders precede the cell fill in the schema
                sf = etree.SubElement(ln, qn("a:solidFill"))
                etree.SubElement(sf, qn("a:srgbClr"), val=COLOR["ink"])
    return tbl


# ==============================================================================
# 1. TITLE
# ==============================================================================
s = new_slide(None, f"""
Good morning. We are Rohan, Rajith and Sai Pranav, and this is the Grantha Heritage Tracker, for Smart India Hackathon problem SIH26096.

The idea in one line: old printed Indian books sit in a digital library in many scripts, and we asked whether a computer can group them by subject without being told the subjects.

Every number you will see comes from our result files. {"We set three targets before the results; where we missed one, we say so." if not all(MET.values()) else "We set three targets before the results, and we show each one beside its result."}
""", dark=True)
text(s, MARGIN, 1.7, 11.5, 1.2, [("Grantha Heritage Tracker", S(font="head", size="display", color="on_dark", line=1.0))])
text(s, MARGIN, 2.95, 10.5, 0.9,
     [(f"Grouping old Indian books by subject across {C['languages']} languages",  # from: deliverable_facts.json:corpus.languages
       S(size="lead", color="on_dark"))])
text(s, MARGIN, 3.55, 10.5, 0.5, [("Smart India Hackathon problem SIH26096", S(size="body", color="on_dark_muted"))])
team = [("Vemuri Rohan", "12403675"), ("Rajith Kolappa Pillai Sundar", "12413353"), ("Etikala Sai Pranav", "12401062")]
for i, (who, roll) in enumerate(team):
    text(s, MARGIN + i * 3.9, 5.55, 3.6, 0.8,
         [(who, S(size="body", color="on_dark", bold=True)), (roll, S(size="small", color="on_dark_muted", space=2))])

# ==============================================================================
# 2. THE PROBLEM
# ==============================================================================
classified = H["effects"]["classified_books"]          # from: deliverable_facts.json:hierarchical.effects.classified_books
usable = C["usable"]                                   # from: deliverable_facts.json:corpus.usable
no_class = 1 - classified / usable
s = new_slide("About half the books carry no library class" if 0.4 <= no_class <= 0.6 else
              "Most books carry no library class" if no_class > 0.6 else
              "Most books carry a library class, but many do not", f"""
Start with the problem an archivist has.

These are scans of old printed books from the Digital Library of India. Of the {n(usable)} books we could use, {n(classified)} carry a library class, the subject code a librarian gives a book. The rest have none, so a subject search cannot find them.

And books in different scripts never meet: a Tamil book and a Telugu book on the same subject sit in separate piles.

So our question: can the computer read the books and group them by subject on its own?
""", source="reports/deliverable_facts.json: hierarchical.effects.classified_books, corpus.usable")
text(s, MARGIN, BODY_Y + 0.2, 8.0, 1.3,
     [[(n(classified), S(font="head", size="stat", color="accent")),             # from: hierarchical.effects.classified_books
       (f"  of {n(usable)}", S(font="head", size="title", color="ink"))]], anchor=MSO_ANCHOR.BOTTOM)  # from: corpus.usable
text(s, MARGIN, BODY_Y + 1.6, 8.0, 0.5,
     [("usable books have a library class from a librarian.", S(size="lead"))])
cd = CategoryChartData()
cd.categories = ["books"]
cd.add_series("with a class", [classified])            # from: hierarchical.effects.classified_books
cd.add_series("without a class", [usable - classified])  # from: corpus.usable minus hierarchical.effects.classified_books
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED_100, Inches(MARGIN - 0.1), Inches(BODY_Y + 2.35),
                        Inches(SLIDE_W - 2 * MARGIN + 0.2), Inches(0.9), cd)
ch = gf.chart
plot = style_chart(ch, labels=False)
ch.category_axis.visible = False
ch.value_axis.visible = False
plot.gap_width = 10
plot.overlap = 100
color_series(ch.series[0], "accent")
color_series(ch.series[1], "rule")
swatch_key(s, MARGIN, BODY_Y + 3.35, [("with a library class", "accent"), ("no class: a subject search misses them", "rule")])
text(s, 7.6, BODY_Y + 3.35, 5.0, 0.8,
     [("Books in different scripts never meet in one subject search.", S(size="body", color="muted"))])

# ==============================================================================
# 3. THE DATA
# ==============================================================================
langs = sorted(C["by_language"], key=lambda r: -r["usable"] / r["harvested"])   # from: corpus.by_language
worst, best = langs[-1], langs[0]
worst_reads_worst = worst["lang"] == min(C["by_language"], key=lambda r: r["median_conf"])["lang"]
why_worst = "its scans are the hardest to read" if worst_reads_worst else "it loses the most books at the quality check"
s = new_slide(f"{n(C['usable'])} of {n(C['harvested'])} books were clear enough to use", f"""
Our data: books from the Digital Library of India, mirrored on the Internet Archive, in {C['languages']} languages. We downloaded {n(C['harvested'])} books.

To read a scan, we use OCR: software that turns a picture of a page into text. A book is usable only when the OCR reads it with enough confidence and finds enough real words.

{n(C['usable'])} books pass, which is {pct(C['usable_share'])}. The grey bar is what we downloaded, the red bar is what we could use. {best['name']} keeps the most, {pct(best['usable'] / best['harvested'], 0)}. {worst['name']} keeps the fewest, {pct(worst['usable'] / worst['harvested'], 0)}: {why_worst}.

The {n(C['excluded'])} excluded books are not deleted; they stay in the database, marked.
""", source="reports/deliverable_facts.json: corpus.by_language[].harvested, corpus.by_language[].usable")
bar_chart(s, MARGIN - 0.1, BODY_Y - 0.15, 8.6, 4.9, [r["name"] for r in langs],
          [("downloaded", [r["harvested"] for r in langs], "neutral"),     # from: corpus.by_language[].harvested
           ("usable", [r["usable"] for r in langs], "accent")],            # from: corpus.by_language[].usable
          number_format="#,##0", gap=45)
swatch_key(s, 9.25, BODY_Y, [("downloaded", "neutral"), ("usable after the quality check", "accent")])
text(s, 9.25, BODY_Y + 1.0, 3.35, 3.6, [
    (f"{pct(C['usable_share'])} of all books are usable.", S(size="lead")),                         # from: corpus.usable_share
    (f"{worst['name']} keeps only {pct(worst['usable'] / worst['harvested'], 0)}: "                  # from: corpus.by_language
     f"{why_worst}.", S(size="body", color="muted", space=14)),
    ("OCR: the software that turns a page image into text.", S(size="body", color="muted", space=14)),
])

# ==============================================================================
# 4. SCAN QUALITY
# ==============================================================================
conf = sorted(C["by_language"], key=lambda r: -r["median_conf"])          # from: corpus.by_language[].median_conf
low2 = conf[-2:]
s = new_slide(f"{low2[1]['name']} and {low2[0]['name']} scans are the hardest to read", f"""
This chart shows how sure the OCR is of the words it reads, from 0 to 100, for the middle book in each language.

{conf[0]['name']} reads best, at {conf[0]['median_conf']:.1f}. {low2[1]['name']} is lowest at {low2[1]['median_conf']:.1f}, then {low2[0]['name']} at {low2[0]['median_conf']:.1f}.

Why it matters: a badly read book gives the computer fewer real words, so it is harder to place. That is why the app warns when a page is poorly read instead of guessing silently.
""", source="reports/deliverable_facts.json: corpus.by_language[].median_conf")
bar_chart(s, MARGIN - 0.1, BODY_Y - 0.15, 8.6, 4.9, [r["name"] for r in conf],
          [("median OCR confidence", [r["median_conf"] for r in conf],         # from: corpus.by_language[].median_conf
            ["neutral"] * (len(conf) - 2) + ["accent", "accent"])],
          number_format="0.0", gap=55, max_scale=100)
text(s, 9.25, BODY_Y, 3.35, 4.0, [
    ("OCR confidence is the reader's own score for how sure it is of each word, from 0 to 100.", S(size="lead")),
    ("Each bar is the middle book of its language.", S(size="body", color="muted", space=14)),
    ("Poorly read pages get a warning in the app.", S(size="body", color="muted", space=14)),
])

# ==============================================================================
# 5. HOW IT WORKS
# ==============================================================================
s = new_slide("Five steps from a scanned page to a subject group", f"""
Here is the whole method in five steps.

One, read: OCR turns each page into text.

Two, embed: an embedding is a list of numbers that stands for the meaning of a text, so books on similar topics get similar numbers. We use {F['encoder']['name']}, which reads all our languages.

Three, centre: we subtract each language's average list of numbers. {"Without this, the strongest signal is the language itself, not the subject; the next slide shows the measurement. This is our key step." if CENTRING_HELPS else "We do this so that language does not dominate; the next slide shows what it changed."}

Four, group: hierarchical clustering joins the closest books step by step into a tree, and we cut the tree into groups. We also run DBSCAN, which looks for crowded regions.

Five, check: we test the groups on books we kept aside, and compare with simple guesses.
""", source="method as built in pipeline/; model name from reports/deliverable_facts.json: encoder.name")
steps = [("Read", "OCR turns each page image into text."),
         ("Embed", "A model turns the text into numbers; similar topics get similar numbers."),
         ("Centre", "Subtract each language's average, so language stops leading."),
         ("Group", "Join the closest books into a tree, then cut it into groups."),
         ("Check", "Test on books kept aside, against simple guesses.")]
col_w = (SLIDE_W - 2 * MARGIN - 4 * GAP) / 5
for i, (head, body) in enumerate(steps):
    x = MARGIN + i * (col_w + GAP)
    key = head == "Centre"
    text(s, x, BODY_Y + 0.3, col_w, 0.8, [(str(i + 1), S(font="head", size="step", color="accent" if key else "neutral"))])
    hline(s, x, BODY_Y + 1.25, col_w, "accent" if key else "ink", 2.0 if key else 1.0)
    text(s, x, BODY_Y + 1.45, col_w, 0.5, [(head, S(font="head", size="lead", bold=False))])
    text(s, x, BODY_Y + 2.05, col_w, 2.0, [(body, S(size="body", color="muted"))])
text(s, MARGIN, BODY_Y + 3.75, 11.5, 0.6,
     [(f"Embedding model: {F['encoder']['name']}." +                                                # from: encoder.name
       (" Centring is the step that changes the result." if CENTRING_HELPS else ""),
       S(size="body"))])


# ==============================================================================
# 6. LANGUAGE FIRST
# ==============================================================================
word_groups = [v for k, v in sorted(NAMES["A_hier"].items(), key=lambda kv: int(kv[0]))]  # from: reports/cluster_names.json:A_hier
word_groups_by_language = all(v.endswith("books") or "(" in v for v in word_groups)
if CE:
    un, ce = CE["uncentred"], CE["centred"]                     # from: deliverable_facts.json:centring_effect
    language_first = un["knn10_same_script"] > 0.5
    title6 = ("Left as they are, books group by language first" if language_first else
              "Even left as they are, books do not group mainly by language")
    notes6 = f"""
This is our main finding.

We take the {n(CE['train_books'])} training books and group them twice with the same model, {F['encoder']['name']}: once with the numbers as the model gives them, and once after subtracting each language's average.

The top chart uses NMI, a score of how much the groups follow language: 0 means not at all, 1 means each group is exactly one language. As the model gives them, NMI is {f2(un['nmi_script'])}; after centring it is {f2(ce['nmi_script'])}. {"So centring takes language out of the groups." if CENTRING_HELPS else "So centring did not lower it."}

The bottom chart asks a simpler question: of each book's 10 closest books, how many are written in the same script? As given, {pct(un['knn10_same_script'], 0)}. After centring, {pct(ce['knn10_same_script'], 0)}. {"Left alone, a book's neighbours are mostly books in its own language, whatever the subject." if language_first else "Even before centring, most neighbours are in other scripts."}

{"On the left, for comparison: an earlier study that grouped books by counting words found one group per language." if word_groups_by_language else ""}
"""
    source6 = "reports/deliverable_facts.json: centring_effect.uncentred, centring_effect.centred; reports/cluster_names.json: A_hier"
else:
    title6 = "Counting words, books group by language first"
    notes6 = f"""
When we grouped books by counting their words, in an earlier study, the groups followed language. NMI, a score of how much groups follow language (0 none, 1 fully), is {f2(H['nmi_script'])} for the final groups.
"""
    source6 = "reports/cluster_names.json: A_hier; reports/deliverable_facts.json: hierarchical.nmi_script"
s = new_slide(title6, notes6, source=source6)
text(s, MARGIN, BODY_Y, 3.6, 0.5, [("Groups from counting words, earlier study", S(size="body", bold=True))])
text(s, MARGIN, BODY_Y + 0.75, 3.6, 3.6, [(g, S(size="body", color="muted", space=4)) for g in word_groups])
if CE:
    for j, (label, key, fmt) in enumerate((("How much the groups follow language (NMI: 0 none, 1 fully)", "nmi_script", "0.00"),
                                           ("Share of a book's 10 closest books in the same script", "knn10_same_script", "0%"))):
        y = BODY_Y + j * 2.35
        text(s, 4.75, y, 7.8, 0.4, [(label, S(size="body", bold=True))])
        bar_chart(s, 4.65, y + 0.4, 7.95, 1.75, ["as the model gives them", "after centring"],
                  [(key, [un[key], ce[key]], ["neutral", "accent"])],    # from: centring_effect.uncentred/centred.<key>
                  number_format=fmt, gap=40, max_scale=1.15)      # headroom so a label near 1 is not clipped
else:
    text(s, 4.75, BODY_Y, 7.8, 0.5, [("How much the final groups follow language (NMI: 0 none, 1 fully)", S(size="body", bold=True))])
    bar_chart(s, 4.65, BODY_Y + 0.45, 7.95, 1.6, [f"{F['encoder']['name']}, centred"],
              [("NMI", [H["nmi_script"]], ["accent"])], number_format="0.00", gap=50, max_scale=1)  # from: hierarchical.nmi_script

# ==============================================================================
# 7. CENTRING HELPS SUBJECT
# ==============================================================================
enc = ENCODERS["encoders"]
enc_rows = sorted(enc.values(), key=lambda e: -e["knn_centred"])     # from: reports/study/encoder_comparison.json:encoders
better = sum(e["knn_centred"] > e["knn_plain"] for e in enc_rows)
claim = "every model" if better == len(enc_rows) else f"{better} of {len(enc_rows)} models" if better else "none of the models"
final_in_test = F["encoder"]["feature_set"] in enc
s = new_slide(f"Removing each language's average helps {claim} find subjects", f"""
Does centring help with subject, not just with language? We checked it on {len(enc_rows)} embedding models, in a separate comparison on labelled books.

The test is simple: guess a book's subject from the books closest to it. If close books share a subject, the guess is right more often.

Grey is the model as it comes. Red is after we subtract each language's average. For {claim}, red is longer{": once language is removed, a book's neighbours are more often on the same subject" if better else ""}.

{"" if final_in_test else "One honest note: " + F['encoder']['name'] + ", the model behind our final groups, was not part of this comparison."}
""", source="reports/study/encoder_comparison.json: encoders[].knn_plain, encoders[].knn_centred (labelled train and validation books)")
bar_chart(s, MARGIN - 0.1, BODY_Y - 0.15, 8.6, 4.9, [e["name"].replace(" embeddings", "") for e in enc_rows],
          [("as the model gives them", [e["knn_plain"] for e in enc_rows], "neutral"),    # from: encoders[].knn_plain
           ("after centring", [e["knn_centred"] for e in enc_rows], "accent")],           # from: encoders[].knn_centred
          number_format="0%", gap=45, max_scale=1)
swatch_key(s, 9.25, BODY_Y, [("as the model gives them", "neutral"), ("after centring", "accent")])
text(s, 9.25, BODY_Y + 1.0, 3.35, 3.6, [
    ("Each bar: how often the closest books guess a book's subject right.", S(size="lead"))] +
    ([] if final_in_test else
     [(f"{F['encoder']['name']}, used for the final groups, was not in this test.", S(size="body", color="muted", space=14))]))

# ==============================================================================
# 8. THE GROUPS
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
shared = [subj for subj, c in subject_count.items() if c > 1]
s = new_slide(f"{len(groups)} broad groups, each mixing {'all ' + str(len(lang_codes)) if all_mixed else 'many'} languages", f"""
These are the groups the model found on all {n(usable)} usable books, using {H['linkage']} linkage cut into {H['k']} groups.

Each row is a group. The columns show what share of the group comes from each language: the darker the cell, the bigger the share. No language holds more than {pct(top_share, 0)} of any group{", so the groups are not language piles" if top_share < 0.5 else ", so one language still dominates at least one group"}.

The subject column is the most common subject among the hand-labelled training books in that group. We did not name the groups by hand. Reading the column: {lean}.

{("Because " + " and ".join(shared) + " leads more than one group, the groups split a subject by something else in the vocabulary. ") if shared else "Each group leads with a different subject. "}These are broad shelves, not a catalogue.
""", source="reports/deliverable_facts.json: groups[].books, groups[].majority_subject, groups[].languages")
max_cell = max(max(g["languages"].values()) for g in groups)
head = [("Group", S(bold=True)), ("Books", S(bold=True, align=PP_ALIGN.RIGHT)), ("Most common subject", S(bold=True))] + \
       [(LANG[l], S(bold=True, align=PP_ALIGN.RIGHT)) for l in lang_codes]
rows = [head]
for g in groups:
    rows.append([(f"Group {g['group'] + 1}", S()),                                      # from: groups[].group
                 (n(g["books"]), S(align=PP_ALIGN.RIGHT)),                              # from: groups[].books
                 (g["majority_subject"] or "no labelled books", S())] +                 # from: groups[].majority_subject
                [(pct(g["languages"].get(l, 0), 0), S(align=PP_ALIGN.RIGHT),            # from: groups[].languages
                  mix("paper", "accent_soft", g["languages"].get(l, 0) / max_cell)) for l in lang_codes])
plain_table(s, MARGIN, BODY_Y + 0.1, SLIDE_W - 2 * MARGIN, rows,
            [1.0, 0.85, 2.45] + [(SLIDE_W - 2 * MARGIN - 4.3) / len(lang_codes)] * len(lang_codes), row_h=0.62)
text(s, MARGIN, BODY_Y + 2.9, 11.8, 1.6, [
    (f"No language holds more than {pct(top_share, 0)} of any group.", S(size="lead")),       # from: groups[].top_language_share
    ("Shares of each group's books by language; darker means a bigger share. "
     "The subject is the most common one among the labelled training books in the group.", S(size="body", color="muted", space=10)),
])

# ==============================================================================
# 9. HOW GOOD
# ==============================================================================
t2_target = TEST["targets"]["T2_points_above_baseline"]                  # from: evaluation.test.targets
ci = TEST.get("t2_accuracy_ci95")                                         # from: evaluation.test.t2_accuracy_ci95
pci = TEST.get("t2_points_ci95")                                          # from: evaluation.test.t2_points_ci95
gain_t, gain_v = TEST["t2_points"], VAL["t2_points"]                      # from: evaluation.test/val.t2_points
significant = TEST["t2_p"] is not None and TEST["t2_p"] < 0.05
best_name = "guessing from the script alone" if TEST["t2_baseline_script"] >= TEST["t2_baseline_common"] else \
    "always guessing the most common subject"
title9 = (f"The groups guess subject {pts(gain_t)} points better than the best simple guess" if gain_t >= 0 else
          "The groups guess subject worse than the best simple guess")
verdict = (f"Our target, written before the results, was {gain(t2_target)} points, so on the test books we "
           f"{'met it' if MET['T2'] else 'did not meet it'}.")
range_note = ""
if pci:
    below = pci[0] < t2_target <= pci[1]
    range_note = (f" The likely range of the gain is {gain(pci[0])} to {gain(pci[1])} points"
                  + (", so it reaches below the target as well as above it." if below and MET["T2"] else
                     ", so it may still reach the target." if below else "."))
val_note = (f" On the validation books the gain was {gain(gain_v)} points, which "
            f"{'also meets' if VAL['met']['T2'] else 'does not meet'} the target.")
p_note = (f"Shuffling the subject labels at random almost never gives a gain this big: p = {TEST['t2_p']:.4f}, so it is not luck."
          if significant else
          f"Shuffling the subject labels at random often gives a gain this big (p = {TEST['t2_p']:.4f}), so it may be luck.")
cat_note = ""
if CAT.get("points_above_best_baseline") is not None:
    cat_gain = CAT["points_above_best_baseline"]
    cat_subjects = sorted(set(CAT.get("group_to_subject", {}).values()))
    cat_note = (f"\n\nA second, exploratory check uses the librarians' own classes instead of our labels. There the groups score "
                f"{gain(cat_gain)} points against the best simple guess, so they do {'better' if cat_gain > 0 else 'worse'} than it"
                + (f"; every group maps to the same class, {cat_subjects[0]}." if len(cat_subjects) == 1 else "."))
s = new_slide(title9, f"""
How good are the groups? We kept some books aside and never used them to build the groups. For {n(TEST['t2_labelled_heldout'])} of these test books we have a subject label.

Each group predicts its most common subject. That is right {pct(TEST['t2_accuracy'])} of the time{f", with a likely range of {pct(ci[0])} to {pct(ci[1])}" if ci else ""}.

Compare with simple guesses. Guessing from the script alone is right {pct(TEST['t2_baseline_script'])} of the time. Always guessing the most common subject is right {pct(TEST['t2_baseline_common'])}. The best of these is {best_name}.

So the groups {"beat" if gain_t > 0 else "fall short of"} the best simple guess by {pts(abs(gain_t)) if gain_t > 0 else gain(gain_t)} points. {verdict}{range_note}{val_note}

{p_note}{cat_note}
{"" if ci else "This run's result file does not hold a confidence interval for the accuracy, so we do not show one."}
""", source="reports/deliverable_facts.json: evaluation.test.t2_accuracy, t2_baseline_script, t2_baseline_common, t2_points, t2_p, targets, met")
bar_chart(s, MARGIN - 0.1, BODY_Y - 0.15, 8.6, 4.4,
          ["Our groups", "Guess from the script alone", "Always the most common subject"],
          [("test books", [TEST["t2_accuracy"], TEST["t2_baseline_script"], TEST["t2_baseline_common"]],  # from: evaluation.test.t2_*
            ["accent", "neutral", "neutral"])], number_format="0.0%", gap=55, max_scale=1)
text(s, 9.25, BODY_Y, 3.35, 4.6, [
    (f"{n(TEST['t2_labelled_heldout'])} labelled books, kept aside until the end.", S(size="lead")),  # from: evaluation.test.t2_labelled_heldout
    (f"Target: {gain(t2_target)} points. Got {gain(gain_t)}: {met_word(MET['T2'])}.",                   # from: targets, t2_points, met.T2
     S(size="body", space=14)),
] + ([(f"Likely range {gain(pci[0])} to {gain(pci[1])} points.", S(size="body", color="muted", space=8))] if pci else []) + [
    (f"Validation books: {gain(gain_v)} points, {met_word(VAL['met']['T2'])}.", S(size="body", color="muted", space=8)),  # from: evaluation.val
    (f"Random shuffles of the labels: p = {TEST['t2_p']:.4f}.", S(size="body", color="muted", space=8)),      # from: evaluation.test.t2_p
])

# ==============================================================================
# 10. STABILITY
# ==============================================================================
hb, dbb = H["bootstrap"], DB["bootstrap"]                   # from: hierarchical.bootstrap, dbscan.bootstrap
t3_target = TEST["targets"]["T3_bootstrap_ari"]             # from: evaluation.test.targets.T3_bootstrap_ari
stable = hb["median"] >= t3_target
db_steadier = dbb["median"] > hb["median"]
s = new_slide("The groups hold when we re-run on other books" if stable else
              "The groups change when we re-run on other books", f"""
A good grouping should not change much if we start from a slightly different set of books. So we re-ran the grouping {len(hb['values'])} times, each time on a random part of the books, and compared each result with the full grouping of all usable books.

We compare groupings with ARI, a score of how much two groupings agree: 1 means identical, 0 means no better than chance.

Each red dot is one re-run of our hierarchical groups. The middle value is {f2(hb['median'])}, and most runs fall between {f2(hb['p10'])} and {f2(hb['p90'])}. Our target was {t3_target}. {'We met it.' if stable else 'We did not meet it: the groups are broad and partly shift.'}

The grey dots are DBSCAN, which looks for crowded regions of books. It is {'steadier' if db_steadier else 'less steady'}, around {f2(dbb['median'])}, and it calls {pct(DB['noise_share'])} of the books noise, meaning they sit in no crowded region. It finds {DB['n_clusters']} clusters. So we use the hierarchical groups as the shelves, because they cover every book, and show DBSCAN's verdict beside them.
""", source="reports/deliverable_facts.json: hierarchical.bootstrap.values, dbscan.bootstrap.values, dbscan.noise_share, evaluation.test.targets")
cd = XyChartData()
for name, vals in (("DBSCAN", dbb["values"]), ("Hierarchical groups", hb["values"])):   # from: dbscan.bootstrap.values, hierarchical.bootstrap.values
    ser = cd.add_series(name)
    for i, v in enumerate(vals, 1):
        ser.add_data_point(i, v)
tser = cd.add_series("target")
tser.add_data_point(1, t3_target)                           # from: evaluation.test.targets.T3_bootstrap_ari
tser.add_data_point(len(hb["values"]), t3_target)
gf = s.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, Inches(MARGIN - 0.1), Inches(BODY_Y - 0.1), Inches(8.6), Inches(4.7), cd)
ch = gf.chart
style_chart(ch, number_format="0.0", labels=False, value_axis=True, max_scale=1)
ch.category_axis.tick_labels.font.color.rgb = rgb("muted")
ch.category_axis.minimum_scale = 0
ch.category_axis.maximum_scale = len(hb["values"]) + 1
ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
for ser, color in zip(ch.series, ("neutral", "accent", "muted")):
    if color == "muted":
        ser.marker.style = XL_MARKER_STYLE.NONE
        ser.format.line.color.rgb = rgb("muted")
        ser.format.line.width = Pt(1.25)
    else:
        ser.format.line.fill.background()
        ser.marker.style = XL_MARKER_STYLE.CIRCLE
        ser.marker.size = 9
        ser.marker.format.fill.solid()
        ser.marker.format.fill.fore_color.rgb = rgb(color)
        ser.marker.format.line.fill.background()
swatch_key(s, 9.25, BODY_Y, [("hierarchical, one dot per re-run", "accent"), ("DBSCAN", "neutral"),
                             (f"target {t3_target}", "muted")])                                     # from: evaluation.test.targets
text(s, 9.25, BODY_Y + 1.35, 3.35, 3.4, [
    (f"Hierarchical: middle value {f2(hb['median'])}, target {t3_target}.", S(size="lead")),       # from: hierarchical.bootstrap.median
    ("ARI: how much two groupings agree, 1 identical, 0 chance.", S(size="body", color="muted", space=14)),
    (f"DBSCAN is {'steadier' if db_steadier else 'less steady'} and calls {pct(DB['noise_share'])} of books noise: "  # from: dbscan.noise_share
     "in no crowded region.", S(size="body", color="muted", space=10)),
])

# ==============================================================================
# 11. CATALOGUE CLASS SUGGESTION (recorded app output)
# ==============================================================================
doc, sug = fixture(f"get_documents__{EXAMPLE_BOOK}"), fixture(f"get_suggest__{EXAMPLE_BOOK}")
if SUG:                                                    # from: reports/features/suggest.json
    sug_beats = SUG["top1"] > SUG["baseline_most_common"]
    sug_line = (f"On {n(SUG['heldout_books'])} held-out books with a class, the top suggestion is right "
                f"{pct(SUG['top1'])} of the time (likely range {pct(SUG['top1_ci95'][0])} to {pct(SUG['top1_ci95'][1])}), "
                f"against {pct(SUG['baseline_most_common'])} for always the most common class.")
    sug_notes = (sug_line + f" So the suggestion does {'better' if sug_beats else 'no better'} than that simple guess. "
                 f"The right class is among the first three suggestions {pct(SUG['top3'])} of the time; we have no simple "
                 "guess to compare that with.")
else:
    sug_line = "Its accuracy on held-out books is not measured yet."
    sug_notes = "We have not yet measured how often the top suggestion is right on books kept aside, so we show no accuracy for it."
s = new_slide("For a book with no class, the tool suggests one", f"""
Now, what does an archivist get? This is a real answer from our app, recorded from the final model.

The book is {doc['title']}, a {doc['script']} book printed {doc['era'].replace('pre-', 'before ')}. It has no library class.

The tool looks at the nearest books that do have a class and lets them vote; closer books count more. The bars are each class's share of the vote. The top suggestion is {sug['suggestions'][0]['class']}, then {sug['suggestions'][1]['class']}.

{sug_notes}

It is a suggestion for the archivist to accept or reject, shown with its evidence.
""", source=f"web/fixtures/get_documents__{EXAMPLE_BOOK}.json, web/fixtures/get_suggest__{EXAMPLE_BOOK}.json (recorded app output)"
            + ("; reports/features/suggest.json" if SUG else ""))
rect(s, MARGIN, BODY_Y, 4.6, 3.2, "tint", name="Catalogue card")
text(s, MARGIN + 0.35, BODY_Y + 0.35, 3.9, 2.6, [
    (doc["title"], S(font="head", size="lead")),                                     # from: fixture documents.title
    (doc["creator"] or "", S(size="body", color="muted", space=6)),                  # from: fixture documents.creator
    (f"{doc['script']} script, printed {doc['era'].replace('pre-', 'before ')}", S(size="body", space=18)),  # from: fixture documents.script, era
    ("Library class", S(size="small", color="muted", space=18)),
    (doc["classification"] or "none", S(size="lead", space=2)),                       # from: fixture documents.classification
])
text(s, 5.85, BODY_Y, 6.7, 0.5, [("Suggested classes, share of the nearest classed books' vote", S(size="body", bold=True))])
bar_chart(s, 5.75, BODY_Y + 0.45, 6.85, 2.4, [x["class"] for x in sug["suggestions"]],
          [("vote share", [x["score"] for x in sug["suggestions"]],                    # from: fixture suggest.suggestions[].score
            ["accent"] + ["neutral"] * (len(sug["suggestions"]) - 1))], number_format="0%", gap=50, max_scale=1)
text(s, 5.85, BODY_Y + 3.0, 6.7, 1.6, [(sug_line, S(size="body", color="ink" if SUG else "muted")),   # from: reports/features/suggest.json
                                       ("A suggestion for the archivist to accept or reject.", S(size="body", color="muted", space=8))])

# ==============================================================================
# 12. RELATED BOOKS IN OTHER SCRIPTS (recorded app output)
# ==============================================================================
rel = fixture(f"get_related__{EXAMPLE_BOOK}")
shown = rel["neighbours"][:8]
other = sorted({x["script"] for x in shown})
rel_line, rel_more = "", False
if REL:                                                    # from: reports/features/related.json
    rs = REL["knn_other_script_share"]
    rel_more = rs["centred"] > rs["uncentred"]
    rel_line = (f"Of a book's {REL['k']} closest books, {pct(rs['centred'])} are in another script after centring, "
                f"against {pct(rs['uncentred'])} before.")
s = new_slide(f"One {doc['script']} book's closest neighbours come from {len(other)} other scripts", f"""
The second tool connects books across scripts, which a normal catalogue search cannot do.

We take the same {doc['script']} book and ask for its closest books written in other scripts. These are the first {len(shown)} answers, again recorded from the app. They come from {', '.join(other)} books.

{rel_line}{" So centring is what lets books meet across scripts." if rel_more else ""}

The model never saw a translation dictionary: these books are simply close to the starting book in the model's numbers. Whether each one is truly on the same subject is for the archivist to judge from the titles and links.
""", source=f"web/fixtures/get_related__{EXAMPLE_BOOK}.json (recorded app output)" + ("; reports/features/related.json" if REL else ""))
text(s, MARGIN, BODY_Y, 3.6, 4.6, [
    ("Starting book", S(size="small", color="muted")),
    (doc["title"], S(font="head", size="lead", space=4)),                              # from: fixture documents.title
    (f"{doc['script']} script", S(size="body", color="muted", space=4)),
    ("Its closest books in other scripts are on the right, closest first.", S(size="body", space=24)),
] + ([(rel_line, S(size="body", color="muted", space=14))] if REL else []))       # from: reports/features/related.json
rows = [[("Title", S(bold=True)), ("Script", S(bold=True))]]
for x in shown:                                                                         # from: fixture related.neighbours[]
    rows.append([(x["title"], S(font="indic")), (x["script"], S(color="muted"))])
plain_table(s, 4.85, BODY_Y, SLIDE_W - MARGIN - 4.85, rows, [5.6, SLIDE_W - MARGIN - 4.85 - 5.6], row_h=0.5)

# ==============================================================================
# 13. A NEW PAGE IS PLACED (recorded app output)
# ==============================================================================
chk = fixture(CHECK_FIXTURE)
t1_target = TEST["targets"]["T1_page_agreement"]           # from: evaluation.test.targets.T1_page_agreement
t1, t1_ci = TEST["t1_agreement"], TEST.get("t1_agreement_ci95")
t1_close = not MET["T1"] and t1_target - t1 < 0.02
t1_verdict = "Met." if MET["T1"] else ("Just short." if t1_close else "Not met.")
s = new_slide("A single new page lands in its book's group " + ("most of the time" if t1 > 0.5 else "less than half the time"), f"""
The third tool: an archivist scans one new page, and the app places it among the archive's books.

The number on the left is our test of exactly this. We took one page from each test book and checked whether it lands in the same group as its whole book. It does {pct(t1)} of the time{f", with a likely range of {pct(t1_ci[0])} to {pct(t1_ci[1])}" if t1_ci else ""}. A random guess would manage {pct(TEST['t1_chance'])}. Our target was {pct(t1_target, 0)}, so {"we met it" if MET['T1'] else "we are just short" if t1_close else "we did not meet it"}.

On the right is a real check of a {chk['script']} page. The app shows the closest archive books, with links, so the archivist can see why it decided. It also says when it is unsure: here DBSCAN says the page {'sits in a crowded region' if chk['dbscan']['in_dense_group'] else 'is not in any crowded region'}, and the app shows that too. When a page has too few readable words, it refuses to guess.
""", source=f"reports/deliverable_facts.json: evaluation.test.t1_agreement, t1_chance; web/fixtures/{CHECK_FIXTURE}.json")
text(s, MARGIN, BODY_Y, 4.4, 1.4, [(pct(t1), S(font="head", size="stat", color="accent"))],  # from: evaluation.test.t1_agreement
     anchor=MSO_ANCHOR.BOTTOM)
text(s, MARGIN, BODY_Y + 1.5, 4.2, 2.6, [
    ("of single test pages land in their own book's group.", S(size="lead")),
    (f"Random guess: {pct(TEST['t1_chance'])}. Target: {pct(t1_target, 0)}. {t1_verdict}",           # from: evaluation.test.t1_chance, targets, met.T1
     S(size="body", color="muted", space=14)),
])
text(s, 5.6, BODY_Y, 7.0, 0.5, [(f"A {chk['script']} page, checked: the closest archive books", S(size="body", bold=True))])
rows = [[("Title", S(bold=True)), ("Printed", S(bold=True, align=PP_ALIGN.RIGHT))]]
for m in chk["matches"]:                                                                # from: fixture check.matches[]
    rows.append([(m["title"], S(font="indic")), (m.get("era") or "undated", S(color="muted", align=PP_ALIGN.RIGHT))])
plain_table(s, 5.6, BODY_Y + 0.5, SLIDE_W - MARGIN - 5.6, rows, [5.7, SLIDE_W - MARGIN - 5.6 - 5.7], row_h=0.48)
text(s, 5.6, BODY_Y + 3.6, 7.0, 0.8, [
    ("In a crowded region (DBSCAN): " + ("yes" if chk["dbscan"]["in_dense_group"] else "no, so treat the group with care"),  # from: fixture check.dbscan
     S(size="body", color="muted"))])

# ==============================================================================
# 14. THE ARCHIVE MAP (the site's map data, first two directions)
# ==============================================================================
GALAXY = load("web/data/galaxy.json") if (ROOT / "web/data/galaxy.json").exists() else None
UMAP_BUILT = (ROOT / "web/data/galaxy_umap.json").exists()      # the site's third map view, shown only when built
if GALAXY:
    tags = [b["lang_tag"] for b in GALAXY["books"]]             # from: web/data/galaxy.json:books[].lang_tag

    def apartness(view: str) -> dict:
        """Per language: how far its books' middle sits from the middle of all books, in units of the overall spread."""
        pts_ = GALAXY["views"][view]                            # from: web/data/galaxy.json:views.<view>
        cx, cy = sum(p[0] for p in pts_) / len(pts_), sum(p[1] for p in pts_) / len(pts_)
        spread = (sum((p[0] - cx) ** 2 + (p[1] - cy) ** 2 for p in pts_) / len(pts_)) ** 0.5
        out = {}
        for lang_ in set(tags):
            own = [p for p, t in zip(pts_, tags) if t == lang_]
            lx, ly = sum(p[0] for p in own) / len(own), sum(p[1] for p in own) / len(own)
            out[lang_] = ((lx - cx) ** 2 + (ly - cy) ** 2) ** 0.5 / spread
        return out

    apart_un, apart_ce = apartness("uncentred"), apartness("centred")
    star = max(apart_un, key=apart_un.get)                      # the language that sits furthest apart as given
    star_name = LANG.get(star, star)
    mixes_in = apart_ce[star] < 0.5 * apart_un[star]
    step = max(1, len(tags) // 1500)                            # a light, even sample keeps the chart quick to open
    s = new_slide(f"On the archive map, {star_name} books sit apart until centring mixes them in" if mixes_in else
                  "The archive map shows every book as a dot, before and after centring", f"""
This is the picture behind our main finding, and it is a page of the site: the archive map.

Each dot is one book, placed by the numbers the model gives its text, flattened to the two directions that spread the books most. The red dots are {star_name} books; the grey dots are every other language.

On the left, the numbers as the model gives them. {f"The {star_name} books sit in their own corner: the map is a map of languages." if mixes_in else f"The {star_name} books already overlap the others."} On the right, after we subtract each language's average. {"The same books now sit among the others, so a book's neighbours can come from any script." if mixes_in else "The picture changes little."}

The slide shows a sample of the {n(usable)} books in two dimensions. On the site the map is in 3-D with every book: you can turn it, colour the dots by language or by group, light up one language, and open sample books from the map.{" A third view places books by their closest neighbours." if UMAP_BUILT else ""}

One caution: a flat picture loses most of the detail, so we use the map to explain, and the measurements on the earlier slides to prove.
""", source="web/data/galaxy.json: views.uncentred, views.centred, books[].lang_tag (first two directions; an even sample of books)")
    for j, (view, label) in enumerate((("uncentred", "As the model gives them"), ("centred", "After centring"))):
        x = MARGIN + j * 4.25
        text(s, x, BODY_Y, 4.0, 0.4, [(label, S(size="body", bold=True))])
        cd = XyChartData()
        pts_ = GALAXY["views"][view]
        for name, keep in (("other languages", lambda t: t != star), (star_name, lambda t: t == star)):
            ser = cd.add_series(name)
            for p, t in list(zip(pts_, tags))[::step]:          # from: web/data/galaxy.json:views.<view>[][0..1]
                if keep(t):
                    ser.add_data_point(p[0], p[1])
        gf = s.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, Inches(x - 0.1), Inches(BODY_Y + 0.4), Inches(4.1), Inches(4.3), cd)
        ch = gf.chart
        style_chart(ch, labels=False)
        ch.value_axis.minimum_scale = None
        ch.value_axis.format.line.fill.background()
        ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
        ch.category_axis.format.line.fill.background()
        for ser, color in zip(ch.series, ("neutral", "accent")):
            ser.format.line.fill.background()
            ser.marker.style = XL_MARKER_STYLE.CIRCLE
            ser.marker.size = 3
            ser.marker.format.fill.solid()
            ser.marker.format.fill.fore_color.rgb = rgb(color)
            ser.marker.format.line.fill.background()
    swatch_key(s, 9.25, BODY_Y, [(f"{star_name} books", "accent"), ("books in every other language", "neutral")])
    text(s, 9.25, BODY_Y + 1.0, 3.35, 3.7, [
        ("Each dot is one book, placed by what its text says.", S(size="lead")),
        (f"A sample of the {n(usable)} usable books, flattened to two directions.",        # from: corpus.usable
         S(size="body", color="muted", space=14)),
        ("On the site the map is 3-D: turn it, colour by language or by group, and open sample books.",
         S(size="body", color="muted", space=10)),
    ])

# ==============================================================================
# 15. SCAN QUALITY PAGE (recorded app output; score evaluation when present)
# ==============================================================================
tri_fix = fixture("get_api_triage__limit-50")
tri_chance = bool(TRI) and TRI["auc_ci95"][0] <= 0.5 <= TRI["auc_ci95"][1]
tri_langs = sorted(tri_fix["by_language"].items(), key=lambda kv: -(kv[1]["re-scan"] + kv[1]["re-ocr"]))  # from: fixture triage.by_language
tri_top = LANG.get(tri_langs[0][0], tri_langs[0][0])
if TRI:                                                    # from: reports/features/triage.json
    th = TRI["rule_thresholds"]
    tri_rule = (f"A book is flagged when its OCR confidence is under {th['min_conf']:.0f}, when it has fewer than "
                f"{th['min_tokens']} readable words, or when it sits in no crowded region.")
    tri_line = (f"Checked on {n(TRI['books'])} books against the archive's own OCR: AUC {TRI['auc']:.2f} "
                f"(likely range {TRI['auc_ci95'][0]:.2f} to {TRI['auc_ci95'][1]:.2f}), where 0.5 is chance.")
    tri_notes = (tri_rule + f"\n\nDoes the score work? We tested it on {n(TRI['books'])} books where we can compare our OCR with "
                 f"the archive's own. AUC is a score of how well it separates good scans from bad: 1 is perfect, 0.5 is a coin "
                 f"toss. Ours is {TRI['auc']:.2f}, with a likely range of {TRI['auc_ci95'][0]:.2f} to {TRI['auc_ci95'][1]:.2f}, "
                 + ("so it is no better than chance. We show the page as a work list built from plain rules, not as a proven predictor."
                    if tri_chance else "so it does better than chance."))
else:
    tri_rule = "A book is flagged when its OCR confidence is low, when it has few readable words, or when it sits in no crowded region."
    tri_line = "How well the score predicts a bad scan is not measured yet."
    tri_notes = tri_rule + "\n\nWe have not yet measured how well the score predicts a bad scan, so we show no accuracy for it."
s = new_slide("The scan quality page lists books to scan again, but its score is not proven" if tri_chance or not TRI else
              "The scan quality page lists the books worth scanning again", f"""
The archive also needs to know which scans to redo. The scan quality page gives every downloaded book one of three verdicts: fine, read again with OCR, or scan again.

The chart counts the flagged books in each language, taken from the app. Red is scan again: our OCR was unsure and the archive has no text of its own. Grey is read again: the book has too few readable words. {tri_top} has the most flagged books.

{tri_notes}
""", source="web/fixtures/get_api_triage__limit-50.json: by_language (recorded app output)" + ("; reports/features/triage.json" if TRI else ""))
bar_chart(s, MARGIN - 0.1, BODY_Y - 0.15, 8.6, 4.9, [LANG.get(k, k) for k, _ in tri_langs],
          [("scan again", [v["re-scan"] for _, v in tri_langs], "accent"),          # from: fixture triage.by_language[].re-scan
           ("read again", [v["re-ocr"] for _, v in tri_langs], "neutral")],        # from: fixture triage.by_language[].re-ocr
          number_format="#,##0", gap=45)
swatch_key(s, 9.25, BODY_Y, [("scan again", "accent"), ("read again with OCR", "neutral")])
text(s, 9.25, BODY_Y + 1.0, 3.35, 3.8, [
    ("Three verdicts: fine, read again, scan again.", S(size="lead")),
    (tri_rule, S(size="small", color="muted", space=14)),
    (tri_line, S(size="body", color="ink" if TRI else "muted", space=10)),
])

# ==============================================================================
# 16. EDITION FINDER (evaluation; shown without numbers when absent)
# ==============================================================================
ed_recorded = [fixture(p.stem) for p in sorted((ROOT / "web" / "fixtures").glob("get_editions__*.json"))]
ed_found = sum(bool(e["candidates"]) for e in ed_recorded)          # from: web/fixtures/get_editions__*.json:candidates
ed_how = ("Two books count as editions of one work when they share a title and an author, after spelling is evened out. "
          "The finder proposes the books that sit closer to a book than a set distance.")
if EDI:                                                    # from: reports/features/editions.json
    ed_p, ed_r, ed_rci = EDI["precision"], EDI["recall"], EDI["recall_ci95"]
    ed_exact, ed_misses = ed_p >= 0.995, ed_r < 0.5
    title16 = ((f"The edition finder is right when it answers, but finds {pct(ed_r, 0)} of known editions" if ed_exact else
                f"The edition finder finds {pct(ed_r, 0)} of known editions") if ed_misses else
               "The edition finder finds most known editions")
    ed_notes = f"""
Precision asks: of the pairs the finder reported, how many were true editions? {pct(ed_p)}{", so it raised no false alarm" if ed_exact else ""}. Recall asks: of the true editions, how many did it find? {pct(ed_r)}, with a likely range of {pct(ed_rci[0])} to {pct(ed_rci[1])}.

That range is wide because the test is small: only {EDI['groups_heldout']} groups of known editions among the test books. So we call this tool {"careful but incomplete" if ed_exact and ed_misses else "promising"}, and too little tested to trust yet.
"""
else:
    title16 = "The edition finder looks for other printings of the same book"
    ed_notes = "\nWe have not yet measured how many editions it finds on books kept aside, so we show no accuracy for it.\n"
s = new_slide(title16, f"""
The last tool looks for other editions of the same book, so an archive does not catalogue or preserve the same work twice without knowing.

{ed_how}
{ed_notes}
{"One more honest note: none of the example books we recorded from the app has another edition in our sample, so we show the measurement and no worked example." if not ed_found else ""}
""", source="reports/features/editions.json: precision, recall, recall_ci95, groups_heldout" if EDI else "method as built in pipeline/")
if EDI:
    bar_chart(s, MARGIN - 0.1, BODY_Y - 0.15, 8.6, 3.0, ["Reported pairs that are true editions (precision)",
                                                       "True editions it found (recall)"],
              [("test books", [ed_p, ed_r], ["neutral", "accent"])],          # from: reports/features/editions.json:precision, recall
              number_format="0.0%", gap=55, max_scale=1.3)
    text(s, MARGIN, BODY_Y + 3.1, 8.2, 1.5, [(ed_how, S(size="body", color="muted"))])
    text(s, 9.25, BODY_Y, 3.35, 4.7, [
        (f"Tested on {EDI['groups_heldout']} groups of known editions among the test books.", S(size="lead")),  # from: editions.groups_heldout
        (f"Recall {pct(ed_r)}, likely range {pct(ed_rci[0])} to {pct(ed_rci[1])}.", S(size="body", space=14)),  # from: editions.recall, recall_ci95
        ("Too few groups to trust yet.", S(size="body", color="muted", space=8)),
    ])
else:
    text(s, MARGIN, BODY_Y, 8.2, 2.0, [(ed_how, S(size="lead")),
                                       ("Its accuracy on held-out books is not measured yet.", S(size="body", color="muted", space=14))])

# ==============================================================================
# 17. THE SITE
# ==============================================================================
site_pages = [("Check a page", "Upload a scan or paste text: its group, closest books, catalogue card."),
              ("Browse groups", "The books in each group, with their languages."),
              ("Archive map", "Every book as a dot in 3-D, coloured by language or by group."),
              ("Scan quality", "Books to read again or scan again, language by language."),
              ("Editions", "Other editions of a chosen book."),
              ("Impact", "Three archive problems, each with its measured result."),
              ("The study", "Every result with its method, a presenter mode, a PDF guide.")]
s = new_slide(f"One site puts every tool in an archivist's hands, in {len(site_pages)} pages", f"""
Everything you have seen runs in one web app. These are its pages.

Check a page is the working desk: upload a scan or paste text, and it returns the group, the closest archive books and a catalogue card for the page. Browse groups lists each group's books. The archive map, scan quality and editions pages are the three tools from the last slides.

Two pages explain rather than do. Impact tells the story as three archive problems, books split by script, loose pages, and the cataloguing backlog, each beside its measured result. The study page shows every result with its method, has a presenter mode, and offers a guide for repeating the study as a PDF.

The site was redesigned for reading: a lighter, paper-like look with a dark mode one click away, and shorter navigation. Behind the pages is an API that gives the same answers to other software, including a check for a whole list of books at once.
""", source="web/*.html (the pages as built); app/ (the API behind them)")
rows = [[("Page", S(bold=True)), ("What it gives the archivist", S(bold=True))]] + \
       [[(page, S()), (what, S(color="muted"))] for page, what in site_pages]
plain_table(s, MARGIN, BODY_Y, 8.2, rows, [1.9, 6.3], row_h=0.5)
text(s, 9.25, BODY_Y, 3.35, 4.7, [
    ("One web app, in a light or a dark theme.", S(size="lead")),
    ("Its results panel reads the same facts file as this deck.", S(size="body", color="muted", space=14)),
    ("An API gives the same answers to other software, with a batch check for a list of books.",
     S(size="body", color="muted", space=10)),
])

# ==============================================================================
# 18. IMPACT (the three stories of the site's impact page, each with its measured number)
# ==============================================================================
if REL and SUG:
    rs = REL["knn_other_script_share"]                     # from: reports/features/related.json:knn_other_script_share
    abstain = TEST.get("t1_abstain_rate")                  # from: deliverable_facts.json:evaluation.test.t1_abstain_rate
    sug_beats = SUG["top1"] > SUG["baseline_most_common"]
    stories = [
        (pct(rs["centred"]), "Books meet across scripts",                                  # from: related.knn_other_script_share.centred
         f"of a book's {REL['k']} closest books are in another script after centring, against {pct(rs['uncentred'])} before."),
        (pct(SUG["top3"]), "Suggests a missing class",                                # from: suggest.top3
         f"of {n(SUG['heldout_books'])} held-out books have their own class in the first three suggestions. The top one is "
         f"right {pct(SUG['top1'])}, against {pct(SUG['baseline_most_common'])} for the simple guess."),
        (pct(t1), "A loose page finds its book",                                           # from: evaluation.test.t1_agreement
         f"of single test pages land in their book's group, against {pct(TEST['t1_chance'])} by chance."
         + (f" Pages with too few words are refused: {pct(abstain)} of them." if abstain is not None else "")),
    ]
    s = new_slide("What this changes for an archive", f"""
Before the limits, the case for the tool in three numbers. These are the three stories on the site's impact page.

One, books meet across scripts. As the model gives them, only {pct(rs['uncentred'])} of a book's {REL['k']} closest books are in another script. After centring, {pct(rs['centred'])}. This shows that other scripts now reach a book's neighbours; whether each neighbour shares the subject is for the archivist to judge.

Two, a class for books that have none. On {n(SUG['heldout_books'])} held-out books that do have a class, the book's own class is among the first three suggestions {pct(SUG['top3'])} of the time. The top suggestion alone is right {pct(SUG['top1'])}, which is {"better than" if sug_beats else "no better than"} always naming the most common class, at {pct(SUG['baseline_most_common'])}. We have no simple guess to compare the first-three number with.

Three, a loose page finds its book. A single page lands in its own book's group {pct(t1)} of the time, against {pct(TEST['t1_chance'])} by chance; that is {"at" if MET['T1'] else "below"} our target of {pct(t1_target, 0)}.{f" And when a page has too few readable words the app refuses to guess, which happened for {pct(abstain)} of the test pages." if abstain is not None else ""}

Each number is measured on books kept aside from the ones the model learned from{"" if REL.get("split") != "train" else ", except the first, which is counted on the training books"}.
""", source="reports/features/related.json, reports/features/suggest.json; reports/deliverable_facts.json: evaluation.test.t1_agreement, "
            "t1_chance, t1_abstain_rate")
    w3 = (SLIDE_W - 2 * MARGIN - 2 * GAP) / 3
    for i, (stat, head_t, body_t) in enumerate(stories):
        x = MARGIN + i * (w3 + GAP)
        text(s, x, BODY_Y + 0.1, w3, 1.0, [(stat, S(font="head", size="display", color="accent", line=1.0))],
             anchor=MSO_ANCHOR.BOTTOM)
        hline(s, x, BODY_Y + 1.3, w3, "ink")
        text(s, x, BODY_Y + 1.5, w3, 0.5, [(head_t, S(font="head", size="lead"))])
        text(s, x, BODY_Y + 2.1, w3, 2.2, [(body_t, S(size="body", color="muted"))])
    text(s, MARGIN, BODY_Y + 4.2, 11.5, 0.5,
         [("Measured, not promised: the limits are on the next slide.", S(size="body"))])

# ==============================================================================
# 19. LIMITS
# ==============================================================================
n_met = sum(MET.values())
cat_gain = CAT.get("points_above_best_baseline")
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
tri_sentence = (f"The scan triage score separates good and bad scans with an AUC of {TRI['auc']:.2f}, where 0.5 is chance, "
                f"{'so it is no better than chance' if tri_chance else 'so it does better than chance'}. " if TRI else "")
edi_sentence = (f"The edition finder found {pct(EDI['recall'])} of known editions in only {EDI['groups_heldout']} test groups, "
                "so that number is very uncertain. " if EDI else "")
s = new_slide("What it does not do yet", f"""
Our limits, plainly.

We set three targets before seeing any results, and this study met {n_met} of them. A page lands with its book {pct(t1)} of the time against a target of {pct(t1_target, 0)}: {met_word(MET['T1'])}. The subject gain is {gain(gain_t)} points against {gain(t2_target)}: {met_word(MET['T2'])}{f", though the validation books gave {gain(gain_v)}" if MET['T2'] and not VAL['met']['T2'] else ""}. Stability, measured on the training books, is {f2(TEST['t3_bootstrap'])} against {t3_target}: {met_word(MET['T3'])}.

{cat_sentence}{tri_sentence}{edi_sentence}

The groups are broad: {H['k']} groups for a whole library. Hard-to-read languages are under-represented; {worst['name']} keeps only {pct(worst['usable'] / worst['harvested'], 0)} of its books. The subject labels we test with were made with an AI assistant and checked by us; they are a measuring tool, not expert cataloguing. And the embedding model is an online Google service, so checking a page sends its text to Google.

So we offer this as a helper that shows its evidence, not as a catalogue.
""", source="reports/deliverable_facts.json: evaluation.test.targets, met, t1_agreement, t2_points, t3_bootstrap, catalogue"
            + ("; reports/features/triage.json" if TRI else ""))
rows = [[("Target set before the results", S(bold=True)), ("Needed", S(bold=True, align=PP_ALIGN.RIGHT)),
         ("Got", S(bold=True, align=PP_ALIGN.RIGHT)), ("", S(bold=True))],
        [("A page lands with its book", S()), (pct(t1_target, 0), S(align=PP_ALIGN.RIGHT)),                 # from: targets.T1_page_agreement
         (pct(t1), S(align=PP_ALIGN.RIGHT)), (met_word(MET["T1"]), S(color="muted"))],                         # from: t1_agreement, met.T1
        [("Subject gain over the best simple guess", S()), (f"{gain(t2_target)} points", S(align=PP_ALIGN.RIGHT)),  # from: targets.T2
         (f"{gain(gain_t)} points", S(align=PP_ALIGN.RIGHT)), (met_word(MET["T2"]), S(color="muted"))],     # from: t2_points, met.T2
        [("Groups hold on re-runs (ARI, train books)", S()), (str(t3_target), S(align=PP_ALIGN.RIGHT)),     # from: targets.T3
         (f2(TEST["t3_bootstrap"]), S(align=PP_ALIGN.RIGHT)), (met_word(MET["T3"]), S(color="muted"))]]    # from: t3_bootstrap, met.T3
plain_table(s, MARGIN, BODY_Y, 7.2, rows, [3.9, 1.2, 1.2, 0.9], row_h=0.55)
text(s, 8.55, BODY_Y, 4.05, 4.7, [(line, S(size="body", space=0 if i == 0 else 10)) for i, line in enumerate(limit_lines)] +
     [("A helper that shows its evidence, not a catalogue.", S(size="body", color="muted", space=10))])

# ==============================================================================
# 20. SUMMARY
# ==============================================================================
if CENTRING_HELPS and gain_t > 0:
    title15 = "Take away the language, and subject starts to show"
elif CENTRING_HELPS:
    title15 = "Taking away the language is not enough on its own"
else:
    title15 = "Grouping by subject across scripts is still open"
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
s = new_slide(title15, f"""
To sum up in three sentences.

One: {p1_head[:-1].lower()}; {p1_tail[0].lower() + p1_tail[1:]}

Two: {p2_head[0].lower() + p2_head[1:-1]}: {p2_tail}

Three: the model is useful to an archivist as a helper: it suggests a class for an uncatalogued book, links books across scripts, places a new page, and draws the whole archive as one map, always with its evidence.

Thank you. We are happy to take your questions.
""", dark=True)
points = [(p1_head, p1_tail),                                                                 # from: centring_effect
          (p2_head, p2_tail),                                                                 # from: evaluation.test.t2_points, targets, met
          ("Useful as an archivist's helper.", "Class suggestions, related books across scripts, page checks, and a map of the whole archive.")]
for i, (head_t, body_t) in enumerate(points):
    x = MARGIN + i * (col_w * 5 + GAP * 4 + GAP) / 3
    w = (SLIDE_W - 2 * MARGIN - 2 * GAP) / 3
    text(s, x, BODY_Y + 0.6, w, 2.6, [(head_t, S(font="head", size="lead", color="on_dark")),
                                      (body_t, S(size="body", color="on_dark_muted", space=10))])
text(s, MARGIN, 5.9, 8.0, 0.6, [("Thank you. Questions are welcome.", S(size="lead", color="on_dark"))])

prs.save(OUT)
print(f"saved {OUT.relative_to(ROOT)} ({len(prs.slides)} slides)")
