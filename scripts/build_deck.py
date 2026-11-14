"""Builds Grantha_Heritage_Tracker_SIH26096.pptx from the result files, with no hand-typed result.

    python scripts/build_deck.py

Reads only:
  reports/deliverable_facts.json           every number written on a slide or in the notes
  web/data/study.json, reports/**/*.json   chart series and names the facts file does not hold
  reports/features/*.json                  feature evaluations, when present (not used while absent)
  web/fixtures/*.json                      real example outputs of the app (catalogue card, related books, page check)

Every number in slide text comes from deliverable_facts.json, so `python scripts/check_claims.py` can trace it.
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
LANG = {r["lang"]: r["name"] for r in C["by_language"]}          # from: deliverable_facts.json:corpus.by_language


def n(x) -> str:
    return f"{int(x):,}"


def pct(x, d=1) -> str:
    return f"{100 * x:.{d}f}%"


def f2(x) -> str:
    return f"{x:.2f}"


def pts(x) -> str:
    return f"{x:.1f}"


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

Every number you will see comes from our result files. Where we missed a target, we say so.
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
s = new_slide("About half the books carry no library class", f"""
Start with the problem an archivist has.

These are scans of old printed books from the Digital Library of India. Of the {n(usable)} books we could use, only {n(classified)} carry a library class, the subject code a librarian gives a book. The rest have none, so a subject search cannot find them.

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
worst = langs[-1]
s = new_slide(f"{n(C['usable'])} of {n(C['harvested'])} books were clear enough to use", f"""
Our data: books from the Digital Library of India, mirrored on the Internet Archive, in {C['languages']} languages. We downloaded {n(C['harvested'])} books.

To read a scan, we use OCR: software that turns a picture of a page into text. A book is usable only when the OCR reads it with enough confidence and finds enough real words.

{n(C['usable'])} books pass, which is {pct(C['usable_share'])}. The grey bar is what we downloaded, the red bar is what we could use. English keeps almost all its books. {worst['name']} keeps the fewest, {pct(worst['usable'] / worst['harvested'], 0)}, because its scans are the hardest to read.

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
     "its scans are the hardest to read.", S(size="body", color="muted", space=14)),
    ("OCR: the software that turns a page image into text.", S(size="body", color="muted", space=14)),
])

# ==============================================================================
# 4. SCAN QUALITY
# ==============================================================================
conf = sorted(C["by_language"], key=lambda r: -r["median_conf"])          # from: corpus.by_language[].median_conf
low2 = conf[-2:]
s = new_slide(f"{low2[1]['name']} and {low2[0]['name']} scans are the hardest to read", f"""
This chart shows how sure the OCR is of the words it reads, from 0 to 100, for the middle book in each language.

English reads best, at {conf[0]['median_conf']:.1f}. {low2[1]['name']} is lowest at {low2[1]['median_conf']:.1f}, then {low2[0]['name']} at {low2[0]['median_conf']:.1f}.

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

Three, centre: we subtract each language's average list of numbers. Without this, the strongest signal is the language itself, not the subject. This is our key step.

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
     [(f"Embedding model: {F['encoder']['name']}. Centring is the step that changes the result.",   # from: encoder.name
       S(size="body"))])

# ==============================================================================
# 6. LANGUAGE FIRST
# ==============================================================================
word_groups = [v for k, v in sorted(NAMES["A_hier"].items(), key=lambda kv: int(kv[0]))]  # from: reports/cluster_names.json:A_hier
nmi_rows = []
if CMP:
    nmi_rows.append((f"Word counts, earlier study", CMP["selection"]["nmi_script"]["A"]))        # from: comparison_study.selection.nmi_script.A
    nmi_rows.append((f"{STUDY['sets']['G']['name']}, centred, earlier study",                      # from: web/data/study.json:sets.G.name
                     CMP["selection"]["nmi_script"]["G"]))                                         # from: comparison_study.selection.nmi_script.G
