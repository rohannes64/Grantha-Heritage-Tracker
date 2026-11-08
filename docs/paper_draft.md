# Script or subject? Unsupervised grouping of multilingual heritage book scans

*Short-paper draft. Authors: Etikala Sai Pranav, Rajith Sundar, Vemuri Rohan. Guide: (to be added).*

## Abstract

Digitised heritage collections in India hold hundreds of thousands of scanned books with no subject labels, in many scripts. We ask whether unsupervised clustering of OCR text can group such books by subject, or whether it only rediscovers their language. We drew a stratified sample of 3,000 printed books in eight languages from the Digital Library of India mirror on the Internet Archive, read five body pages of each with Tesseract 5, and kept 2,578 books whose OCR passed a readability filter. On the same books we compared two representations (TF-IDF with latent semantic analysis, and LaBSE multilingual sentence embeddings) under hierarchical clustering (Ward, average, complete) and DBSCAN, choosing the distance metric, settings and final representation by rules fixed before the run. With TF-IDF, both methods recover the seven scripts exactly (normalised mutual information with script 1.00) and nothing else. With LaBSE, dependence on script falls to 0.38 and three groups emerge that cross languages: English-language books, religious and classical texts, and modern prose (silhouette 0.107, bootstrap ARI 0.71). DBSCAN on LaBSE finds one dense core and one small cross-language group of modern fiction, and leaves 37% of books as noise. After the readability filter, OCR confidence does not predict which books DBSCAN calls noise (AUC 0.54). Adding standardised catalogue metadata to the embeddings collapses the groups, so we cluster text alone. The results come with a working tool: a web application that places a newly uploaded page among these groups without retraining, and abstains when its OCR is too weak.

## 1. Introduction

Large digitisation projects such as the Digital Library of India scanned books faster than they could be catalogued. Many records carry a title, a language tag and the scanning centre, but no subject. A reader holding one such scan has no way to find the books it belongs with.

Unsupervised clustering of the OCR text is a natural first step, but multilingual collections raise a specific risk: books in different scripts share almost no surface tokens, so any word-based representation will separate scripts before subjects. A clustering that "finds eight groups" in an eight-language collection may only have found the languages. This paper measures that risk directly and tests whether a multilingual embedding removes it.

Contributions:

1. A reproducible, rights-respecting sample of 3,000 heritage books in eight languages, with per-language OCR quality measured before the full run.
2. A controlled comparison of two text representations under hierarchical clustering and DBSCAN, with metric choice, settings and the final representation all decided by rules fixed in advance, and the dependence of every grouping on script, era and catalogue subject reported.
3. Two negative results that matter for practice: word features cluster by script, and catalogue metadata overwhelms weak topical structure.
4. An open tool that checks a new page against the groups, with an abstain rule tied to OCR quality.

## 2. Data

**Source.** The `digitallibraryindia` collection on the Internet Archive (about 578,000 items). Rights are marked as not available, so we keep only OCR text, catalogue fields and links back to the archive.

**Sample.** For English, Hindi, Sanskrit, Bengali, Gujarati, Telugu, Kannada and Tamil, we built a frame of books published up to 1960 or undated, and drew 375 per language with a seeded round-robin across five era bands. From each book we took five pages at 15, 30, 50, 70 and 85% of its length, to avoid covers, contents and indexes.

**OCR.** Tesseract 5 with orientation and script detection. A pilot of 50 books per language showed the script detector misroutes Gujarati (3 of 50 books read with the Gujarati model); when the detected script disagrees with the catalogue tag, we now read the middle page with both models and keep the more confident one (43 of 50 after the fix). Pilot median word confidence ranged from 92 (English) to 55 (Telugu). Telugu fails our pre-set usability rule (60) but agrees 86% with the archive's own OCR, so we kept it.

**Readability filter.** A book is used if its word-weighted mean confidence is at least 50 and it yields at least 100 clean tokens. 2,578 of 3,000 books pass, from 70% (Telugu) to 99% (English).

