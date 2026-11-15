"""Galaxy data: 3-D PCA of every book with and without per-language centring."""
import json

import numpy as np
import pytest
from sklearn.metrics import silhouette_score

from pipeline import galaxy

LANGS = ["hin", "tam", "ben"]


def synthetic(per=40, dim=24, seed=0):
    """Each language has a large offset (script signal) plus 2 topics with small spread."""
    rng = np.random.default_rng(seed)
    E, lang, groups = [], [], []
    for li, l in enumerate(LANGS):
        offset = rng.normal(size=dim) * 5
        for i in range(per):
            topic = i % 2
            v = offset + (topic - .5) * np.eye(dim)[3 + topic] * 2 + rng.normal(size=dim) * .3
            E.append(v); lang.append(l); groups.append(topic)
    return np.array(E), [f"b{i}" for i in range(len(E))], lang, groups


def test_galaxy_views_have_same_book_order_and_length():
    E, ids, lang, groups = synthetic()
    g = galaxy.build(E, ids, lang, groups)
    assert g["n"] == len(ids)
    assert len(g["views"]["centred"]) == len(g["views"]["uncentred"]) == len(g["books"]) == len(ids)
    assert [b["identifier"] for b in g["books"]] == ids
    assert [b["lang_tag"] for b in g["books"]] == lang
    assert [b["group"] for b in g["books"]] == groups
    assert all(len(p) == 3 for v in g["views"].values() for p in v)


def test_explained_variance_is_three_floats_per_view():
    g = galaxy.build(*synthetic())
    for view in ("centred", "uncentred"):
        ev = g["explained"][view]
        assert len(ev) == 3 and all(isinstance(x, float) and 0 <= x <= 1 for x in ev)
        assert sum(ev) <= 1.0001


def test_uncentred_view_is_more_script_separated():
    E, ids, lang, groups = synthetic()
    g = galaxy.build(E, ids, lang, groups)
    s = {v: silhouette_score(np.array(g["views"][v]), lang) for v in ("centred", "uncentred")}
    assert s["uncentred"] > s["centred"]


def test_centring_uses_each_languages_own_mean():
    E, ids, lang, groups = synthetic()
    g = galaxy.build(E, ids, lang, groups)
    c = np.array(g["views"]["centred"])
    # per-language centring leaves no between-language offset: language means of the view are near the origin
    spread = np.ptp(c, axis=0).max()
    for l in LANGS:
        m = c[np.array(lang) == l].mean(axis=0)
        assert np.abs(m).max() < .2 * spread
    # the means really are per language: mislabelled books (each shifted one place) give a different view
    wrong = galaxy.build(E, ids, lang[1:] + lang[:1], groups)
    assert not np.allclose(wrong["views"]["centred"], c)


def test_output_is_json_with_contract_keys_and_rounding():
    g = galaxy.build(*synthetic())
    assert set(g) == {"n", "views", "explained", "books"}
    assert set(g["views"]) == set(g["explained"]) == {"centred", "uncentred"}
    assert set(g["books"][0]) == {"identifier", "lang_tag", "group"}
    out = json.loads(json.dumps(g))
    assert out == g
    assert all(round(x, 4) == x for p in g["views"]["centred"] for x in p)
    assert isinstance(g["books"][0]["group"], int) and isinstance(g["n"], int)


def test_static_pages_revalidate_but_api_is_untouched():
    from fastapi.testclient import TestClient
    import app.main as main
    client = TestClient(main.app)
    page = client.get("/index.html")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-cache"
    api = client.get("/api/health")
    assert "no-cache" not in api.headers.get("cache-control", "")