nmi_rows.append((f"{F['encoder']['name']}, centred, this study", H["nmi_script"]))                  # from: hierarchical.nmi_script
s = new_slide("Counting words, books group by language first", f"""
This is our main finding.

When we grouped books by simply counting their words, in an earlier study, every group turned out to be one language: English books, Bengali books, Tamil books and so on. That is on the left. It is correct, but useless: we already know each book's language.

To measure this we use NMI, a score of how much the groups follow language: 0 means not at all, 1 means each group is exactly one language.

Word counts score {f2(CMP['selection']['nmi_script']['A']) if CMP else 'high'}. With embeddings and centring, the score falls to {f2(H['nmi_script'])} in this study: the groups no longer follow language, so subject can come through.
""", source="reports/cluster_names.json: A_hier; reports/deliverable_facts.json: comparison_study.selection.nmi_script, hierarchical.nmi_script")
text(s, MARGIN, BODY_Y, 3.6, 0.5, [("Groups from word counts", S(size="body", bold=True))])
text(s, MARGIN, BODY_Y + 0.5, 3.6, 3.6, [(g, S(size="body", color="muted", space=4)) for g in word_groups])
text(s, 4.75, BODY_Y, 7.8, 0.5, [("How much the groups follow language (NMI: 0 none, 1 fully)", S(size="body", bold=True))])
bar_chart(s, 4.65, BODY_Y + 0.45, 7.95, 3.4, [r[0] for r in nmi_rows],
          [("NMI with script", [r[1] for r in nmi_rows],
            ["neutral"] * (len(nmi_rows) - 1) + ["accent"])], number_format="0.00", gap=50, max_scale=1)

# ==============================================================================
# 7. CENTRING HELPS SUBJECT
# ==============================================================================
enc = ENCODERS["encoders"]
enc_rows = sorted(enc.values(), key=lambda e: -e["knn_centred"])     # from: reports/study/encoder_comparison.json:encoders
better = sum(e["knn_centred"] > e["knn_plain"] for e in enc_rows)
claim = "every model" if better == len(enc_rows) else f"{better} of {len(enc_rows)} models"
s = new_slide(f"Removing each language's average helps {claim} find subjects", f"""
Does centring really help with subject? We checked it on four embedding models, on labelled books from the earlier study.

The test is simple: guess a book's subject from the books closest to it. If close books share a subject, the guess is right more often.

Grey is the model as it comes. Red is after we subtract each language's average. For {claim}, red is longer: once language is removed, a book's neighbours are more often on the same subject.

One honest note: {F['encoder']['name']}, the model behind our final groups, was not part of this comparison.
""", source="reports/study/encoder_comparison.json: encoders[].knn_plain, encoders[].knn_centred (labelled train and validation books)")
bar_chart(s, MARGIN - 0.1, BODY_Y - 0.15, 8.6, 4.9, [e["name"].replace(" embeddings", "") for e in enc_rows],
          [("as the model gives them", [e["knn_plain"] for e in enc_rows], "neutral"),    # from: encoders[].knn_plain
           ("after centring", [e["knn_centred"] for e in enc_rows], "accent")],           # from: encoders[].knn_centred
          number_format="0%", gap=45, max_scale=1)
swatch_key(s, 9.25, BODY_Y, [("as the model gives them", "neutral"), ("after centring", "accent")])
text(s, 9.25, BODY_Y + 1.0, 3.35, 3.6, [
    ("Each bar: how often the closest books guess a book's subject right.", S(size="lead")),
    (f"{F['encoder']['name']}, used for the final groups, was not in this test.", S(size="body", color="muted", space=14)),
])

