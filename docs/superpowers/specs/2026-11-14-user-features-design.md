# User features and presentation UI: design

Approved in conversation on 2026-11-14 (features 1–5 and UI views A–F). Implementation is split into waves of
subagents; see `docs/superpowers/plans/2026-11-14-user-features.md`.

## Why

About half of the Digital Library of India books in our sample carry no catalogue classification, and the
"subject" field is mostly the scanning centre's name. Books in different scripts never meet in a subject search,
and an eighth of scans are too poorly read to use. The features turn the clustering study into a catalogue
assistant for an archivist: suggest a class, connect books across scripts, flag bad scans, find other editions,
and do it for a whole list at once. The UI makes that, and the study's main finding (language is the first axis
of multilingual embeddings until it is removed), visible in a presentation.

## Goals, non-goals, anti-goals

- Goals: features 1–5 as API endpoints on the final model; UI views A–F; every number on screen and in the
  deliverables traceable to a result file; each feature evaluated on held-out books with confidence intervals.
- Non-goals: user accounts, editing catalogue records, new harvesting, training any model on labels.
- Anti-goals (a failure even if it works): any invented number, label or example on screen; a demo that shows a
  recorded result as live; a suggestion shown without the evidence it came from.

## Features (backend)

| # | Feature | Computed from | Evaluated by (writes `reports/features/<name>.json`) |
|---|---|---|---|
| 1 | Related books in other scripts | nearest books in the final 100-d space, filtered to other scripts | share of a book's 10 nearest neighbours in another script, centred vs uncentred vectors (train books) |
| 2 | Catalogue class suggestion | classes (`pipeline/catalogue.py`) of the nearest coded train books, distance-weighted | top-1 and top-3 accuracy on held-out coded books, bootstrap 95% CI, against the most-common-class baseline |
| 3 | Scan quality triage | fixed rules on OCR confidence, archive text availability, tokens, DBSCAN noise | AUC of the triage score for low agreement between our OCR and the archive's (pilot books with both) |
| 4 | Batch | wraps 1–3 over a list of identifiers | tests only |
| 5 | Edition / translation finder | very close books, threshold calibrated on train-book title+author matches | precision and recall on held-out title+author groups, with CIs |

Thresholds are fixed on train books before any held-out number is computed, and logged.

## UI (frontend)

Extends the existing site in `web/` (plain JavaScript, its design tokens). Every frontend agent follows the
Hallmark skill (`D:\claude\skills\hallmark\SKILL.md`): its Floor rules, and `scripts/sloplint.mjs --render` must
pass. Views: A catalogue-card check result; B archive galaxy (3D PCA of all books, centred vs uncentred toggle)
plus neighbour ring; C triage dashboard; D edition explorer; E results panel with confidence intervals;
F presenter mode (preloaded sample pages; recorded results labelled as recorded).

## The no-invention contract

1. `docs/superpowers/specs/api-contract.md` defines every endpoint and field; each field names the code that
   produces it.
2. The frontend renders only API responses, `web/data/*.json` written by the pipeline, and `reports/deliverable_facts.json`.
3. `web/fixtures/` holds real responses recorded from the real model by `scripts/make_fixtures.py`; the frontend
   is built and tested against them. Nothing is hand-written into a fixture.
4. `scripts/check_claims.py` also scans the website's visible text and JavaScript string literals.
5. Each wave ends with a code review, the full test suite, the claims check and Hallmark's linter.

## Calls made (mine, open to change)

- Batch is limited to 500 identifiers per request (one request should stay under a minute).
- The galaxy ships as a static file (`web/data/galaxy.json`) written by the export step, not an API call.
- Class suggestion uses the 25 nearest coded train books (`k` is an argument; 25 is the default to evaluate).
