"""The numbers the written documents quote, read from the result files and nowhere else.

Shared by scripts/build_viva_notes.py, scripts/build_speaker_script.py, scripts/build_readme_results.py and
scripts/build_viva_guide.py. Sources (all written by the pipeline run):

  reports/deliverable_facts.json        corpus, encoder, selection, clustering, DBSCAN, evaluation, groups
  reports/features/*.json               class suggestion, related books, edition finder, scan triage
  reports/eval/evaluation_test.json     cross-check of the held-out test numbers (must equal the facts)
  reports/eval/evaluation_val.json      cross-check of the validation numbers
  reports/study/selection_train.json    cross-check of the setting chosen on train books
  reports/study/encoder_comparison.json which encoders were in the centring comparison (names only)
  web/fixtures/*.json                   recorded app answers shown on the deck (titles and scripts only)

Every number is defined once below with a `# from: <file>:<key path>` comment; the builders use only these
names (and pipeline constants that scripts/check_claims.py also accepts), so a number cannot reach a document
unless a result file holds it. Formatting helpers print numbers in forms check_claims.py recognises.
"""
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


FACTS = load("reports/deliverable_facts.json")
FEAT_DIR = ROOT / "reports" / "features"
FEATURES = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(FEAT_DIR.glob("*.json"))}
EVAL_TEST = load("reports/eval/evaluation_test.json")
EVAL_VAL = load("reports/eval/evaluation_val.json")
SEL_TRAIN = load("reports/study/selection_train.json")
ENCODERS = load("reports/study/encoder_comparison.json")

for _name in ("suggest", "related", "editions", "triage"):
    if _name not in FEATURES:
        raise SystemExit(f"reports/features/{_name}.json is missing: run the feature evaluations first")


# ------------------------------------------------------------------------------------------------ formatting
def n(x) -> str:
    """Whole number with thousands separators: 13358 -> '13,358'."""
    return f"{int(round(x)):,}"


def pct(x, d=1) -> str:
    """Share as a percentage: 0.5299 -> '53.0%'."""
    return f"{100 * x:.{d}f}%"


def pts(x) -> str:
    """Points with a sign: 14.53 -> '+14.5'."""
    return f"{x:+.1f}"


def f2(x) -> str:
    return f"{x:.2f}"


def f3(x) -> str:
    return f"{x:.3f}"


def pct_ci(ci, d=1) -> str:
    return f"{pct(ci[0], d)} to {pct(ci[1], d)}"


def pts_ci(ci) -> str:
    return f"{pts(ci[0])} to {pts(ci[1])}"


def num_ci(ci, fmt=f3) -> str:
    return f"{fmt(ci[0])} to {fmt(ci[1])}"


def met(flag: bool) -> str:
    return "met" if flag else "not met"


# ------------------------------------------------------------------------------------------------ the numbers
F = FACTS
C, ENC, SEL, H, DB = F["corpus"], F["encoder"], F["selection"], F["hierarchical"], F["dbscan"]
T, V = F["evaluation"]["test"], F["evaluation"]["val"]
CE, X = F["centring_effect"], F["extras"]
SUG, REL, ED, TRI = FEATURES["suggest"], FEATURES["related"], FEATURES["editions"], FEATURES["triage"]

