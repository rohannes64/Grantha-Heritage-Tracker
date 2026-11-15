"""Related books in other scripts: endpoint, check enrichment and the centring evaluation."""
import json
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from tests.test_app import bundle  # noqa: F401  (fixture)
from tests.test_study import TOPICS


@pytest.fixture()
def client(bundle, tmp_path, monkeypatch):  # noqa: F811
    import app.main as main
    path = tmp_path / "bundle.joblib"
    joblib.dump(bundle, path)
    monkeypatch.setattr(main, "BUNDLE", path)
    main.checker.cache_clear()
    yield TestClient(main.app)
    main.checker.cache_clear()


def test_related_excludes_same_script_when_asked(client):
    import app.main as main
    doc = main.checker().docs[0]
    r = client.get(f"/api/related/{doc['identifier']}", params={"k": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["script"] == doc["script"] and body["neighbours"]
    assert all(n["script"] != doc["script"] for n in body["neighbours"])
    d = [n["distance"] for n in body["neighbours"]]
    assert d == sorted(d)
    assert doc["identifier"] not in {n["identifier"] for n in body["neighbours"]}
    same = client.get(f"/api/related/{doc['identifier']}", params={"other_scripts": "false"}).json()
    names = [n["identifier"] for n in same["neighbours"]]
    assert doc["identifier"] not in names
    assert any(n["script"] == doc["script"] for n in same["neighbours"])
    d = [n["distance"] for n in same["neighbours"]]
    assert d == sorted(d) and d[0] > 0


def test_related_unknown_identifier_is_404(client):
    assert client.get("/api/related/nope").status_code == 404


def test_related_k_out_of_range_is_400(client):
    ident = "law-1"
    for ok in (1, 50):
        assert client.get(f"/api/related/{ident}", params={"k": ok}).status_code == 200
    assert client.get(f"/api/related/{ident}", params={"k": 0}).status_code == 400
    assert client.get(f"/api/related/{ident}", params={"k": 51}).status_code == 400


def test_related_can_be_empty(monkeypatch):
    import app.main as main
    docs = [{"identifier": f"b{i}", "title": "t", "lang_tag": "eng", "script": "Latin", "url": "u"} for i in range(4)]
    stub = SimpleNamespace(Z=np.random.default_rng(0).normal(size=(4, 3)), docs=docs,
                           index={d["identifier"]: i for i, d in enumerate(docs)},
                           b={"hier": {"metric": "euclidean"}})
    monkeypatch.setattr(main, "checker", lambda: stub)
    r = TestClient(main.app).get("/api/related/b0")
    assert r.status_code == 200 and r.json()["neighbours"] == []


def test_check_gains_related_other_scripts(client):
    r = client.post("/api/check", data={"text": (TOPICS["law"] + " ") * 15, "lang": "eng"})
    assert r.status_code == 200, r.text
    rel = r.json()["related_other_scripts"]
    assert 0 < len(rel) <= 5
    assert all(n["script"] != r.json()["script"] for n in rel)
    d = [n["distance"] for n in rel]
    assert d == sorted(d)


def test_related_eval_reports_centred_and_uncentred_share(tmp_path):
    from pipeline import related_eval
    rng = np.random.default_rng(0)
    n, d = 120, 20
    lang = np.array(["eng"] * (n // 2) + ["hin"] * (n // 2))
    offset = {"eng": rng.normal(size=d) * 5, "hin": rng.normal(size=d) * 5}
    E = np.vstack([offset[l] for l in lang]) + rng.normal(size=(n, d))
    script = np.where(lang == "eng", "Latin", "Devanagari")

    def write(folder, E, lang, script, split):
        folder.mkdir()
        ids = [f"b{i}" for i in range(len(E))]
        np.save(folder / "embeddings_raw_X.npy", E)
        (folder / "embeddings_ids_X.json").write_text(json.dumps(ids))
        pd.DataFrame({"identifier": ids, "lang_tag": lang, "split": split, "script": script}).to_csv(
            folder / "docs.csv", index=False)
        return related_eval.run(folder / "embeddings_raw_X.npy", folder / "docs.csv", out=folder / "related.json")

    only = write(tmp_path / "only", E, lang, script, "train")
    # extra val/test books with unrelated vectors must not change anything
    E2 = np.vstack([E, rng.normal(size=(40, d)) * 20])
    lang2 = np.concatenate([lang, ["eng"] * 20 + ["hin"] * 20])
    script2 = np.concatenate([script, ["Latin"] * 20 + ["Devanagari"] * 20])
    split2 = ["train"] * n + ["val"] * 20 + ["test"] * 20
    out = write(tmp_path / "mixed", E2, lang2, script2, split2)
    assert out == only and out["books"] == n
    assert json.loads((tmp_path / "mixed" / "related.json").read_text()) == out
    s = out["knn_other_script_share"]
    assert s["centred"] > s["uncentred"]
    assert out["k"] == 10 and out["books"] == n and out["split"] == "train"
