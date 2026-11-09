"""Data flow diagrams (Yourdon notation) for the report: Level 0, Level 1, and Level 2 for
processes 3 (preprocess and features), 4 (clustering study) and 5 (check a new page).

    python scripts/dfd.py        -> reports/figures/dfd_level0.png ... dfd_level2_p5.png

Flows are straight routed segments (horizontal/vertical), each label sitting on its line.
An entity drawn twice carries a short stroke in its corner (the usual DFD duplicate mark).
"""
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle

OUT = Path(__file__).resolve().parent.parent / "reports" / "figures"
INK, LINE, FILL, PROC, SURF = "#1b1a17", "#4a4844", "#f4f1ea", "#fbe9d6", "#ffffff"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})


class D:
    def __init__(self, w, h, title):
        self.fig, self.ax = plt.subplots(figsize=(w, h))
        self.ax.set_xlim(0, w * 10)
        self.ax.set_ylim(0, h * 10)
        self.ax.set_aspect("equal")
        self.ax.axis("off")
        self.ax.set_title(title, fontsize=11, fontweight="bold", color=INK, loc="left")
        self.n = {}

    def entity(self, key, x, y, label, w=17, h=8, dup=False):
        self.ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc=FILL, ec=INK, lw=1.4, zorder=3))
        self.ax.text(x, y, label, ha="center", va="center", color=INK, zorder=4)
        if dup:
            self.ax.plot([x - w / 2, x - w / 2 + 2.5], [y - h / 2 + 2.5, y - h / 2], color=INK, lw=1.2, zorder=4)
        self.n[key] = ("rect", x, y, w / 2, h / 2)

    def process(self, key, x, y, num, label, r=7):
        self.ax.add_patch(Circle((x, y), r, fc=PROC, ec=INK, lw=1.4, zorder=3))
        self.ax.text(x, y + r * 0.45, num, ha="center", va="center", color=INK, fontweight="bold", zorder=4)
        self.ax.text(x, y - r * 0.12, label, ha="center", va="center", color=INK, fontsize=8, zorder=4)
        self.n[key] = ("circle", x, y, r, r)

    def store(self, key, x, y, ident, label, w=24, h=5.5):
        x0, x1, y0, y1 = x - w / 2, x + w / 2, y - h / 2, y + h / 2
        self.ax.add_patch(Rectangle((x0, y0), w, h, fc=SURF, ec="none", zorder=3))
        for xs, ys in [([x0, x1], [y1, y1]), ([x0, x1], [y0, y0]), ([x0, x0], [y0, y1]), ([x0 + 5, x0 + 5], [y0, y1])]:
            self.ax.plot(xs, ys, color=INK, lw=1.4, zorder=4)
        self.ax.text(x0 + 2.5, y, ident, ha="center", va="center", color=INK, fontweight="bold", fontsize=8, zorder=5)
        self.ax.text(x0 + 5 + (w - 5) / 2, y, label, ha="center", va="center", color=INK, fontsize=8, zorder=5)
        self.n[key] = ("rect", x, y, w / 2, h / 2)

    def port(self, key, side, off=0.0):
        """Where a ray leaving the shape's centre on `side`, shifted by `off`, crosses its outline."""
        kind, x, y, hw, hh = self.n[key]
        if kind == "circle":
            d = math.sqrt(max(hw * hw - off * off, 0))
            return {"e": (x + d, y + off), "w": (x - d, y + off), "n": (x + off, y + d), "s": (x + off, y - d)}[side]
        return {"e": (x + hw, y + off), "w": (x - hw, y + off), "n": (x + off, y + hh), "s": (x + off, y - hh)}[side]

    def flow(self, a, sa, b, sb, label, oa=0.0, ob=0.0, via=(), seg=None, lab_off=(0, 0)):
        pts = [self.port(a, sa, oa), *via, self.port(b, sb, ob)]
        xs, ys = zip(*pts)
        self.ax.plot(xs, ys, color=LINE, lw=1.1, zorder=2)
        self.ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=11, color=LINE, lw=1.1,
                                          shrinkA=0, shrinkB=0, zorder=2))
        i = (len(pts) - 2) // 2 if seg is None else seg
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        self.ax.text((x1 + x2) / 2 + lab_off[0], (y1 + y2) / 2 + lab_off[1], label, ha="center", va="center",
                     fontsize=7.4, color=INK, zorder=6, bbox=dict(boxstyle="round,pad=0.18", fc=SURF, ec="none"))

    def save(self, name):
        OUT.mkdir(parents=True, exist_ok=True)
        self.fig.tight_layout()
        self.fig.savefig(OUT / f"{name}.png", dpi=200, facecolor=SURF)
        plt.close(self.fig)
        print("wrote", OUT / f"{name}.png")