**Text.** Tokens are runs of letters and combining marks (`[\p{L}\p{M}]+`), which keeps Indic vowel signs inside words. Mixed-script tokens are dropped as OCR noise. Stopwords are learned per language: any term in more than 30% of that language's books.

## 3. Method

**Representations.** (A) TF-IDF on word 1–2-grams and character 3–5-grams, truncated SVD to 100 dimensions (33% of variance), unit-length rows. (B) LaBSE embeddings of four evenly spaced 64-word chunks per book, averaged, PCA to 100 dimensions (84% of variance), unit-length rows.

**Distance.** Euclidean and Manhattan were compared on four criteria fixed in advance: relative contrast, cophenetic correlation under average and complete linkage, and the best average-linkage silhouette. Euclidean won 4 of 4 on B and 3 of 4 on A.

**Hierarchical clustering.** Ward, average and complete linkage for k = 2–15. Valid settings have k ≥ 3 and no group smaller than max(10, 1% of books); the highest silhouette wins.

**DBSCAN.** MinPts ∈ {5, 10, 15, 20}; for each, eps at the 10/25/40/55/70% quantiles of the k-distance curve and at its knee (24 combinations). Valid settings have at least two clusters and at most 50% noise; the highest silhouette on clustered points wins.

**Stability and agreement.** Twenty bootstrap reruns on 80% subsamples, plus neighbouring settings, scored by adjusted Rand index (ARI) against the full-data labels. Hierarchical and DBSCAN labels are compared by ARI and NMI on non-noise books.

**Effects.** NMI of every grouping with detected script, era band, and the catalogue classification where present (1,319 books). For DBSCAN, the area under the ROC curve for low OCR confidence predicting noise.

**Selection rule.** Among representations whose hierarchical groups have silhouette > 0 and median bootstrap ARI ≥ 0.5, choose the one with the lowest NMI with script.

**Sensitivity.** The standardised metadata block (year with missing flag, log pages, OCR confidence, log tokens, one-hot script) appended to each representation at weights 0.25, 0.5 and 1, with the chosen hierarchical setting refitted.

## 4. Results

**Table 1. Chosen settings and their dependence on script, era and subject.**

| Representation, method | Setting | Groups | Silhouette | Bootstrap ARI | NMI script | NMI era | NMI subject |
|---|---|---|---|---|---|---|---|
| TF-IDF+LSA, hierarchical | Ward, k=7 | 7 | 0.477 | 1.00 | 1.00 | 0.01 | 0.27 |
| TF-IDF+LSA, DBSCAN | MinPts 15, eps 0.484 | 8 + 15% noise | 0.512 | 0.92 | 0.89 | 0.01 | 0.27 |
| LaBSE, hierarchical | average, k=3 | 3 | 0.107 | 0.71 | 0.38 | 0.01 | 0.14 |
| LaBSE, DBSCAN | MinPts 20, eps 1.029 | 2 + 37% noise | 0.062 | 0.57 | 0.18 | 0.01 | 0.08 |

**Word features find scripts.** All three linkages on TF-IDF+LSA give the same seven groups, one per script (Devanagari holds both Hindi and Sanskrit), and DBSCAN agrees (ARI 0.98 on non-noise books). The high silhouette reflects how far apart scripts are, not topical structure. DBSCAN's only within-script split separates Sanskrit commentary from modern Hindi prose.

**Multilingual embeddings cross scripts.** LaBSE's hierarchical groups are: English-language books (505, 99% Latin script); religious and classical texts (1,026: Tamil 25%, Devanagari 24%, Telugu 21%, Gujarati 14%, Kannada 11%; typical books include a Telugu Ramayana, the Bhagavad Gita and a Tamil purana; median year 1919); and modern prose and essays (1,047: Bengali 30%, Devanagari 24%, Kannada 20%, Gujarati 18%; median year 1930). NMI with script drops from 1.00 to 0.38. The groups are weak but reproducible: silhouette 0.107, bootstrap ARI 0.71 (0.66–0.73), and k=4 agrees with k=3 at ARI 0.81.

