# API contract

The single source of truth for what the frontend may read. A field not listed here does not exist; a field listed
here is produced by the code named next to it and by nothing else. Errors are FastAPI's `{"detail": "<message>"}`
with the status code shown. `identifier` is an Internet Archive identifier, e.g. `in.ernet.dli.2015.188558`.

Status: **existing** = in `app/main.py` today; **wave 1/2** = to be built (see the plan).

## Existing

| Method and path | Returns | Produced by |
|---|---|---|
| `GET /api/health` | `{status: "ok"\|"no-model", documents: int, feature_set: str\|null, needs_internet: bool, embedding_configured: bool\|null}` | `app/main.py: health` |
| `GET /api/clusters?method=hierarchical\|dbscan` | list of `{cluster, name, size, share, terms[8], script_mix, median_year}` | `app/main.py: clusters` from `web/data/study.json` |
| `GET /api/clusters/{id}?method=` | one group profile (study.json `profiles` entry) plus `name`; 404 if none | `app/main.py: cluster` |
| `GET /api/documents/{identifier}` | bundle `docs` row (`identifier, title, creator, year, era, lang_tag, script, mean_conf, classification, total_pages, url`) plus `hier: int, dbscan: int`; 404 if not in the sample | `app/main.py: document` |
| `GET /api/study` | `web/data/study.json` | `pipeline/export.py` |
| `POST /api/check` (multipart `file` or form `text`, optional `lang`) | see `app/checker.py: check_text`: `status: ok\|caution\|abstain`, `script, tokens, ocr_conf, cautions[], feature_set, feature_name`; on abstain also `message` and nothing below; else `hierarchical{cluster, name, distance, level, spread, runner_up, runner_up_name, runner_up_distance, also_close_to[]}`, `dbscan{cluster, name, nearest_core_distance, eps, in_dense_group}`, `matches[5]{<docs row>, distance, hier, dbscan, shared_terms[]}`, `pca{x, y}`; then `input: scan\|text` and, for scans, `ocr{model, pages, script_detected, preview}`; plus any fields added by check enrichers (below) | `app/main.py: check`, `app/checker.py` |

### Extension points (how wave agents add to the API without editing shared files)

- A feature adds `app/routes/<name>.py` defining `router = APIRouter()`; `app/routes/__init__.py: discover()` finds it
  and `app/main.py` includes it before the static site is mounted.
- A feature that adds a field to `POST /api/check` also defines `enrich_check(checker, result, vector) -> dict`
  (the fields to add). `vector` is the page's feature vector, so no feature embeds the page a second time.
  Enrichers run only when `status` is not `abstain`.

## Feature 1: related books in other scripts (wave 1)

`GET /api/related/{identifier}?k=10&other_scripts=true` → `{identifier, script, k, other_scripts, neighbours:
[{identifier, title, lang_tag, script, distance, url}]}`; 404 if not in the sample; 400 if `k` not in 1–50.
`POST /api/check` gains `related_other_scripts: [{identifier, title, lang_tag, script, distance, url}]` (up to 5).
Produced by `app/routes/related.py` from the bundle's final vectors (`Z`). Evaluation: `reports/features/related.json`
(`{knn_other_script_share: {centred, uncentred}, k, books, split: "train"}`).

## Feature 2: catalogue class suggestion (wave 1)

`GET /api/suggest/{identifier}?k=25` → `{identifier, catalogue_class: str|null, k, suggestions: [{class, score}]
(top 3, scores sum to at most 1; `[]` and `neighbours_used: 0` when no book has a code), basis: "nearest coded books in the model", neighbours_used: int}`.
`POST /api/check` gains `suggested_classes: [{class, score}]` (top 3).
`k` is clamped to 1–200; the book itself is never its own neighbour; 404 for an unknown identifier. Classes are exactly `pipeline/catalogue.py: CLASSES`. Neighbours are every coded book in the shipped model (built on all books). The evaluation instead uses a train-only fit with held-out books, the honest estimate of how well the suggestion generalises. Produced by `app/routes/suggest.py` from bundle
`docs.classification` mapped by `main_class`. Evaluation: `reports/features/suggest.json` (`{top1, top3, top1_ci95,
top3_ci95, baseline_most_common, k, heldout_books, method}`, plus `metric, train_coded_books, split, feature_set`), from `pipeline/suggest_eval.py`.

## Feature 3: scan quality triage (wave 1)

`GET /api/triage/{identifier}` → `{identifier, verdict: "fine"|"re-ocr"|"re-scan", score: float 0–1, reasons:
[str], signals: {mean_conf, text_source, n_tokens, dbscan_noise}}`.
`GET /api/triage?lang=<code>&verdict=<v>&limit=100&offset=0` → `{total, counts: {fine, re-ocr, re-scan},
by_language: {<lang>: {fine, re-ocr, re-scan}}, rows: [the per-book object above plus title, lang_tag]}`.
Triage covers every harvested book, not only the model's usable books (bundle key `triage_books`: `identifier, title,
lang_tag, mean_conf, text_source, n_tokens, usable`); `signals.dbscan_noise` is `null` for books not in the model.
`total` is the number of books matching `lang`/`verdict`; `counts` and `by_language` are over those same books, so
they sum to `total`. `limit` outside 1–500, negative `offset` or an unknown `verdict` → 400.
Rules and thresholds live in `pipeline/triage.py` (constants, documented). Evaluation: `reports/features/triage.json`
(`{auc, auc_ci95, books, signal: "agreement of our OCR with the archive's OCR", rule_thresholds}`).

## Feature 4: batch (wave 2)

`POST /api/batch` with JSON `{identifiers: [str] (1–500)}` or a multipart `file` (one identifier per line or a CSV
with an `identifier` column) → `text/csv` with columns `identifier, title, lang_tag, suggested_class_1, score_1,
suggested_class_2, score_2, suggested_class_3, score_3, triage_verdict, related_other_scripts` (identifiers joined
by `;`), `found` (`yes|no`). Unknown identifiers get `found=no` and empty fields. 400 over 500 identifiers.
Produced by `app/routes/batch.py` calling features 1–3.

## Feature 5: edition / translation finder (wave 2)

`GET /api/editions/{identifier}` → `{identifier, threshold, method, candidates: [{identifier, title, lang_tag,
script, distance, same_title_author: bool, url}]}`. The threshold is calibrated on train books and stored in the
bundle; `method` describes it in words. Produced by `app/routes/editions.py`, `pipeline/editions.py`. Evaluation:
`reports/features/editions.json` (`{precision, recall, precision_ci95, recall_ci95, groups_heldout, threshold}`).

## Static files written by the pipeline

- `web/data/galaxy.json` (wave 2, `pipeline/export.py`): `{n, views: {centred: [[x, y, z]], uncentred: [[x, y, z]]},
  explained: {centred: [3 floats], uncentred: [3 floats]}, books: [{identifier, lang_tag, group}]}`: a 3-D PCA of
  every book's vector with and without language centring, same book order in both views.
- `web/fixtures/*.json`: recorded responses of the endpoints above, from `scripts/make_fixtures.py`.
- `web/data/facts.json` (wave 3, `scripts/deliverable_facts.py`): a copy of `reports/deliverable_facts.json`, for the results panel.
