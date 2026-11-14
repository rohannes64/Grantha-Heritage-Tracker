"""Record real API responses for the frontend to build against (docs/superpowers/specs/api-contract.md).

Calls the actual FastAPI app on the actual model bundle for real sample books (the first book of each language,
by identifier) and the real sample page in web/data/sample_page.json, and writes each response to
web/fixtures/<name>.json with an index of provenance. Endpoints that do not exist yet are skipped, so re-run it
after every backend wave. Nothing here is hand-written: a fixture is exactly what the API returned.

    python scripts/make_fixtures.py
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
OUT = BASE / "web" / "fixtures"

# per-book endpoints, filled with sample identifiers; the API decides which exist
PER_BOOK = ["/api/documents/{id}", "/api/related/{id}", "/api/suggest/{id}", "/api/triage/{id}", "/api/editions/{id}"]
GLOBAL = ["/api/health", "/api/clusters", "/api/clusters?method=dbscan", "/api/clusters/0", "/api/triage?limit=50"]


def sample_ids(docs: list[dict]) -> list[str]:
    """The first book of each language, by identifier: deterministic and spread across scripts."""
    first = {}
    for d in sorted(docs, key=lambda d: d["identifier"]):
        first.setdefault(d.get("lang_tag"), d["identifier"])
    return [first[k] for k in sorted(first, key=str)]


def requests_for(docs: list[dict], sample_page: dict | None) -> list[tuple[str, str, str, dict]]:
    reqs = [(f"get_{p.strip('/').replace('/', '_').replace('?', '__').replace('=', '-')}", "GET", p, {}) for p in GLOBAL]
    for ident in sample_ids(docs):
        for tpl in PER_BOOK:
            path = tpl.format(id=ident)
            reqs.append((f"get_{tpl.split('/')[2]}__{ident}", "GET", path, {}))
    if sample_page and sample_page.get("text"):
        reqs.append((f"post_check__{sample_page.get('identifier', 'sample')}", "POST", "/api/check",
                     {"data": {"text": sample_page["text"], "lang": sample_page.get("lang") or "auto"}}))
    return reqs


def record(client, requests, out: Path, provenance: dict) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    index = {"generated_by": "scripts/make_fixtures.py", **provenance, "fixtures": {}}
    for name, method, path, kwargs in requests:
        r = client.request(method, path, **kwargs)
        if r.status_code == 404 and r.json().get("detail") == "Not Found":
            continue                       # the endpoint is not built yet
        ctype = r.headers.get("content-type", "")
        body = r.json() if "json" in ctype else r.text
        (out / f"{name}.json").write_text(json.dumps({"status": r.status_code, "body": body}, ensure_ascii=False,
                                                     indent=1), encoding="utf-8")
        index["fixtures"][name] = {"method": method, "path": path, "status": r.status_code}
    (out / "_index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return index


def main() -> None:
    from fastapi.testclient import TestClient
    from app import main as app_main
    bundle = Path(app_main.BUNDLE)
    sample = BASE / "web" / "data" / "sample_page.json"
    with TestClient(app_main.app) as client:
        docs = app_main.checker().docs
        page = json.loads(sample.read_text(encoding="utf-8")) if sample.exists() else None
        prov = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "bundle": str(bundle.relative_to(BASE)) if bundle.is_relative_to(BASE) else str(bundle),
                "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
                "feature_set": app_main.checker().b["feature_set"]}
        idx = record(client, requests_for(docs, page), OUT, prov)
    print(f"recorded {len(idx['fixtures'])} fixtures into {OUT}")


if __name__ == "__main__":
    main()
