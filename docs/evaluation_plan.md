# Evaluation plan (written 2026-11-09, before any of the results it governs)

This file fixes, in advance, how the second version of the study is built, chosen and judged. It is committed before the new results exist, so the git history shows that no rule was bent to fit an outcome.

## 1. What changes from version 1

| | Version 1 | Version 2 |
|---|---|---|
| Text per book | 5 pages read by our Tesseract | The whole book: the Internet Archive's own OCR (page-indexed hOCR text, or the full `_djvu.txt` where only that exists). Books with neither keep our 5 Tesseract pages. |
| Our 5 Tesseract pages | The training text | Kept out of training wherever the archive text is page-indexed, and used as the test material for the upload check (section 4). |
| Feature sets | A: TF-IDF+LSA, B: LaBSE | A, B, and C: IndicSBERT (`l3cube-pune/indic-sentence-similarity-sbert`), a sentence model trained on Indian languages. B and C read 10 evenly spaced 64-word chunks per book instead of 4. |
| Extra comparison | none | HDBSCAN (density-based with varying density) as an extra row next to DBSCAN. DBSCAN stays, as the brief requires. |
| Robustness | none | (a) silhouette computed within each script, (b) the chosen clustering refitted on books with OCR confidence of 70 or more. |

Everything the brief asks for is unchanged: preprocessing (missing values, encoding, scaling, relevance), Euclidean vs Manhattan, hierarchical with three linkages, DBSCAN with a 24-setting grid, direct comparison, PCA, silhouette-based final choice, stability, interpretation, limits, and the new-record check.

## 2. The readability filter

Unchanged: a book is used if the word-weighted mean confidence of our 5 Tesseract pages is at least 50 and its clean text has at least 100 tokens. (The archive's OCR has no confidence scores, so our pages remain the quality gauge.)

## 3. Splits (seed 2026, stratified by language)

- **Train, 60%:** every fitting step (stopwords, TF-IDF, SVD, PCA, clustering, DBSCAN eps, centroids).
- **Validation, 20%:** used only if a design choice must be revisited (section 6).
- **Test, 20%:** touched once, for the final numbers. Never used to choose anything.

After the test numbers are recorded, the app's model is refitted on all usable books with the same settings, which is standard practice and changes no choice.

## 4. Final choice (silhouette-based, as the brief requires)

Among all feature sets (A, B, C) and all valid hierarchical settings, keep only candidates whose groups:
1. depend on script with NMI of 0.5 or less (so they are not language groups), and
2. have a median bootstrap ARI of 0.5 or more.

The final setting is the remaining candidate with the **highest silhouette**. If no candidate passes, the one with the lowest script NMI among those with silhouette above zero is chosen, and this is reported as a failure of the rule. The DBSCAN setting is chosen on the chosen feature set exactly as in version 1 (best silhouette among valid settings).

## 5. How accuracy is judged (targets fixed now)

**T1. Upload check, out of sample.** For each test book, each of its Tesseract pages is sent through the app's checker as if uploaded (model fitted on train books only). The page's group is compared with the group of that book's full text. Target: agreement of **0.80 or more** on the pages the checker does not abstain on, with the abstain rate reported. Chance level (assigning groups in proportion to their sizes) is reported next to it.

**T2. Subject, out of sample.** About 300 books, drawn at random (seed 2026) from the usable books, are labelled with one broad subject: religion and philosophy; literature (poetry, drama, fiction); history, biography and geography; language and grammar; science, medicine and technology; society, law, economics and politics; other. Labels come from the title, the catalogue classification where present, and the OCR text. They are made by the assistant and marked as such, for the team to spot-check, and they are **never** used to fit or choose anything. A group-to-subject map is learned on the labelled train books (each group takes its majority subject) and applied to the labelled test books. Target: subject accuracy **at least 10 points above** the better of two baselines: (a) always guessing the most common subject, (b) guessing from the book's script alone (each script's majority subject). Baseline (b) is the one that matters: beating it shows the groups carry topic beyond language.

**T3. Stability.** Median bootstrap ARI of the final hierarchical groups at least **0.60**.

**T4. Behaviour.** Every app path works: image, multi-page PDF, pasted text, each of the 8 languages on detect and when chosen, wrong language chosen, blank page, too little text, unsupported file, oversized file. Each gives the documented response.

## 6. If a target is missed

Design choices may be revisited (feature set, number of chunks, k range, the noise and abstain thresholds) using the **validation** split only, never the test split. Each revision and its validation result is logged in `docs/evaluation_log.md`. The test split is then used once more for the final numbers. At most three revision rounds; if a target is still missed after that, it is reported as missed with the numbers, not hidden.

## 7. What "realistically acceptable" means here

Unsupervised topic groups of OCR'd, multilingual, century-old books will not be clean categories. The bar is: groups that beat the language-only baseline on subject (T2), uploads that land where their own book lands (T1), groups that survive resampling (T3), and an app that never crashes or answers when it should abstain (T4).
