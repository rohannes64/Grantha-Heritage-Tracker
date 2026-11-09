# Accuracy plan: topic groups, not language groups

Written 2026-11-09, after validation round 0 and before any round-1 result. It extends
`docs/evaluation_plan.md`; that plan's rules (splits, train-only fitting, silhouette-based final choice,
targets T1 to T3, test set used once) still hold.

## The problem

The brief asks for grouping **by topic** ("An Unsupervised Grouping Study of Heritage Documents by Topic").
Round 0 (LaBSE, average linkage, k=3) gave groups that mostly follow language:

| Validation, round 0 | Result | Target |
|---|---|---|
| T1 upload page lands with its own book | 0.903 (chance 0.36) | 0.80, met |
| T2 subject accuracy from the groups | 0.409 vs 0.376 for "subject from script" (+3.2 points) | +10 points, **missed** |
| T3 bootstrap ARI | 0.78 | 0.60, met |

Cause: multilingual sentence encoders place each language in its own region of the vector space, so the
largest distances between books are language distances. Clustering finds those first. TF-IDF is worse
(its vocabulary differs per script, so its groups are scripts).

## What stays fixed

- The grouping methods: hierarchical clustering (Ward, average, complete) and DBSCAN, as the brief asks.
- The final setting is chosen by silhouette, under the script and stability limits of the evaluation plan.
- Subject labels never fit or choose clusters; they only measure.
- The test books are not looked at until the final measurement, which happens once.

## Fix 1: remove the language effect (preprocessing)

Each language's mean embedding, computed on the train books only, is subtracted from every book of that
language, and rows are rescaled to unit length. A new upload is centred by the language Tesseract read it
in; pasted text with no language given takes the closest language centre within its script.
Quick check on the cached LaBSE embeddings (validation): script NMI 0.38 to 0.04, subject accuracy
0.41 to 0.50-0.63 depending on k. Implemented in `pipeline/features.py` (`CENTRE_BY_LANGUAGE`), the
evaluation and `app/checker.py`; unit test in `tests/test_study.py`.

Expected side effect, to be explained in the study and report: silhouette drops (about 0.14 to 0.04),
because the old silhouette was mostly the distance between languages.

## Fix 2: choose a better encoder (preprocessing)

Candidates: LaBSE (current), IndicSBERT, BGE-M3. (Multilingual-E5-large was listed and then dropped
before it was run, at Karthik's call, to save time; it was not measured.)
Measure: after centring, the share of labelled train+validation books whose subject matches the majority of
their 7 nearest neighbours (5-fold cross-validation, seed 2026). This is how much topic information the
numbers carry, the ceiling any grouping of them can reach.
Rule: the highest score wins; if the top two are within 2 points, the smaller model wins (the app runs on
a CPU). The winner becomes the embedding feature set; the study compares it with TF-IDF (A), and the
comparison table of all four encoders goes in the study and report.

## Fix 3: more labels for validation decisions

Only 93 validation books carry a subject label, so one book is about 1 point of accuracy. Before round 1
is judged, more train and validation books are labelled the same way (title, catalogue subject, a text
snippet; marked for team spot-check). Test books are not labelled further.

## Rounds (validation only, at most 3, each a line in `docs/evaluation_log.md`)

1. Round 1: centring + the chosen encoder; full study on train; evaluate on validation.
2. Round 2, only if a target is missed: more text per book (20 chunks instead of 10).
3. Round 3, only if still missed: report the shortfall honestly; no further tuning on validation.

Then: test once; refit on all books with the chosen setting; new group names from distinctive terms and
typical books; export; site, Docker image, report, deck, viva notes and paper rebuilt with the new numbers;
app checks against the container.

## Realistic ceiling

On the current encoder even a supervised 7-nearest-neighbour guess reaches about 64% subject accuracy
(seven broad subjects, noisy OCR of eight languages, many books mixing subjects). Unsupervised groups cannot
pass that ceiling, so the aim is to approach it and to say so plainly.
