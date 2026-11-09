# Language or topic? Unsupervised grouping of multilingual heritage book scans

*Short-paper draft. Authors: Etikala Sai Pranav, Rajith Sundar, Vemuri Rohan. Guide: (to be added).*

## Abstract

Digitised heritage collections in India hold hundreds of thousands of scanned books with no subject labels, in many scripts. We ask whether unsupervised clustering of their OCR text can group such books by topic, or whether it only rediscovers their language. On a stratified sample of 3,000 printed books in eight languages from the Digital Library of India mirror on the Internet Archive (2,578 readable), split 60/20/20 into train, validation and test before any result, we find that it rediscovers language. TF-IDF groups match the scripts almost exactly (normalised mutual information with script 0.99 at the highest-silhouette setting), and groups from multilingual sentence embeddings beat a "subject from script" guess by only 3 points. Silhouette, the usual guide, rewards these language groups. Two label-free changes turn them into topic groups: subtracting each language's mean from the embeddings, which lowers dependence on script from 0.38 to 0.05, and choosing the encoder by how much topic information it carries, measured before clustering (nearest-neighbour subject agreement rose by 4 to 11 points for every one of four encoders). With hierarchical clustering chosen by silhouette among settings that do not merely follow script, six cross-language groups emerge (fiction; public life; science and medicine; poetry and epics; Christian scriptures; religion and philosophy). On test books evaluated once, the group predicts a book's subject 58.7% of the time against 48.0% for the best simple guess, and a single page lands with its own book's group 72.5% of the time. The groups come with an open tool that places a new page among them without retraining.

## 1. Introduction

Large digitisation projects such as the Digital Library of India scanned books faster than they could be catalogued. Many records carry a title, a language tag and the scanning centre, but no subject. Unsupervised clustering of the OCR text is a natural first step, but multilingual collections carry a specific risk: books in different scripts share almost no surface tokens, and even multilingual sentence encoders place each language in its own region of the vector space. A clustering that "finds groups" in an eight-language collection may only have found the languages.

Contributions:

1. Evidence, on real heritage scans, that both word-based and multilingual-embedding clustering group books by language first, and that silhouette favours those groups.
2. A label-free fix (removing per-language means, and choosing the encoder by nearest-neighbour topic agreement on a labelled development set) that turns language groups into topic groups, measured on held-out books with targets fixed in advance.
3. A comparison of five multilingual encoders on noisy OCR of Indian-language books, before and after language removal.
4. An open tool that checks a new page against the groups, with abstain and "also close to" rules.

## 2. Data

**Source.** The `digitallibraryindia` collection on the Internet Archive; about 434,000 books in our eight languages are published up to 1960 or undated. Rights are marked as not available, so we keep only OCR text, catalogue fields and links back to the archive.

**Sample.** For English, Hindi, Sanskrit, Bengali, Gujarati, Telugu, Kannada and Tamil, 375 books per language, drawn with a seeded round-robin across five era bands.

**Text and OCR.** Each book's text is the archive's own whole-book OCR (2,971 of 3,000 books), trimmed of its first and last 5% and sampled as 40 windows of 100 tokens. Five pages per book were also read with Tesseract 5 (orientation and script detection, with a confidence check that fixed Gujarati routing) to measure OCR quality and to simulate uploads. A book is used if its OCR confidence is at least 50 and it yields at least 100 clean tokens: 2,578 books.

**Splits and labels.** 60/20/20 train, validation and test by language, fixed before any result. For evaluation only, 704 books (629 train and validation, 75 test) were given one of seven broad subjects (religion and philosophy; literature; history, biography and geography; society, law and economics; science, medicine and technology; language and grammar; other) from title, catalogue subject and a text snippet. Labels never form or choose groups.

## 3. Method

**Representations.** (A) TF-IDF on word 1–2-grams and character 3–5-grams, truncated SVD to 100 dimensions. (G) Sentence embeddings of up to ten 64-word passages per book, averaged; each language's mean over the fitted books is subtracted and rows rescaled; PCA to 100 dimensions. A new page is centred by the language its OCR used.

**Encoder choice.** On labelled train and validation books only: 5-fold cross-validated agreement between a book's subject and the majority subject of its seven nearest neighbours, before and after language removal. This bounds what any grouping of the vectors can achieve. Rule fixed in advance: highest wins, smaller model within 2 points.

**Clustering.** Euclidean and Manhattan compared on four pre-set criteria (Euclidean won 3 of 4 on both representations). Hierarchical clustering with Ward, average and complete linkage for k = 2–15 (valid: k ≥ 3, no group under max(10, 1%)); DBSCAN with MinPts ∈ {5, 10, 15, 20} and eps from k-distance quantiles and knee (24 settings).

