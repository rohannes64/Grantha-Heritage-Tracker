# Viva Q&A notes: Grantha (SIH26096), version 2

Short answers with the real numbers. Each section belongs to the person who answers it; anyone may answer the general part.
Figures are in `reports/figures/`; every number comes from `reports/` and can be checked on the Study page.
How the numbers were reached: `docs/accuracy_plan.md` and `docs/evaluation_log.md`.

---

## General (anyone)

**What does the project do, in one sentence?**
It groups 2,578 old printed Indian books in 8 languages by topic without any labels, and lets a person upload a page from an unindexed scan to see which group it falls into and which archive books, often in other languages, it sits closest to.

**Who would use it, and why?**
Archivists, librarians and researchers who hold a scan with no subject heading. The app puts it next to its nearest neighbours in the archive, with links, names its group and says how sure the match is. The Gyan Bharatam Mission's call for automated manuscript cataloguing shows the need is current.

**What is the input and what is the output?**
Input: a page image, a PDF (first 5 pages) or pasted text. Output: the hierarchical group with a closeness level and any other groups it is "also close to", the DBSCAN verdict (a dense group or noise), the 5 closest archive books with shared words, and the page's place on the PCA map. It abstains under 20 usable words.

**Does checking a new page retrain anything?**
No. The page is embedded, centred by its OCR language and projected with the saved PCA. Hierarchical: nearest group centre, compared with that group's own spread. DBSCAN: it joins a group only within eps of a core book.

**What did you find?**
Done naively, clustering finds languages, not topics: TF-IDF groups match the scripts exactly (NMI 1.00), and our first multilingual version beat a "guess the subject from the script" baseline by only 3 points. Removing each language's average position from the embeddings, and choosing the encoder that carries the most topic information, turns the groups into topics: 6 groups (modern fiction; politics and public life; science and medicine; poetry and epics; Christian scriptures; religion and philosophy), each across several languages, with script NMI 0.05. On test books measured once, the group predicts the subject 58.7% of the time against 48.0% for the best simple guess.

**Is this really unsupervised?**
Yes. Hierarchical clustering and DBSCAN never see a label. 704 subject labels exist only to measure the groups afterwards and to compare encoders; they never form or choose groups. The encoders are pre-trained by others and used as fixed text-to-number converters.

**Biggest limitation?**
The encoder is Google's Gemini Embedding 001, a closed online model: checking a page needs the internet and sends its text to Google. The best open model (BGE-M3) was about 7 points lower. Two targets were missed narrowly (page-to-book 72.5% vs 80%; stability 0.58 vs 0.60).

---

## Data and OCR (Rajith Sundar)

**Where does the data come from?**
The Digital Library of India scans mirrored on the Internet Archive (collection `digitallibraryindia`). In our 8 languages there are about 434,000 books published up to 1960 or undated (English 253,682 down to Tamil 4,644). Public, no key. Links for all 3,000 sampled books: `reports/dataset_links.csv`.

**How was the sample drawn?**
For each language a seeded draw (seed 2026) round-robin over 5 era bands (pre-1900, 1900–19, 1920–39, 1940–60, undated): 375 books per language, 3,000 in all, so English (58% of the pool) does not dominate.

**What text does each book contribute?**
The archive's own whole-book OCR (hOCR or djvu text) for 2,971 books: first and last 5% trimmed (covers, indexes), 40 evenly spaced windows of 100 tokens kept. Five pages per book were also read with our Tesseract, to measure OCR quality and to test uploads; books without archive text use those pages.

**How was the data split?**
Before any result: 60/20/20 into train, validation and test, by language, fixed seed. Of 2,578 usable books: 1,548 train, 515 validation, 515 test. Every fitting step uses train books only; the test books were evaluated once.

**How was OCR done?**
Tesseract 5 in Docker with 8 language models. OSD turns each page upright and guesses the script. If that disagrees with the catalogue's language, the middle page is read with both models and the more confident wins: Gujarati went from 3 to 43 of 50 pilot books read with the Gujarati model.

**How good is the OCR?**
Pilot median word confidence: English 92, Hindi 76, Kannada 76, Bengali 73, Gujarati 70, Tamil 64, Sanskrit 62, Telugu 55. Telugu fails our rule (60) but agrees 86% with the archive's own OCR, so its confidence runs low rather than its text being bad; it was kept.

