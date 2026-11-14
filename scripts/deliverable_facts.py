"""Every number the deck, viva guide and notes quote, gathered from the pipeline's result files.

Writes reports/deliverable_facts.json. The deliverable builders (scratch/build_hallmark_presentation_v2.py,
scratch/generate_viva_guide_pdf.py) read only this file, so a number cannot appear in a deliverable
unless a result file holds it. Run on the machine that has data/ (after the protocol run):

    python scripts/deliverable_facts.py [--compare-dir backup_20261113/reports]   # optional earlier study
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from pipeline import config  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def evaluation(path: Path) -> dict:
    e = load(path)
    t1, t2 = e["T1_upload_check"], e["T2_subject"]
    return {"feature_set": e["feature_set"], "setting": e["setting"], "held_out_books": e["held_out_books"],
            "t1_agreement": t1["agreement"], "t1_chance": t1["chance"], "t1_abstain_rate": t1["abstain_rate"],
            "t1_tagged": (t1.get("tagged") or {}).get("agreement_tagged"), "t1_books": t1.get("books"),
            "t1_left_out_own_pages": t1.get("left_out_own_pages"),
            "t2_accuracy": t2.get("accuracy_groups"), "t2_baseline_script": t2.get("baseline_script_only"),
            "t2_baseline_common": t2.get("baseline_most_common"), "t2_points": t2.get("points_above_best_baseline"),
            "t2_p": t2.get("permutation_p"), "t2_labelled_train": t2.get("labelled_train"),
            "t2_labelled_heldout": t2.get("labelled_heldout"), "group_to_subject": t2.get("group_to_subject", {}),
            "t3_bootstrap": e["T3_bootstrap_median"], "targets": e["targets"], "met": e["met"],
            "t1_agreement_ci95": t1.get("agreement_ci95"), "t2_accuracy_ci95": t2.get("accuracy_groups_ci95"),
            "t2_points_ci95": t2.get("points_above_best_baseline_ci95"),
            "catalogue": {k: v for k, v in e.get("T2_catalogue_exploratory", {}).items()
                          if k in ("accuracy_groups", "baseline_most_common", "baseline_script_only",
                                   "points_above_best_baseline", "permutation_p", "labelled_train", "labelled_heldout",
                                   "accuracy_groups_ci95", "points_above_best_baseline_ci95", "group_to_subject",
                                   "books_with_a_code", "books_mapped", "note")}}


def group_profiles(res: dict, docs: pd.DataFrame, g2s: dict, ids: list[str]) -> list[dict]:
    labels = np.asarray(res["hierarchical"]["labels"])
    assert len(ids) == len(labels), "features.joblib and the study results cover different books"
    sub = docs.loc[ids]
    out = []
    for g in sorted(set(labels)):
        m = labels == g
        mix = sub["lang_tag"][m].value_counts(normalize=True)
        out.append({"group": int(g), "books": int(m.sum()), "share": float(m.mean()),
                    "majority_subject": g2s.get(str(g)),
                    "languages": {k: round(float(v), 3) for k, v in mix.items()},
                    "top_language_share": float(mix.max())})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare-dir", help="reports/ folder of an earlier study to quote for comparison")
    a = ap.parse_args()
    rep = config.REPORTS
    study = load(BASE / "web" / "data" / "study.json")
    sel = load(rep / "study" / "selection.json")
    fs = sel["chosen"]
    res = load(rep / "study" / f"results_{fs}.json")
    docs = pd.read_csv(config.PROCESSED / "docs.csv", low_memory=False).set_index("identifier")
    val, test = evaluation(rep / "eval" / "evaluation_val.json"), evaluation(rep / "eval" / "evaluation_test.json")
    h, d = res["hierarchical"], res["dbscan"]
    usable = docs[docs["usable"] == 1]
    pages = None
    if config.DB_PATH.exists():
        with sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True) as con:
            pages = con.execute("SELECT COUNT(*) FROM pages WHERE text IS NOT NULL").fetchone()[0]
    facts = {
        "corpus": {"harvested": int(len(docs)), "usable": int(len(usable)), "excluded": int(len(docs) - len(usable)),
                   "usable_share": float(len(usable) / len(docs)), "ocr_pages": pages,
                   "by_language": study["corpus"]["by_language"],
                   "splits": {k: int(v) for k, v in usable["split"].value_counts().items()},
                   "text_source": {k: int(v) for k, v in usable["text_source"].value_counts().items()},
                   "languages": len(study["corpus"]["by_language"])},
        "encoder": {"feature_set": fs, "name": res["name"], "dims": res["dims"],
                    "pca_explained": res["explained_variance"]},
        "selection": {"rule_met": sel["rule_met"], "rule": sel["rule"], "chosen_on": sel.get("chosen_on")},
        "hierarchical": {**h["final"], "bootstrap": h["bootstrap_ari"], "neighbours": h.get("neighbours"),
                         "effects": h.get("effects")},
        "distance": {"chosen": res["distance"]["chosen"], "wins": res["distance"]["wins"]},
        "dbscan": {**d["final"], "grid_settings": len(d["grid"]), "bootstrap": d.get("bootstrap_ari"),
                   "min_pts_tried": sorted({g["min_pts"] for g in d["grid"]}),
                   "eps_range": [min(g["eps"] for g in d["grid"]), max(g["eps"] for g in d["grid"])]},
        "hier_vs_dbscan": {k: v for k, v in res.get("comparison", {}).items() if k != "crosstab"},
        "pca": res["pca"]["explained"],
        "extras": {k: v for k, v in res.get("extras", {}).items() if k != "hdbscan"}
                  | {"hdbscan": {k: v for k, v in res.get("extras", {}).get("hdbscan", {}).items() if k != "labels"}},
        "evaluation": {"val": val, "test": test},
        "groups": group_profiles(res, docs, test["group_to_subject"], joblib.load(config.PROCESSED / "features.joblib")["ids"]),
    }
    for name in (f"centring_effect_{fs}.json",):
        if (rep / "study" / name).exists():
            facts["centring_effect"] = load(rep / "study" / name)
    if (rep / "figures" / "figure_facts.json").exists():
        facts["figures"] = load(rep / "figures" / "figure_facts.json")
    if a.compare_dir:
        c = Path(a.compare_dir)
        csel = load(c / "study" / "selection.json")
        facts["comparison_study"] = {"feature_set": csel["chosen"], "selection": csel,
                                     "test": evaluation(c / "eval" / "evaluation_test.json"),
                                     "val": evaluation(c / "eval" / "evaluation_val.json")}
    out = rep / "deliverable_facts.json"
    out.write_text(json.dumps(facts, indent=2, default=float), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
