"""300 DPI figures for the SIH26096 deck and viva guide, drawn only from the pipeline's own outputs.

Every number on these figures is read from a results file (nothing is typed in):
  web/data/study.json            corpus counts per language, final selection
  data/processed/docs.csv        per-book OCR confidence, usable flag, split
  reports/variable_relevance.csv field-by-field keep/drop decisions
  reports/study/results_<FS>.json, selection.json   hierarchical grid, DBSCAN grid, PCA, effects
  reports/eval/evaluation_test.json  group -> majority subject (learned on labelled train books)
  data/model/bundle.joblib       the final model: Z (books x 100), labels, the embedder's PCA

Run from the repository root after the study, evaluation and export:  python scripts/generate_specialist_plots.py
"""
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))          # the bundle pickles pipeline.* classes
FIG = Path(os.environ.get("FIG_DIR", BASE / "reports" / "figures"))
FIG.mkdir(parents=True, exist_ok=True)

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cophenet, dendrogram, linkage
from scipy.spatial.distance import pdist
from sklearn.decomposition import PCA

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948", "#8c564b", "#17becf"]
INK, INK2, MUTED, GRID, AXIS, SURFACE, NOISE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb", "#b9b8b2"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.titlecolor": INK, "legend.frameon": False, "lines.linewidth": 2,
})
LANG_NAMES = {"ben": "Bengali", "eng": "English", "guj": "Gujarati", "hin": "Hindi", "kan": "Kannada",
              "san": "Sanskrit", "tam": "Tamil", "tel": "Telugu"}


def load(path):
    return json.loads((BASE / path).read_text(encoding="utf-8"))


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("saved", FIG / name)


def group_names(evaluation, k):
    """'G1 · literature' using the majority subject each group took on the labelled train books."""
    g2s = evaluation.get("T2_subject", {}).get("group_to_subject", {})
    return {g: f"G{g + 1} · {g2s.get(str(g), 'no labelled books')}" for g in range(k)}


# ---------------------------------------------------------------- Fig 2.1
def plot_dataset(study, docs, relevance):
    corpus = study["corpus"]
    langs = sorted(corpus["by_language"], key=lambda r: -r["usable"])
    names = [r["name"] for r in langs]
    harv = np.array([r["harvested"] for r in langs])
    usab = np.array([r["usable"] for r in langs])
    fig, ax = plt.subplots(2, 2, figsize=(13, 9))

    y = np.arange(len(names))
    a = ax[0, 0]
    a.barh(y, usab, color="#1baf7a", height=0.6, label="Usable (passed both gates)")
    a.barh(y, harv - usab, left=usab, color="#e87ba4", height=0.6, label="Excluded")
    for i, (u, h) in enumerate(zip(usab, harv)):
        a.text(h + harv.max() * 0.01, i, f"{u:,} of {h:,} ({u / h:.0%})", va="center", fontsize=8.5, color=INK2)
    a.set_yticks(y, names)
    a.invert_yaxis()
    a.set_xlim(0, harv.max() * 1.35)
    a.set_xlabel("Books")
    a.set_title(f"A. Harvested vs usable books by language ({corpus['usable']:,} of {corpus['harvested']:,})")
    a.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)

    a = ax[0, 1]
    conf = docs.dropna(subset=["mean_conf"])
    data = [conf.loc[conf["lang_tag"].map(LANG_NAMES) == n, "mean_conf"].to_numpy() for n in names]
    a.boxplot(data, vert=False, positions=y, widths=0.5, showfliers=False, patch_artist=True,
              boxprops=dict(facecolor="#cfe3f7", edgecolor=INK2), medianprops=dict(color=INK, linewidth=1.6),
              whiskerprops=dict(color=MUTED), capprops=dict(color=MUTED))
    for i, d in enumerate(data):
        if len(d):
            a.text(np.median(d), i - 0.36, f"{np.median(d):.1f}", ha="center", fontsize=7.5, color=INK)
    a.axvline(50, color="#e34948", linestyle="--", linewidth=1.4, label="Gate: mean confidence ≥ 50")
    a.set_yticks(y, names)
    a.invert_yaxis()
    a.set_xlabel("Mean Tesseract word confidence per book (box = middle half)")
    a.set_title("B. OCR confidence by language and the quality gate")
    a.legend(loc="upper left")

    a = ax[1, 0]
    usable = docs[docs["usable"] == 1]
    split = usable["split"].value_counts()
    rows = [("Harvested with OCR", len(docs), "#2a78d6"),
            ("Usable (confidence ≥ 50 and ≥ 100 tokens)", len(usable), "#1baf7a"),
            ("Train split (fits everything)", int(split.get("train", 0)), "#eb6834"),
            ("Validation split", int(split.get("val", 0)), "#eda100"),
            ("Test split (used once)", int(split.get("test", 0)), "#6250d6")]
    a.barh(range(len(rows)), [r[1] for r in rows], color=[r[2] for r in rows], height=0.6)
    for i, (_, n, _) in enumerate(rows):
        a.text(n + len(docs) * 0.01, i, f"{n:,}", va="center", fontsize=9, color=INK)
    a.set_yticks(range(len(rows)), [r[0] for r in rows])
    a.invert_yaxis()
    a.set_xlim(0, len(docs) * 1.15)
    a.set_xlabel("Books")
    a.set_title("C. From harvest to the stratified 60 / 20 / 20 splits")

    a = ax[1, 1]
    rel = relevance.copy()
    keep = rel["decision"].str.startswith("keep")
    a.barh(range(len(rel)), rel["missing_pct"], color=np.where(keep, "#1baf7a", "#e34948"), height=0.6)
    for i, (m, d) in enumerate(zip(rel["missing_pct"], rel["decision"])):
        a.text(m + 0.8, i, d, va="center", fontsize=7.5, color=INK2)
    a.set_yticks(range(len(rel)), rel["field"])
    a.invert_yaxis()
    a.set_xlim(0, max(60, rel["missing_pct"].max() * 1.6))
    a.set_xlabel("Missing values (%)   ·   green = kept as a feature, red = dropped")
    a.set_title("D. Variable relevance audit (reports/variable_relevance.csv)")

    fig.suptitle("Dataset: harvest, OCR quality gate, splits and variable audit", fontsize=13, fontweight="bold", y=1.0)
    save(fig, "dataset_preprocessing_summary.png")