**The two methods disagree on LaBSE.** DBSCAN finds one large dense core (58%), one small dense group of modern fiction and stories (126 books, Bengali and Kannada, median year 1938) and calls 37% noise; agreement with the hierarchical groups is low (ARI 0.08). We read this as a continuum with one dense region rather than separated clusters: hierarchical clustering has to cut it, density-based clustering declines to.

**OCR noise.** Among usable books, OCR confidence barely predicts DBSCAN noise (AUC 0.54 for LaBSE, 0.46 for TF-IDF): the readability filter had already removed the worst scans. OCR quality does differ between the LaBSE groups (median confidence 63 for the classical group, 76 for modern prose), which is a confound we cannot fully separate from subject and era.

**Metadata overwhelms text.** Adding the metadata block to LaBSE at weight 0.25 halves agreement with the text-only groups (ARI 0.41) and puts 80% of books in one group; at 0.5, 99.7% of books fall into one group. TF-IDF groups do not move (ARI ≥ 0.99). Weak topical structure is easily swamped by strong, low-dimensional covariates.

## 5. A tool for unlabelled scans

The fitted transformers, centroids, per-group distance spreads and DBSCAN core books are saved, and a web application uses them to place a new page without retraining. A page's distance to its nearest centroid is reported against that group's own books (closer than the median book, within the 90th percentile, within the farthest, or outside). DBSCAN membership requires lying within eps of a core book. The tool abstains below 20 usable words and cautions below 100 words or below the corpus's own OCR bar. When no language is given, the script detector's guess is kept only if it reads the page at confidence 70 or more; otherwise every model is tried, which fixed a Tamil scan the detector had labelled Latin (confidence 23 → 73). A Tamil commentary page from outside the sample was placed in the classical group, beside Kuruntokai and Tolkappiyam. Checking one page takes about six seconds on a CPU, in a Docker image that runs offline.

## 6. Limitations

Five pages stand in for a book; the sample follows the archive's own mix of subjects; OCR quality varies by script and is entangled with era and subject; silhouettes are low; group names are our reading of distinctive terms and typical books; catalogue subjects exist for only half of the books and are inconsistent, so they serve as a weak check, not ground truth. The books are printed, not handwritten manuscripts.

## 7. Conclusion

In a multilingual heritage collection, word-based clustering mostly rediscovers the scripts, while multilingual sentence embeddings produce weaker but reproducible cross-language groups that separate classical and religious texts from modern prose. Reporting the dependence of every grouping on script, and choosing the representation by a rule fixed before seeing the groups, guards against mistaking language for subject. Next steps: more pages per book, an Indic-specific embedding model, density methods that allow varying density (HDBSCAN), and a small expert-labelled set to measure the groups against.

## Reproducibility

All code, the sampling seed, per-step reports and the Docker images are in the project repository; `scripts/run_study.sh` reruns every step after OCR. Numbers in this draft come from `reports/study/*.json`.

## References (to complete)

- Feng, F., Yang, Y., Cer, D., Arivazhagan, N., Wang, W. (2022). Language-agnostic BERT Sentence Embedding. ACL.
- Ester, M., Kriegel, H.-P., Sander, J., Xu, X. (1996). A density-based algorithm for discovering clusters in large spatial databases with noise. KDD.
- Deerwester, S., et al. (1990). Indexing by latent semantic analysis. JASIS.
- Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation and validation of cluster analysis. J. Comput. Appl. Math.
- Hubert, L., Arabie, P. (1985). Comparing partitions. Journal of Classification.
- Smith, R. (2007). An overview of the Tesseract OCR engine. ICDAR.
- Aggarwal, C. C., Hinneburg, A., Keim, D. A. (2001). On the surprising behavior of distance metrics in high dimensional space. ICDT.