**What counts as a usable book?**
OCR confidence of at least 50 and at least 100 clean tokens: 2,578 of 3,000 (86%). The other 422 stay in the database, flagged.

**Missing values, encoding, scaling?**
Year missing for about a fifth: median fill plus a `year_missing` flag. Script one-hot. Year, page count, OCR confidence and length standardised. Each book's language (its OCR model) is also used to remove that language's average position from its embedding.

**Variable relevance: what did you drop?**
The `subject` field holds the scanning centre, not a topic: dropped as leakage. Title, creator, publisher: display only. `classification` (49% missing): only an outside check. Full table: `reports/variable_relevance.csv`.

**Was the encoded metadata used?**
In a sensitivity check: added to the text features at weight 1 it puts 91% of books in one group. So the study clusters text alone.

**Tokenising Indian scripts? Stopwords?**
`[\p{L}\p{M}]+` keeps vowel signs inside words (`\w+` splits them). Stopwords per language: a term in more than 30% of that language's books. No hand-written lists.

**Rights?**
Marked "not available". We keep only text, catalogue fields and links; no scans in the repository or the Docker image. Book text is sent to Google's API to be embedded.

---

## ML study (Etikala Sai Pranav)

**What went wrong in the first version, and why?**
Multilingual encoders place each language in its own region, so the largest distances between books are language distances, and clustering finds languages first. Silhouette made it worse: language groups are far apart, so they scored higher (0.14) than topic groups (0.06–0.07).

**How did you fix it without labels?**
Two steps. (1) Subtract each language's mean embedding, computed on the training books, and rescale; a new page is centred by the language Tesseract read it in. Script NMI fell from 0.38 to 0.05. (2) Choose the encoder by how much topic information it carries.

**How did you choose the encoder?**
On labelled train and validation books only (never test): how often a book's subject matches the most common subject of its 7 nearest neighbours, 5-fold cross-validated. This is the most any grouping of those numbers could achieve. After removing the language: Gemini 75.0%, BGE-M3 68.2%, LaBSE 64.9%, IndicSBERT 64.5%; multilingual-E5-large 65.8% on an earlier 325-book set. Rule fixed in advance: highest wins, within 2 points the smaller model. Reproducible: `python -m pipeline.encoders`.

**What are the two feature sets?**
A: TF-IDF on word 1–2-grams plus character 3–5-grams, SVD to 100 dimensions. G: Gemini Embedding 001 of 10 evenly spaced 64-word passages per book, averaged, language mean removed, PCA to 100 dimensions (77% of variance).

**Euclidean or Manhattan?**
Four criteria fixed in advance (relative contrast, cophenetic correlation for average and complete linkage, best silhouette with average linkage); majority wins, tie to Euclidean. Euclidean wins 3 of 4 on both sets. With unit-length rows, Euclidean distance is a monotone function of cosine similarity.

**Which linkages, and how was the final setting chosen?**
Ward, average and complete, k = 2 to 15; valid if k ≥ 3 and every group ≥ max(10 books, 1%). Final rule, fixed in advance: highest silhouette among settings whose groups follow script with NMI ≤ 0.5 and whose median bootstrap ARI ≥ 0.5. On the train books TF-IDF (silhouette 0.228) fails because its groups are scripts (NMI 0.65); Gemini average linkage with k = 6 (0.072) wins. Silhouette chose 6 groups by itself; we set no floor.

**Then you refitted on all books?**
Yes, with the same setting (average, k = 6), not re-chosen: silhouette 0.064. On all books k = 5 would score marginally higher (0.066), but re-choosing on data that includes the test books is what the plan forbids.

**Why is the silhouette so low?**
The topics overlap: devotional poetry is religion and literature. The elbow method shows the same: within-group spread falls smoothly with no sharp elbow. Low silhouette here means honest, overlapping topics, not a failure.

