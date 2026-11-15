"""Catalogue class suggestion: the vote, the endpoint, and the held-out evaluation on synthetic arrays."""
import joblib
import numpy as np
import pytest

from pipeline import catalogue, suggest_eval
from tests.test_app import bundle  # noqa: F401  (fixture)

CODES = {"law": "Social sciences | Law", "astronomy": "Natural sciences | Astronomy"}


@pytest.fixture
def client(bundle, tmp_path, monkeypatch):  # noqa: F811
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import app.main as main
    b = dict(bundle)
    b["docs"] = [d | {"classification": CODES.get(d["identifier"].split("-")[0])} for d in bundle["docs"]]
    path = tmp_path / "bundle.joblib"
    joblib.dump(b, path)
    monkeypatch.setattr(main, "BUNDLE", path)
    main.checker.cache_clear()
    yield TestClient(main.app), main
    main.checker.cache_clear()


def test_scores_are_distance_weighted_votes_summing_to_at_most_one():
    d = np.array([1.0, 2.0, 4.0, 0.5])
    out = suggest_eval.vote(d, ["a", "b", "a", None], k=3)
    assert out["neighbours_used"] == 3
    w = 1 / (np.array([1.0, 2.0, 4.0]) + 1e-9)
    assert out["suggestions"][0]["class"] == "a"
    assert out["suggestions"][0]["score"] == pytest.approx((w[0] + w[2]) / w.sum())
    assert sum(s["score"] for s in out["suggestions"]) <= 1 + 1e-9


def test_only_classes_from_catalogue_CLASSES_appear(client):
    c, main = client
    body = c.get("/api/suggest/law-1?k=10").json()
    assert body["suggestions"] and {s["class"] for s in body["suggestions"]} <= set(catalogue.CLASSES)
    assert body["catalogue_class"] == "social sciences" and body["k"] == 10
    assert body["basis"] == "nearest coded books in the model"
    assert body["suggestions"][0]["class"] == "social sciences"
    assert len(body["suggestions"]) <= 3 and sum(s["score"] for s in body["suggestions"]) <= 1 + 1e-9


def test_book_is_not_its_own_neighbour(client):
    from app.routes import suggest
    _, main = client
    ch = main.checker()
    i = ch.index["law-1"]
    z = ch.Z[i]
    assert suggest.suggest(ch, z, k=1)["neighbours_used"] == 1
    # k = all coded books: excluding the book removes exactly one neighbour
    n = sum(catalogue.main_class(d["classification"]) is not None for d in ch.docs)
    assert suggest.suggest(ch, z, k=10 ** 6)["neighbours_used"] == n
    assert suggest.suggest(ch, z, k=10 ** 6, exclude=i)["neighbours_used"] == n - 1


def test_no_coded_neighbours_gives_empty_suggestions(bundle, tmp_path, monkeypatch):  # noqa: F811
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import app.main as main
    b = dict(bundle)
    b["docs"] = [d | {"classification": None} for d in bundle["docs"]]
    path = tmp_path / "bundle.joblib"
    joblib.dump(b, path)
    monkeypatch.setattr(main, "BUNDLE", path)
    main.checker.cache_clear()
    r = TestClient(main.app).get("/api/suggest/law-1")
    main.checker.cache_clear()
    assert r.status_code == 200
    assert r.json()["suggestions"] == [] and r.json()["neighbours_used"] == 0


def test_unknown_identifier_is_404(client):
    assert client[0].get("/api/suggest/nope").status_code == 404