**Selection.** Highest silhouette among settings whose groups follow script with NMI ≤ 0.5 and whose median bootstrap ARI (20 reruns on 80% samples) is at least 0.5, chosen on train books and then refitted on all books without re-choosing.

**Evaluation.** Targets fixed in advance: a single upload page lands with its own book's group ≥ 80% (T1); the group predicts subject ≥ 10 points better than the better of "most common subject" and "subject from script" (T2); bootstrap ARI ≥ 0.60 (T3). Two revision rounds on validation (language removal with the new encoder; then multi-tags), test once. Multi-tags: the nearest group plus any group within its own 90th-percentile spread, at most three.

## 4. Results

**Language first.** On TF-IDF the highest-silhouette setting (Ward, k = 7, silhouette 0.52) matches the scripts (NMI 0.99). In our first embedding version (LaBSE, four passages from five pages per book) the selected groups had script NMI 0.38 and predicted subject only 3 points better than guessing from the script, though their silhouette (0.14) was higher than any topic grouping found later. Silhouette rewards the separation between languages.

**Table 1. Topic information per encoder (7-NN subject agreement, labelled train and validation books).**

| Encoder | As is | Language removed |
|---|---|---|
| Gemini Embedding 001 | 63.9% | **75.0%** |
| BGE-M3 | 60.7% | 68.2% |
| LaBSE | 60.9% | 64.9% |
| IndicSBERT | 55.8% | 64.5% |
| multilingual-E5-large (325 books) | 57.2% | 65.8% |

Removing the language helps every encoder. A closed API model leads the best open model by about 7 points.

**Table 2. Chosen settings on all books and their dependence on script, era and subject.**

| Representation, method | Setting | Groups | Silhouette | Bootstrap ARI | NMI script | NMI era | NMI subject |
|---|---|---|---|---|---|---|---|
| TF-IDF+LSA, hierarchical* | average, k=3 | 3 | 0.231 | 1.00 | 0.57 | 0.00 | 0.10 |
| TF-IDF+LSA, DBSCAN | MinPts 20, eps 0.355 | 7 + 37% noise | 0.606 | 0.85 | 0.76 | 0.02 | 0.25 |
| Gemini, hierarchical | average, k=6 | 6 | 0.064 | 0.51 | 0.05 | 0.01 | 0.19 |
| Gemini, DBSCAN | MinPts 15, eps 0.798 | 11 + 47% noise | 0.057 | 0.70 | 0.10 | 0.02 | 0.20 |

\* No TF-IDF setting meets the script limit; the one with the least script dependence is shown.

**Topic groups.** With language removed, silhouette chose six groups on the training books without any floor on k: modern fiction (438 books), politics and public life (679), science and medicine (441), poetry, epics and classical literature (481), Christian scriptures (44), and religion and philosophy (495). Every group spans several scripts; the poetry group holds Telugu, Tamil, Devanagari and Gujarati books in nearly equal shares. DBSCAN keeps narrower dense topics (medicine, Buddhist scriptures, the national movement, regional dynastic history, English fiction and others) and calls the overlapping middle noise; HDBSCAN agrees with the hierarchical groups on the books it clusters (ARI 0.84). Nearest neighbours now cross languages: a Hindi passage on fevers finds Tamil fever-treatment books.

**Table 3. Held-out evaluation (strict; tagged in brackets).**

| Books | Page with own book (T1) | Subject from group (T2) | Best simple guess | Bootstrap (T3) |
|---|---|---|---|---|
| Validation (515; 293 labelled) | 70.4% (81.8%) | 59.0% (70.0%) | 46.4% | 0.58 |
| Test (515; 75 labelled) | 72.5% (82.5%) | 58.7% (72.0%) | 48.0% | 0.58 |