**DBSCAN?**
MinPts 5/10/15/20; eps from each k-distance curve (5 quantiles plus the knee): 24 combinations, 9 valid. Chosen: MinPts 15, eps 0.798, 11 dense groups, 47% noise. Its groups are narrower: medicine, Hindu and Jain philosophy, modern prose fiction, classical Tamil and Kannada poetry, regional dynastic history, Indology, administration reports, the national movement (Gandhi, Nehru, Tilak), English fiction, Buddhist scriptures, Kannada Christian texts. HDBSCAN agrees with the hierarchical groups on the books it clusters (ARI 0.84).

**How do the two methods compare?**
ARI 0.34, NMI 0.56 on books DBSCAN groups: DBSCAN keeps the dense cores of topics and calls the overlapping middle noise; hierarchical clustering must place every book.

**How stable are the groups?**
Bootstrap (20 reruns on 80% samples): hierarchical median 0.58 on train books, 0.51 on all books; neighbouring k = 5 and 7 agree at 0.96–0.98. DBSCAN 0.70. Topic groups are less stable than script groups (TF-IDF: 1.00) because overlapping topics move between neighbours.

**How did you measure accuracy?**
Targets fixed before any result: T1, a single uploaded page lands with its own book's group ≥ 80%; T2, the group predicts subject ≥ 10 points better than the better of "most common subject" and "subject from script"; T3, bootstrap ARI ≥ 0.60. Revisions on validation only (2 rounds used); test once.

**Results on test books?**
T2 met: 58.7% vs 48.0% (+10.7, p = 0.0005). T1 missed: 72.5%, about 4 times chance (18%); a page must pick 1 of 6 groups from noisier OCR than its book. T3 missed: 0.58. Validation agreed within about 2 points, so no overfitting. The test rests on 75 labelled books (about ±6 points).

**What are the tags?**
A rule fixed before measuring it: the nearest group, plus any group the item sits as close to as 9 in 10 of that group's own books (at most 3). With tags, a page's tags include its book's group 82.5% of the time (1.48 tags), and a book's subject is among its tags 72.0% of the time, but only 49% of tags are right, so they are hints. Strict scores are always reported beside them.

**Where do the misses come from?**
About 30% are religion against literature (epics, devotional poetry), which a second labeller would often call the other way; the "other" category (magazines, music, encyclopaedias) cannot be found by topic; accuracy is lower for noisy OCR and for Sanskrit and Tamil.

**Who made the subject labels?**
The project's assistant, from title, catalogue subject and a text snippet, marked for team spot-check. They only measure.

---

## App and delivery (Vemuri Rohan)

**Architecture?**
FastAPI serves a JSON API and a static website. The model bundle holds the fitted TF-IDF, the Gemini embedder settings with each language's mean, the PCA, group centres and spreads, and DBSCAN core books. Tesseract runs in the container; embedding goes to Google's API.

**Where is the API key?**
In a git-ignored `.env` file, passed to the container at run time by `docker compose`. It is never in the code, the repository or the image. If Google cannot be reached, the check page says so (HTTP 503).

**How does "detect the language" work?**
OSD guesses the script; if that model reads page 1 at confidence 70 or more it stands, otherwise all 8 models read page 1 and the most confident wins.

**How is closeness reported?**
Distance to the nearest centroid against that group's own books: "sits well inside" (closer than its median book), "inside" (90th percentile), "at the edge" (farthest book), "outside every group". Plus "also close to" for other groups by the tag rule.

**When does it refuse?**
Under 20 usable words it abstains; under 100 words or OCR confidence below 50 it cautions.

**Docker?**
`docker compose up` runs `grantha:2.0`, 1.11 GB (version 1 was 6.1 GB, because PyTorch and LaBSE were inside it). A build switch adds PyTorch back if a local encoder is used. A `pipeline` service reproduces the whole study.

**Tests?**
40 pytest tests (study on a synthetic corpus, language centring, the tag rule, the Gemini client with the network faked, OCR, the API). App checks against the container: 65 of 66 passed, including real scans in all 8 languages, a two-page PDF and every error path. The one failure: a Sanskrit page on detect was read with the Hindi model (same script, slightly more confident); its group was the same.

**UI choices?**
A dark theme fitted to the subject. Each Study section opens with a plain-language finding; numbers in collapsible panels; limits on the page, including the closed-model trade-off and the missed targets.

**Is any user data stored?**
No. Uploads are read in memory and discarded; the text is sent to Google only to be embedded.
