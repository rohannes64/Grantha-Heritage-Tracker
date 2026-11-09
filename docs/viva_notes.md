# Viva Q&A notes: Grantha (SIH26096)

Short answers with the real numbers. Each section belongs to the person who answers it; anyone may answer the general part.
Figures are in `reports/figures/`; every number comes from `reports/` and can be checked on the Study page.

---

## General (anyone)

**What does the project do, in one sentence?**
It groups 2,578 old printed Indian books by topic without any labels, and lets a person upload a page from an unindexed scan to see which group it falls into and which archive books it sits closest to.

**Who would use it, and why?**
Archivists, librarians and researchers who hold a scan with no subject heading. Today that scan is read alone. The app puts it next to its nearest neighbours in the archive (with links), names the group it falls into, and says how sure the match is.

**What is the input and what is the output?**
Input: a page image, a PDF (first 5 pages) or pasted text, in English, Hindi, Sanskrit, Bengali, Gujarati, Telugu, Kannada or Tamil. Output: the group from hierarchical clustering with a closeness level, the DBSCAN verdict ("within reach of a dense group" or "noise"), the 5 closest archive books with the words they share, and the page's place on the PCA map. It abstains if fewer than 20 usable words are read.

**Does checking a new page retrain anything?**
No. The saved transformers turn the text into the same 100-dimensional features. Hierarchical: nearest centroid, with the distance compared with that group's own spread (median, 90th percentile, maximum). DBSCAN: the page joins a group only if it is within eps of one of that group's core books.

**What did you find?**
Word-based features (TF-IDF + LSA) group books by script, not topic: the 7 hierarchical groups match the 7 scripts exactly (NMI 1.00). Multilingual LaBSE embeddings cross languages (NMI with script 0.38) and give three groups: English-language books, religious and classical texts, and modern prose. The groups are weak (silhouette 0.107) but stable (bootstrap ARI 0.71).

**Biggest limitation?**
The groups are tendencies, not categories. Silhouette is low, DBSCAN on LaBSE leaves 37% of books as noise, and the "religious and classical" group also has older books and lower OCR confidence, so era and OCR quality are partly mixed with topic.

---

## Data and OCR (Rajith Sundar)

**Where does the data come from?**
The Digital Library of India scans mirrored on the Internet Archive (collection `digitallibraryindia`, about 578,000 items). Public, no key. We download single pages (`/page/n<k>_w1200.jpg`), never whole PDFs.

**How was the sample drawn?**
For each of 8 languages, a sampling frame of books published up to 1960 or undated, then a seeded draw (seed 2026) stratified round-robin over 5 era bands (pre-1900, 1900–19, 1920–39, 1940–60, undated). 375 books per language, 3,000 in all. 5 body pages per book at 15/30/50/70/85% through, so covers, contents and indexes are skipped.

**Why not NDLI directly?**
NDLI aggregates metadata and has no public bulk API. The DLI scans are the files behind many NDLI records.

**How was OCR done?**
Tesseract 5 in Docker with the 8 language models. OSD turns each page upright and guesses the script. If that guess disagrees with the catalogue's language, the middle page is read with both models and the one with higher mean confidence wins.

**Why that confidence check?**
The pilot showed OSD calls most Gujarati pages Bengali or Latin: only 3 of 50 Gujarati books were read with the Gujarati model, at median confidence 36. With the check, 43 of 50 are, and the language's median confidence is 70. Some Gujarati-tagged books really are printed in Devanagari, and those correctly keep the Hindi model.

**How good is the OCR?**
Pilot (50 books per language), median word confidence: English 92, Hindi 76, Kannada 76, Bengali 73, Gujarati 70, Tamil 64, Sanskrit 62, Telugu 55. Agreement with the archive's own OCR is 86–99%.

**Telugu fails your usability rule. Why keep it?**
Its median confidence is 55, below the rule's 60, but its text agrees 86% with the archive's own OCR. So Tesseract's confidence runs low for Telugu rather than the text being bad. We kept it and say so; dropping a language was left to the team lead.

**What counts as a usable book?**
Word-weighted mean confidence of at least 50 and at least 100 clean tokens. 2,578 of 3,000 pass (86%). The other 422 stay in the database, flagged, not silently dropped.

