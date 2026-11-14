# User Features and Presentation UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Five archivist features (related books across scripts, class suggestion, scan triage, batch, edition finder) as API endpoints on the final model, and six presentation views (A–F) on the existing site, with no number that a result file does not support.

**Architecture:** Each backend feature is one module in `app/routes/` (auto-discovered; optional `enrich_check` adds fields to `POST /api/check`) plus, where it needs offline work, one module in `pipeline/` with its own evaluation writing `reports/features/<name>.json`. Each frontend view is its own page and script in `web/`, built against real recorded responses in `web/fixtures/`.

**Tech Stack:** Python 3.12, FastAPI, numpy/scikit-learn, pytest; plain JavaScript, the site's CSS tokens, three.js (pinned CDN version) for view B only; Node 24 for Hallmark's linter.

**Spec:** `docs/superpowers/specs/2026-11-14-user-features-design.md` and `docs/superpowers/specs/api-contract.md` (field-level source of truth).

## Global Constraints

- Every field returned must be listed in `api-contract.md` with the code that produces it; a task that needs a new field updates the contract in the same commit.
- No number may be typed into a page, script, doc or fixture; `python scripts/check_claims.py` must report `0 unsourced number(s)`.
- Fixtures come only from `python scripts/make_fixtures.py`; never edit a file in `web/fixtures/` by hand.
- Thresholds are fixed on train books before any held-out number is computed; evaluations report bootstrap 95% CIs (`pipeline/evaluate.py: interval`, `N_CI = 2000`).
- Routes read the model with a lazy `import app.main as m; m.checker()` inside the handler (importing `app.main` at module level is circular).
- Frontend: follow `D:\claude\skills\hallmark\SKILL.md` (its Floor is not waivable); run `node D:\claude\skills\hallmark\scripts\sloplint.mjs <page> --render` and fix every FAIL; reuse `web/tokens.css` tokens, never a literal colour or font.
- Shared files (`app/main.py`, `pipeline/export.py`, `web/components.css`, `web/js/common.js`) are edited only by the task that names them below, never by two tasks in one wave.
- Batch limit 500 identifiers; class suggestion default `k = 25`; related default `k = 10`.
- Agents do not commit: "Commit" steps mean "stage nothing, report the files changed"; the orchestrator commits at each wave gate only after the user approves.
- `data/` exists only on the VM (`grantha-worker-eng:/opt/grantha`); locally, tests use the synthetic bundle of `tests/test_app.py`; every `*_eval`/`evaluate` function is run on the VM by the orchestrator at the wave gate.

## Review Focus

- A book with no catalogue code and no coded neighbours within `k`: `/api/suggest` returns `suggestions: []`, not an error (Task 2).
- A book whose only neighbours share its script: `/api/related?other_scripts=true` returns an empty list with 200 (Task 1).
- An identifier not in the sample for every per-book endpoint: 404 with `detail`, never 500 (Tasks 1, 2, 3, 5).
- Batch input with blank lines, duplicates, a BOM or a header row: blank lines and the header ignored, duplicates kept once, `found=no` for unknowns (Task 4).
- The galaxy page on a phone and with reduced motion: no auto-rotation under `prefers-reduced-motion`, readable at 375 px (Task 8).

---

## Wave 1 (parallel: Tasks 1–3; each touches only its own files, except Task 3 which alone owns `pipeline/export.py` in this wave)

### Task 1: Related books in other scripts

**Files:** Create `app/routes/related.py`, `pipeline/related_eval.py`; Test `tests/test_related.py`; Modify `docs/superpowers/specs/api-contract.md` only if a field changes.

**Interfaces:**
- Consumes: `checker().Z` (n×d final vectors), `checker().docs` (list of dicts with `identifier, title, lang_tag, script, url`), `checker().index` (identifier → row), `checker().b["hier"]["metric"]`.
- Produces: `related(checker, i: int, k: int = 10, other_scripts: bool = True) -> list[dict]`; `GET /api/related/{identifier}`; `enrich_check(checker, result, vector) -> {"related_other_scripts": [...]}` (up to 5); `pipeline.related_eval.run(features_path, docs_path) -> dict` writing `reports/features/related.json`.

- [ ] **Step 1: Write the failing tests** in `tests/test_related.py` using the `bundle` fixture pattern of `tests/test_app.py`:
  `test_related_excludes_same_script_when_asked` (every neighbour's `script` differs from the book's); `test_related_unknown_identifier_is_404`; `test_related_k_out_of_range_is_400` (`k=0`, `k=51`); `test_related_can_be_empty` (a corpus where all books share one script → `neighbours == []`, status 200); `test_check_gains_related_other_scripts` (POST `/api/check` → key present, length ≤ 5); `test_related_eval_reports_centred_and_uncentred_share` (on a synthetic matrix where uncentred vectors cluster by script, `knn_other_script_share["centred"] > knn_other_script_share["uncentred"]`).