# ==============================================================================
# 8. THE GROUPS
# ==============================================================================
groups = F["groups"]                                         # from: deliverable_facts.json:groups
lang_codes = [r["lang"] for r in C["by_language"]]
top_share = max(g["top_language_share"] for g in groups)    # from: groups[].top_language_share
all_mixed = all(all(g["languages"].get(l, 0) > 0 for l in lang_codes) for g in groups)
s = new_slide(f"{len(groups)} broad groups, each mixing {'all ' + str(len(lang_codes)) if all_mixed else 'many'} languages", f"""
These are the groups the model found on all {n(usable)} usable books, using {H['linkage']} linkage cut into {H['k']} groups.

Each row is a group. The columns show what share of the group comes from each language: the darker the cell, the bigger the share. No language holds more than {pct(top_share, 0)} of any group, so the groups are not language piles any more.

The subject column is the most common subject among the hand-labelled training books in that group. We did not name the groups by hand.

Be honest about what this shows: the groups are broad. Two of them lean to literature, so they split one subject by something else in the vocabulary. These are rough shelves, not a catalogue.
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
best_base = max(TEST["t2_baseline_script"], TEST["t2_baseline_common"])
t2_target = TEST["targets"]["T2_points_above_baseline"]                  # from: evaluation.test.targets
ci = TEST.get("t2_accuracy_ci95")
ci_text = f" Likely range {pct(ci[0])} to {pct(ci[1])}." if ci else ""
s = new_slide(f"The groups guess subject {pts(TEST['t2_points'])} points better than the best simple guess", f"""
How good are the groups? We kept some books aside and never used them to build the groups. For {n(TEST['t2_labelled_heldout'])} of these test books we have a subject label.

Each group predicts its most common subject. That is right {pct(TEST['t2_accuracy'])} of the time.

Is that good? Compare with simple guesses. Guessing from the script alone is right {pct(TEST['t2_baseline_script'])} of the time. Always guessing the most common subject is right {pct(TEST['t2_baseline_common'])}.

So the groups beat the best simple guess by {pts(TEST['t2_points'])} points. Our target, written before the results, was {t2_target:.0f} points, so we did not meet it. On the validation books the gain was {pts(VAL['t2_points'])} points.

Shuffling the subject labels at random almost never gives a gain this big: p = {TEST['t2_p']:.4f}. So the gain is real, just smaller than we wanted.
{"The likely range of the accuracy is " + pct(ci[0]) + " to " + pct(ci[1]) + "." if ci else "This run's result file does not yet hold a confidence interval for the accuracy, so we do not show one. With this few labelled books, treat the gain as approximate."}
{f"For comparison, our earlier smaller study with {STUDY['sets']['G']['name']} beat its best simple guess by {pts(CMP['test']['t2_points'])} points." if CMP else ""}
""", source="reports/deliverable_facts.json: evaluation.test.t2_accuracy, t2_baseline_script, t2_baseline_common, t2_points, t2_p, targets")
bar_chart(s, MARGIN - 0.1, BODY_Y - 0.15, 8.6, 4.4,
          ["Our groups", "Guess from the script alone", "Always the most common subject"],
          [("test books", [TEST["t2_accuracy"], TEST["t2_baseline_script"], TEST["t2_baseline_common"]],  # from: evaluation.test.t2_*
            ["accent", "neutral", "neutral"])], number_format="0.0%", gap=55, max_scale=1)
text(s, 9.25, BODY_Y, 3.35, 4.6, [
    (f"{n(TEST['t2_labelled_heldout'])} labelled books, kept aside until the end.{ci_text}", S(size="lead")),  # from: evaluation.test.t2_labelled_heldout
    (f"Target: {t2_target:.0f} points. {'Met.' if TEST['met']['T2'] else 'Not met.'}",                       # from: evaluation.test.targets, met
     S(size="body", space=14)),
    (f"Random shuffles of the labels: p = {TEST['t2_p']:.4f}.", S(size="body", color="muted", space=14)),      # from: evaluation.test.t2_p
    (f"Validation books: {pts(VAL['t2_points'])} points.", S(size="body", color="muted", space=8)),          # from: evaluation.val.t2_points
])

# ==============================================================================
# 10. STABILITY
# ==============================================================================
hb, dbb = H["bootstrap"], DB["bootstrap"]                   # from: hierarchical.bootstrap, dbscan.bootstrap
t3_target = TEST["targets"]["T3_bootstrap_ari"]             # from: evaluation.test.targets.T3_bootstrap_ari
stable = hb["median"] >= t3_target
s = new_slide("The groups hold when we re-run on other books" if stable else
              "The groups change when we re-run on other books", f"""
A good grouping should not change much if we start from a slightly different set of books. So we re-ran the grouping {len(hb['values'])} times, each time on a random part of the books, and compared each result with the full grouping of all usable books.

We compare groupings with ARI, a score of how much two groupings agree: 1 means identical, 0 means no better than chance.

Each red dot is one re-run of our hierarchical groups. The middle value is {f2(hb['median'])}, and most runs fall between {f2(hb['p10'])} and {f2(hb['p90'])}. Our target was {t3_target}. {'We met it.' if stable else 'We did not meet it: the groups are broad and partly shift.'}

The grey dots are DBSCAN, which looks for crowded regions of books. It is steadier, around {f2(dbb['median'])}, but it calls {pct(DB['noise_share'])} of the books noise, meaning they sit in no crowded region. It finds only {DB['n_clusters']} clusters. So we use the hierarchical groups as the shelves and show DBSCAN's verdict beside them.
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
    (f"DBSCAN is steadier but calls {pct(DB['noise_share'])} of books noise: in no crowded region.",  # from: dbscan.noise_share
     S(size="body", color="muted", space=10)),
])