**How did you handle missing values?**
`year` is missing for 19% of usable books: filled with the median (1923) plus a `year_missing` flag, so undated books are not mistaken for typical-year books. Unusable OCR is flagged, not imputed.

**Encoding and scaling?**
Year, log page count, mean OCR confidence and log token count are standardised (zero mean, unit variance) so year, in the hundreds, does not outweigh confidence, in the tens. Script is one-hot encoded (7 scripts). Era is derived from year, so it is used only to describe groups and to stratify the sample.

**Variable relevance: what did you drop and why?**
The archive's `subject` field turned out to hold the scanning centre ("Banasthali", "IIIT"), not a topic, so it was dropped as leakage, along with `scanning_centre` and `source_library`. Title, creator and publisher are free text, mostly unique, and missing for a new scan: display only. `classification` (49% missing) is kept only as an outside check. The full table is in `reports/variable_relevance.csv`.

**Was the encoded metadata used at all?**
Yes, in a sensitivity check. Added to the LaBSE features at weight 0.5, it merges almost every book into one group (99.7%). So the study clusters text alone.

**How is Indian-script text tokenised?**
With the regex `[\p{L}\p{M}]+`, which keeps vowel signs inside the word. The default `\w+` splits Indic words at vowel signs. Tokens mixing scripts are dropped as OCR noise.

**Stopwords for 8 languages?**
No hand-written lists. A term that appears in more than 30% of one language's books is that language's stopword (694 in all). This is reproducible and checkable.

**Rights?**
The catalogue marks these scans' rights as not available. We keep only OCR text, catalogue fields and links; no scans are redistributed, including in the Docker image.

---

## ML study (Etikala Sai Pranav)

**What are the two feature sets?**
A: TF-IDF on word 1–2-grams plus character 3–5-grams, reduced with truncated SVD to 100 dimensions (33% of variance), rows L2-normalised. B: LaBSE sentence embeddings of 4 evenly spaced 64-word chunks per book, averaged, PCA to 100 dimensions (84% of variance), rows normalised.

**Why character n-grams?**
They tolerate OCR errors: a misread letter breaks a word but keeps most of its character 3–5-grams.

**Why LaBSE?**
It maps 109 languages, including all 8 here, into one space where translations sit close together. That is what lets a Tamil and a Telugu book on the same subject land near each other.

**Euclidean or Manhattan, and how did you decide?**
Four criteria, fixed in advance: relative contrast (farthest vs nearest neighbour), cophenetic correlation for average and for complete linkage, and best silhouette with average linkage. Majority wins; a tie goes to Euclidean because Ward needs it. B: Euclidean wins all four (cophenetic average 0.76 vs 0.67, complete 0.69 vs 0.45, silhouette 0.119 vs 0.063, contrast 0.81 vs 0.71). A: Euclidean wins 3 of 4; Manhattan has the higher contrast. Since the rows are unit length, Euclidean distance is a monotone function of cosine similarity, which suits text.

**Which linkages?**
Ward, average and complete, each for k = 2 to 15. A setting is valid if k ≥ 3 and every group holds at least max(10 books, 1%). The best valid silhouette wins. B: average k=3 (0.107) beats Ward k=3 (0.099) and complete k=4 (0.089). A: all three give the same 7 script groups (0.477).

**Why is the silhouette so low?**
Text embeddings of whole books are high-dimensional and topics overlap; values of 0.05–0.25 are normal for text. Above zero means books sit closer to their own group than to the next one. We report it plainly and pair it with stability.

**How did you set DBSCAN's parameters?**
MinPts in {5, 10, 15, 20}. For each, eps comes from the k-distance curve (distance to the (MinPts−1)th neighbour): its 10/25/40/55/70% quantiles plus the knee, 24 combinations in all. Valid if at least 2 clusters and at most 50% noise; best silhouette on clustered books wins. B: MinPts 20, eps 1.029, 2 clusters, 37% noise, silhouette 0.062. A: MinPts 15, eps 0.484, 8 clusters, 15% noise, silhouette 0.512.

**How do hierarchical and DBSCAN compare?**
On A they agree almost completely (ARI 0.98 on non-noise books): both find scripts. On B they barely agree (ARI 0.08, NMI 0.18). DBSCAN finds one large dense core and one small dense group of modern fiction (Bengali and Kannada, median year 1938), and calls the sparse rest noise. Hierarchical clustering must place every book, so it cuts the continuum into three parts.