T2 is met on test (+10.7 points, permutation p = 0.0005); T1 and T3 are missed narrowly. Validation and test agree, so the two revision rounds did not overfit validation. Tags help (82.5% of pages include their book's group at 1.48 tags) but only 49% of extra tags carry the right subject. About 30% of the remaining errors are religion against literature (epics, devotional poetry), a boundary a second annotator would often draw differently.

**Metadata overwhelms text.** Appending standardised catalogue metadata at weight 1 puts 91% of books in one group, so we cluster text alone.

## 5. A tool for unlabelled scans

The fitted transforms, language means, group centres and spreads, and DBSCAN core books are saved; a web application places a new page without retraining, reports its closeness against the group's own books, lists groups it is also close to and its five nearest archive books, and abstains below 20 usable words. It runs in a 1.1 GB Docker image; the encoder is reached over the internet with a key supplied at run time.

## 6. Limitations

The best encoder is a closed online model: the page's text is sent to its provider and the model may change. Silhouettes are low (topics overlap). Subject labels were made by the project's assistant from titles, catalogue subjects and snippets and await expert checking; only 75 test books are labelled (about ±6 points). OCR quality varies by script and is entangled with era. The books are printed, not handwritten manuscripts.

## 7. Conclusion

In a multilingual heritage collection, both word features and multilingual embeddings group books by language before topic, and silhouette prefers those groups. Removing per-language means and choosing the encoder by measured topic information turns them into cross-language topic groups that predict subject about 11 points better than the script does, on books never seen during any choice. Reporting each grouping's dependence on script, and fixing selection rules and targets before results, guards against mistaking language for subject. Next: unsupervised fine-tuning of an open encoder on archive text, more books per language, and expert-checked labels.

## Reproducibility

Code, seeds, splits, the evaluation plan and log, and per-step reports are in the project repository (`docs/evaluation_plan.md`, `docs/accuracy_plan.md`, `docs/evaluation_log.md`); `scripts/run_study.sh` reruns every step after OCR. Numbers come from `reports/study/*.json` and `reports/eval/*.json`.

## References

1. Aggarwal, C. C., Hinneburg, A., Keim, D. A. (2001). On the surprising behavior of distance metrics in high dimensional space. ICDT 2001, LNCS 1973, 420–434. https://doi.org/10.1007/3-540-44503-X_27
2. Campello, R. J. G. B., Moulavi, D., Sander, J. (2013). Density-based clustering based on hierarchical density estimates. PAKDD 2013, LNCS 7819, 160–172. https://doi.org/10.1007/978-3-642-37456-2_14
3. Chen, J., Xiao, S., Zhang, P., Luo, K., Lian, D., Liu, Z. (2024). BGE M3-Embedding: Multi-lingual, multi-functionality, multi-granularity text embeddings through self-knowledge distillation. Findings of ACL 2024. arXiv:2402.03216.
4. Deerwester, S., Dumais, S. T., Furnas, G. W., Landauer, T. K., Harshman, R. (1990). Indexing by latent semantic analysis. Journal of the American Society for Information Science, 41(6), 391–407.
5. Deode, S., Gadre, J., Kajale, A., Joshi, A., Joshi, R. (2023). L3Cube-IndicSBERT: A simple approach for learning cross-lingual sentence representations using multilingual BERT. arXiv:2304.11434.
6. Ester, M., Kriegel, H.-P., Sander, J., Xu, X. (1996). A density-based algorithm for discovering clusters in large spatial databases with noise. KDD-96, 226–231.
7. Feng, F., Yang, Y., Cer, D., Arivazhagan, N., Wang, W. (2022). Language-agnostic BERT sentence embedding. ACL 2022, 878–891. https://doi.org/10.18653/v1/2022.acl-long.62
8. Hubert, L., Arabie, P. (1985). Comparing partitions. Journal of Classification, 2(1), 193–218. https://doi.org/10.1007/BF01908075
9. Lee, J., Dai, Z., Ren, X., et al. (2025). Gemini Embedding: Generalizable embeddings from Gemini. arXiv:2503.07891.
10. Libovický, J., Rosa, R., Fraser, A. (2020). On the language neutrality of pre-trained multilingual representations. Findings of EMNLP 2020, 1663–1674. https://doi.org/10.18653/v1/2020.findings-emnlp.150
11. Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation and validation of cluster analysis. Journal of Computational and Applied Mathematics, 20, 53–65. https://doi.org/10.1016/0377-0427(87)90125-7
12. Smith, R. (2007). An overview of the Tesseract OCR engine. ICDAR 2007, vol. 2, 629–633. https://doi.org/10.1109/ICDAR.2007.4376991
13. Vinh, N. X., Epps, J., Bailey, J. (2010). Information theoretic measures for clusterings comparison. Journal of Machine Learning Research, 11, 2837–2854.
14. Wang, L., Yang, N., Huang, X., Yang, L., Majumder, R., Wei, F. (2024). Multilingual E5 text embeddings: A technical report. arXiv:2402.05672.
15. Ward, J. H. (1963). Hierarchical grouping to optimize an objective function. Journal of the American Statistical Association, 58(301), 236–244. https://doi.org/10.1080/01621459.1963.10500845
16. Internet Archive. Digital Library of India collection (digitallibraryindia). https://archive.org/details/digitallibraryindia (accessed November 2026).