# ---------------------------------------------------------------- Fig 3.1
def plot_dfd(study, docs, dims):
    harvested, usable = len(docs), int((docs["usable"] == 1).sum())
    fig, ax = plt.subplots(figsize=(12, 6.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.5)
    ax.axis("off")

    def store(x, y, w, h, label, sid):
        ax.plot([x, x + w], [y + h, y + h], color=INK, lw=1.5)
        ax.plot([x, x + w], [y, y], color=INK, lw=1.5)
        ax.plot([x + 0.5, x + 0.5], [y, y + h], color=INK, lw=1.0)
        ax.text(x + 0.25, y + h / 2, sid, ha="center", va="center", fontweight="bold", fontsize=9)
        ax.text(x + 0.5 + (w - 0.5) / 2, y + h / 2, label, ha="center", va="center", fontsize=8.3)

    def proc(x, y, r, label, num):
        ax.add_patch(patches.Circle((x, y), r, facecolor="#ffffff", edgecolor=INK, lw=1.6, zorder=3))
        ax.plot([x - r * 0.88, x + r * 0.88], [y + r * 0.35, y + r * 0.35], color=AXIS, lw=0.9, zorder=4)
        ax.text(x, y + r * 0.58, num, ha="center", va="center", fontsize=8, fontweight="bold", color="#2a78d6", zorder=5)
        ax.text(x, y - r * 0.12, label, ha="center", va="center", fontsize=7.3, color=INK, zorder=5)

    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", color=INK2, lw=1.3))
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.16, label, ha="center", va="center", fontsize=7, color=MUTED,
                    bbox=dict(boxstyle="square,pad=0.1", fc=SURFACE, ec="none"))

    store(0.4, 4.4, 2.3, 0.9, f"Book text\n({harvested:,} books)", "D1")
    store(0.4, 1.3, 2.3, 0.9, "Catalogue metadata\n(Internet Archive)", "D2")
    store(9.6, 2.8, 2.2, 0.9, f"Feature store\n({dims}-d vectors)", "D3")
    proc(4.2, 4.85, 0.72, "Clean text\nUnicode NFC\nstopwords", "3.1")
    proc(4.2, 1.75, 0.72, "Review fields\nimpute year\nlog scale", "3.2")
    proc(6.2, 3.3, 0.75, "Usability gate\nconf ≥ 50\ntokens ≥ 100", "3.3")
    proc(8.3, 4.75, 0.75, "Vertex AI\n768-d, ≤10 chunks\nof 64 words", "3.4")
    proc(8.3, 1.85, 0.75, "Subtract language\nmean, PCA to\n" + f"{dims}-d", "3.5")
    arrow(2.7, 4.85, 3.48, 4.85, "OCR text")
    arrow(2.7, 1.75, 3.48, 1.75, "metadata")
    arrow(4.92, 4.85, 5.75, 3.85, "clean tokens")
    arrow(4.92, 1.75, 5.75, 2.75, "year, pages, conf")
    arrow(6.95, 3.5, 7.55, 4.5, f"{usable:,} usable")
    arrow(8.3, 4.0, 8.3, 2.6, "768-d book vectors")
    arrow(9.05, 1.85, 9.6, 2.9, "centred vectors")
    excluded = harvested - usable
    ax.annotate("", xy=(6.2, 1.1), xytext=(6.2, 2.55), arrowprops=dict(arrowstyle="->", color="#e34948", lw=1.2, ls="--"))
    ax.text(6.2, 0.75, f"Excluded: {excluded:,} books ({excluded / harvested:.1%})\nlow OCR confidence or too few tokens",
            ha="center", va="center", fontsize=7.5, color="#e34948", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="#fdf2f2", ec="#f8b4b4", lw=0.8))
    ax.set_title("Figure 3.1: DFD Level 2, Process 3.0: cleaning, usability gate, Vertex AI embedding and language centring",
                 fontsize=11, fontweight="bold", pad=12)
    save(fig, "dfd_level2_p3.png")