# ==============================================================================
# 11. CATALOGUE CLASS SUGGESTION (recorded app output)
# ==============================================================================
doc, sug = fixture(f"get_documents__{EXAMPLE_BOOK}"), fixture(f"get_suggest__{EXAMPLE_BOOK}")
s = new_slide("For a book with no class, the tool suggests one", f"""
Now, what does an archivist get? This is a real answer from our app, recorded from the final model.

The book is {doc['title']}, a {doc['script']} book printed {doc['era'].replace('pre-', 'before ')}. It has no library class.

The tool looks at the nearest books that do have a class and lets them vote; closer books count more. The bars are each class's share of the vote. The top suggestion is {sug['suggestions'][0]['class']}, then {sug['suggestions'][1]['class']}.

It is a suggestion for the archivist to accept or reject, shown with its evidence. {"" if FEATURES else "We have not yet measured how often the top suggestion is right on books kept aside, so we show no accuracy for it."}
""", source=f"web/fixtures/get_documents__{EXAMPLE_BOOK}.json, web/fixtures/get_suggest__{EXAMPLE_BOOK}.json (recorded app output)")
rect(s, MARGIN, BODY_Y, 4.6, 3.2, "tint", name="Catalogue card")
text(s, MARGIN + 0.35, BODY_Y + 0.35, 3.9, 2.6, [
    (doc["title"], S(font="head", size="lead")),                                     # from: fixture documents.title
    (doc["creator"] or "", S(size="body", color="muted", space=6)),                  # from: fixture documents.creator
    (f"{doc['script']} script, printed {doc['era'].replace('pre-', 'before ')}", S(size="body", space=18)),  # from: fixture documents.script, era
    ("Library class", S(size="small", color="muted", space=18)),
    (doc["classification"] or "none", S(size="lead", space=2)),                       # from: fixture documents.classification
])
text(s, 5.85, BODY_Y, 6.7, 0.5, [("Suggested classes, share of the nearest classed books' vote", S(size="body", bold=True))])
bar_chart(s, 5.75, BODY_Y + 0.45, 6.85, 2.6, [x["class"] for x in sug["suggestions"]],
          [("vote share", [x["score"] for x in sug["suggestions"]],                    # from: fixture suggest.suggestions[].score
            ["accent"] + ["neutral"] * (len(sug["suggestions"]) - 1))], number_format="0%", gap=50, max_scale=1)
text(s, 5.85, BODY_Y + 3.3, 6.7, 1.0, [
    ("A suggestion for the archivist to accept or reject." +
     ("" if FEATURES else " Its accuracy on held-out books is not measured yet."), S(size="body", color="muted"))])

