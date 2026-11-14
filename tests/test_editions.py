"""Edition / translation finder: key, calibration, endpoint, evaluation."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from pipeline import editions
from tests.test_app import bundle  # noqa: F401  (fixture)


def D(ident, title, creator=None, **kw):
    return {"identifier": ident, "title": title, "creator": creator, **kw}


def test_title_author_normalisation_groups_transliteration_variants():
    docs = [D("a", "The  Rāmāyaṇa, of Vālmīki!", "Valmiki"), D("b", "the rāmāyaṇa of vālmīki", "  VALMIKI. "),
            D("c", "THE RĀMĀYAṆA — OF VĀLMĪKI", "valmiki"), D("d", "Another Book Entirely", "Someone"),
            D("e", "Lonely title here", None), D("f", "Two words", None), D("g", "Two words", None)]
    g = editions.groups(docs)
    assert sorted(map(sorted, g.values())) == [["a", "b", "c"]]   # singletons and keyless books are left out
    # a missing creator keys on a title of three or more words only
    assert editions.key(D("x", "Two words", None)) is None
    assert editions.key(D("x", "Three whole words", None)) is not None
    assert editions.key(D("x", None, "Someone")) is None


def _toy():
    # rows 0,1 are one edition and sit close; 2,3 another; 4 alone and far
    Z = np.array([[0, 0.0], [0.1, 0], [5, 5], [5, 5.2], [20, 0], [0.5, 0]])
    ids = list("abcdef")
    docs = [D("a", "alpha beta gamma", "x"), D("b", "Alpha, Beta Gamma", "X"), D("c", "delta epsilon zeta", "y"),
            D("d", "delta epsilon zeta", "y"), D("e", "solo title here", "z"), D("f", "other thing again", "w")]
    return Z, ids, docs


def test_threshold_is_calibrated_on_train_groups_only():
    Z, ids, docs = _toy()
    g = editions.groups(docs)
    t = editions.calibrate(Z[:4], {k: v for k, v in g.items()}, ids=ids[:4], metric="euclidean")
    assert 0.1 <= t < 5   # joins a-b (0.1) and c-d (0.2) but not a-c
    # rows outside the training matrix do not influence it: add far-apart "same key" test rows
    Z2 = np.vstack([Z, [[100, 100], [-100, 100]]])
    ids2 = ids + ["g", "h"]
    g2 = dict(g, extra=["g", "h"])
    assert editions.calibrate(Z2[:4], g2, ids=ids2[:4], metric="euclidean") == t
    assert editions.calibrate(Z2, g2, ids=ids2, metric="euclidean") != t


def test_calibrate_without_any_same_key_pair_is_zero():
    assert editions.calibrate(np.eye(3), {}, ids=list("abc"), metric="euclidean") == 0.0


@pytest.fixture()
def client(bundle, tmp_path, monkeypatch):  # noqa: F811
    import app.main as main
    b = dict(bundle)
    b["docs"] = [dict(d) for d in bundle["docs"]]
    from sklearn.metrics import pairwise_distances
    near = np.argsort(pairwise_distances(bundle["Z"][:1], bundle["Z"], metric=bundle["hier"]["metric"])[0])[:3]
    for d in (b["docs"][i] for i in near):   # row 0 and its two nearest books are "the same edition"
        d["title"], d["creator"] = "Shared Edition Title", "Some Author"
    b["editions_threshold"], b["editions_method"] = 1e9, "test method"
    path = tmp_path / "bundle.joblib"
    joblib.dump(b, path)
    monkeypatch.setattr(main, "BUNDLE", path)
    main.checker.cache_clear()
    yield TestClient(main.app)
    main.checker.cache_clear()


def test_candidates_within_threshold_sorted_by_distance(client):
    import app.main as main
    ident = main.checker().docs[0]["identifier"]
    r = client.get(f"/api/editions/{ident}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["identifier"] == ident and body["method"] == "test method" and body["threshold"] == 1e9
    cands = body["candidates"]
    assert 0 < len(cands) <= 10 and ident not in {c["identifier"] for c in cands}
    d = [c["distance"] for c in cands]
    assert d == sorted(d)
    assert set(cands[0]) == {"identifier", "title", "lang_tag", "script", "distance", "same_title_author", "url"}
    main.checker().b["editions_threshold"] = d[0]
    only = client.get(f"/api/editions/{ident}").json()["candidates"]
    assert only and all(c["distance"] <= d[0] for c in only)


def test_same_title_author_flag(client):
    import app.main as main
    docs = main.checker().docs
    ident = docs[0]["identifier"]
    assert docs[0]["title"] == "Shared Edition Title"
    cands = {c["identifier"]: c for c in client.get(f"/api/editions/{ident}").json()["candidates"]}
    shared = {d["identifier"] for d in docs[1:] if d["title"] == "Shared Edition Title"}
    assert len(shared) == 2 and {i for i, c in cands.items() if c["same_title_author"]} == shared
    assert any(not c["same_title_author"] for c in cands.values())


def test_unknown_identifier_is_404(client):
    assert client.get("/api/editions/nope").status_code == 404


def test_old_bundle_without_threshold_gives_no_candidates(bundle, tmp_path, monkeypatch):  # noqa: F811
    import app.main as main
    path = tmp_path / "b.joblib"
    joblib.dump({k: v for k, v in bundle.items() if not k.startswith("editions")}, path)
    monkeypatch.setattr(main, "BUNDLE", path)
    main.checker.cache_clear()
    ident = main.checker().docs[0]["identifier"]
    body = TestClient(main.app).get(f"/api/editions/{ident}").json()
    main.checker.cache_clear()
    assert body["threshold"] is None and body["candidates"] == []


def test_bundle_stores_threshold_and_method(bundle):  # noqa: F811
    assert isinstance(bundle["editions_threshold"], float)
    assert "all" in bundle["editions_method"] and "split" in bundle["editions_method"]


def test_evaluate_reports_heldout_precision_recall(tmp_path):
    rng = np.random.default_rng(1)
    n_groups = 30
    centres = rng.normal(size=(n_groups, 8)) * 10
    Z, docs, splits = [], [], []
    for g in range(n_groups):
        for j in range(2):   # two editions per title, near each other
            Z.append(centres[g] + rng.normal(size=8) * 0.1)
            docs.append(D(f"b{g}-{j}", f"title number {g} here", f"author {g}",
                          split="train" if g < 15 else "test"))
    out = tmp_path / "editions.json"
    res = editions.evaluate(np.array(Z), docs, metric="euclidean", out=out)
    assert json.loads(out.read_text()) == res
    assert res["groups_heldout"] == 15 and res["precision"] == 1.0 and res["recall"] == 1.0
    assert set(res) >= {"precision", "recall", "precision_ci95", "recall_ci95", "groups_heldout", "threshold"}
    lo, hi = res["recall_ci95"]
    assert lo <= res["recall"] <= hi
    cal = editions.calibrate(np.array(Z)[:30], editions.groups(docs[:30]), ids=[d["identifier"] for d in docs[:30]],
                             metric="euclidean")
    assert res["threshold"] == cal   # train rows only


def test_bundle_calibration_uses_train_rows_when_split_exists():
    Z, ids, docs = _toy()
    for d, s in zip(docs, ["train"] * 4 + ["test"] * 2):
        d["split"] = s
    t, method = editions.calibrate_for_bundle(Z, ids, docs, "euclidean")
    assert t == editions.calibrate(Z[:4], editions.groups(docs[:4]), ids=ids[:4], metric="euclidean")
    assert "train books" in method and "split column" not in method


def test_nfkc_matters_for_the_key():
    a = D("a", "Ｒａｍａｙａｎａ　ｏｆ　Valmiki", "Ｖａｌｍｉｋｉ")   # full-width forms
    b = D("b", "Ramayana of Valmiki", "Valmiki")
    assert editions.key(a) == editions.key(b)
    assert editions.groups([a, b]) == {editions.key(a): ["a", "b"]}


def _study(fit):
    rng = np.random.default_rng(3)
    centres = rng.normal(size=(20, 6)) * 10
    docs, tr, te = [], [], []
    for g in range(20):
        for j in range(2):
            docs.append(D(f"b{g}-{j}", f"title number {g} here", f"author {g}", split="train" if g < 12 else "test"))
            (tr if g < 12 else te).append(centres[g] + rng.normal(size=6) * 0.1)
    d = pd.DataFrame(docs).set_index("identifier")
    train_ids = [x["identifier"] for x in docs if x["split"] == "train"]
    hold_ids = [x["identifier"] for x in docs if x["split"] == "test"]
    feats = {"fit": fit, "ids": train_ids, "A": {"Z": np.array(tr)}, "holdout": {"ids": hold_ids, "A": np.array(te)}}
    st = {"fit": fit, "selection": {"chosen": "A"}, "results": {"A": {"hierarchical": {"final": {"metric": "euclidean"}}}}}
    return feats, st, d


def test_from_study_uses_the_holdout_block(tmp_path):
    feats, st, d = _study("train")
    res = editions.from_study(feats, st, d, out=tmp_path / "e.json")
    assert res["groups_heldout"] == 8 and res["heldout_books"] == 16 and res["train_books"] == 24
    assert res["precision"] == 1.0 and res["recall"] == 1.0


def test_main_refuses_a_fit_all_file(monkeypatch):
    feats, st, d = _study("all")
    monkeypatch.setattr(joblib, "load", lambda p: feats if "features" in str(p) else st)
    with pytest.raises(SystemExit):
        editions.main()


def test_nonpositive_threshold_means_not_calibrated(client):
    import app.main as main
    ident = main.checker().docs[0]["identifier"]
    main.checker().b["editions_threshold"] = 0.0
    body = client.get(f"/api/editions/{ident}").json()
    assert body["threshold"] is None and body["candidates"] == []


def test_bootstrap_resamples_groups_not_books(tmp_path):
    # held-out: one 6-book edition group (found perfectly) and 6 ungrouped decoys far from everything
    rng = np.random.default_rng(0)
    docs, Z = [], []
    for g in range(10):
        for j in range(2):
            docs.append(D(f"t{g}-{j}", f"train title {g} words", f"x{g}", split="train"))
            Z.append(rng.normal(size=4) * .01 + 50 * g)
    for j in range(6):
        docs.append(D(f"g{j}", "big edition title here", "a", split="test"))
        Z.append(rng.normal(size=4) * .01 - 500)
    res = editions.evaluate(np.array(Z), docs, metric="euclidean", out=tmp_path / "e.json")
    assert res["groups_heldout"] == 1 and res["recall"] == 1.0 and res["recall_ci95"] == [1.0, 1.0]


def test_bootstrap_resamples_groups_and_matches_a_hand_cluster_bootstrap(tmp_path):
    from pipeline import config
    from pipeline.evaluate import N_CI, interval
    rng = np.random.default_rng(0)
    docs, Z = [], []
    for g in range(10):   # train: editions 0.01 apart, titles 50 apart -> threshold in between
        for j in range(2):
            docs.append(D(f"t{g}-{j}", f"train title {g} words", f"x{g}", split="train"))
            Z.append(rng.normal(size=4) * .01 + 50 * g)
    for j in range(8):    # held-out: one big edition group, all found
        docs.append(D(f"big{j}", "big edition title here", "a", split="test"))
        Z.append(rng.normal(size=4) * .01 - 5000)
    for s in range(6):    # held-out: small groups whose two books are far apart, none found
        for j in range(2):
            docs.append(D(f"s{s}-{j}", f"small group {s} title", "b", split="test"))
            Z.append(np.array([1000.0 * (s + 1), 100.0 * j, 0, 0]))
    res = editions.evaluate(np.array(Z), docs, metric="euclidean", out=tmp_path / "e.json")
    assert res["groups_heldout"] == 7 and res["recall"] == 56 / 68 and res["precision"] == 1.0

    # per-cluster (candidates, correct, true): the big group, then six small groups
    clusters = np.array([[56, 56, 56]] + [[0, 0, 2]] * 6, dtype=float)
    books = np.array([[7, 7, 7]] * 8 + [[0, 0, 1]] * 12, dtype=float)

    def ci(units, num, den, draw):
        vals = []
        for _ in range(N_CI):
            t = units[draw()].sum(axis=0)
            if t[den]:
                vals.append(t[num] / t[den])
        return interval(vals)

    r = np.random.default_rng(config.SEED)
    draw = lambda: r.integers(0, 7, 7)
    hand_p, hand_r = ci(clusters, 1, 0, draw), ci(clusters, 1, 2, draw)
    assert res["precision_ci95"] == hand_p and res["recall_ci95"] == hand_r
    rb = np.random.default_rng(config.SEED)
    book_r = ci(books, 1, 2, lambda: rb.integers(0, 20, 20))
    assert hand_r[1] - hand_r[0] > book_r[1] - book_r[0]   # groups are not independent: the interval is wider
