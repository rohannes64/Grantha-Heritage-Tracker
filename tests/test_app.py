"""The new-record checker and the API, on a model bundle built from the synthetic test corpus
by the same code path as the real export."""
import numpy as np
import pytest

from pipeline import export, features, study
from tests.test_study import TOPICS, corpus


@pytest.fixture(scope="module")
def bundle():
    toks, docs = corpus()
    docs["lang_tag"] = np.where(docs["script"] == "Latin", "eng", "hin")
    docs["creator"] = None
    docs["total_pages"] = 100
    lsa = features.TfidfLSA()
    lsa.svd.n_components = 20
    lsa.stop_cap = 0.5   # 3 planted topics: each topic word is in a third of its script's books
    Z, Xw = lsa.fit_transform(toks, docs["script"].tolist())
    feats = {"ids": docs["identifier"].tolist(), "A": {"Z": Z, "Xw": Xw, "transform": lsa, "explained_variance": .5}}
    res = study.run_feature_set("A", feats, docs, np.random.default_rng(0))
    models = {"A": res.pop("_models")}
    st = {"results": {"A": res}, "models": models, "selection": {"chosen": "A"}}
    return export.build_bundle(feats, st, docs.set_index("identifier"))


def test_checker_places_a_law_text_with_law_books(bundle):
    from app.checker import Checker
    c = Checker(bundle)
    law = (TOPICS["law"] + " ") * 15
    r = c.check_text(law)
    assert r["status"] in ("ok", "caution")
    assert r["script"] == "Latin"
    assert all(m["identifier"].startswith("law-") for m in r["matches"])
    assert r["hierarchical"]["level"] in ("strong", "good", "weak", "outside")
    assert set(r["matches"][0]["shared_terms"]) <= set(TOPICS["law"].split()) | {
        f"{a} {b}" for a in TOPICS["law"].split() for b in TOPICS["law"].split()}


def test_checker_abstains_on_too_little_text(bundle):
    from app.checker import Checker
    r = Checker(bundle).check_text("court judge")
    assert r["status"] == "abstain"


def test_unrelated_text_is_dbscan_noise(bundle):
    from app.checker import Checker
    r = Checker(bundle).check_text(" ".join(["banana mango papaya guava orange grape lemon cherry"] * 10))
    assert r["dbscan"]["cluster"] == -1 and not r["dbscan"]["in_dense_group"]


def test_detect_script():
    from app.checker import detect_script
    assert detect_script("இது தமிழ் உரை with some English") == "Tamil"
    assert detect_script("plain english text") == "Latin"


def test_api(bundle, tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    import joblib
    from fastapi.testclient import TestClient
    path = tmp_path / "bundle.joblib"
    joblib.dump(bundle, path)
    import app.main as main
    monkeypatch.setattr(main, "BUNDLE", path)
    main.checker.cache_clear()
    client = TestClient(main.app)
    assert client.get("/api/health").json()["status"] == "ok"
    r = client.post("/api/check", data={"text": (TOPICS["astronomy"] + " ") * 15, "lang": "eng"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["matches"][0]["identifier"].startswith("astronomy-")
    assert client.post("/api/check", data={"lang": "xx", "text": "a"}).status_code == 400
    assert client.post("/api/check", data={}).status_code == 400
    assert client.get("/api/documents/law-1").json()["identifier"] == "law-1"
    assert client.get("/api/documents/nope").status_code == 404


def test_fixtures_record_exactly_what_the_api_returns(bundle, tmp_path, monkeypatch):
    import json
    import joblib
    import sys
    from fastapi.testclient import TestClient
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"))
    import make_fixtures
    import app.main as main
    path = tmp_path / "bundle.joblib"
    joblib.dump(bundle, path)
    monkeypatch.setattr(main, "BUNDLE", path)
    main.checker.cache_clear()
    client = TestClient(main.app)
    docs = main.checker().docs
    reqs = make_fixtures.requests_for(docs, {"identifier": "page", "text": (TOPICS["law"] + " ") * 15, "lang": "eng"})
    idx = make_fixtures.record(client, reqs, tmp_path / "fx", {"bundle_sha256": "test"})
    ids = make_fixtures.sample_ids(docs)
    assert ids == sorted(ids) or len(set(d["lang_tag"] for d in docs)) == len(ids)
    rec = json.loads((tmp_path / "fx" / f"get_documents__{ids[0]}.json").read_text(encoding="utf-8"))
    assert rec == {"status": 200, "body": client.get(f"/api/documents/{ids[0]}").json()}
    assert "post_check__page" in idx["fixtures"] and "get_api_health" in idx["fixtures"]
    assert not any(k.startswith("get_editions") for k in idx["fixtures"])   # not built yet: skipped, not faked
    main.checker.cache_clear()