# ==============================================================================
# 12. RELATED BOOKS IN OTHER SCRIPTS (recorded app output)
# ==============================================================================
rel = fixture(f"get_related__{EXAMPLE_BOOK}")
shown = rel["neighbours"][:8]
other = sorted({x["script"] for x in shown})
s = new_slide(f"One {doc['script']} book's closest neighbours come from {len(other)} other scripts", f"""
The second tool connects books across scripts, which a normal catalogue search cannot do.

We take the same {doc['script']} book and ask for its closest books written in other scripts. These are the first {len(shown)} answers, again recorded from the app.

They come from {', '.join(other)} books. Several titles are about religion, for example a Hindu way of life and temple entry, which matches the suggested classes on the previous slide.

The model never saw a translation dictionary: it found these because, after centring, books on similar subjects sit close together whatever their script.
""", source=f"web/fixtures/get_related__{EXAMPLE_BOOK}.json (recorded app output)")
text(s, MARGIN, BODY_Y, 3.6, 3.0, [
    ("Starting book", S(size="small", color="muted")),
    (doc["title"], S(font="head", size="lead", space=4)),                              # from: fixture documents.title
    (f"{doc['script']} script", S(size="body", color="muted", space=4)),
    ("Its closest books in other scripts are on the right, closest first.", S(size="body", space=24)),
])
rows = [[("Title", S(bold=True)), ("Script", S(bold=True))]]
for x in shown:                                                                         # from: fixture related.neighbours[]
    rows.append([(x["title"], S(font="indic")), (x["script"], S(color="muted"))])
plain_table(s, 4.85, BODY_Y, SLIDE_W - MARGIN - 4.85, rows, [5.6, SLIDE_W - MARGIN - 4.85 - 5.6], row_h=0.5)

# ==============================================================================
# 13. A NEW PAGE IS PLACED (recorded app output)
# ==============================================================================
chk = fixture(CHECK_FIXTURE)
t1_target = TEST["targets"]["T1_page_agreement"]           # from: evaluation.test.targets.T1_page_agreement
s = new_slide("A single new page lands in its book's group most of the time", f"""
The third tool: an archivist scans one new page, and the app places it among the archive's books.

The number on the left is our test of exactly this. We took one page from each test book and checked whether it lands in the same group as its whole book. It does {pct(TEST['t1_agreement'])} of the time. A random guess would manage {pct(TEST['t1_chance'])}. Our target was {pct(t1_target, 0)}, so we are just short.

On the right is a real check of a {chk['script']} page. The app shows the closest archive books, with links, so the archivist can see why it decided. It also says when it is unsure: here DBSCAN says the page {'sits in a crowded region' if chk['dbscan']['in_dense_group'] else 'is not in any crowded region'}, and the app shows that too. When a page has too few readable words, it refuses to guess.
""", source=f"reports/deliverable_facts.json: evaluation.test.t1_agreement, t1_chance; web/fixtures/{CHECK_FIXTURE}.json")
text(s, MARGIN, BODY_Y, 4.4, 1.4, [(pct(TEST["t1_agreement"]), S(font="head", size="stat", color="accent"))],  # from: evaluation.test.t1_agreement
     anchor=MSO_ANCHOR.BOTTOM)