def test_eval_top3_at_least_top1_and_ci_contains_estimate():
    rng = np.random.default_rng(0)
    cls = catalogue.CLASSES[:3]
    centres = rng.normal(size=(3, 5)) * 4
    ytr = [cls[i % 3] for i in range(90)]
    Xtr = np.array([centres[i % 3] for i in range(90)]) + rng.normal(size=(90, 5))
    yte = [cls[i % 3] for i in range(30)] + [None]
    Xte = np.vstack([np.array([centres[i % 3] for i in range(30)]) + rng.normal(size=(30, 5)), np.zeros((1, 5))])
    r = suggest_eval.evaluate(Xtr, ytr, Xte, yte, k=5)
    assert r["heldout_books"] == 30 and r["k"] == 5 and r["method"]
    assert r["top3"] >= r["top1"]
    for key in ("top1", "top3"):
        lo, hi = r[key + "_ci95"]
        assert lo <= r[key] <= hi
    assert 0 <= r["baseline_most_common"] <= 1


def test_route_never_votes_for_the_book_itself(bundle, tmp_path, monkeypatch):  # noqa: F811
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import app.main as main
    b = dict(bundle)
    b["docs"] = [d | {"classification": "Arts" if d["identifier"] == "law-1" else CODES.get(d["identifier"].split("-")[0])}
                 for d in bundle["docs"]]
    path = tmp_path / "bundle.joblib"
    joblib.dump(b, path)
    monkeypatch.setattr(main, "BUNDLE", path)
    main.checker.cache_clear()
    body = TestClient(main.app).get("/api/suggest/law-1").json()
    main.checker.cache_clear()
    assert body["catalogue_class"] == "arts"
    assert "arts" not in [s["class"] for s in body["suggestions"]]


def test_k_is_clamped_and_check_gains_suggested_classes(client):
    from app.routes import suggest
    from tests.test_study import TOPICS
    c, main = client
    assert c.get("/api/suggest/law-1?k=0").json()["k"] == 1
    assert c.get("/api/suggest/law-1?k=9999").json()["k"] == 200
    r = c.post("/api/check", data={"text": (TOPICS["law"] + " ") * 15, "lang": "eng"}).json()
    assert r["suggested_classes"][0]["class"] == "social sciences"


def test_from_study_reads_held_out_books_from_the_holdout_block():
    import pandas as pd
    rng = np.random.default_rng(1)
    cls = catalogue.CLASSES[:2]
    code = {cls[0]: "Religion | x", cls[1]: "Arts | x"}
    tr_ids = [f"t{i}" for i in range(20)]
    ho_ids = [f"v{i}" for i in range(4)] + [f"x{i}" for i in range(6)] + ["x_uncoded"]
    centres = np.array([[5.0, 0, 0], [0, 5.0, 0]])
    lab = lambda ids: [i % 2 for i in range(len(ids))]
    Z = centres[lab(tr_ids)] + rng.normal(size=(20, 3)) * .3
    H = centres[lab(ho_ids)] + rng.normal(size=(len(ho_ids), 3)) * .3
    docs = pd.DataFrame({"identifier": tr_ids + ho_ids,
                         "split": ["train"] * 20 + ["val"] * 4 + ["test"] * 7,
                         "classification": [code[cls[i]] for i in lab(tr_ids)] +
                         [code[cls[i]] for i in lab(ho_ids[:-1])] + [None]}).set_index("identifier")
    feats = {"ids": tr_ids, "fit": "train", "A": {"Z": Z}, "holdout": {"ids": ho_ids, "A": H}}
    st = {"selection": {"chosen": "A"}, "results": {"A": {"hierarchical": {"final": {"metric": "euclidean"}}}}}
    r = suggest_eval.from_study(feats, st, docs, "test")
    assert r["heldout_books"] == 6 and r["metric"] == "euclidean" and r["split"] == "test"
    assert r["top1"] == 1.0
    assert suggest_eval.from_study(feats, st, docs, "val")["heldout_books"] == 4


def test_eval_refuses_zero_heldout_books_and_baseline_ties_are_deterministic():
    X = np.zeros((4, 2))
    with pytest.raises(ValueError):
        suggest_eval.evaluate(X, ["arts"] * 4, X, [None] * 4)
    y = ["religion", "arts", "religion", "arts"]
    assert suggest_eval.evaluate(X + np.arange(4)[:, None], y, X[:2], ["arts", "religion"], k=2)["baseline_most_common"] == 0.5
