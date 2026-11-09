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

Candidates: LaBSE (current), IndicSBERT, BGE-M3, multilingual-E5-large. E5-large was dropped from the
GPU run at Karthik's call to save time, but an earlier CPU run of it had kept going and finished on the
first 325 labelled books. On those same 325 books, after centring: BGE-M3 66.8%, E5-large 65.8%,
LaBSE 64.3%, IndicSBERT 63.1%. BGE-M3 leads on both label sets.
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

## Round 2: multi-tags (fixed 2026-11-09, before any round-2 result)

Round 1 met T2 and missed T1 (0.704) and T3 (0.58). Round 2 adds tags, without changing any target.

- Main tag: the nearest group centre, as now. Every strict score (T1, T2, T3) stays as defined.
- Extra tags: a group is also a tag if the item is within that group's own 90th-percentile distance (how far
  9 in 10 of the group's train books sit from its centre). At most 3 tags in total, nearest first. No labels
  are used to set this; it comes from the train books' distances alone.
- Reported alongside the strict scores, as secondary measures with no targets of their own:
  - T1 tagged: the book's group is among the uploaded page's tags; average tags per page.
  - T2 tagged: the book's subject is among the subjects of its tags (each group's subject from train, as in T2);
    average tags per book; and tag precision (share of all tags whose subject is right), so over-tagging shows.
- T3 is unchanged (tags do not change the groups).
- The app shows the main group and "also close to" groups by the same rule.