def level0():
    d = D(12, 4.6, "DFD Level 0: context diagram")
    d.entity("user", 16, 22, "Archivist /\nresearcher", w=18, h=16)
    d.process("sys", 60, 22, "0", "Grantha", r=13)
    d.entity("ia", 104, 22, "Internet Archive\n(DLI mirror)", w=20, h=10)
    d.flow("user", "e", "sys", "w", "scan, PDF or text, language", oa=6, ob=6)
    d.flow("sys", "w", "user", "e", "group, confidence, 5 nearest books, map")
    d.flow("user", "e", "sys", "w", "browse and study requests", oa=-6, ob=-6)
    d.flow("ia", "w", "sys", "e", "catalogue metadata, page images")
    d.save("dfd_level0")


def level1():
    d = D(13, 8.6, "DFD Level 1: the system's processes and data stores")
    d.entity("ia", 12, 70, "Internet Archive", w=18)
    d.process("p1", 40, 70, "1.0", "Harvest\nsample")
    d.store("d1", 72, 78, "D1", "Page images + metadata")
    d.process("p2", 104, 70, "2.0", "OCR\npages")
    d.store("d2", 104, 48, "D2", "Text corpus + OCR quality")
    d.process("p3", 72, 48, "3.0", "Preprocess +\nfeatures")
    d.store("d3", 40, 48, "D3", "Features + transformers")
    d.process("p4", 40, 24, "4.0", "Clustering\nstudy")
    d.store("d4", 72, 24, "D4", "Models + study results")
    d.process("p5", 104, 24, "5.0", "Check a\nnew page")
    d.process("p6", 72, 7, "6.0", "Browse /\nview study")
    d.entity("user", 124, 7, "User", w=12)
    d.flow("ia", "e", "p1", "w", "metadata, page images")
    d.flow("p1", "n", "d1", "w", "pages, catalogue fields", via=[(40, 78)], seg=1)
    d.flow("d1", "e", "p2", "n", "page images", via=[(104, 78)])
    d.flow("p2", "s", "d2", "n", "text, confidence")
    d.flow("d2", "w", "p3", "e", "page texts")
    d.flow("d1", "s", "p3", "n", "metadata")
    d.flow("p3", "w", "d3", "e", "feature matrices")
    d.flow("d3", "s", "p4", "n", "features")
    d.flow("p4", "e", "d4", "w", "labels, models, metrics")
    d.flow("d4", "e", "p5", "w", "centroids, core books")
    d.flow("d3", "s", "p5", "n", "fitted transformers", oa=9, ob=-3, via=[(49, 37), (101, 37)], seg=1)
    d.flow("d2", "s", "p5", "n", "nearest books", oa=6, ob=3, via=[(110, 40), (107, 40)], seg=0)
    d.flow("d4", "s", "p6", "n", "groups, results")
    d.flow("p6", "e", "user", "w", "pages")
    d.flow("user", "n", "p5", "e", "scan or text", oa=3, ob=3, via=[(127, 27)], seg=0)
    d.flow("p5", "e", "user", "n", "group, matches, map", oa=-3, ob=-3, via=[(121, 21)], seg=1)
    d.save("dfd_level1")


def level2_p3():
    d = D(13, 5.8, "DFD Level 2: process 3.0, preprocess and build features")
    d.store("d2", 12, 42, "D2", "Text corpus", w=20)
    d.store("d1", 12, 16, "D1", "Metadata", w=20)
    d.process("p31", 40, 42, "3.1", "Clean text\n(per script)")
    d.process("p32", 40, 16, "3.2", "Review fields,\nimpute, encode")
    d.process("p33", 68, 29, "3.3", "Usability\nfilter")
    d.process("p34", 96, 42, "3.4", "TF-IDF\n+ LSA (A)")
    d.process("p35", 96, 16, "3.5", "Gemini embed.\n+ centring, PCA")
    d.store("d3", 122, 29, "D3", "Features", w=18)
    d.flow("d2", "e", "p31", "w", "OCR text")
    d.flow("d1", "e", "p32", "w", "catalogue fields")
    d.flow("p31", "e", "p33", "n", "tokens", via=[(68, 42)])
    d.flow("p32", "e", "p33", "s", "year, pages, confidence", via=[(68, 16)])
    d.flow("p33", "e", "p34", "s", "usable books", oa=3, via=[(96, 32)])
    d.flow("p33", "e", "p35", "n", "usable books", oa=-3, via=[(96, 26)])
    d.flow("p34", "e", "d3", "n", "matrix A", via=[(122, 42)])
    d.flow("p35", "e", "d3", "s", "matrix B", via=[(122, 16)])
    d.flow("p32", "s", "d3", "s", "encoded metadata block", via=[(40, 4), (127, 4)], seg=1, ob=5)
    d.save("dfd_level2_p3")


