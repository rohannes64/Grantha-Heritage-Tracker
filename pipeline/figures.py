"""Static report figures (PNG) from the study results. The web app draws its own interactive charts.

    python -m pipeline.figures

Colours: validated categorical order (dataviz reference palette), light print surface, thin marks,
one axis per chart, direct labels where there are few series.
"""
import json

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.cluster.hierarchy import dendrogram

from . import config

STUDY = config.REPORTS / "study"
FIG = config.REPORTS / "figures"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
NOISE = "#b9b8b2"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.titlecolor": INK, "legend.frameon": False, "lines.linewidth": 2,
})


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png", dpi=180)
    plt.close(fig)


def silhouette_vs_k(r, fs):
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    grid = r["hierarchical"]["grid"]
    fin = r["hierarchical"]["final"]
    for i, link in enumerate(["ward", "average", "complete"]):
        rows = [g for g in grid if g["linkage"] == link and g["silhouette"] is not None]
        ks = [g["k"] for g in rows]
        ss = [g["silhouette"] for g in rows]
        ax.plot(ks, ss, color=SERIES[i], marker="o", markersize=4, label=f"{link} ({rows[0]['metric']})")
        ax.annotate(link, (ks[-1], ss[-1]), xytext=(4, 0), textcoords="offset points", color=INK2, va="center")
    ax.scatter([fin["k"]], [fin["silhouette"]], s=90, facecolor="none", edgecolor=INK, linewidth=1.5, zorder=5)
    ax.annotate("chosen", (fin["k"], fin["silhouette"]), xytext=(6, 8), textcoords="offset points", color=INK)
    ax.set(xlabel="number of clusters k", ylabel="silhouette", title=f"Hierarchical: silhouette by k ({r['name']})")
    ax.legend(loc="upper right")
    save(fig, f"{fs}_hier_silhouette")


def kdistance(r, fs):
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    for i, (mp, curve) in enumerate(r["dbscan"]["kdist"].items()):
        ax.plot(np.arange(len(curve)), curve, color=SERIES[i], label=f"MinPts {mp}", linewidth=1.6)
    fin = r["dbscan"]["final"]
    ax.axhline(fin["eps"], color=INK2, linewidth=1, linestyle="--")
    ax.annotate(f"chosen eps = {fin['eps']:.3f}", (len(curve) * 0.6, fin["eps"]), xytext=(0, 4),
                textcoords="offset points", color=INK2)
    ax.set(xlabel="books, sorted by distance", ylabel="distance to (MinPts-1)-th neighbour",
           title=f"DBSCAN k-distance curves ({r['name']})")
    ax.legend()
    save(fig, f"{fs}_kdistance")


def dbscan_grid(r, fs):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2))
    grid = r["dbscan"]["grid"]
    for i, mp in enumerate(sorted({g["min_pts"] for g in grid})):
        rows = sorted([g for g in grid if g["min_pts"] == mp], key=lambda g: g["eps"])
        eps = [g["eps"] for g in rows]
        axes[0].plot(eps, [100 * g["noise_share"] for g in rows], color=SERIES[i], marker="o", markersize=4,
                     label=f"MinPts {mp}")
        axes[1].plot(eps, [g["n_clusters"] for g in rows], color=SERIES[i], marker="o", markersize=4)
    axes[0].set(xlabel="eps", ylabel="noise (% of books)", title="Noise share")
    axes[0].axhline(50, color=MUTED, linewidth=1, linestyle=":")
    axes[1].set(xlabel="eps", ylabel="clusters found", title="Clusters found")
    axes[0].legend()
    fig.suptitle(f"DBSCAN parameter grid ({r['name']})", fontsize=10, fontweight="bold", color=INK)
    save(fig, f"{fs}_dbscan_grid")


def pca_side_by_side(r, fs):
    xy = np.array(r["pca"]["coords"])
    ev = r["pca"]["explained"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharex=True, sharey=True)
    for ax, key, title in [(axes[0], "hierarchical", "Hierarchical"), (axes[1], "dbscan", "DBSCAN")]:
        lab = np.array(r[key]["labels"])
        noise = lab == -1
        ax.scatter(xy[noise, 0], xy[noise, 1], s=8, color=NOISE, label="noise", linewidths=0)
        for c in sorted(set(lab) - {-1}):
            m = lab == c
            color = SERIES[c % len(SERIES)]
            ax.scatter(xy[m, 0], xy[m, 1], s=9, color=color, linewidths=0.3, edgecolors=SURFACE)
            cx, cy = xy[m].mean(axis=0)
            ax.annotate(str(c + 1), (cx, cy), color=INK, fontweight="bold", ha="center", va="center",
                        bbox=dict(boxstyle="round,pad=0.2", fc=SURFACE, ec=AXIS, lw=0.6))
        ax.set(title=f"{title} ({len(set(lab) - {-1})} clusters"
                     f"{', ' + format(noise.mean(), '.0%') + ' noise' if noise.any() else ''})",
               xlabel=f"PC1 ({ev[0]:.1%} of variance)")
    axes[0].set_ylabel(f"PC2 ({ev[1]:.1%} of variance)")
    fig.suptitle(f"Both methods on the same PCA projection ({r['name']}); numbers mark cluster centres",
                 fontsize=10, fontweight="bold", color=INK)
    save(fig, f"{fs}_pca_compare")


def dendro(models, r, fs):
    fig, ax = plt.subplots(figsize=(9, 3.6))
    dendrogram(models["linkage"], truncate_mode="lastp", p=30, ax=ax, color_threshold=0,
               above_threshold_color=INK2, leaf_font_size=7)
    ax.grid(False)
    fin = r["hierarchical"]["final"]
    ax.set(title=f"Dendrogram, {fin['linkage']} linkage, last 30 merges ({r['name']})",
           ylabel="merge distance", xlabel="cluster (size in brackets)")
    save(fig, f"{fs}_dendrogram")


def distance_bars(r, fs):
    d = r["distance"]["metrics"]
    crit = ["relative_contrast", "cophenetic_average", "cophenetic_complete", "best_silhouette_average"]
    names = ["relative contrast", "cophenetic (average)", "cophenetic (complete)", "best silhouette (average)"]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    x = np.arange(len(crit))
    for i, (m, label) in enumerate([("euclidean", "Euclidean"), ("cityblock", "Manhattan")]):
        vals = [d[m][c] or 0 for c in crit]
        ax.bar(x + (i - 0.5) * 0.36, vals, width=0.34, color=SERIES[i], label=label)
    ax.set_xticks(x, names)
    ax.set(title=f"Euclidean vs Manhattan ({r['name']}): chosen {r['distance']['chosen'].replace('cityblock', 'Manhattan').title()}")
    ax.legend()
    save(fig, f"{fs}_distance")


def main() -> None:
    study = joblib.load(config.DATA / "processed" / "study.joblib")
    for fs, r in study["results"].items():
        silhouette_vs_k(r, fs)
        kdistance(r, fs)
        dbscan_grid(r, fs)
        pca_side_by_side(r, fs)
        dendro(study["models"][fs], r, fs)
        distance_bars(r, fs)
    print(f"figures written to {FIG}")


if __name__ == "__main__":
    main()
