"""Scan quality triage: the rules, the API, and the bundle fields they read."""
import numpy as np
import pytest

from pipeline import export, features, study, triage
from pipeline.preprocess import MIN_DOC_CONF, MIN_DOC_TOKENS
from tests.test_study import corpus


def test_low_confidence_without_archive_text_is_rescan():
    v = triage.verdict(MIN_DOC_CONF - 1, "tesseract_pages", MIN_DOC_TOKENS * 5, False)
    assert v["verdict"] == "re-scan" and 0 <= v["score"] <= 1


def test_archive_text_present_keeps_book_out_of_rescan():
    for conf in (0.0, None, MIN_DOC_CONF - 1):
        v = triage.verdict(conf, "djvu", MIN_DOC_TOKENS * 5, True)
        assert v["verdict"] != "re-scan"
    assert triage.verdict(0.0, "djvu", MIN_DOC_TOKENS * 5, False)["verdict"] == "fine"
    assert triage.verdict(0.0, "djvu", MIN_DOC_TOKENS - 1, False)["verdict"] == "re-ocr"


def test_reasons_name_each_rule_that_fired():
    none = triage.verdict(MIN_DOC_CONF + 10, "tesseract_pages", MIN_DOC_TOKENS * 5, False)
    assert none["verdict"] == "fine" and none["reasons"] == [] and none["score"] == 0
    all3 = triage.verdict(MIN_DOC_CONF - 1, "tesseract_pages", MIN_DOC_TOKENS - 1, True)
    assert len(all3["reasons"]) == 3
    noise_only = triage.verdict(MIN_DOC_CONF + 10, "tesseract_pages", MIN_DOC_TOKENS * 5, True)
    assert noise_only["verdict"] == "fine" and len(noise_only["reasons"]) == 1
    assert noise_only["score"] > none["score"]
    assert all3["score"] > triage.verdict(MIN_DOC_CONF - 1, "tesseract_pages", MIN_DOC_TOKENS * 5, False)["score"]
    assert all3["score"] <= 1


def test_nan_text_source_and_conf_are_missing_not_archive_text():
    nan = float("nan")
    v = triage.verdict(10.0, nan, MIN_DOC_TOKENS * 5, None)
    assert v["verdict"] == "re-scan"
    v = triage.verdict(nan, nan, MIN_DOC_TOKENS * 5, None)
    assert v["verdict"] == "re-scan" and "missing" in v["reasons"][0]
    assert triage.verdict(10.0, "", MIN_DOC_TOKENS * 5, None)["verdict"] == "re-scan"


def test_evaluate_auc_on_separable_books():
    rows, sims = [], {}
    for i in range(20):
        bad = i % 2 == 0
        rows.append({"identifier": f"b{i}", "mean_conf": 10.0 if bad else 90.0, "text_source": "tesseract_pages",
                     "n_tokens": 1000, "dbscan_noise": None})
        sims[f"b{i}"] = 0.2 + 0.01 * i if bad else 0.8 + 0.01 * i
    r = triage.evaluate(rows, sims)
    assert r["books"] == 20 and r["auc"] == 1.0 and r["auc_ci95"][0] <= r["auc"] <= r["auc_ci95"][1]


@pytest.fixture(scope="module")
def bundle():
    toks, docs = corpus()
    docs["lang_tag"] = np.where(docs["script"] == "Latin", "eng", "hin")
    docs["creator"] = None
    docs["total_pages"] = 100
    n = len(docs)
    docs["text_source"] = ["djvu" if i % 3 == 0 else "tesseract_pages" for i in range(n)]
    docs["n_tokens"] = [50 if i % 5 == 0 else 5000 for i in range(n)]
    docs["mean_conf"] = [20.0 if i % 4 == 0 else 85.0 for i in range(n)]
    docs["usable"] = 1
    lsa = features.TfidfLSA()
    lsa.svd.n_components = 20
    lsa.stop_cap = 0.5
    Z, Xw = lsa.fit_transform(toks, docs["script"].tolist())
    feats = {"ids": docs["identifier"].tolist(), "A": {"Z": Z, "Xw": Xw, "transform": lsa, "explained_variance": .5}}
    res = study.run_feature_set("A", feats, docs, np.random.default_rng(0))
    models = {"A": res.pop("_models")}
    st = {"results": {"A": res}, "models": models, "selection": {"chosen": "A"}}
    return export.build_bundle(feats, st, docs.set_index("identifier"))