# ---------------------------------------------------------------- Fig 4.1
def plot_dendrograms(Z, res):
    final = res["hierarchical"]["final"]
    d = pdist(Z, "euclidean")
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    coph = {}
    for a, m in zip(axes.flat, ["ward", "complete", "average", "single"]):
        L = linkage(d, method=m) if m != "ward" else linkage(Z, method="ward")
        coph[m] = float(cophenet(L, d)[0])
        dendrogram(L, truncate_mode="lastp", p=30, ax=a, above_threshold_color=INK2, leaf_font_size=7,
                   color_threshold=L[-(final["k"] - 1), 2] if m == final["linkage"] else 0.7 * L[-1, 2])
        a.grid(False)
        chosen = " (chosen)" if m == final["linkage"] else ""
        a.set_title(f"{m.capitalize()} linkage{chosen}: cophenetic r = {coph[m]:.3f}", fontsize=10)
        a.set_ylabel("Merge distance")
        a.set_xlabel("Last 30 merges (leaf size in brackets)")
    fig.suptitle(f"Hierarchical clustering on {len(Z):,} books ({Z.shape[1]}-d, Euclidean): four linkages",
                 fontsize=12, fontweight="bold", y=0.995)
    save(fig, "hierarchical_4linkage_comparison_dendrograms.png")
    return coph


# ---------------------------------------------------------------- Fig 7.1
def plot_silhouette(res, selection):
    h = res["hierarchical"]
    final = h["final"]
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    for m, color in zip(("ward", "average", "complete"), ("#2a78d6", "#1baf7a", "#eb6834")):
        for metric, style in (("euclidean", "-"), ("cityblock", ":")):
            rows = sorted([r for r in h["grid"] if r["linkage"] == m and r["metric"] == metric
                           and r["silhouette"] is not None], key=lambda r: r["k"])
            if rows:
                ax.plot([r["k"] for r in rows], [r["silhouette"] for r in rows], color=color, marker="o",
                        markersize=4, linestyle=style, label=f"{m}, {metric}")
    ax.scatter([final["k"]], [final["silhouette"]], s=150, facecolor="none", edgecolor="#e34948", linewidth=2.4, zorder=6)
    met = "met" if selection.get("rule_met") else "NOT met"
    ax.annotate(f"Chosen on train books: {final['linkage']}, k = {final['k']}, s = {final['silhouette']:.3f}\n"
                f"script NMI {final['nmi_script']:.3f}, bootstrap ARI {final['boot_median']:.2f} (rule {met})",
                (final["k"], final["silhouette"]), xytext=(40, -70), textcoords="offset points", fontsize=8.3,
                bbox=dict(boxstyle="round,pad=0.3", fc="#fbf5e6", ec="#eda100", lw=0.8),
                arrowprops=dict(arrowstyle="->", color=INK2, lw=1))
    ax.set_xlabel("Number of groups k")
    ax.set_ylabel("Mean silhouette")
    ax.set_title("Silhouette by k for each linkage (all books, final fit)")
    ax.legend(loc="upper right", fontsize=7.5)
    save(fig, "hierarchical_silhouette_linkages_k2_15.png")