R = SimpleNamespace(
    # corpus
    harvested=C["harvested"],                                 # from: deliverable_facts.json:corpus.harvested
    usable=C["usable"],                                       # from: deliverable_facts.json:corpus.usable
    usable_share=C["usable_share"],                           # from: deliverable_facts.json:corpus.usable_share
    excluded=C["excluded"],                                   # from: deliverable_facts.json:corpus.excluded
    excluded_share=1 - C["usable_share"],                     # from: deliverable_facts.json:corpus.usable_share (1 minus)
    ocr_pages=C["ocr_pages"],                                 # from: deliverable_facts.json:corpus.ocr_pages
    languages=C["languages"],                                 # from: deliverable_facts.json:corpus.languages
    by_language=sorted(C["by_language"], key=lambda r: -r["usable"]),   # from: deliverable_facts.json:corpus.by_language[]
    train=C["splits"]["train"],                               # from: deliverable_facts.json:corpus.splits.train
    val=C["splits"]["val"],                                   # from: deliverable_facts.json:corpus.splits.val
    test=C["splits"]["test"],                                 # from: deliverable_facts.json:corpus.splits.test
    text_hocr=C["text_source"]["hocr"],                       # from: deliverable_facts.json:corpus.text_source.hocr
    text_djvu=C["text_source"]["djvu"],                       # from: deliverable_facts.json:corpus.text_source.djvu
    text_tesseract=C["text_source"]["tesseract_pages"],       # from: deliverable_facts.json:corpus.text_source.tesseract_pages
    text_archive=C["text_source"]["hocr"] + C["text_source"]["djvu"],   # from: deliverable_facts.json:corpus.text_source.hocr + .djvu
    classified_books=H["effects"]["classified_books"],        # from: deliverable_facts.json:hierarchical.effects.classified_books
    # encoder and PCA
    encoder=ENC["name"],                                      # from: deliverable_facts.json:encoder.name
    dims=ENC["dims"],                                         # from: deliverable_facts.json:encoder.dims
    pca_kept=ENC["pca_explained"],                            # from: deliverable_facts.json:encoder.pca_explained
    pc1=F["pca"][0],                                          # from: deliverable_facts.json:pca[0]
    pc2=F["pca"][1],                                          # from: deliverable_facts.json:pca[1]
    # centring (train books)
    ce_train_books=CE["train_books"],                         # from: deliverable_facts.json:centring_effect.train_books
    ce_nmi_before=CE["uncentred"]["nmi_script"],              # from: deliverable_facts.json:centring_effect.uncentred.nmi_script
    ce_nmi_after=CE["centred"]["nmi_script"],                 # from: deliverable_facts.json:centring_effect.centred.nmi_script
    ce_knn_before=CE["uncentred"]["knn10_same_script"],       # from: deliverable_facts.json:centring_effect.uncentred.knn10_same_script
    ce_knn_after=CE["centred"]["knn10_same_script"],          # from: deliverable_facts.json:centring_effect.centred.knn10_same_script
    encoders_compared=[e["name"] for e in ENCODERS["encoders"].values()],   # from: study/encoder_comparison.json:encoders[].name
    # selection and hierarchical model
    rule=SEL["rule"],                                         # from: deliverable_facts.json:selection.rule
    rule_met=SEL["rule_met"],                                 # from: deliverable_facts.json:selection.rule_met
    linkage=H["linkage"],                                     # from: deliverable_facts.json:hierarchical.linkage
    metric=H["metric"],                                       # from: deliverable_facts.json:hierarchical.metric
    k=H["k"],                                                 # from: deliverable_facts.json:hierarchical.k
    sil_train=SEL_TRAIN["setting"]["silhouette"],             # from: study/selection_train.json:setting.silhouette
    nmi_train=SEL_TRAIN["setting"]["nmi_script"],             # from: study/selection_train.json:setting.nmi_script
    sil_all=H["silhouette"],                                  # from: deliverable_facts.json:hierarchical.silhouette
    nmi_all=H["nmi_script"],                                  # from: deliverable_facts.json:hierarchical.nmi_script
    ari_script=H["effects"]["ari_script"],                    # from: deliverable_facts.json:hierarchical.effects.ari_script
    nmi_class=H["effects"]["nmi_classification"],             # from: deliverable_facts.json:hierarchical.effects.nmi_classification
    boot_all=H["bootstrap"]["median"],                        # from: deliverable_facts.json:hierarchical.bootstrap.median
    boot_p10=H["bootstrap"]["p10"],                           # from: deliverable_facts.json:hierarchical.bootstrap.p10
    boot_p90=H["bootstrap"]["p90"],                           # from: deliverable_facts.json:hierarchical.bootstrap.p90
    neighbours=H["neighbours"],                               # from: deliverable_facts.json:hierarchical.neighbours[].k, .ari
    largest_share=H["largest_share"],                         # from: deliverable_facts.json:hierarchical.largest_share
    distance_wins=F["distance"]["wins"],                      # from: deliverable_facts.json:distance.wins
    within_script_sil=X["within_script_silhouette"]["weighted_mean"],   # from: deliverable_facts.json:extras.within_script_silhouette.weighted_mean
    hc_books=X["high_conf_refit"]["books"],                   # from: deliverable_facts.json:extras.high_conf_refit.books
    hc_share=X["high_conf_refit"]["share"],                   # from: deliverable_facts.json:extras.high_conf_refit.share
    hc_ari=X["high_conf_refit"]["ari_vs_full"],               # from: deliverable_facts.json:extras.high_conf_refit.ari_vs_full
    hdb_noise=X["hdbscan"]["noise_share"],                    # from: deliverable_facts.json:extras.hdbscan.noise_share
    hdb_clusters=X["hdbscan"]["n_clusters"],                  # from: deliverable_facts.json:extras.hdbscan.n_clusters
    # DBSCAN
    db_eps=DB["eps"],                                         # from: deliverable_facts.json:dbscan.eps
    db_minpts=DB["min_pts"],                                  # from: deliverable_facts.json:dbscan.min_pts
    db_minpts_tried=DB["min_pts_tried"],                      # from: deliverable_facts.json:dbscan.min_pts_tried
    db_eps_range=DB["eps_range"],                             # from: deliverable_facts.json:dbscan.eps_range
    db_settings=DB["grid_settings"],                          # from: deliverable_facts.json:dbscan.grid_settings
    db_clusters=DB["n_clusters"],                             # from: deliverable_facts.json:dbscan.n_clusters
    db_noise=DB["noise_share"],                               # from: deliverable_facts.json:dbscan.noise_share
    db_sil=DB["silhouette"],                                  # from: deliverable_facts.json:dbscan.silhouette
    db_boot=DB["bootstrap"]["median"],                        # from: deliverable_facts.json:dbscan.bootstrap.median
    db_vs_hier=F["hier_vs_dbscan"]["ari_non_noise"],          # from: deliverable_facts.json:hier_vs_dbscan.ari_non_noise
    # groups
    groups=F["groups"],                                       # from: deliverable_facts.json:groups[].books, .majority_subject, .languages
    max_lang_share=max(g["top_language_share"] for g in F["groups"]),   # from: deliverable_facts.json:groups[].top_language_share
    # targets (fixed before the results)
    target_t1=T["targets"]["T1_page_agreement"],              # from: deliverable_facts.json:evaluation.test.targets.T1_page_agreement
    target_t2=T["targets"]["T2_points_above_baseline"],       # from: deliverable_facts.json:evaluation.test.targets.T2_points_above_baseline
    target_t3=T["targets"]["T3_bootstrap_ari"],               # from: deliverable_facts.json:evaluation.test.targets.T3_bootstrap_ari
    met_t1=T["met"]["T1"],                                    # from: deliverable_facts.json:evaluation.test.met.T1
    met_t2=T["met"]["T2"],                                    # from: deliverable_facts.json:evaluation.test.met.T2
    met_t3=T["met"]["T3"],                                    # from: deliverable_facts.json:evaluation.test.met.T3
    # T1 page check
    t1=T["t1_agreement"],                                     # from: deliverable_facts.json:evaluation.test.t1_agreement
    t1_ci=T["t1_agreement_ci95"],                             # from: deliverable_facts.json:evaluation.test.t1_agreement_ci95
    t1_chance=T["t1_chance"],                                 # from: deliverable_facts.json:evaluation.test.t1_chance
    t1_abstain=T["t1_abstain_rate"],                          # from: deliverable_facts.json:evaluation.test.t1_abstain_rate
    t1_tagged=T["t1_tagged"],                                 # from: deliverable_facts.json:evaluation.test.t1_tagged
    t1_books=T["t1_books"],                                   # from: deliverable_facts.json:evaluation.test.t1_books
    t1_val=V["t1_agreement"],                                 # from: deliverable_facts.json:evaluation.val.t1_agreement
    t1_val_ci=V["t1_agreement_ci95"],                         # from: deliverable_facts.json:evaluation.val.t1_agreement_ci95
    # T2 subject
    t2_acc=T["t2_accuracy"],                                  # from: deliverable_facts.json:evaluation.test.t2_accuracy
    t2_acc_ci=T["t2_accuracy_ci95"],                          # from: deliverable_facts.json:evaluation.test.t2_accuracy_ci95
    t2_script=T["t2_baseline_script"],                        # from: deliverable_facts.json:evaluation.test.t2_baseline_script
    t2_common=T["t2_baseline_common"],                        # from: deliverable_facts.json:evaluation.test.t2_baseline_common
    t2_points=T["t2_points"],                                 # from: deliverable_facts.json:evaluation.test.t2_points
    t2_points_ci=T["t2_points_ci95"],                         # from: deliverable_facts.json:evaluation.test.t2_points_ci95
    t2_p=T["t2_p"],                                           # from: deliverable_facts.json:evaluation.test.t2_p
    t2_train_labels=T["t2_labelled_train"],                   # from: deliverable_facts.json:evaluation.test.t2_labelled_train
    t2_test_labels=T["t2_labelled_heldout"],                  # from: deliverable_facts.json:evaluation.test.t2_labelled_heldout
    t2_val_acc=V["t2_accuracy"],                              # from: deliverable_facts.json:evaluation.val.t2_accuracy
    t2_val_script=V["t2_baseline_script"],                    # from: deliverable_facts.json:evaluation.val.t2_baseline_script
    t2_val_points=V["t2_points"],                             # from: deliverable_facts.json:evaluation.val.t2_points
    t2_val_points_ci=V["t2_points_ci95"],                     # from: deliverable_facts.json:evaluation.val.t2_points_ci95
    t2_val_p=V["t2_p"],                                       # from: deliverable_facts.json:evaluation.val.t2_p
    t2_val_labels=V["t2_labelled_heldout"],                   # from: deliverable_facts.json:evaluation.val.t2_labelled_heldout
    # T3 stability
    t3=T["t3_bootstrap"],                                     # from: deliverable_facts.json:evaluation.test.t3_bootstrap
    # exploratory: librarians' catalogue classes
    cat_labels=T["catalogue"]["labelled_heldout"],            # from: deliverable_facts.json:evaluation.test.catalogue.labelled_heldout
    cat_acc=T["catalogue"]["accuracy_groups"],                # from: deliverable_facts.json:evaluation.test.catalogue.accuracy_groups
    cat_common=T["catalogue"]["baseline_most_common"],        # from: deliverable_facts.json:evaluation.test.catalogue.baseline_most_common
    cat_script=T["catalogue"]["baseline_script_only"],        # from: deliverable_facts.json:evaluation.test.catalogue.baseline_script_only
    cat_points=T["catalogue"]["points_above_best_baseline"],  # from: deliverable_facts.json:evaluation.test.catalogue.points_above_best_baseline
    cat_points_ci=T["catalogue"]["points_above_best_baseline_ci95"],   # from: deliverable_facts.json:evaluation.test.catalogue.points_above_best_baseline_ci95
    cat_subject=sorted(set(T["catalogue"]["group_to_subject"].values())),   # from: deliverable_facts.json:evaluation.test.catalogue.group_to_subject
    # feature: class suggestion
    sug_top1=SUG["top1"],                                     # from: features/suggest.json:top1
    sug_top1_ci=SUG["top1_ci95"],                             # from: features/suggest.json:top1_ci95
    sug_top3=SUG["top3"],                                     # from: features/suggest.json:top3
    sug_top3_ci=SUG["top3_ci95"],                             # from: features/suggest.json:top3_ci95
    sug_base=SUG["baseline_most_common"],                     # from: features/suggest.json:baseline_most_common
    sug_k=SUG["k"],                                           # from: features/suggest.json:k
    sug_heldout=SUG["heldout_books"],                         # from: features/suggest.json:heldout_books
    sug_train=SUG["train_coded_books"],                       # from: features/suggest.json:train_coded_books
    # feature: related books across scripts
    rel_centred=REL["knn_other_script_share"]["centred"],     # from: features/related.json:knn_other_script_share.centred
    rel_uncentred=REL["knn_other_script_share"]["uncentred"],  # from: features/related.json:knn_other_script_share.uncentred
    rel_k=REL["k"],                                           # from: features/related.json:k
    rel_books=REL["books"],                                   # from: features/related.json:books
    # feature: edition finder
    ed_precision=ED["precision"],                             # from: features/editions.json:precision
    ed_precision_ci=ED["precision_ci95"],                     # from: features/editions.json:precision_ci95
    ed_recall=ED["recall"],                                   # from: features/editions.json:recall
    ed_recall_ci=ED["recall_ci95"],                           # from: features/editions.json:recall_ci95
    ed_groups=ED["groups_heldout"],                           # from: features/editions.json:groups_heldout
    ed_threshold=ED["threshold"],                             # from: features/editions.json:threshold
    ed_heldout=ED["heldout_books"],                           # from: features/editions.json:heldout_books
    # feature: scan triage
    tri_auc=TRI["auc"],                                       # from: features/triage.json:auc
    tri_auc_ci=TRI["auc_ci95"],                               # from: features/triage.json:auc_ci95
    tri_books=TRI["books"],                                   # from: features/triage.json:books
    tri_weights=TRI["rule_thresholds"]["weights"],            # from: features/triage.json:rule_thresholds.weights
)