text(s, MARGIN, BODY_Y + 1.5, 4.2, 2.6, [
    ("of single test pages land in their own book's group.", S(size="lead")),
    (f"Random guess: {pct(TEST['t1_chance'])}. Target: {pct(t1_target, 0)}. "                       # from: evaluation.test.t1_chance, targets
     f"{'Met.' if TEST['met']['T1'] else ('Just short.' if t1_target - TEST['t1_agreement'] < 0.02 else 'Not met.')}", S(size="body", color="muted", space=14)),
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
# 14. LIMITS
# ==============================================================================
s = new_slide("What it does not do yet", f"""
Our limits, plainly.

We set three targets before seeing any results, and this study met {sum(TEST['met'].values())} of them. A page lands with its book {pct(TEST['t1_agreement'])} of the time against a target of {pct(t1_target, 0)}. The subject gain is {pts(TEST['t2_points'])} points against {t2_target:.0f}. Stability, measured on the training books, is {f2(TEST['t3_bootstrap'])} against {t3_target}.

The groups are broad: {H['k']} groups for a whole library. Hard-to-read languages are under-represented; {worst['name']} keeps only {pct(worst['usable'] / worst['harvested'], 0)} of its books. The subject labels we test with were made with an AI assistant and checked by us; they are a measuring tool, not expert cataloguing. And the embedding model is an online Google service, so checking a page sends its text to Google.

So we offer this as a helper that shows its evidence, not as a catalogue.
""", source="reports/deliverable_facts.json: evaluation.test.targets, evaluation.test.met, evaluation.test.t1_agreement, t2_points, t3_bootstrap")
yes = lambda ok: "met" if ok else "not met"
rows = [[("Target set before the results", S(bold=True)), ("Needed", S(bold=True, align=PP_ALIGN.RIGHT)),
         ("Got", S(bold=True, align=PP_ALIGN.RIGHT)), ("", S(bold=True))],
        [("A page lands with its book", S()), (pct(t1_target, 0), S(align=PP_ALIGN.RIGHT)),                 # from: targets.T1_page_agreement
         (pct(TEST["t1_agreement"]), S(align=PP_ALIGN.RIGHT)), (yes(TEST["met"]["T1"]), S(color="muted"))],  # from: t1_agreement, met.T1
        [("Subject gain over the best simple guess", S()), (f"{t2_target:.0f} points", S(align=PP_ALIGN.RIGHT)),  # from: targets.T2
         (f"{pts(TEST['t2_points'])} points", S(align=PP_ALIGN.RIGHT)), (yes(TEST["met"]["T2"]), S(color="muted"))],
        [("Groups hold on re-runs (ARI, train books)", S()), (str(t3_target), S(align=PP_ALIGN.RIGHT)),                     # from: targets.T3
         (f2(TEST["t3_bootstrap"]), S(align=PP_ALIGN.RIGHT)), (yes(TEST["met"]["T3"]), S(color="muted"))]]    # from: t3_bootstrap
plain_table(s, MARGIN, BODY_Y, 7.2, rows, [3.9, 1.2, 1.2, 0.9], row_h=0.55)
text(s, 8.55, BODY_Y, 4.05, 4.6, [
    (f"{worst['name']} keeps only {pct(worst['usable'] / worst['harvested'], 0)} of its books.", S(size="body")),   # from: corpus.by_language
    ("Test labels were made with an AI assistant and checked by us, not by expert cataloguers.", S(size="body", space=14)),
    ("The embedding model is an online Google service: a checked page's text goes to Google.", S(size="body", space=14)),
    ("A helper that shows its evidence, not a catalogue.", S(size="body", color="muted", space=14)),
])

# ==============================================================================
# 15. SUMMARY
# ==============================================================================
s = new_slide("Take away the language, and subject starts to show", f"""
To sum up in three sentences.

One: multilingual book vectors group by language first; subtracting each language's average is what lets subject come through.

Two: the groups beat simple guesses on books kept aside, but by {pts(TEST['t2_points'])} points, less than our target, and they are not yet stable.

Three: even now the model is useful to an archivist as a helper: it suggests a class for an uncatalogued book, links books across scripts, and places a new page, always with its evidence.

Thank you. We are happy to take your questions.
""", dark=True)
points = [("Books group by language first.", "Subtracting each language's average lets subject come through."),
          ("The groups beat simple guesses, by less than we aimed.",
           f"{pts(TEST['t2_points'])} points against a target of {t2_target:.0f}; not yet stable."),   # from: evaluation.test.t2_points, targets
          ("Useful now as an archivist's helper.", "Class suggestions, related books across scripts, page checks.")]
for i, (head_t, body_t) in enumerate(points):
    x = MARGIN + i * (col_w * 5 + GAP * 4 + GAP) / 3
    w = (SLIDE_W - 2 * MARGIN - 2 * GAP) / 3
    text(s, x, BODY_Y + 0.6, w, 2.6, [(head_t, S(font="head", size="lead", color="on_dark")),
                                      (body_t, S(size="body", color="on_dark_muted", space=10))])
text(s, MARGIN, 5.9, 8.0, 0.6, [("Thank you. Questions are welcome.", S(size="lead", color="on_dark"))])

prs.save(OUT)
print(f"saved {OUT.relative_to(ROOT)} ({len(prs.slides)} slides)")