- [ ] **Step 2: Run** `python -m pytest tests/test_related.py -q` — Expected: FAIL (module missing).
- [ ] **Step 3: Implement** the interfaces above. Distances with the bundle's `hier.metric`; exclude the book itself; neighbours sorted ascending by `distance`. Evaluation on train books only: 10 nearest neighbours, share in another script, for vectors with and without the per-language mean removed (same reduction as `scripts/centring_effect.py`).
- [ ] **Step 4: Run** `python -m pytest -q` — Expected: all pass.
- [ ] **Step 5: Commit** `feat(api): related books in other scripts`.

### Task 2: Catalogue class suggestion

**Files:** Create `app/routes/suggest.py`, `pipeline/suggest_eval.py`; Test `tests/test_suggest.py`.

**Interfaces:**
- Consumes: `pipeline.catalogue.main_class(code) -> str|None`, `pipeline.catalogue.CLASSES`, `checker().Z/docs/index`.
- Produces: `suggest(checker, z: np.ndarray, k: int = 25, exclude: int|None = None) -> dict` returning `{"suggestions": [{"class", "score"}] (≤3, desc), "neighbours_used": int}`; `GET /api/suggest/{identifier}`; `enrich_check(...) -> {"suggested_classes": [...]}`; `pipeline.suggest_eval.run(...) -> dict` writing `reports/features/suggest.json` with `top1, top3, top1_ci95, top3_ci95, baseline_most_common, k, heldout_books, method`.

- [ ] **Step 1: Write the failing tests:** `test_scores_are_distance_weighted_votes_summing_to_at_most_one`; `test_only_classes_from_catalogue_CLASSES_appear`; `test_book_is_not_its_own_neighbour` (`exclude` honoured); `test_no_coded_neighbours_gives_empty_suggestions` (200, `[]`); `test_unknown_identifier_is_404`; `test_eval_top3_at_least_top1_and_ci_contains_estimate`.
- [ ] **Step 2: Run** `python -m pytest tests/test_suggest.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement.** Weight = `1 / (distance + 1e-9)` over the `k` nearest books whose `main_class` is not None; scores are weight shares. Evaluation: features fitted on train books (`data/processed/features.joblib`, `fit == "train"`); neighbours from coded train books only; tested on coded held-out books of the given split; CIs by resampling held-out books.
- [ ] **Step 4: Run** `python -m pytest -q` — Expected: all pass.
- [ ] **Step 5: Commit** `feat(api): catalogue class suggestion`.

### Task 3: Scan quality triage (owns `pipeline/export.py` in wave 1)

**Files:** Create `pipeline/triage.py`, `app/routes/triage.py`; Modify `pipeline/export.py` (add `text_source`, `n_tokens` to each bundle `docs` row); Test `tests/test_triage.py`.

**Interfaces:**
- Consumes: bundle `docs` rows (`mean_conf`, plus the two added fields), `checker().b["dbscan"]["labels"]`.
- Produces: `pipeline.triage.verdict(mean_conf: float|None, text_source: str, n_tokens: int, dbscan_noise: bool) -> dict` returning `{"verdict": "fine"|"re-ocr"|"re-scan", "score": float, "reasons": [str]}`; module constants holding every threshold; `GET /api/triage/{identifier}`, `GET /api/triage` (filters `lang`, `verdict`, `limit` ≤ 500, `offset`); `pipeline.triage.evaluate(...) -> dict` writing `reports/features/triage.json`.

- [ ] **Step 1: Write the failing tests:** `test_low_confidence_without_archive_text_is_rescan`; `test_archive_text_present_keeps_book_out_of_rescan`; `test_reasons_name_each_rule_that_fired`; `test_summary_counts_sum_to_total` (`/api/triage`); `test_limit_over_500_is_400`; `test_bundle_docs_carry_text_source_and_n_tokens` (export path, on the test bundle).
- [ ] **Step 2: Run** `python -m pytest tests/test_triage.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement.** Rules use the usability gate's own thresholds (`preprocess.MIN_DOC_CONF`, `checker.MIN_TOKENS_CONFIDENT`) so no new number is invented; evaluation: AUC of `score` against "agreement with the archive's OCR below its pilot median" on pilot books that have both, with bootstrap CI.
- [ ] **Step 4: Run** `python -m pytest -q` — Expected: all pass.
- [ ] **Step 5: Commit** `feat(api): scan quality triage`.

**Wave 1 gate:** code review (superpowers:requesting-code-review), `python -m pytest -q`, `python scripts/check_claims.py`; then on the VM: export, run each `*_eval`, `scripts/make_fixtures.py`; pull `reports/features/` and `web/fixtures/`.

## Wave 2 (Tasks 4–5 backend, then 6; Tasks 7–8 frontend in parallel with them)

### Task 4: Batch

**Files:** Create `app/routes/batch.py`; Test `tests/test_batch.py`.
**Interfaces:** Consumes `related`, `suggest`, `pipeline.triage.verdict` (Tasks 1–3). Produces `POST /api/batch` per the contract (CSV columns in contract order).

