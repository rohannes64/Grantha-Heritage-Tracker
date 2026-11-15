"""Feature routes are discovered from app/routes/, and check enrichers add fields to /api/check."""
import sys

import numpy as np


def test_discover_finds_routers_and_enrichers(tmp_path, monkeypatch):
    pkg = tmp_path / "fake_routes"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "ping.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n"
        "@router.get('/api/ping')\ndef ping():\n    return {'pong': True}\n"
        "def enrich_check(checker, result, vector):\n    return {'ping_seen': len(vector)}\n")
    (pkg / "_private.py").write_text("router = 'not a router'\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    from app import routes
    routers, enrichers = routes.discover("fake_routes")
    assert [r.routes[0].path for r in routers] == ["/api/ping"]
    assert enrichers[0](None, {}, [1, 2, 3]) == {"ping_seen": 3}
    sys.modules.pop("fake_routes", None)


def test_check_runs_enrichers_with_the_page_vector_and_hides_it(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main

    class Stub:
        b = {"feature_set": "A"}

        def check_text(self, raw, script=None, ocr_conf=None, lang=None, keep_vector=False):
            out = {"status": "ok", "script": "Latin"}
            return out | ({"_vector": np.array([0.5, 0.25])} if keep_vector else {})

    monkeypatch.setattr(main, "checker", lambda: Stub())
    monkeypatch.setattr(main, "ENRICHERS", [lambda c, r, v: {"vector_sum": float(np.sum(v))}])
    r = TestClient(main.app).post("/api/check", data={"text": "word " * 30, "lang": "eng"})
    assert r.status_code == 200
    body = r.json()
    assert body["vector_sum"] == 0.75 and "_vector" not in body


def test_enrichers_do_not_run_when_the_checker_abstains(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    called = []

    class Abstain:
        b = {"feature_set": "A"}

        def check_text(self, raw, script=None, ocr_conf=None, lang=None, keep_vector=False):
            return {"status": "abstain", "message": "too little text"}

    monkeypatch.setattr(main, "checker", lambda: Abstain())
    monkeypatch.setattr(main, "ENRICHERS", [lambda c, r, v: called.append(1) or {}])
    r = TestClient(main.app).post("/api/check", data={"text": "word " * 30, "lang": "eng"})
    assert r.status_code == 200 and not called