# ---------------------------------------------------------------- scree
def plot_scree(embedder):
    ratio = embedder.pca.explained_variance_ratio_ * 100
    n = min(20, len(ratio))
    comps, cum = np.arange(1, n + 1), np.cumsum(ratio)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
    ax[0].bar(comps, ratio[:n], color="#2a78d6", width=0.6)
    ax[0].set_xlabel("Principal component")
    ax[0].set_ylabel("Share of centred 768-d variance (%)")
    ax[0].set_title(f"A. Scree: PC1 {ratio[0]:.1f}%, PC2 {ratio[1]:.1f}%, PC3 {ratio[2]:.1f}%")
    ax[1].plot(np.arange(1, len(ratio) + 1), cum, color="#1baf7a")
    ax[1].scatter([2, 3, len(ratio)], [cum[1], cum[2], cum[-1]], color=INK, s=30, zorder=5)
    for x in (2, 3, len(ratio)):
        ax[1].annotate(f"{cum[x - 1]:.1f}% with {x}", (x, cum[x - 1]), xytext=(6, -12), textcoords="offset points", fontsize=8)
    ax[1].set_xlabel("Components kept")
    ax[1].set_ylabel("Cumulative variance (%)")
    ax[1].set_title(f"B. Cumulative: {len(ratio)} components keep {cum[-1]:.1f}%")
    fig.suptitle("PCA of the language-centred Vertex AI book vectors", fontsize=12, fontweight="bold", y=1.02)
    save(fig, "pca_scree_plot.png")
    return ratio


# ---------------------------------------------------------------- Fig 6.1
def plot_pca(Z, labels, names):
    pca = PCA(n_components=3, random_state=2026).fit(Z)
    c3 = pca.transform(Z)
    var = pca.explained_variance_ratio_ * 100
    fig = plt.figure(figsize=(14, 6))
    a1 = fig.add_subplot(121)
    a2 = fig.add_subplot(122, projection="3d")
    for g in sorted(set(labels)):
        m = labels == g
        col = SERIES[g % len(SERIES)]
        a1.scatter(c3[m, 0], c3[m, 1], s=4, color=col, alpha=0.45, linewidths=0, label=names[g])
        a1.annotate(f"G{g + 1}", (c3[m, 0].mean(), c3[m, 1].mean()), ha="center", va="center", fontweight="bold",
                    bbox=dict(boxstyle="circle,pad=0.2", fc=SURFACE, ec=col, lw=1.5))
        a2.scatter(c3[m, 0], c3[m, 1], c3[m, 2], s=3, color=col, alpha=0.35, linewidths=0)
    a1.set_xlabel(f"PC1 ({var[0]:.1f}%)")
    a1.set_ylabel(f"PC2 ({var[1]:.1f}%)")
    a1.set_title(f"A. 2-D: {var[:2].sum():.1f}% of the variance of the {Z.shape[1]}-d vectors")
    a1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=7.5, markerscale=3)
    a2.set_xlabel(f"PC1 ({var[0]:.1f}%)")
    a2.set_ylabel(f"PC2 ({var[1]:.1f}%)")
    a2.set_zlabel(f"PC3 ({var[2]:.1f}%)")
    a2.set_title(f"B. 3-D: {var.sum():.1f}% (PC3 adds {var[2]:.1f} points)")
    a2.view_init(elev=22, azim=130)
    fig.suptitle(f"PCA of {len(Z):,} books coloured by hierarchical group", fontsize=12, fontweight="bold", y=0.99)
    save(fig, "pca_2d_vs_3d_comparison.png")
    return var


# ---------------------------------------------------------------- Fig 5.1
def plot_dbscan(res):
    db = res["dbscan"]
    final = db["final"]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
    for i, mp in enumerate(sorted({g["min_pts"] for g in db["grid"]})):
        rows = sorted([g for g in db["grid"] if g["min_pts"] == mp], key=lambda g: g["eps"])
        ax[0].plot([g["eps"] for g in rows], [100 * g["noise_share"] for g in rows], color=SERIES[i], marker="o",
                   markersize=4, label=f"MinPts = {mp}")
        ax[1].plot([g["eps"] for g in rows], [g["n_clusters"] for g in rows], color=SERIES[i], marker="o", markersize=4)
    for a in ax:
        a.axvline(final["eps"], color="#e34948", linestyle="--", linewidth=1.2)
    ax[0].set_xlabel("eps")
    ax[0].set_ylabel("Noise (% of books)")
    ax[0].set_title("A. Noise share")
    ax[0].legend(fontsize=8)
    ax[1].set_xlabel("eps")
    ax[1].set_ylabel("Clusters found")
    ax[1].set_title("B. Number of clusters")
    fig.suptitle(f"DBSCAN grid ({len(db['grid'])} settings); dashed = chosen: eps {final['eps']:.3f}, MinPts {final['min_pts']}, "
                 f"{final['n_clusters']} clusters, {final['noise_share']:.1%} noise", fontsize=10.5, fontweight="bold")
    save(fig, "dbscan_sensitivity_grid_300dpi.png")

    fig, a = plt.subplots(figsize=(7.5, 4.0))
    for i, (mp, curve) in enumerate(db["kdist"].items()):
        a.plot(np.arange(len(curve)), curve, color=SERIES[i % len(SERIES)], label=f"MinPts {mp}", linewidth=1.6)
    a.axhline(final["eps"], color="#e34948", linestyle="--", linewidth=1.3,
              label=f"chosen eps {final['eps']:.3f} ({'at' if final.get('eps_is_knee') else 'not at'} the knee)")
    a.set_xlabel("Books ranked by distance to their k-th neighbour")
    a.set_ylabel("k-distance")
    a.set_title("Sorted k-distance curves used to place the eps grid")
    a.legend(fontsize=8)
    save(fig, "dbscan_kdistance_calibration_300dpi.png")