def test_bundle_docs_carry_text_source_and_n_tokens(bundle):
    assert all("text_source" in d and "n_tokens" in d for d in bundle["docs"])
    assert {d["text_source"] for d in bundle["docs"]} == {"djvu", "tesseract_pages"}
    assert len(bundle["triage_books"]) == len(bundle["docs"])
    assert {"identifier", "title", "lang_tag", "mean_conf", "text_source", "n_tokens", "usable"} <= set(
        bundle["triage_books"][0])


@pytest.fixture
def client(bundle, tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    import joblib
    from fastapi.testclient import TestClient
    import app.main as main
    path = tmp_path / "bundle.joblib"
    joblib.dump(bundle, path)
    monkeypatch.setattr(main, "BUNDLE", path)
    main.checker.cache_clear()
    yield TestClient(main.app)
    main.checker.cache_clear()


def test_single_book(client, bundle):
    ident = bundle["docs"][0]["identifier"]
    r = client.get(f"/api/triage/{ident}")
    assert r.status_code == 200
    b = r.json()
    assert b["verdict"] in triage.VERDICTS and 0 <= b["score"] <= 1
    assert set(b["signals"]) == {"mean_conf", "text_source", "n_tokens", "dbscan_noise"}
    assert isinstance(b["signals"]["dbscan_noise"], bool)
    assert client.get("/api/triage/nope").status_code == 404


def test_summary_counts_sum_to_total(client, bundle):
    r = client.get("/api/triage?limit=500")
    assert r.status_code == 200
    b = r.json()
    assert b["total"] == len(bundle["triage_books"])
    assert sum(b["counts"].values()) == b["total"]
    assert sum(sum(v.values()) for v in b["by_language"].values()) == b["total"]
    assert len(b["rows"]) == b["total"] and "title" in b["rows"][0] and "lang_tag" in b["rows"][0]
    f = client.get("/api/triage?verdict=re-scan&lang=eng").json()
    assert all(x["verdict"] == "re-scan" and x["lang_tag"] == "eng" for x in f["rows"])
    assert f["total"] == f["counts"]["re-scan"]
    assert len(client.get("/api/triage?limit=3&offset=2").json()["rows"]) == 3


def test_limit_over_500_is_400(client):
    assert client.get("/api/triage?limit=501").status_code == 400
    assert client.get("/api/triage?limit=0").status_code == 400
    assert client.get("/api/triage?offset=-1").status_code == 400
    assert client.get("/api/triage?verdict=bad").status_code == 400


def test_book_outside_the_model_has_null_noise(bundle, tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    import joblib
    from fastapi.testclient import TestClient
    import app.main as main
    b = dict(bundle, triage_books=list(bundle["triage_books"]) + [
        {"identifier": "outside-1", "title": "x", "lang_tag": "eng", "mean_conf": 5.0,
         "text_source": "tesseract_pages", "n_tokens": 10, "usable": False}])
    path = tmp_path / "b.joblib"
    joblib.dump(b, path)
    monkeypatch.setattr(main, "BUNDLE", path)
    main.checker.cache_clear()
    try:
        r = TestClient(main.app).get("/api/triage/outside-1")
        assert r.status_code == 200
        assert r.json()["signals"]["dbscan_noise"] is None and r.json()["verdict"] == "re-scan"
    finally:
        main.checker.cache_clear()


def test_export_with_nan_signals_is_json_serialisable():
    import json
    import pandas as pd
    nan = float("nan")
    docs = pd.DataFrame({"title": ["a", "b"], "lang_tag": ["eng", "hin"], "mean_conf": [nan, 70.0],
                         "text_source": [nan, "djvu"], "n_tokens": [nan, 300], "usable": [0, 1]},
                        index=pd.Index(["x", "y"], name="identifier"))
    books = export.triage_books(docs)
    json.dumps(books, allow_nan=False)
    assert books[0]["mean_conf"] is None and books[0]["text_source"] is None and books[0]["n_tokens"] is None
    assert books[1]["n_tokens"] == 300 and books[1]["usable"] is True
