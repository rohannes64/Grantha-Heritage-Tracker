"""End-to-end check of features + study on a small synthetic corpus with planted topics.
(Synthetic data is used only to test the code; the study itself runs on the real archive sample.)"""
import json

import numpy as np
import pandas as pd

from pipeline import features, study

TOPICS = {
    "law": "court judge law statute contract property inheritance decree appeal witness",
    "astronomy": "star planet orbit moon eclipse comet telescope solar lunar celestial",
    "medicine": "fever disease remedy herb pulse physician dose cure wound patient",
}
HINDI = {"law": "न्यायालय कानून संपत्ति", "astronomy": "ग्रह नक्षत्र सूर्य", "medicine": "रोग औषधि वैद्य"}


def corpus(n_per=40, seed=0):
    rng = np.random.default_rng(seed)
    toks, rows = [], []
    for t, words in TOPICS.items():
        vocab = words.split()
        for i in range(n_per):
            script = "Devanagari" if i % 4 == 0 else "Latin"
            pool = vocab + (HINDI[t].split() if script == "Devanagari" else [])
            doc = list(rng.choice(pool, 150)) + list(rng.choice("common filler word text page".split(), 40))
            toks.append(doc)
            rows.append({"identifier": f"{t}-{i}", "script": script, "era": "1900-1919", "year": 1910.0,
                         "mean_conf": float(rng.uniform(55, 95)), "title": f"{t} {i}",
                         "classification": t.title() if i % 2 else None, "topic": t})
    return toks, pd.DataFrame(rows)


def test_study_end_to_end_recovers_planted_topics():
    toks, docs = corpus()
    lsa = features.TfidfLSA()
    lsa.svd.n_components = 20
    lsa.stop_cap = 0.5   # 3 planted topics: each topic word is in a third of its script's books
    Z, Xw = lsa.fit_transform(toks, docs["script"].tolist())   # script stands in for language here
    assert Z.shape == (len(toks), 20)
    assert np.allclose(np.linalg.norm(Z, axis=1), 1, atol=1e-5)
    # a new document goes through the same transform
    z_new, _ = lsa.transform([toks[0]])
    assert np.allclose(z_new, Z[0], atol=1e-4)

    bundle = {"ids": docs["identifier"].tolist(),
              "A": {"Z": Z, "Xw": Xw, "transform": lsa, "explained_variance": 0.5}}
    res = study.run_feature_set("A", bundle, docs, np.random.default_rng(0))
    h = res["hierarchical"]
    assert h["rule_met"]
    labels = np.array(h["labels"])
    from sklearn.metrics import adjusted_rand_score
    # TF-IDF vocabularies differ by script, so groups split topic x script (the language-split effect
    # the study measures on real data). The selection rule caps how much groups may follow script
    # (NMI <= 0.5), so the chosen groups must each hold one planted topic, while some follow script.
    purity = pd.crosstab(labels, docs["topic"]).max(axis=1).sum() / len(labels)
    assert purity > 0.95
    assert adjusted_rand_score(docs["topic"] + "/" + docs["script"], labels) > 0.8
    assert 0.2 < res["hierarchical"]["effects"]["nmi_script"] <= study.MAX_SCRIPT_NMI
    assert h["bootstrap_ari"]["median"] > 0.8
    assert res["distance"]["chosen"] in ("euclidean", "cityblock")
    assert len(res["dbscan"]["grid"]) >= 3 * len(study.MINPTS)       # brief asks for >= 3 eps/MinPts combos
    assert {r["linkage"] for r in h["grid"]} == {"ward", "average", "complete"}
    assert len(res["pca"]["coords"]) == len(toks)
    terms = {t["term"] for p in h["profiles"] for t in p["terms"][:5]}
    assert terms & set(TOPICS["law"].split()) and terms & set(TOPICS["astronomy"].split())
    res.pop("_models")
    json.loads(json.dumps(study.clean_json(res)))   # browser-safe JSON


def test_stopwords_are_per_language():
    hin = [["है", "राम"]] * 5 + [["है", "ग्रह"]] * 25
    san = [["इति", "वा"]] * 30
    eng = [["the", "law"]] * 30
    toks = hin + san + eng
    langs = ["hin"] * 30 + ["san"] * 30 + ["eng"] * 30
    stop = features.language_stopwords(toks, langs)
    assert "है" in stop and "इति" in stop     # function words of each language, each only 1/3 of the corpus
    assert "the" in stop
    assert "राम" not in stop                    # in 5 of 30 Hindi books: content, kept


def _res(sil, nmi, boot, rule_met):
    return {"hierarchical": {"rule_met": rule_met, "final": {"silhouette": sil}, "effects": {"nmi_script": nmi},
                             "bootstrap_ari": {"median": boot}}}


def test_final_choice_is_highest_silhouette_among_sets_passing_the_rule():
    # A: script groups (high silhouette, fails the rule); B and C pass; C has the higher silhouette.
    r = {"A": _res(0.48, 1.00, 1.0, False), "B": _res(0.11, 0.38, 0.71, True), "C": _res(0.14, 0.30, 0.65, True)}
    sel = study.choose_feature_set(r)
    assert sel["chosen"] == "C" and sel["rule_met"]


def test_final_choice_falls_back_to_lowest_script_dependence_and_says_so():
    r = {"A": _res(0.48, 1.00, 1.0, False), "B": _res(0.11, 0.60, 0.4, False)}
    sel = study.choose_feature_set(r)
    assert sel["chosen"] == "B" and not sel["rule_met"]


def test_pick_hierarchical_skips_settings_that_only_find_script():
    rng = np.random.default_rng(0)
    # two scripts far apart, and within each, two topics close together
    pts, scripts = [], []
    for s, sx in (("Latin", 0.0), ("Devanagari", 10.0)):
        for t, ty in ((0, 0.0), (1, 1.5)):
            pts.append(rng.normal([sx, ty], 0.2, size=(30, 2)))
            scripts += [s] * 30
    Z = np.vstack(pts)
    scripts = np.array(scripts)
    from sklearn.metrics import pairwise_distances
    D = {m: pairwise_distances(Z, metric=m) for m in study.METRICS}
    rows, linkages = study.hierarchical_grid(D, "euclidean")
    best, lab, boot, ok = study.pick_hierarchical(rows, linkages, D, scripts, rng)
    assert best["nmi_script"] <= study.MAX_SCRIPT_NMI or not ok
    assert best["k"] != 2   # k=2 is exactly the script split (and invalid anyway, k >= 3)
