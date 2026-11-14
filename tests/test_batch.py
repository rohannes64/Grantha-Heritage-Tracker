"""Batch endpoint: JSON and file inputs, parsing edge cases, contract column order."""
import csv
import io

import joblib
import pytest

from tests.test_app import bundle  # noqa: F401  (fixture)

COLUMNS = ["identifier", "title", "lang_tag", "suggested_class_1", "score_1", "suggested_class_2", "score_2",
           "suggested_class_3", "score_3", "triage_verdict", "related_other_scripts", "found"]
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


def rows(resp):
    return list(csv.DictReader(io.StringIO(resp.text)))


def test_json_and_file_inputs_give_the_same_csv(client):
    c, _ = client
    ids = ["law-1", "astronomy-1", "nope"]
    a = c.post("/api/batch", json={"identifiers": ids})
    b = c.post("/api/batch", files={"file": ("ids.txt", "\n".join(ids).encode())})
    d = c.post("/api/batch", files={"file": ("ids.csv", ("identifier\n" + "\n".join(ids)).encode())})
    assert a.status_code == b.status_code == d.status_code == 200
    assert a.text == b.text == d.text
    assert a.headers["content-type"].startswith("text/csv") and "utf-8" in a.headers["content-type"]
    assert a.headers["content-disposition"] == 'attachment; filename="grantha_batch.csv"'
    assert [r["identifier"] for r in rows(a)] == ids


def test_header_blank_lines_bom_and_duplicates(client):
    c, _ = client
    raw = "\ufeffidentifier\n\nlaw-1\n\nastronomy-1\nlaw-1\n  \n".encode("utf-8")
    out = rows(c.post("/api/batch", files={"file": ("ids.csv", raw)}))
    assert [r["identifier"] for r in out] == ["law-1", "astronomy-1"]
    assert all(r["found"] == "yes" for r in out)
    # a BOM on a header-less one-column .txt file is stripped too
    out = rows(c.post("/api/batch", files={"file": ("ids.txt", "\ufefflaw-1\nlaw-1\n".encode("utf-8"))}))
    assert [r["identifier"] for r in out] == ["law-1"]
    # a CSV with an identifier column among others
    raw = b"title,identifier\nx,law-1\ny,nope\n"
    assert [r["identifier"] for r in rows(c.post("/api/batch", files={"file": ("a.csv", raw)}))] == ["law-1", "nope"]


def test_unknown_identifier_gets_found_no(client):
    c, _ = client
    out = rows(c.post("/api/batch", json={"identifiers": ["nope", "law-1"]}))
    assert list(out[0].keys()) == COLUMNS
    assert out[0]["found"] == "no"
    assert all(v == "" for k, v in out[0].items() if k not in ("identifier", "found"))
    assert out[1]["found"] == "yes" and out[1]["title"]


def test_over_500_is_400(client):
    c, _ = client
    r = c.post("/api/batch", json={"identifiers": [f"b{i}" for i in range(501)]})
    assert r.status_code == 400 and "500" in r.json()["detail"]
    assert c.post("/api/batch", json={"identifiers": [f"b{i}" for i in range(500)]}).status_code == 200
    assert c.post("/api/batch", json={"identifiers": []}).status_code == 400
    assert c.post("/api/batch", json={"identifiers": "law-1"}).status_code == 400
    assert c.post("/api/batch", content=b"x", headers={"content-type": "text/plain"}).status_code == 400


def test_csv_columns_match_contract_order(client):
    c, main = client
    r = c.post("/api/batch", json={"identifiers": ["law-1"]})
    assert r.text.splitlines()[0].split(",") == COLUMNS
    row = rows(r)[0]
    from app.routes import related, suggest
    ch = main.checker()
    i = ch.index["law-1"]
    want = suggest.suggest(ch, ch.Z[i], exclude=i)["suggestions"]
    assert row["suggested_class_1"] == want[0]["class"] and float(row["score_1"]) == pytest.approx(want[0]["score"])
    rel = related.related(ch, i, 5, True)
    assert row["related_other_scripts"] == ";".join(n["identifier"] for n in rel)
    from app.routes import triage as tr
    assert row["triage_verdict"] == tr._assess(ch, next(b for b in tr._books(ch) if b["identifier"] == "law-1"))["verdict"]
    assert row["lang_tag"] == ch.docs[i]["lang_tag"]


def test_formula_cells_are_neutralised(client, monkeypatch):
    c, main = client
    ch = main.checker()
    ch.docs[ch.index["law-1"]]["title"] = '=HYPERLINK("http://x","a")'
    out = rows(c.post("/api/batch", json={"identifiers": ["law-1", "=1+1", "@x", "-2", "+3"]}))
    assert out[0]["title"] == "'" + '=HYPERLINK("http://x","a")'
    assert [r["identifier"] for r in out[1:]] == ["'=1+1", "'@x", "'-2", "'+3"]
    assert float(out[0]["score_1"]) >= 0   # numbers are not prefixed


def test_oversized_and_malformed_files(client, monkeypatch):
    c, main = client
    assert c.post("/api/batch", files={"file": ("a.csv", b"x" * 200000)}).status_code == 400
    monkeypatch.setattr(main, "MAX_UPLOAD", 100)
    r = c.post("/api/batch", files={"file": ("a.txt", b"law-1\n" * 30)})
    assert r.status_code == 413 and r.json()["detail"] == "file is larger than 20 MB"
    monkeypatch.setattr(main, "MAX_UPLOAD", 20 * 1024 * 1024)
    assert c.post("/api/batch", files={"file": ("a.txt", "é".encode("latin-1"))}).status_code == 400


def test_txt_and_csv_parsing_details(client):
    c, _ = client

    def ids(name, raw):
        return [r["identifier"] for r in rows(c.post("/api/batch", files={"file": (name, raw)}))]
    assert ids("a.txt", b"identifier\n\n law-1 \n\n\nastronomy-1\n") == ["law-1", "astronomy-1"]
    assert ids("a.csv", b"identifier\n\n,\n law-1 \n\nastronomy-1\n") == ["law-1", "astronomy-1"]
    # headered CSV without an identifier column: header skipped, column 0 used
    assert ids("a.csv", b"id,title\nlaw-1,x\n") == ["law-1"]
    # single unnamed column: every row is data
    assert ids("a.csv", b"law-1\nastronomy-1\n") == ["law-1", "astronomy-1"]


def test_suggestions_exclude_the_book_itself(client, monkeypatch):
    from app.routes import suggest
    c, main = client
    seen = []
    real = suggest.suggest

    def spy(ch, z, k=25, exclude=None):
        seen.append(exclude)
        return real(ch, z, k, exclude)
    monkeypatch.setattr(suggest, "suggest", spy)
    c.post("/api/batch", json={"identifiers": ["law-1"]})
    assert seen == [main.checker().index["law-1"]]