def level2_p4():
    d = D(13, 5.8, "DFD Level 2: process 4.0, the clustering study")
    d.store("d3", 12, 29, "D3", "Features", w=18)
    d.process("p41", 38, 29, "4.1", "Euclidean vs\nManhattan")
    d.process("p42", 64, 44, "4.2", "Hierarchical\ngrid")
    d.process("p43", 64, 14, "4.3", "DBSCAN\ngrid")
    d.process("p44", 90, 29, "4.4", "Select by\nsilhouette")
    d.process("p45", 118, 44, "4.5", "Stability,\ncomparison")
    d.process("p46", 118, 14, "4.6", "Profiles,\nPCA")
    d.store("d4", 118, 29, "D4", "Results", w=16)
    d.flow("d3", "e", "p41", "w", "features")
    d.flow("p41", "n", "p42", "w", "chosen metric", via=[(38, 44)])
    d.flow("p41", "s", "p43", "w", "chosen metric", via=[(38, 14)])
    d.flow("p42", "e", "p44", "n", "linkage x k scores", via=[(90, 44)])
    d.flow("p43", "e", "p44", "s", "eps x MinPts scores", via=[(90, 14)])
    d.flow("p44", "e", "p45", "w", "final settings", oa=3, via=[(100, 32), (100, 44)], seg=1)
    d.flow("p44", "e", "p46", "w", "final labels", oa=-3, via=[(104, 26), (104, 14)], seg=1)
    d.flow("p45", "s", "d4", "n", "ARI, NMI")
    d.flow("p46", "n", "d4", "s", "profiles, map")
    d.save("dfd_level2_p4")


def level2_p5():
    d = D(14.5, 6.6, "DFD Level 2: process 5.0, check a new page")
    d.entity("user", 10, 42, "User", w=12)
    d.process("p51", 32, 42, "5.1", "OCR upload\n(script, rotate)")
    d.process("p52", 56, 42, "5.2", "Clean +\nabstain check")
    d.process("p53", 80, 42, "5.3", "Transform to\nfeatures")
    d.store("d3", 80, 59, "D3", "Transformers", w=20)
    d.process("p54", 104, 54, "5.4", "Nearest\ncentroid")
    d.process("p55", 104, 30, "5.5", "Within eps of\na core book?")
    d.store("d4", 128, 42, "D4", "Models", w=14)
    d.process("p56", 80, 18, "5.6", "Nearest books,\nshared words")
    d.process("p57", 116, 10, "5.7", "Compose\nresult")
    d.entity("user2", 136, 10, "User", w=10, dup=True)
    d.flow("user", "e", "p51", "w", "scan, language")
    d.flow("p51", "e", "p52", "w", "text, confidence")
    d.flow("p52", "e", "p53", "w", "tokens")
    d.flow("d3", "s", "p53", "n", "fitted transforms")
    d.flow("p53", "e", "p54", "w", "vector", oa=3, via=[(93, 45), (93, 54)], seg=1)
    d.flow("p53", "e", "p55", "w", "vector", oa=-3, via=[(93, 39), (93, 30)], seg=1)
    d.flow("p53", "s", "p56", "n", "vector")
    d.flow("d4", "n", "p54", "e", "centroids", via=[(128, 54)])
    d.flow("d4", "s", "p55", "e", "core books, eps", via=[(128, 30)])
    d.flow("p54", "n", "p57", "n", "group, level", ob=3, via=[(104, 64), (142, 64), (142, 24), (119, 24)], seg=2)
    d.flow("p55", "s", "p57", "n", "dense group or noise", ob=-4, via=[(104, 22), (112, 22)], seg=0)
    d.flow("p56", "e", "p57", "w", "5 books, shared words")
    d.flow("p52", "s", "p57", "s", "abstain: too little text", via=[(56, 1.5), (116, 1.5)], seg=1)
    d.flow("p57", "e", "user2", "w", "result")
    d.save("dfd_level2_p5")


if __name__ == "__main__":
    level0(); level1(); level2_p3(); level2_p4(); level2_p5()