**How stable are the groups?**
Twenty reruns on random 80% samples, compared by ARI with the full-data labels. B hierarchical: median 0.71 (10th–90th percentile 0.66–0.73). B DBSCAN: median 0.57 (0.52–0.87). Neighbouring settings: hierarchical k=4 agrees at 0.81 and k=2 at 0.41; DBSCAN is sensitive to eps (ARI 0.09 and 0.17 one grid step either way). A is near-perfectly stable (1.00 and 0.92), as script groups would be.

**How did you choose the final feature set?**
A rule fixed before the run: among sets whose hierarchical groups have silhouette > 0 and median bootstrap ARI ≥ 0.5, take the one whose groups depend least on script (lowest NMI with script). Both pass; B wins (0.38 vs 1.00).

**What does PCA show?**
2-D projections for the maps: 23% of variance for B, 26% for A. On A the scripts form separate lines; on B English sits apart and the Indian-language books form one continuum from classical to modern. The maps show shape, not exact distances.

**How did you name the groups?**
By reading each group's distinctive terms (ranked by lift, so common words do not win) and its most typical books (closest to the centroid). For example, the classical group's typical books are a Telugu Ramayana, the Bhagavad Gita, a Bhagavatam and a Tamil purana. No language model was used.

**Does OCR quality drive DBSCAN noise?**
Not among usable books: low confidence predicts noise with AUC 0.54 for B and 0.46 for A, close to chance. The readability filter had already removed the worst scans. Across groups, though, OCR quality differs (63 vs 76 median confidence for the classical vs modern groups).

**What would you do with more time?**
Use more pages per book, test IndicSBERT against LaBSE, run HDBSCAN for varying density, and get a few hundred books labelled by subject experts to measure the groups against.

---

## App and delivery (Vemuri Rohan)

**Architecture?**
FastAPI serves a JSON API and a static website from one process. The model bundle (joblib) holds the fitted transformers, centroids, group spreads, DBSCAN core books and the PCA. Tesseract and LaBSE run inside the same container.

**Endpoints?**
`POST /api/check` (file or text, language or `auto`), `GET /api/clusters`, `/api/clusters/{id}`, `/api/documents/{id}`, `/api/study`, `/api/health`.

**How does "detect the language" work?**
OSD guesses the script; that model reads the first page. If its mean confidence is 70 or more it stands, otherwise all 8 models read the first page and the most confident wins. We added this after OSD called a real Tamil scan Latin (confidence 23, wrong group); now it reads as Tamil at 73.

**How is closeness reported?**
The page's distance to the nearest centroid is compared with that group's own books: "sits well inside" if it is closer than the median book, "inside" if within the 90th percentile, "at the edge" if within the farthest book, and "outside every group" beyond that. DBSCAN says whether the page is within eps of a core book.

**When does it refuse to answer?**
Under 20 usable words it abstains. Under 100 words, or OCR confidence below 50 (the bar archive books had to meet), it answers with a caution.

**How fast is it?**
About 6 seconds for a one-page scan on CPU, most of it OCR.

**Why a static site and no framework?**
Five pages, no build step, nothing to break offline. Charts are hand-built SVG.

**UI choices?**
A dark theme fitted to the subject (warm black, paper-white text, one amber accent). Each Study section opens with a plain-language finding, with the numbers in collapsible panels; limits are shown on the page. Lint-checked with Hallmark.

**Docker?**
`docker compose up` runs image `heritage-topics:1.0` (6.1 GB: PyTorch CPU, LaBSE 1.8 GB, Tesseract with 8 languages). It runs with no network: tested with `--network none` (health, pages, and a Tamil scan check in 6 s). A second `pipeline` service reproduces the whole study.

**Why 6 GB when the plan said 2–3?**
PyTorch and LaBSE together are about 3 GB. LaBSE is copied in as a plain folder because the Hugging Face cache uses symlinks that a Windows build context cannot send.

**Tests?**
30 pytest tests: sampling, OCR (rotation, wrong-tag routing, auto language), text cleaning, the study on a synthetic corpus, the checker and the API.

**Is any user data stored?**
No. Uploads are read in memory and discarded.
