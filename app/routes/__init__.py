"""Feature routes. Each feature is one module here (docs/superpowers/specs/api-contract.md, "Extension points"):

- `router = APIRouter()` with its endpoints, included by app/main.py before the static site;
- optionally `enrich_check(checker, result, vector) -> dict`, the fields it adds to POST /api/check.

Modules whose name starts with "_" are skipped. Adding a feature never edits a shared file.
"""
import importlib
import pkgutil

from fastapi import APIRouter


def discover(package: str = __name__) -> tuple[list[APIRouter], list]:
    pkg = importlib.import_module(package)
    routers, enrichers = [], []
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{info.name}")
        if isinstance(getattr(module, "router", None), APIRouter):
            routers.append(module.router)
        if callable(getattr(module, "enrich_check", None)):
            enrichers.append(module.enrich_check)
    return routers, enrichers
