// Content of the report (v2). Loaded by report.js, which supplies the building blocks.
module.exports = (ctx) => {
const { P, b, i, H1, H2, bullet, numbered, newList, pageBreak, figure, table, f, pct, n, AlignmentType, Paragraph, TextRun, TableOfContents, HeadingLevel, FONT, J } = ctx;

const study = J("web/data/study.json");
const A = J("reports/study/results_A.json"), G = J("reports/study/results_G.json");
const sel = J("reports/study/selection.json");
const sens = J("reports/study/sensitivity.json");
const pilot = J("reports/pilot_ocr_quality.json");
const names = J("reports/cluster_names.json");
const enc = J("reports/study/encoder_comparison.json");
const val = J("reports/eval/evaluation_val.json"), test = J("reports/eval/evaluation_test.json");
const checks = J("reports/eval/app_checks.json");

const hG = G.hierarchical, dG = G.dbscan, hA = A.hierarchical, dA = A.dbscan;
const med = (v) => v.median;
const corpus = study.corpus;
const tsel = sel.train_selection;
const T1 = test.T1_upload_check, T2 = test.T2_subject, V1 = val.T1_upload_check, V2 = val.T2_subject;
const best = (t2) => Math.max(t2.baseline_most_common, t2.baseline_script_only);
const content = [];

// Title page
content.push(
  new Paragraph({ spacing: { before: 2400, after: 200 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Grantha", bold: true, size: 56, font: FONT })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: "An Unsupervised Grouping Study of Heritage Documents by Topic", size: 30 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: "Project report, SIH26096", size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: "Course outcomes CO2, CO3. Units III and IV: hierarchical and density clustering, PCA visualisation", size: 20 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 800, after: 80 }, children: [new TextRun({ text: "Rajith Sundar (data and OCR)", size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: "Etikala Sai Pranav (clustering study)", size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: "Vemuri Rohan (application and delivery)", size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 600 }, children: [new TextRun({ text: "Guide: ______________________     Date: November 2026", size: 22 })] }),
  pageBreak(),
);

content.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Contents")] }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
  P(i("Right-click the table and choose Update Field if page numbers are missing.")), pageBreak());

// Abstract
content.push(H1("Abstract"),
  P(`Old scanned books in Indian digital archives carry no subject labels, so each is read alone instead of next to the books it belongs with. We built a web application that groups ${n(corpus.usable)} printed heritage books in eight languages by topic without labels, and places a newly uploaded page among those groups without retraining. The books were drawn at random from the Digital Library of India scans on the Internet Archive (${n(corpus.harvested)} sampled, stratified by language and era) and read from the archive's whole-book OCR text, with five pages per book read again with Tesseract 5 to measure OCR quality and test uploads.`),
  P(`A first version grouped the books by language rather than topic: TF-IDF groups matched the scripts exactly, and multilingual embeddings beat a "subject from script" guess by only 3 points. Two changes fixed this without labels: each language's average position in embedding space is subtracted before clustering, and the encoder was chosen, from five, by how much topic information it carries. Hierarchical clustering (Ward, average, complete; k 2–15) and DBSCAN (24 eps and MinPts settings) were then compared, and the final setting chosen by silhouette among settings that do not merely follow script and survive resampling, all on training books only. Gemini Embedding 001 with average linkage gave ${hG.final.k} topic groups (silhouette ${f(hG.final.silhouette)}, dependence on script ${f(hG.effects.nmi_script, 2)}); DBSCAN found ${dG.final.n_clusters} dense groups. On test books measured once, the group predicts a book's subject ${pct(T2.accuracy_groups, 1)} of the time against ${pct(best(T2), 1)} for the best simple guess, and a single uploaded page lands with its own book's group ${pct(T1.agreement, 1)} of the time (${pct(T1.tagged.agreement_tagged, 1)} counting "also close to" tags).`),
  pageBreak());

// 1 Problem
content.push(H1("1. Problem and use case"),
  P("India's digitisation projects scanned hundreds of thousands of books. Many catalogue records hold a title, a language tag and the scanning centre, but no subject. An archivist, librarian or researcher who holds one of these scans cannot easily find the books it belongs with. The Gyan Bharatam Mission's call for automated cataloguing of manuscripts shows the need is current."),
  P([b("Users. "), "Archivists, librarians and researchers working with unindexed scans of printed books in Indian languages."]),
  P([b("Input. "), "A page image, a PDF (first five pages) or pasted text, in English, Hindi, Sanskrit, Bengali, Gujarati, Telugu, Kannada or Tamil; the language can be left on detect."]),
  P([b("Output. "), "The topic group the page falls into from hierarchical clustering, with a closeness level and any other groups it is also close to; DBSCAN's verdict (within reach of a dense group, or noise); the five closest archive books, often in other languages, with shared words and links to their scans; and the page's position on the PCA map. When the OCR yields too few readable words, the tool says so instead of guessing."]),
  P([b("Also. "), "A Browse page with every group, and a Study page with every result required by the brief, each section opening with its finding in plain words and the numbers in collapsible panels."]),
  P([b("Scope note. "), "The collection is printed books. Handwritten manuscripts need handwriting recognition, which Tesseract does not provide; this is future work."]),
);

// 2 Dataset
content.push(H1("2. Dataset"),
  H2("2.1 Source"),
  P("The Digital Library of India (DLI) mirror on the Internet Archive, collection digitallibraryindia. It is public and needs no key. In the eight study languages it holds about 434,000 books published up to 1960 or undated (English 253,682; Sanskrit 49,599; Hindi 39,102; Gujarati 37,806; Bengali 31,337; Telugu 12,477; Kannada 5,543; Tamil 4,644). For each sampled book we use its catalogue record, the archive's own whole-book OCR text where it exists, and five page images read with our own OCR."),
  H2("2.2 Sample and splits"),
  bullet("Eight languages; Urdu was left out because Tesseract reads its script poorly."),
  bullet("For each language a seeded draw (seed 2026) taken round-robin across five era bands: before 1900, 1900–1919, 1920–1939, 1940–1960 and undated. 375 books per language, 3,000 in all, so that English does not dominate."),
  bullet(`Text: the archive's whole-book OCR (hOCR or djvu text) for ${n(2971)} books; the first and last 5% are trimmed (covers, indexes) and 40 evenly spaced windows of 100 tokens kept. Books without it use our five Tesseract pages.`),
  bullet(`Splits, fixed before any result: 60% train, 20% validation, 20% test, by language with a fixed seed. Of ${n(corpus.usable)} usable books, ${n(1548)} train, ${n(515)} validation, ${n(515)} test. Every fitting step uses train books only; the test books were evaluated once.`),
  H2("2.3 Pilot before the full run"),
  P("The first 50 books of each language were read and judged before the full harvest, with a usability rule fixed in advance: median word confidence of at least 60 and a median script ratio of at least 0.80."),
  ...table("Pilot OCR quality, 50 books per language.",
    ["Language", "Median confidence", "Pages at 70+", "Tag matches script", "Agreement with archive OCR", "Usable"],
    pilot.map((p) => [p.name, f(p.median_conf, 1), `${f(p.pages_conf_ge_70_pct, 0)}%`, `${f(p.tag_matches_script_pct, 0)}%`, f(p.median_ia_similarity, 0), p.usable ? "yes" : "no"]),
    [16, 14, 12, 14, 18, 9]),
  P("Telugu fails the rule on confidence (55) but agrees 86% with the archive's own OCR, so its confidence scores run low rather than its text being bad. It was kept, and the decision is stated wherever results are reported."),
  H2("2.4 Known data problems"),
  ...table("Problems found in the real records and how each was handled.",
    ["Problem", "Handling"],
    [["The subject field holds the scanning centre, not a topic", "Dropped from features as leakage"],
      ["Some language tags are wrong", `Script detected from the OCR text; ${n(corpus.tag_mismatch)} of 3,000 books did not match their tag`],
      ["No true topic labels", "704 books (629 train and validation, 75 test) were given one of seven broad subjects, for evaluation only; they never fit or choose groups"],
      ["Printed books, not manuscripts", "Stated in the report and the application"],
      ["Rights marked as not available", "Only OCR text, catalogue fields and links are kept; no scans are redistributed, including in the Docker image"]],
    [42, 58]),
);

// 3 Preprocessing
content.push(H1("3. OCR and preprocessing"),
  H2("3.1 OCR"),
  P("Tesseract 5 runs in Docker with the eight language models. Orientation and script detection (OSD) turns each page upright and guesses its script. The pilot showed that OSD calls most Gujarati pages Bengali or Latin; when OSD disagrees with the catalogue tag, the middle page is read with both models and the more confident one wins. After the fix, 43 of 50 Gujarati pilot books use the Gujarati model; the rest are printed in Devanagari and correctly keep the Hindi model."),
  H2("3.2 Readability filter"),
  P(`A book is used if its OCR confidence is at least 50 and it yields at least 100 clean tokens. ${n(corpus.usable)} of ${n(corpus.harvested)} books pass; the other ${n(corpus.harvested - corpus.usable)} stay in the database, flagged and reported.`),
  ...table("Books per language after the readability filter.",
    ["Language", "Sampled", "Readable", "Readable share", "Median OCR confidence"],
    corpus.by_language.map((x) => [x.name, n(x.harvested), n(x.usable), pct(x.usable / x.harvested), f(x.median_conf, 1)]),
    [20, 14, 14, 16, 20]),
  H2("3.3 Text cleaning"),
  (newList(), numbered("Unicode NFC normalisation.")),
  numbered("Tokens are runs of letters and combining marks ([\\p{L}\\p{M}]+); the usual \\w+ pattern splits Indian-script words at vowel signs."),
  numbered("Tokens shorter than two characters, starting with a stray vowel sign, or mixing scripts are dropped as OCR noise."),
  numbered("Latin tokens are lower-cased and English function words removed."),
  numbered("Function words of every language are removed by a per-language document-frequency cap: a term in more than 30% of one language's books is that language's stopword. No hand-written lists, so the rule is reproducible."),
  H2("3.4 Variable relevance review"),
  ...table("Every catalogue and OCR field, with the decision and the reason.",
    ["Field", "Missing", "Distinct", "Decision", "Reason"],
    study.relevance.map((v) => [v.field, `${f(v.missing_pct, 1)}%`, n(v.distinct), v.decision, v.reason]),
    [14, 9, 9, 18, 40]),
  H2("3.5 Missing values, encoding and scaling"),
  bullet([b("Missing values. "), "Year is missing for about a fifth of usable books. It is filled with the median and a year_missing flag is added. Books with unusable OCR are flagged, not imputed."]),
  bullet([b("Encoding. "), "Detected script is one-hot encoded. The language of each book (its OCR model) is also used to remove each language's average position from the embeddings (section 5.1)."]),
  bullet([b("Scaling. "), "Year, log page count, mean OCR confidence and log token count are standardised; embedding rows are scaled to unit length."]),
  bullet([b("Use. "), "The study clusters text alone, so that groups reflect content rather than script or era. The encoded metadata block was tested in a sensitivity check (section 6.7)."]),
);

// 4 System design
content.push(pageBreak(), H1("4. System design"),
  H2("4.1 Architecture and technology"),
  ...table("Technology used in each layer.",
    ["Layer", "Choice"],
    [["Language", "Python 3.12 in Docker"], ["Data", "requests; Internet Archive scrape, metadata and download APIs; whole-book OCR text"],
      ["OCR", "Tesseract 5 with eng, hin, san, ben, guj, tel, kan, tam and osd; pytesseract, Pillow; PyMuPDF for uploaded PDFs"],
      ["ML", "scikit-learn, SciPy, NumPy, pandas; Gemini Embedding 001 through Google's API; sentence-transformers and CUDA PyTorch for the local encoders compared"],
      ["Storage", "SQLite (corpus), JSON (book text, study results), joblib (fitted models)"],
      ["Backend", "FastAPI and uvicorn"], ["Frontend", "Static HTML, CSS and JavaScript; charts drawn as SVG; dark theme built with the Hallmark design skill"],
      ["Tests", "pytest (40 tests) and an app check script (66 checks)"], ["Packaging", "Docker and Docker Compose; the API key is read from a git-ignored .env file at run time"], ["Version control", "git, one branch per team area"]],
    [22, 78]),
  H2("4.2 API"),
  ...table("Endpoints served by the application.",
    ["Method and path", "Does"],
    [["POST /api/check", "File or text in; OCR; group from each method, closeness, other close groups, five nearest books, PCA position, cautions"],
      ["GET /api/clusters", "All groups with summaries"], ["GET /api/clusters/{id}", "One group: terms, typical books, language and era mix"],
      ["GET /api/documents/{id}", "One book: catalogue fields, group, archive link"], ["GET /api/study", "All study results for the Study page"], ["GET /api/health", "Health, and whether the topic service is configured"]],
    [30, 70]),
  H2("4.3 Data flow diagrams"),
  P("The diagrams use Yourdon notation: external entities as rectangles, processes as numbered circles, data stores as open-ended boxes."),
  ...figure("reports/figures/dfd_level0.png", "Level 0 (context): the system, the user and the Internet Archive."),
  ...figure("reports/figures/dfd_level1.png", "Level 1: six processes and four data stores.", 600),
  ...figure("reports/figures/dfd_level2_p3.png", "Level 2 for process 3.0, preprocessing and features."),
  ...figure("reports/figures/dfd_level2_p4.png", "Level 2 for process 4.0, the clustering study."),
  ...figure("reports/figures/dfd_level2_p5.png", "Level 2 for process 5.0, checking a new page."),
);

// 5 Methods
const encRows = Object.entries(enc.encoders).sort((x, y) => y[1].knn_centred - x[1].knn_centred);
content.push(pageBreak(), H1("5. Methods"),
  H2("5.1 Features"),
  bullet([b("A. TF-IDF + LSA. "), `Word 1–2-grams and character 3–5-grams, weighted by TF-IDF, reduced with truncated SVD to 100 dimensions (${pct(A.explained_variance)} of variance), rows scaled to unit length. Its axes can be mapped back to words.`]),
  bullet([b("G. Sentence embeddings with the language removed. "), `Up to 10 evenly spaced 64-word passages per book are embedded and averaged. Multilingual encoders place each language in its own region, so the largest distances between books are language distances; each language's mean vector (from the fitted books) is therefore subtracted and rows rescaled. A new page is centred by the language Tesseract read it in. Then PCA to 100 dimensions (${pct(G.explained_variance)} of variance).`]),
  H2("5.2 Choosing the encoder"),
  P(`Five encoders were compared on labelled train and validation books only: how often a book's subject matches the most common subject among its seven nearest neighbours (5-fold cross-validation), before and after removing the language. This is the most topic information the numbers carry; no grouping of them can do better. Rule, fixed before the run: ${enc.rule}.`),
  ...table(`Topic information carried by each encoder (${n(encRows[0][1].books)} labelled train and validation books).`,
    ["Encoder", "As is", "Language removed"],
    [...encRows.map(([, e]) => [e.model, pct(e.knn_plain, 1), pct(e.knn_centred, 1)]), ["intfloat/multilingual-e5-large (325 books only)", "57.2%", "65.8%"]],
    [56, 20, 24], { highlight: (r) => r === 0 }),
  P("Removing the language raised every encoder by 4 to 11 points. Gemini Embedding 001, a closed model reached through Google's API, carries the most topic information; the best open model, BGE-M3, is about 7 points lower. Trading offline use for accuracy was the team's decision; section 9 lists its costs."),
  H2("5.3 Euclidean or Manhattan"),
  P("Both metrics were measured against four criteria fixed in advance: relative contrast, cophenetic correlation under average and under complete linkage, and the best silhouette with average linkage. The metric winning most criteria is chosen; a tie goes to Euclidean, which Ward linkage requires."),
  H2("5.4 Hierarchical clustering"),
  P("Ward, average and complete linkage, each cut at k = 2 to 15 (42 settings per feature set). A setting is valid if k is at least 3 and no group holds fewer than max(10 books, 1% of books)."),
  H2("5.5 DBSCAN"),
  P("MinPts takes 5, 10, 15 and 20. For each, eps takes the 10, 25, 40, 55 and 70% quantiles and the knee of the k-distance curve: 24 combinations per feature set. A combination is valid with at least two clusters and at most 50% noise; the highest silhouette on clustered books wins."),
  H2("5.6 Comparison, PCA and stability"),
  bullet("Agreement between the methods: adjusted Rand index (ARI) and normalised mutual information (NMI) on books DBSCAN groups."),
  bullet("PCA to two dimensions for side-by-side maps."),
  bullet("Stability: 20 reruns on random 80% samples, scored by ARI against the full labels, and agreement with neighbouring settings."),
  bullet("What drives the groups: NMI with detected script, era and catalogue subject; silhouette within each script; a refit on books with OCR confidence 70 or more; HDBSCAN as a check on DBSCAN."),
  H2("5.7 The final choice, by silhouette"),
  P(`Rule, fixed before the results: ${sel.rule}. Raw silhouette would pick groups that follow script, because languages sit far apart; the two limits keep the choice silhouette-based while excluding that. The rule was applied to the training books; the chosen setting was then refitted on all books without being chosen again.`),
  H2("5.8 Evaluation on unseen books"),
  P("Targets, fixed before any result (docs/evaluation_plan.md): T1, a single uploaded page lands in the same group as its whole book at least 80% of the time; T2, the group predicts a book's subject at least 10 points better than the better of two simple guesses (always the most common subject; the most common subject of the book's script); T3, median bootstrap ARI at least 0.60. Revisions were allowed on validation books only, at most three rounds, each logged; the test books were evaluated once."),
  P("Multi-tags, added in round 2 by a rule fixed beforehand: a page's tags are its nearest group plus any group it sits as close to as nine in ten of that group's own books do (at most three). Tagged scores are reported beside the strict ones, with the number of tags and the share of tags that are right; they have no targets of their own."),
);

// 6 Results
const dm = (r) => r.distance.metrics;
const critNames = [["relative_contrast", "Relative contrast"], ["cophenetic_average", "Cophenetic, average linkage"], ["cophenetic_complete", "Cophenetic, complete linkage"],
  ["best_silhouette_average", "Best silhouette, average linkage"], ["knn_same_script", "10-NN same script (context)"], ["knn_same_classification", "10-NN same subject (context)"]];
const bestBy = (grid) => { const o = {}; for (const r of grid) { if (!r.valid) continue; const k = r.linkage; if (!o[k] || r.silhouette > o[k].silhouette) o[k] = r; } return o; };
const hbG = bestBy(hG.grid), hbA = bestBy(hA.grid);
content.push(pageBreak(), H1("6. Results"),
  H2("6.1 Distance metric"),
  P(`Euclidean distance was chosen for both feature sets: it wins three of four criteria on each. Because rows are unit length, Euclidean distance is a monotone function of cosine similarity.`),
  ...table("Euclidean against Manhattan on both feature sets (all books).",
    ["Criterion", "A Euclidean", "A Manhattan", "G Euclidean", "G Manhattan"],
    critNames.map(([k, label]) => [label, f(dm(A).euclidean[k]), f(dm(A).cityblock[k]), f(dm(G).euclidean[k]), f(dm(G).cityblock[k])]),
    [34, 16, 16, 16, 16]),
  ...figure("reports/figures/G_distance.png", "Gemini embeddings: the four criteria under each metric.", 540),
  H2("6.2 The final choice"),
  ...table("The selection rule on the training books.",
    ["Feature set", "Silhouette", "Follows script (NMI)", "Bootstrap ARI", "Passes"],
    [["A: TF-IDF + LSA", f(tsel.silhouette.A), f(tsel.nmi_script.A, 2), f(tsel.boot_median.A, 2), tsel.passes.A ? "yes" : "no"],
      ["G: Gemini, language removed", f(tsel.silhouette.G), f(tsel.nmi_script.G, 2), f(tsel.boot_median.G, 2), tsel.passes.G ? "yes" : "no"]],
    [34, 16, 18, 16, 12], { highlight: (r) => r === 1 }),
  P(`TF-IDF has the higher silhouette only because its groups are scripts (NMI ${f(tsel.nmi_script.A, 2)}); it fails the limit. On the training books silhouette chose average linkage with ${tsel.setting ? tsel.setting.k : hG.final.k} groups for Gemini, without any floor on k.`),
  H2("6.3 Hierarchical clustering"),
  ...table("Best valid setting for each linkage, all books (Euclidean).",
    ["Feature set", "Linkage", "k", "Silhouette", "Largest group"],
    [...["ward", "average", "complete"].map((l) => ["A: TF-IDF + LSA", l, hbA[l].k, f(hbA[l].silhouette), pct(hbA[l].largest_share)]),
      ...["ward", "average", "complete"].map((l) => ["G: Gemini", l, hbG[l].k, f(hbG[l].silhouette), pct(hbG[l].largest_share)])],
    [26, 16, 10, 16, 16]),
  P(`Refitted on all books with the setting chosen on training books (average, k = ${hG.final.k}), the silhouette is ${f(hG.final.silhouette)}; on all books k = 5 would score marginally higher (${f(hbG.average.silhouette)}), but the plan forbids re-choosing on data that includes the test books. Silhouettes this low mean the topics overlap: devotional poetry is both religion and literature. They were higher in the first version (0.14) only because language groups are far apart.`),
  ...figure("reports/figures/G_hier_silhouette.png", "Gemini: silhouette against k for each linkage; the chosen setting is marked.", 520),
  ...figure("reports/figures/G_dendrogram.png", `Gemini, average linkage: the last 30 merges, with the cut for k = ${hG.final.k}.`, 600),
  H2("6.4 DBSCAN"),
  ...table("Gemini: every eps and MinPts combination tried (eps from the k-distance curve).",
    ["MinPts", "eps", "Clusters", "Noise", "Silhouette", "Valid"],
    dG.grid.map((r) => [r.min_pts, f(r.eps), r.n_clusters, pct(r.noise_share), f(r.silhouette), r.valid ? "yes" : "no"]),
    [12, 14, 14, 14, 16, 10], { highlight: (ri) => dG.grid[ri].min_pts === dG.final.min_pts && Math.abs(dG.grid[ri].eps - dG.final.eps) < 1e-6 }),
  P(`${dG.grid.filter((r) => r.valid).length} of 24 combinations are valid. The chosen one, MinPts ${dG.final.min_pts} with eps ${f(dG.final.eps)}, finds ${dG.final.n_clusters} dense groups and leaves ${pct(dG.final.noise_share)} of books as noise. Its groups are narrower than the hierarchical ones: medicine, Hindu and Jain philosophy, modern prose fiction, classical Tamil and Kannada poetry, regional dynastic history, Indology, administration reports, the national movement, English fiction, Buddhist scriptures and Kannada Christian texts. HDBSCAN, which allows varying density, keeps only ${pct(1 - G.extras.hdbscan.noise_share)} of books in ${G.extras.hdbscan.n_clusters} groups, and those agree closely with the hierarchical groups (ARI ${f(G.extras.hdbscan.ari_vs_hierarchical_non_noise, 2)}).`),
  ...figure("reports/figures/G_kdistance.png", "Gemini: k-distance curves for each MinPts, with the chosen eps.", 520),
  ...figure("reports/figures/G_dbscan_grid.png", "Gemini: clusters, noise and silhouette across the DBSCAN grid.", 600),
  H2("6.5 The two methods compared, and PCA"),
  P(`On TF-IDF + LSA both methods recover the scripts (ARI ${f(A.comparison.ari_non_noise, 2)} on non-noise books). On Gemini they agree moderately (ARI ${f(G.comparison.ari_non_noise, 2)}, NMI ${f(G.comparison.nmi_non_noise, 2)}): DBSCAN splits the dense parts of the hierarchical groups into narrower topics and leaves the overlapping middle as noise. PCA keeps ${pct(G.pca.explained[0] + G.pca.explained[1])} of the Gemini variance in two dimensions, so the maps show shape rather than exact distance.`),
  ...figure("reports/figures/G_pca_compare.png", "Gemini: both methods on the same PCA projection; grey = DBSCAN noise.", 620),
  ...figure("reports/figures/A_pca_compare.png", "TF-IDF + LSA: each band of points is one script; both methods find the same groups.", 620),
  H2("6.6 Stability"),
  ...table("Bootstrap and neighbouring-setting agreement (ARI with the full-data labels, all books).",
    ["Grouping", "Bootstrap median", "10th–90th percentile", "Neighbouring settings"],
    [["A hierarchical", f(med(hA.bootstrap_ari), 2), `${f(hA.bootstrap_ari.p10, 2)}–${f(hA.bootstrap_ari.p90, 2)}`, hA.neighbours.map((x) => `k=${x.k}: ${f(x.ari, 2)}`).join("; ")],
      ["A DBSCAN", f(med(dA.bootstrap_ari), 2), `${f(dA.bootstrap_ari.p10, 2)}–${f(dA.bootstrap_ari.p90, 2)}`, dA.neighbours.map((x) => f(x.ari, 2)).join("; ")],
      ["G hierarchical", f(med(hG.bootstrap_ari), 2), `${f(hG.bootstrap_ari.p10, 2)}–${f(hG.bootstrap_ari.p90, 2)}`, hG.neighbours.map((x) => `k=${x.k}: ${f(x.ari, 2)}`).join("; ")],
      ["G DBSCAN", f(med(dG.bootstrap_ari), 2), `${f(dG.bootstrap_ari.p10, 2)}–${f(dG.bootstrap_ari.p90, 2)}`, dG.neighbours.map((x) => f(x.ari, 2)).join("; ")]],
    [20, 16, 20, 44]),
  P(`Topic groups are less stable than script groups (median ${f(med(hG.bootstrap_ari), 2)} on all books, 0.58 on training books), because overlapping topics shift between neighbouring groups when a fifth of the books is removed. Neighbouring k values change little (k = 5 and 7 agree at 0.96–0.98). A refit on the ${n(G.extras.high_conf_refit.books)} books with OCR confidence 70 or more returns similar groups (ARI ${f(G.extras.high_conf_refit.ari_vs_full, 2)}).`),
  H2("6.7 What drives the groups, and the metadata check"),
  ...table("Normalised mutual information of each grouping with script, era and catalogue subject (0 none, 1 complete).",
    ["Grouping", "Script", "Era", "Catalogue subject"],
    [["A hierarchical", hA.effects], ["A DBSCAN", dA.effects], ["G hierarchical", hG.effects], ["G DBSCAN", dG.effects]]
      .map(([k, e]) => [k, f(e.nmi_script, 2), f(e.nmi_era, 2), f(e.nmi_classification, 2)]),
    [30, 20, 20, 20], { highlight: (r) => r === 2 }),
  P(`With the language removed, the groups barely depend on script (${f(hG.effects.nmi_script, 2)}) and follow the archive's own subject classification more than any other grouping (${f(hG.effects.nmi_classification, 2)}). Low OCR confidence does not predict DBSCAN noise (AUC ${f(dG.ocr_noise.auc_low_conf_predicts_noise, 2)}).`),
  ...table("Sensitivity: the encoded metadata block added to the text features (chosen hierarchical setting refitted).",
    ["Feature set", "Weight", "Silhouette", "NMI script", "ARI with text-only", "Largest group"],
    ["A", "G"].flatMap((k) => sens.feature_sets[k].rows.map((r) => [k === "A" ? "TF-IDF + LSA" : "Gemini", f(r.weight, 2), f(r.silhouette), f(r.nmi_script, 2), f(Math.abs(r.ari_vs_text_only) < 0.005 ? 0 : r.ari_vs_text_only, 2), pct(r.largest_share, 1)])),
    [20, 12, 14, 14, 20, 16]),
  P("Adding the metadata breaks the topic groups: at weight 1, 91% of books fall into one group. The study therefore clusters text alone."),
);

// 7 Accuracy on unseen books
const evRow = (lab, e) => [lab, pct(e.T1_upload_check.agreement, 1), pct(e.T1_upload_check.tagged.agreement_tagged, 1),
  pct(e.T2_subject.accuracy_groups, 1), pct(best(e.T2_subject), 1), pct(e.T2_subject.tagged.accuracy_tagged, 1), f(e.T3_bootstrap_median, 2)];
content.push(pageBreak(), H1("7. Accuracy on unseen books"),
  P(`Measured on books no fitting step saw. Validation books guided the two revision rounds; the ${n(test.held_out_books)} test books were measured once, at the end.`),
  ...table("Validation and test results (strict scores, then with tags).",
    ["Books", "Page with own book", "…with tags", "Subject from group", "Best simple guess", "…with tags", "Stability"],
    [evRow("Validation", val), evRow("Test", test)], [14, 14, 12, 14, 14, 12, 12], { highlight: (r) => r === 1 }),
  ...table("Targets on the test books.",
    ["Target", "Result", "Aim", "Met"],
    [["T1: a single page lands with its own book's group", pct(T1.agreement, 1), "80%", test.met.T1 ? "yes" : "no"],
      ["T2: subject accuracy above the best simple guess", `${f(T2.points_above_best_baseline, 1)} points (p ${f(T2.permutation_p, 4)})`, "10 points", test.met.T2 ? "yes" : "no"],
      ["T3: groups survive resampling (bootstrap ARI)", f(test.T3_bootstrap_median, 2), "0.60", test.met.T3 ? "yes" : "no"]],
    [48, 22, 14, 10]),
  bullet([b("T2 met. "), `The groups predict a book's subject ${pct(T2.accuracy_groups, 1)} of the time against ${pct(best(T2), 1)} for guessing from its script. In the first version, whose groups followed language, the margin was 3 points.`]),
  bullet([b("T1 missed. "), `${pct(T1.agreement, 1)}, about ${f(T1.agreement / T1.chance, 1)} times chance (${pct(T1.chance)}). A single page must pick 1 of ${hG.final.k} groups from noisier OCR than its book's text; the 80% aim was set when there were 3 groups. With tags, ${pct(T1.tagged.agreement_tagged, 1)} of pages include their book's group, at ${f(T1.tagged.tags_per_page, 2)} tags per page: most misses are between neighbouring groups.`]),
  bullet([b("T3 missed narrowly. "), `${f(test.T3_bootstrap_median, 2)} against 0.60: overlapping topic groups are less stable than script groups.`]),
  bullet([b("Tags. "), `A book's subject is among its tags ${pct(T2.tagged.accuracy_tagged, 1)} of the time at ${f(T2.tagged.tags_per_book, 2)} tags per book, but only ${pct(T2.tagged.tag_precision)} of all tags are right, so extra tags are a hint, not a second answer.`]),
  bullet([b("Overfitting. "), "Validation and test agree within about 2 points on every measure, so the revisions made on validation books did not overfit them."]),
  P(`Where the misses come from (labelled train and validation books): about 30% are religion against literature (devotional poetry, epics), which a second labeller would often call the other way; the "other" category (magazines, encyclopaedias, music) cannot be found by topic at all; and accuracy is lower for noisier OCR and for Sanskrit and Tamil. The test score rests on ${n(T2.labelled_heldout)} labelled test books, so it is uncertain by about ±6 points.`),
);

// 8 Interpretation
const prof = (p, nm) => [nm, n(p.size), pct(p.share), Object.entries(p.script_mix).filter(([, v]) => v >= 0.05).slice(0, 4).map(([s, v]) => `${s} ${pct(v)}`).join(", "), p.median_year ? Math.round(p.median_year) : "n/a", f(p.median_conf, 0)];
content.push(H1("8. Interpretation of the groups"),
  P("Each group was named by reading its most distinctive terms (ranked by lift) and its most typical books (those closest to its centre). Names are our reading, not subject headings."),
  ...table(`Gemini, hierarchical (average linkage, k = ${hG.final.k}).`,
    ["Group", "Books", "Share", "Main scripts", "Median year", "Median OCR conf."],
    hG.profiles.map((p) => prof(p, names.G_hier[String(p.cluster)])), [26, 9, 9, 32, 11, 13]),
  bullet([b("Every group spans several scripts. "), "Unlike the first version, no group is one language: the poetry and epics group holds Telugu, Tamil, Devanagari and Gujarati books in nearly equal shares."]),
  bullet([b("The groups are recognisable subjects. "), "Their distinctive words: dialogue verbs of novels for modern fiction; political, national, council, economic for public life; acid, surface, disease, treatment for science and medicine; Brahman, Veda, yoga for religion and philosophy; Jesus, Christ, Amen in Kannada for the small Christian group."]),
  bullet([b("Cross-language neighbours. "), "A Hindi passage on fevers finds Hindi homeopathy and Tamil fever-treatment books as its nearest neighbours; a devotional poem in English finds Krishna devotional works in Hindi, Bengali and Gujarati."]),
  ...table(`Gemini, DBSCAN (MinPts ${dG.final.min_pts}, eps ${f(dG.final.eps)}).`,
    ["Group", "Books", "Share", "Main scripts", "Median year", "Median OCR conf."],
    dG.profiles.map((p) => prof(p, names.G_dbscan[String(p.cluster)])), [26, 9, 9, 32, 11, 13]),
  H2("8.1 Responsible reading"),
  bullet("Groups are tendencies with uncertain borders; the application shows a closeness level, other close groups and the nearest books so that a reader can judge each placement."),
  bullet("The poetry and religion groups are older and have lower OCR confidence than the fiction and public-life groups; part of a split can reflect print and OCR quality, not only subject."),
  bullet("Subject labels were made by the project's assistant from titles, catalogue subjects and a text snippet, for evaluation only, and await a spot-check by the team."),
);

// 9 Application
content.push(H1("9. The application"),
  H2("9.1 Checking a new page without retraining"),
  (newList(), numbered("The upload is OCR'd as in the study. If the language is left on detect, the script detector's guess is kept only if it reads the first page at confidence 70 or more; otherwise all eight models read the first page and the most confident wins.")),
  numbered("The text is cleaned, embedded through the Gemini API, centred by its OCR language and projected with the saved PCA."),
  numbered("Hierarchical: the nearest group centre, with a closeness level against that group's own books, and any other group the page sits as close to as nine in ten of that group's books (\"also close to\")."),
  numbered("DBSCAN: the page joins a group only within eps of one of its core books; otherwise it is noise."),
  numbered("The five nearest archive books are listed with shared words and links; the page is placed on the PCA map."),
  numbered("Fewer than 20 readable words: the tool abstains. Fewer than 100 words, or OCR confidence below 50: it answers with a caution. If Google's service cannot be reached, it says so."),
  ...figure("web/assets/check-screen.png", "The check screen: a Hindi passage on treating fevers, placed with science and medicine (DBSCAN: medicine and health); its nearest books include Tamil medical works.", 600),
  H2("9.2 Docker and running it"),
  P(`docker compose up runs the image grantha:2.0 (1.11 GB, down from 6.1 GB in the first version, because the encoder no longer runs inside it). The image holds Tesseract with the eight languages, the fitted model, the study results and the website, and no page scans. The Gemini key is read at run time from a git-ignored .env file and never enters the image or the repository. A check needs an internet connection.`),
  H2("9.3 Testing"),
  P(`40 pytest tests cover sampling, OCR, text cleaning, the full study on a synthetic corpus, language centring, the tag rule, the Gemini client (with the network faked: rate limits, a missing key) and the API. An app check script exercised every path of the running container: ${checks.passed} of ${checks.total} checks passed, including real scans in all eight languages, a two-page PDF and every error path. The one failure: a Sanskrit page left on detect was read with the Hindi model, which shares its script and read it slightly more confidently; its group was the same either way.`),
);

// 10 Limits
content.push(H1("10. Limitations"),
  bullet("Printed books only; handwritten manuscripts are out of scope."),
  bullet("The encoder is a closed model reached over the internet: the application needs a connection, the page's text is sent to Google, and the model may change or be retired. The best open model tested was about 7 points lower."),
  bullet("Two targets were missed: a single page lands with its own book's group 72.5% of the time (aim 80%), and stability is 0.58 (aim 0.60)."),
  bullet("Silhouettes are low (0.06–0.07); topics overlap, and the groups are tendencies."),
  bullet("Subject labels were made by the assistant and cover 75 test books; the test accuracy is uncertain by about ±6 points."),
  bullet("OCR quality differs by script (Telugu and Sanskrit lowest), and accuracy is lower for them."),
  H2("Future work"),
  bullet("More books per language (mainly for stability and finer groups), and a team or expert check of the subject labels."),
  bullet("Unsupervised fine-tuning of an open encoder on the archive's own text, to close the gap to the closed model offline."),
  bullet("Handwriting recognition for manuscripts."),
);

// 11 Team
content.push(H1("11. Team contributions"),
  ...table("Areas, branches and parts of this report.",
    ["", "Rajith Sundar", "Etikala Sai Pranav", "Vemuri Rohan"],
    [["Area", "Data and OCR", "Clustering study", "Application and delivery"],
      ["Work", "Harvest, whole-book text, OCR container and routing, pilot quality, text cleaning, missing values, encoding, scaling, splits", "Feature sets, language centring, encoder choice, distance study, hierarchical and DBSCAN grids, stability, evaluation, tags", "FastAPI, new-page checker, upload OCR, web pages and charts, Docker, plan and documents"],
      ["Report", "Sections 2, 3; DFD level 2 for process 3", "Sections 5, 6, 7, 8; DFD level 2 for process 4", "Sections 1, 4, 9; DFD levels 0, 1 and level 2 for process 5"]],
    [12, 29, 29, 30]),
);

// References
content.push(H1("References"),
  ...[
    "Aggarwal, C. C., Hinneburg, A., Keim, D. A. (2001). On the surprising behavior of distance metrics in high dimensional space. Database Theory (ICDT 2001), LNCS 1973, 420–434. Springer. https://doi.org/10.1007/3-540-44503-X_27",
    "Campello, R. J. G. B., Moulavi, D., Sander, J. (2013). Density-based clustering based on hierarchical density estimates. PAKDD 2013, LNCS 7819, 160–172. Springer. https://doi.org/10.1007/978-3-642-37456-2_14",
    "Chen, J., Xiao, S., Zhang, P., Luo, K., Lian, D., Liu, Z. (2024). BGE M3-Embedding: Multi-lingual, multi-functionality, multi-granularity text embeddings through self-knowledge distillation. Findings of ACL 2024. arXiv:2402.03216.",
    "Deerwester, S., Dumais, S. T., Furnas, G. W., Landauer, T. K., Harshman, R. (1990). Indexing by latent semantic analysis. Journal of the American Society for Information Science, 41(6), 391–407.",
    "Deode, S., Gadre, J., Kajale, A., Joshi, A., Joshi, R. (2023). L3Cube-IndicSBERT: A simple approach for learning cross-lingual sentence representations using multilingual BERT. arXiv:2304.11434.",
    "Ester, M., Kriegel, H.-P., Sander, J., Xu, X. (1996). A density-based algorithm for discovering clusters in large spatial databases with noise. KDD-96, 226–231. AAAI Press.",
    "Feng, F., Yang, Y., Cer, D., Arivazhagan, N., Wang, W. (2022). Language-agnostic BERT sentence embedding. ACL 2022, 878–891. https://doi.org/10.18653/v1/2022.acl-long.62",
    "Hubert, L., Arabie, P. (1985). Comparing partitions. Journal of Classification, 2(1), 193–218. https://doi.org/10.1007/BF01908075",
    "Lee, J., Dai, Z., Ren, X., et al. (2025). Gemini Embedding: Generalizable embeddings from Gemini. arXiv:2503.07891.",
    "Libovický, J., Rosa, R., Fraser, A. (2020). On the language neutrality of pre-trained multilingual representations. Findings of EMNLP 2020, 1663–1674. https://doi.org/10.18653/v1/2020.findings-emnlp.150",
    "Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation and validation of cluster analysis. Journal of Computational and Applied Mathematics, 20, 53–65. https://doi.org/10.1016/0377-0427(87)90125-7",
    "Smith, R. (2007). An overview of the Tesseract OCR engine. ICDAR 2007, vol. 2, 629–633. IEEE. https://doi.org/10.1109/ICDAR.2007.4376991",
    "Vinh, N. X., Epps, J., Bailey, J. (2010). Information theoretic measures for clusterings comparison. Journal of Machine Learning Research, 11, 2837–2854.",
    "Wang, L., Yang, N., Huang, X., Yang, L., Majumder, R., Wei, F. (2024). Multilingual E5 text embeddings: A technical report. arXiv:2402.05672.",
    "Ward, J. H. (1963). Hierarchical grouping to optimize an objective function. Journal of the American Statistical Association, 58(301), 236–244. https://doi.org/10.1080/01621459.1963.10500845",
    "Internet Archive. Digital Library of India collection (digitallibraryindia). https://archive.org/details/digitallibraryindia (accessed November 2026).",
  ].map((t, k) => (k === 0 && newList(), numbered(t))));

return content;
};