# ---------------------------------------------------------------- Fig 8.1
def plot_side_by_side(res, names):
    xy = np.asarray(res["pca"]["coords"])
    ev = res["pca"]["explained"]
    hl = np.asarray(res["hierarchical"]["labels"])
    dl = np.asarray(res["dbscan"]["labels"])
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 5.0), sharex=True, sharey=True)
    for g in sorted(set(hl)):
        m = hl == g
        ax[0].scatter(xy[m, 0], xy[m, 1], s=4, color=SERIES[g % len(SERIES)], alpha=0.5, linewidths=0, label=names[g])
    ax[0].set_title(f"Hierarchical, {res['hierarchical']['final']['linkage']} linkage, k = {len(set(hl))}")
    ax[0].legend(loc="lower left", fontsize=7, markerscale=3)
    noise = dl == -1
    ax[1].scatter(xy[noise, 0], xy[noise, 1], s=3, color=NOISE, alpha=0.5, linewidths=0, label="noise (-1)")
    for i, c in enumerate(sorted(set(dl) - {-1})):
        m = dl == c
        ax[1].scatter(xy[m, 0], xy[m, 1], s=4, color=SERIES[i % len(SERIES)], alpha=0.6, linewidths=0, label=f"cluster {i + 1}")
    ax[1].set_title(f"DBSCAN: {len(set(dl) - {-1})} clusters, {noise.mean():.1%} noise")
    ax[1].legend(loc="lower left", fontsize=7, markerscale=3)
    for a in ax:
        a.set_xlabel(f"PC1 ({ev[0]:.1%})")
    ax[0].set_ylabel(f"PC2 ({ev[1]:.1%})")
    ari = res.get("comparison", {}).get("ari_non_noise")
    fig.suptitle(f"Same books, two methods (agreement on non-noise books: ARI {ari:.3f})" if ari is not None
                 else "Same books, two methods", fontsize=11.5, fontweight="bold")
    save(fig, "pca_clusters_2d_300dpi.png")


def main():
    study = load("web/data/study.json")
    selection = load("reports/study/selection.json")
    fs = selection["chosen"]
    res = load(f"reports/study/results_{fs}.json")
    test = load("reports/eval/evaluation_test.json")
    docs = pd.read_csv(BASE / "data" / "processed" / "docs.csv", low_memory=False)
    relevance = pd.read_csv(BASE / "reports" / "variable_relevance.csv")
    bundle = joblib.load(BASE / "data" / "model" / "bundle.joblib")
    assert bundle["feature_set"] == fs, f"bundle is {bundle['feature_set']}, study chose {fs}: run the export first"
    Z = np.asarray(bundle["Z"])
    labels = np.asarray(res["hierarchical"]["labels"])
    assert len(labels) == len(Z) == len(res["pca"]["coords"]), "results and bundle cover different books"
    names = group_names(test, int(labels.max()) + 1)

    plot_dataset(study, docs, relevance)
    plot_dfd(study, docs, Z.shape[1])
    coph = plot_dendrograms(Z, res)
    plot_silhouette(res, selection)
    ratio = plot_scree(bundle["transform"])
    var3 = plot_pca(Z, labels, names)
    plot_dbscan(res)
    plot_side_by_side(res, names)
    facts = {"feature_set": fs, "books": int(len(Z)), "dims": int(Z.shape[1]), "cophenetic": coph,
             "pca_embedder_pc123": [float(x) for x in ratio[:3]], "pca_embedder_total": float(ratio.sum()),
             "pca_Z_3d": [float(x) for x in var3], "group_names": names}
    (FIG / "figure_facts.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
    print(json.dumps(facts, indent=2))


if __name__ == "__main__":
    main()