R.best_base = max(R.t2_script, R.t2_common)                   # from: deliverable_facts.json:evaluation.test.t2_baseline_* (larger)
R.best_base_name = "guessing from the script alone" if R.t2_script >= R.t2_common else "always guessing the most common subject"
R.cat_best = max(R.cat_script, R.cat_common)                  # from: deliverable_facts.json:evaluation.test.catalogue.baseline_* (larger)
R.telugu = next(r for r in C["by_language"] if r["name"] == "Telugu")   # from: deliverable_facts.json:corpus.by_language[Telugu]
R.telugu_share = R.telugu["usable"] / R.telugu["harvested"]   # from: deliverable_facts.json:corpus.by_language[Telugu].usable / .harvested
R.n_met = sum([R.met_t1, R.met_t2, R.met_t3])                 # from: deliverable_facts.json:evaluation.test.met


def group_languages(g, top=3) -> str:
    """'eng 19%, ben 16%, hin 13%' for a group's largest language shares."""
    return ", ".join(f"{lang} {100 * v:.0f}%" for lang, v in sorted(g["languages"].items(), key=lambda kv: -kv[1])[:top])


def _close(a, b, tol=1e-9) -> bool:
    return abs(float(a) - float(b)) <= tol


def cross_check() -> None:
    """The facts file must say what the evaluation and selection files say; stop if a stale copy slipped in."""
    tt, vt = EVAL_TEST["T2_subject"], EVAL_VAL["T2_subject"]
    pairs = [(R.t2_acc, tt["accuracy_groups"]), (R.t2_points, tt["points_above_best_baseline"]), (R.t2_p, tt["permutation_p"]),
             (R.t1, EVAL_TEST["T1_upload_check"]["agreement"]), (R.t3, EVAL_TEST["T3_bootstrap_median"]),
             (R.t2_val_points, vt["points_above_best_baseline"]), (R.t1_val, EVAL_VAL["T1_upload_check"]["agreement"]),
             (R.cat_acc, EVAL_TEST["T2_catalogue_exploratory"]["accuracy_groups"]),
             (R.sil_train, T["setting"]["silhouette"])]
    bad = [(a, b) for a, b in pairs if not _close(a, b)]
    if bad or EVAL_TEST["met"] != T["met"]:
        raise SystemExit(f"reports/deliverable_facts.json disagrees with reports/eval or reports/study: {bad}; "
                         "rerun scripts/deliverable_facts.py")


cross_check()


def fixture(name: str) -> dict:
    """A recorded app answer (web/fixtures/<name>.json); used only for the deck's worked example's titles and scripts."""
    return load(f"web/fixtures/{name}.json")["body"]
