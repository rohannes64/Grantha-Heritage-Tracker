"""Feature 4: batch lookup (docs/superpowers/specs/api-contract.md). Calls features 1-3; no logic of its own."""
import csv
import io

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.routes import related as related_mod
from app.routes import suggest as suggest_mod
from app.routes import triage as triage_mod

router = APIRouter()
MAX_IDS = 500
COLUMNS = ["identifier", "title", "lang_tag", "suggested_class_1", "score_1", "suggested_class_2", "score_2",
           "suggested_class_3", "score_3", "triage_verdict", "related_other_scripts", "found"]


def parse_identifiers(text: str, is_csv: bool) -> list[str]:
    """Identifiers from a .txt (one per line) or .csv. The BOM is stripped here, once.

    .txt: one identifier per line; blank lines and a first line `identifier` are ignored.
    .csv: if the first row has an `identifier` column (case-insensitive) that column is used and the row is a
    header. Otherwise column 0 is used; a file with more than one column and no `identifier` column has a
    header row, which is skipped; a single unnamed column is all data. Values are stripped, blanks dropped.
    Raises csv.Error on unparseable CSV.
    """
    text = text.lstrip("\ufeff")
    if not is_csv:
        raw = [line.strip() for line in text.splitlines()]
        if raw and raw[0].lower() == "identifier":
            raw = raw[1:]
    else:
        rows = [r for r in csv.reader(io.StringIO(text)) if any(x.strip() for x in r)]
        col = 0
        if rows:
            head = [x.strip().lower() for x in rows[0]]
            if "identifier" in head:
                col, rows = head.index("identifier"), rows[1:]
            elif len(head) > 1:
                rows = rows[1:]
        raw = [r[col].strip() if col < len(r) else "" for r in rows]
    return list(dict.fromkeys(x for x in raw if x))   # blanks dropped, duplicates kept once, order kept


FORMULA_STARTS = ("=", "+", "-", "@", chr(9), chr(13))


def _safe(v):
    """Neutralise spreadsheet formulas in text cells (leading = + - @ tab CR)."""
    return "'" + v if isinstance(v, str) and v[:1] in FORMULA_STARTS else v


def _row(c, identifier: str, books: dict) -> dict:
    row = dict.fromkeys(COLUMNS, "") | {"identifier": identifier, "found": "no"}
    i = c.index.get(identifier)
    book = books.get(identifier)
    if i is None and book is None:
        return row
    row["found"] = "yes"
    src = c.docs[i] if i is not None else book
    row["title"], row["lang_tag"] = src.get("title") or "", src.get("lang_tag") or ""
    if book is not None:
        row["triage_verdict"] = triage_mod._assess(c, book)["verdict"]
    if i is not None:
        for n, s in enumerate(suggest_mod.suggest(c, c.Z[i], exclude=i)["suggestions"][:3], 1):
            row[f"suggested_class_{n}"], row[f"score_{n}"] = s["class"], s["score"]
        row["related_other_scripts"] = ";".join(n["identifier"] for n in related_mod.related(c, i, 5, True))
    return row


def _render(c, ids: list[str]) -> str:
    books = {b["identifier"]: b for b in triage_mod._books(c)}
    out = io.StringIO(newline="")
    w = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows({k: _safe(v) for k, v in _row(c, x, books).items()} for x in ids)
    return out.getvalue()


@router.post("/api/batch")
async def batch(request: Request):
    import app.main as m
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("application/json"):
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "body is not valid JSON")
        ids = body.get("identifiers") if isinstance(body, dict) else None
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            raise HTTPException(400, "identifiers must be a list of strings")
        ids = list(dict.fromkeys(x.strip() for x in ids if x.strip()))
    elif ctype.startswith("multipart/form-data"):
        form = await request.form()
        f = form.get("file")
        if f is None or not hasattr(f, "read"):
            raise HTTPException(400, "send a file field")
        data = await f.read(m.MAX_UPLOAD + 1)
        if len(data) > m.MAX_UPLOAD:
            raise HTTPException(413, "file is larger than 20 MB")
        try:
            text = data.decode("utf-8")
            ids = parse_identifiers(text, (f.filename or "").lower().endswith(".csv"))
        except UnicodeDecodeError:
            raise HTTPException(400, "file must be UTF-8 text")
        except csv.Error:
            raise HTTPException(400, "file is not a valid CSV")
    else:
        raise HTTPException(400, "send JSON {identifiers: [...]} or a multipart file")
    if not ids:
        raise HTTPException(400, "no identifiers given")
    if len(ids) > MAX_IDS:
        raise HTTPException(400, f"at most {MAX_IDS} identifiers per batch")
    body = await run_in_threadpool(_render, m.checker(), ids)
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="grantha_batch.csv"'})