- [ ] **Step 1: Write the failing tests:** `test_json_and_file_inputs_give_the_same_csv`; `test_header_blank_lines_bom_and_duplicates` (Review Focus line 4); `test_unknown_identifier_gets_found_no`; `test_over_500_is_400`; `test_csv_columns_match_contract_order`.
- [ ] **Step 2: Run** — Expected: FAIL. **Step 3: Implement.** **Step 4: Run all tests** — PASS. **Step 5: Commit** `feat(api): batch`.

### Task 5: Edition and translation finder (owns `pipeline/export.py` in wave 2)

**Files:** Create `pipeline/editions.py`, `app/routes/editions.py`; Modify `pipeline/export.py` (store `editions_threshold` and `editions_method` in the bundle); Test `tests/test_editions.py`.
**Interfaces:** Produces `pipeline.editions.groups(docs) -> dict[str, list[str]]` (normalised title+author key → identifiers, groups of ≥ 2), `calibrate(Z_train, groups_train) -> float`, `evaluate(...) -> dict` → `reports/features/editions.json`; `GET /api/editions/{identifier}`.

- [ ] **Step 1: Write the failing tests:** `test_title_author_normalisation_groups_transliteration_variants` (case, punctuation, spaces); `test_threshold_is_calibrated_on_train_groups_only`; `test_candidates_within_threshold_sorted_by_distance`; `test_same_title_author_flag`; `test_unknown_identifier_is_404`.
- [ ] **Step 2–5:** run (FAIL), implement, run all (PASS), commit `feat(api): edition finder`.

### Task 6: Galaxy data (after Task 5; owns `pipeline/export.py`)

**Files:** Modify `pipeline/export.py` (write `web/data/galaxy.json` per the contract); Test `tests/test_galaxy.py`.
- [ ] **Step 1: Write the failing tests:** `test_galaxy_views_have_same_book_order_and_length`; `test_explained_variance_is_three_floats_per_view`; `test_uncentred_view_is_more_script_separated` (synthetic data with script offsets: silhouette by script higher for `uncentred`).
- [ ] **Step 2–5:** run (FAIL), implement (PCA to 3-D of `Z` and of the uncentred reduction), run all (PASS), commit `feat(export): galaxy data`.

### Task 7 (frontend F1): Catalogue-card check result

**Files:** Modify `web/check.html`, `web/js/check.js`; may add `web/check.css`. **Data:** `web/fixtures/post_check__*.json` (shape in contract).
- [ ] **Step 1:** Render the card from a fixture loaded via `?fixture=<name>` in development and from `/api/check` in production; fields: suggested classes with score bars, triage badge, related books grouped by script, editions (when the field exists), existing matches and PCA map.
- [ ] **Step 2:** `node D:\claude\skills\hallmark\scripts\sloplint.mjs web/check.html --render` — Expected: no FAIL.
- [ ] **Step 3:** `python scripts/check_claims.py` — Expected: 0 unsourced. **Step 4:** Commit `feat(web): catalogue card`.

### Task 8 (frontend F2): Archive galaxy and neighbour ring

**Files:** Create `web/galaxy.html`, `web/js/galaxy.js`; **Data:** `web/data/galaxy.json`, `web/fixtures/get_related__*.json`.
- [ ] **Step 1:** three.js point cloud (one point per book, coloured by language); toggle animates between `views.uncentred` and `views.centred`; axis labels show `explained` values; clicking a book shows its ring of related books (fixture/API). Under `prefers-reduced-motion`: no auto-rotation, instant toggle.
- [ ] **Step 2–4:** sloplint (no FAIL), claims check (0), commit `feat(web): archive galaxy`.

## Wave 3 (frontend, parallel)

### Task 9 (F3): Triage dashboard — `web/triage.html`, `web/js/triage.js`; data `/api/triage` fixtures; summary counts, bars per language, sortable table, CSV via `/api/batch`. Steps as Task 7.
### Task 10 (F4): Edition explorer — `web/editions.html`, `web/js/editions.js`; data `get_editions__*` fixtures. Steps as Task 7.
### Task 11 (F5): Results panel and presenter mode — Modify `web/study.html`, `web/js/study.js`, `scripts/deliverable_facts.py` (also write `web/data/facts.json`, a copy of the facts); owns `web/js/common.js` and `web/components.css` in this wave (navigation links to the new pages). Results chart reads `reports/deliverable_facts.json` copied to `web/data/facts.json` by `scripts/deliverable_facts.py`; presenter mode loads `web/fixtures/` and labels each result "recorded" with the fixture's `generated_at`. Steps as Task 7.

## Wave 4: verification

- [ ] `python -m pytest -q` (all pass), `python scripts/check_claims.py` (0), sloplint on every page (no FAIL).
- [ ] break-ui pass on views A–D with worst-case data; fix what breaks.
- [ ] Independent fresh-eyes audit of contract vs code vs pages.
- [ ] Rebuild facts, deck and viva material so the new features' evaluations appear, from `reports/features/*.json` only.
