// Builds docs/Heritage_Topic_Finder_Report.docx from the study outputs in reports/ and web/data/.
// Run from the project root:  node docs/build/report.js
const fs = require("fs");
const path = require("path");
const sizeOf = (() => { const m = require("image-size"); return m.imageSize || m.default || m; })();
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, HeadingLevel, LevelFormat, PageBreak, TableOfContents, Footer, PageNumber, BorderStyle,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const J = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const study = J("web/data/study.json");
const A = J("reports/study/results_A.json"), B = J("reports/study/results_B.json");
const sel = J("reports/study/selection.json");
const sens = J("reports/study/sensitivity.json");
const pilot = J("reports/pilot_ocr_quality.json");
const names = J("reports/cluster_names.json");

const FONT = "Arial";
const W = 9638;                       // A4 with 2 cm margins, in DXA
const f = (x, d = 3) => (x == null ? "n/a" : Number(x).toFixed(d));
const pct = (x, d = 0) => `${(100 * x).toFixed(d)}%`;
const n = (x) => Number(x).toLocaleString("en-IN");

// ---------- building blocks
const P = (text, opts = {}) => new Paragraph({ spacing: { after: 120, line: 300 }, ...opts,
  children: (Array.isArray(text) ? text : [text]).map((t) => (typeof t === "string" ? new TextRun(t) : t)) });
const b = (t) => new TextRun({ text: t, bold: true });
const i = (t) => new TextRun({ text: t, italics: true });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const bullet = (t) => new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60, line: 290 },
  children: (Array.isArray(t) ? t : [t]).map((x) => (typeof x === "string" ? new TextRun(x) : x)) });
let listNo = 0;
const newList = () => { listNo += 1; };
const numbered = (t) => new Paragraph({ numbering: { reference: "numbers", level: 0, instance: listNo }, spacing: { after: 60, line: 290 },
  children: (Array.isArray(t) ? t : [t]).map((x) => (typeof x === "string" ? new TextRun(x) : x)) });
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

let figNo = 0, tabNo = 0;
function figure(rel, caption, widthPx = 620) {
  const file = path.join(ROOT, rel);
  const data = fs.readFileSync(file);
  const d = sizeOf(data);
  const w = Math.min(widthPx, 640), h = Math.round((d.height / d.width) * w);
  figNo += 1;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: "png", data, transformation: { width: w, height: h },
        altText: { title: caption, description: caption, name: path.basename(rel) } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: `Figure ${figNo}. `, bold: true, size: 18 }), new TextRun({ text: caption, size: 18 })] }),
  ];
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(caption, heads, rows, widths, { highlight } = {}) {
  const total = widths.reduce((a, c) => a + c, 0);
  const scale = W / total;
  const cw = widths.map((x) => Math.floor(x * scale));
  cw[cw.length - 1] += W - cw.reduce((a, c) => a + c, 0);
  const cell = (text, j, { head, hi } = {}) => new TableCell({
    borders, width: { size: cw[j], type: WidthType.DXA },
    shading: head ? { fill: "E8E2D6", type: ShadingType.CLEAR, color: "auto" } : hi ? { fill: "FFF4DF", type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ alignment: j > 0 && /^[-\d.,%+ ]+$|^n\/a$/.test(String(text)) ? AlignmentType.RIGHT : AlignmentType.LEFT,
      children: [new TextRun({ text: String(text), bold: !!head, size: 18 })] })],
  });
  tabNo += 1;
  return [
    new Paragraph({ spacing: { before: 160, after: 80 }, keepNext: true,
      children: [new TextRun({ text: `Table ${tabNo}. `, bold: true, size: 18 }), new TextRun({ text: caption, size: 18 })] }),
    new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: cw, rows: [
      new TableRow({ tableHeader: true, children: heads.map((h, j) => cell(h, j, { head: true })) }),
      ...rows.map((r, ri) => new TableRow({ children: r.map((c, j) => cell(c, j, { hi: highlight && highlight(ri) })) })),
    ] }),
    new Paragraph({ spacing: { after: 120 }, children: [] }),
  ];
}

// ---------- numbers used in the text
const hB = B.hierarchical, dB = B.dbscan, hA = A.hierarchical, dA = A.dbscan;
const med = (v) => v.median;
const corpus = study.corpus;

// ---------- content
const content = [];

// Title page
content.push(
  new Paragraph({ spacing: { before: 2400, after: 200 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Heritage Topic Finder", bold: true, size: 56, font: FONT })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: "An Unsupervised Grouping Study of Heritage Documents by Topic", size: 30 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: "Project report, SIH26096", size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: "Course outcomes CO2, CO3. Units III and IV: hierarchical and density clustering, PCA visualisation", size: 20 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 800, after: 80 }, children: [new TextRun({ text: "Rajith Sundar (data and OCR)", size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: "Etikala Sai Pranav (clustering study)", size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: "Vemuri Rohan (application and delivery)", size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 600 }, children: [new TextRun({ text: "Guide: ______________________     Date: November 2026", size: 22 })] }),
  pageBreak(),
);

// Contents
content.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Contents")] }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
  P(i("Right-click the table and choose Update Field if page numbers are missing.")), pageBreak());

// Abstract
content.push(H1("Abstract"),
  P(`Old scanned books in Indian digital archives carry no subject labels, so each one is read alone instead of next to the books it belongs with. We built a web application that groups ${n(corpus.usable)} printed heritage books in eight languages by topic without labels, and places a newly uploaded page among those groups without retraining. The books were drawn at random from the Digital Library of India scans on the Internet Archive (${n(corpus.harvested)} sampled, stratified by language and era), read with Tesseract 5, cleaned in each book's own script, and represented in two ways: TF-IDF with latent semantic analysis, and LaBSE multilingual sentence embeddings.`),
  P(`On each representation we compared Euclidean and Manhattan distance, hierarchical clustering with Ward, average and complete linkage (k from 2 to 15), and DBSCAN over 24 eps and MinPts combinations taken from k-distance curves. Settings were chosen by silhouette under rules fixed before the run, and checked by bootstrap stability. Word-based features grouped the books by script and nothing else (normalised mutual information with script ${f(hA.effects.nmi_script, 2)}). Multilingual embeddings, chosen by the pre-set rule, produced three cross-language groups (English-language books, religious and classical texts, and modern prose) with a silhouette of ${f(hB.final.silhouette)} and a bootstrap agreement of ${f(med(hB.bootstrap_ari), 2)}. DBSCAN found one dense core, one small group of modern fiction, and ${pct(dB.final.noise_share)} noise. The application, packaged as an offline Docker image, reads a page in about six seconds and abstains when its OCR is too weak.`),
  pageBreak());

// 1 Introduction
content.push(H1("1. Problem and use case"),
  P("India's digitisation projects scanned hundreds of thousands of books. Many catalogue records hold a title, a language tag and the scanning centre, but no subject. An archivist, librarian or researcher who holds one of these scans cannot easily find the books it belongs with."),
  P([b("Users. "), "Archivists, librarians and researchers working with unindexed scans of printed books in Indian languages."]),
  P([b("Input. "), "A page image, a PDF (first five pages) or pasted text, in English, Hindi, Sanskrit, Bengali, Gujarati, Telugu, Kannada or Tamil; the language can be left on detect."]),
  P([b("Output. "), "The topic group the page falls into from hierarchical clustering, with a closeness level measured against the group's own books; DBSCAN's verdict (within reach of a dense group, or noise); the five closest archive books with the words they share and links to their scans; and the page's position on the PCA map. When the OCR yields too few readable words, the tool says so instead of guessing."]),
  P([b("Also. "), "A Browse page with every group, its distinctive words, typical books and language mix, and a Study page with every result required by the brief, each section opening with its finding in plain words and the numbers in collapsible panels."]),
  P([b("Scope note. "), "The collection is printed books. Handwritten manuscripts need handwriting recognition, which Tesseract does not provide; this is listed as future work."]),
);

// 2 Dataset
content.push(H1("2. Dataset"),
  H2("2.1 Source"),
  P("The Digital Library of India (DLI) mirror on the Internet Archive, collection digitallibraryindia, about 578,000 items. It is public and needs no key. The National Digital Library of India mainly aggregates metadata and offers no public bulk API; the DLI scans are the files behind many of its records. Single page images are downloaded (about 1 MB each); whole PDFs never are."),
  H2("2.2 Sample"),
  bullet("Eight languages: English, Hindi, Sanskrit, Bengali, Gujarati, Telugu, Kannada, Tamil. Urdu was left out because Tesseract reads its script poorly."),
  bullet("For each language, a sampling frame of books published up to 1960 or undated; then a seeded draw (seed 2026) taken round-robin across five era bands: before 1900, 1900–1919, 1920–1939, 1940–1960 and undated."),
  bullet("375 books per language, 3,000 in all. Five body pages per book at 15, 30, 50, 70 and 85% of its length, which skips covers, contents and indexes."),
  bullet("Requests paced to about one start per second per language, cached and resumable."),
  H2("2.3 Pilot before the full run"),
  P("The first 50 books of each language were read and judged before the full harvest, with a usability rule fixed in advance: median word confidence of at least 60 and a median script ratio of at least 0.80. Agreement with the archive's own OCR was measured as a consistency check, not as ground truth."),
  ...table("Pilot OCR quality, 50 books per language (after the routing fix described in 3.1).",
    ["Language", "Median confidence", "Pages at 70+", "Tag matches script", "Agreement with archive OCR", "Usable"],
    pilot.map((p) => [p.name, f(p.median_conf, 1), `${f(p.pages_conf_ge_70_pct, 0)}%`, `${f(p.tag_matches_script_pct, 0)}%`, f(p.median_ia_similarity, 0), p.usable ? "yes" : "no"]),
    [16, 14, 12, 14, 18, 9]),
  P("Telugu fails the rule on confidence (55) but agrees 86% with the archive's own OCR, so its confidence scores run low rather than its text being bad. It was kept, and the decision is stated wherever results are reported."),
  H2("2.4 Known data problems"),
  ...table("Problems found in the real records and how each was handled.",
    ["Problem", "Handling"],
    [["The subject field holds the scanning centre (for example Banasthali, IIIT), not a topic", "Dropped from features as leakage"],
      ["Some language tags are wrong", `Script detected from the OCR text; ${n(corpus.tag_mismatch)} of 3,000 books did not match their tag`],
      ["No true topic labels", "The catalogue classification, present for about half the books, is used only as a weak outside check"],
      ["Printed books, not manuscripts", "Stated in the report and the application"],
      ["Rights marked as not available", "Only OCR text, catalogue fields and links are kept; no scans are redistributed, including in the Docker image"]],
    [50, 50]),
);

// 3 Preprocessing
content.push(H1("3. OCR and preprocessing"),
  H2("3.1 OCR"),
  P("Tesseract 5 runs in Docker with the eight language models. Orientation and script detection (OSD) turns each page upright and guesses its script. The pilot showed that OSD calls most Gujarati pages Bengali or Latin: only 3 of 50 Gujarati books were read with the Gujarati model, at a median confidence of 36. The fix: when OSD's script disagrees with the catalogue tag, the middle page is read with both models and the one with the higher mean confidence wins. After the fix, 43 of 50 Gujarati pilot books use the Gujarati model; those that do not are printed in Devanagari, and correctly keep the Hindi model."),
  H2("3.2 Readability filter"),
  P(`A book is used if its word-weighted mean confidence is at least 50 and it yields at least 100 clean tokens. ${n(corpus.usable)} of ${n(corpus.harvested)} books pass. The other ${n(corpus.harvested - corpus.usable)} stay in the database, flagged, and are reported, not silently dropped.`),
  ...table("Books per language after the readability filter.",
    ["Language", "Sampled", "Readable", "Readable share", "Median OCR confidence"],
    corpus.by_language.map((x) => [x.name, n(x.harvested), n(x.usable), pct(x.usable / x.harvested), f(x.median_conf, 1)]),
    [20, 14, 14, 16, 20]),
  H2("3.3 Text cleaning"),
  (newList(), numbered("Unicode NFC normalisation.")),
  numbered("Tokens are runs of letters and combining marks ([\\p{L}\\p{M}]+). The usual \\w+ pattern splits Indian-script words at vowel signs."),
  numbered("Tokens shorter than two characters, starting with a stray vowel sign, or mixing scripts are dropped as OCR noise; tokens in the book's own script or in Latin are kept."),
  numbered("Latin tokens are lower-cased and English function words removed."),
  numbered("Function words of every language are removed by a per-language document-frequency cap: a term in more than 30% of one language's books is that language's stopword (694 in all). No hand-written lists, so the rule is reproducible."),
  H2("3.4 Variable relevance review"),
  ...table("Every catalogue and OCR field, with the decision and the reason.",
    ["Field", "Missing", "Distinct", "Decision", "Reason"],
    study.relevance.map((v) => [v.field, `${f(v.missing_pct, 1)}%`, n(v.distinct), v.decision, v.reason]),
    [14, 9, 9, 18, 40]),
  H2("3.5 Missing values, encoding and scaling"),
  bullet([b("Missing values. "), "Year is missing for 19% of usable books. It is filled with the median (1923) and a year_missing flag is added, so undated books are not mistaken for typical-year books. Books with unusable OCR are flagged, not imputed."]),
  bullet([b("Encoding. "), "Detected script is one-hot encoded (seven scripts). Unknown categories at prediction time are ignored rather than raising an error."]),
  bullet([b("Scaling. "), "Year, log page count, mean OCR confidence and log token count are standardised to zero mean and unit variance, so year (hundreds) does not outweigh confidence (tens) in distances."]),
  bullet([b("Use. "), "The main study clusters text alone, so that groups reflect content rather than script or era. The encoded metadata block was tested in a sensitivity check (section 6.6)."]),
);

// 4 System design
content.push(pageBreak(), H1("4. System design"),
  H2("4.1 Architecture and technology"),
  ...table("Technology used in each layer.",
    ["Layer", "Choice"],
    [["Language", "Python 3.12 in Docker"], ["Harvest", "requests, Internet Archive scrape and metadata APIs"],
      ["OCR", "Tesseract 5 with eng, hin, san, ben, guj, tel, kan, tam and osd; pytesseract, Pillow; PyMuPDF for uploaded PDFs"],
      ["ML", "scikit-learn, SciPy, NumPy, pandas, sentence-transformers (LaBSE, CPU PyTorch)"],
      ["Storage", "SQLite (corpus), one JSON file per OCR'd book, joblib (fitted models), JSON (study results)"],
      ["Backend", "FastAPI and uvicorn"], ["Frontend", "Static HTML, CSS and JavaScript; charts drawn as SVG; dark theme built with the Hallmark design skill"],
      ["Tests", "pytest, 30 tests"], ["Packaging", "Docker and Docker Compose (app, pipeline and dev services)"], ["Version control", "git, one branch per team area"]],
    [22, 78]),
  H2("4.2 API"),
  ...table("Endpoints served by the application.",
    ["Method and path", "Does"],
    [["POST /api/check", "File or text in; OCR; group from each method, closeness, five nearest books with shared words, PCA position, cautions"],
      ["GET /api/clusters", "All groups with summaries"], ["GET /api/clusters/{id}", "One group: terms, typical books, language and era mix"],
      ["GET /api/documents/{id}", "One book: catalogue fields, group, archive link"], ["GET /api/study", "All study results for the Study page"], ["GET /api/health", "Health check"]],
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
content.push(pageBreak(), H1("5. Methods"),
  H2("5.1 Two feature sets"),
  bullet([b("A. TF-IDF + LSA. "), `Word 1–2-grams and character 3–5-grams (character n-grams tolerate OCR errors), weighted by TF-IDF, reduced with truncated SVD to 100 dimensions (${pct(A.explained_variance)} of variance), rows scaled to unit length. Its axes can be mapped back to words.`]),
  bullet([b("B. LaBSE embeddings. "), `Language-agnostic BERT sentence embeddings, which place 109 languages, including all eight here, in one space. Four evenly spaced 64-word chunks per book (128 word-pieces each), averaged, PCA to 100 dimensions (${pct(B.explained_variance)} of variance), rows scaled to unit length.`]),
  H2("5.2 Euclidean or Manhattan"),
  P("Both metrics were measured on the same matrices against four criteria fixed in advance: relative contrast (how much farther the farthest neighbour is than the nearest), cophenetic correlation under average and under complete linkage, and the best silhouette with average linkage. The metric winning most criteria is chosen; a tie goes to Euclidean, which Ward linkage requires. Two further measures are reported as context: how often a book's ten nearest neighbours share its script, and its catalogue subject."),
  H2("5.3 Hierarchical clustering"),
  P("Ward, average and complete linkage, each cut at k = 2 to 15 (42 settings per feature set). A setting is valid if k is at least 3 and no group holds fewer than max(10 books, 1% of books). The highest silhouette among valid settings is chosen."),
  H2("5.4 DBSCAN"),
  P("MinPts takes 5, 10, 15 and 20. For each, the distance from every book to its (MinPts − 1)th neighbour is sorted into a k-distance curve, and eps takes the curve's 10, 25, 40, 55 and 70% quantiles and its knee: 24 combinations per feature set, each grounded in the data. A combination is valid with at least two clusters and at most 50% noise; the highest silhouette on clustered books wins."),
  H2("5.5 Comparison, PCA and stability"),
  bullet("Agreement between the two methods: adjusted Rand index (ARI) and normalised mutual information (NMI) on books DBSCAN groups, plus a cross-table."),
  bullet("PCA to two dimensions for side-by-side maps, with the variance kept."),
  bullet("Stability: 20 reruns on random 80% samples, scored by ARI against the full-data labels, and agreement with neighbouring settings (k ± 1; eps one grid step either way; MinPts ± 5)."),
  bullet("What drives the groups: NMI of each grouping with detected script, era band and catalogue subject; for DBSCAN, whether low OCR confidence predicts noise (ROC AUC)."),
  H2("5.6 Choosing the final feature set"),
  P(`The rule, fixed in advance: ${sel.rule}. The application uses the chosen set.`),
);

// 6 Results
const dm = (r) => r.distance.metrics;
const critNames = [["relative_contrast", "Relative contrast"], ["cophenetic_average", "Cophenetic, average linkage"], ["cophenetic_complete", "Cophenetic, complete linkage"],
  ["best_silhouette_average", "Best silhouette, average linkage"], ["knn_same_script", "10-NN same script (context)"], ["knn_same_classification", "10-NN same subject (context)"]];
const bestBy = (grid) => { const o = {}; for (const r of grid) { if (!r.valid) continue; const k = r.linkage; if (!o[k] || r.silhouette > o[k].silhouette) o[k] = r; } return o; };
const hbB = bestBy(hB.grid), hbA = bestBy(hA.grid);
content.push(pageBreak(), H1("6. Results"),
  H2("6.1 Distance metric"),
  P(`Euclidean distance was chosen for both feature sets: it wins all four criteria on LaBSE and three of four on TF-IDF + LSA, where Manhattan has the higher relative contrast. Because rows are unit length, Euclidean distance is a monotone function of cosine similarity, the usual measure for text.`),
  ...table("Euclidean against Manhattan on both feature sets.",
    ["Criterion", "A Euclidean", "A Manhattan", "B Euclidean", "B Manhattan"],
    critNames.map(([k, label]) => [label, f(dm(A).euclidean[k]), f(dm(A).cityblock[k]), f(dm(B).euclidean[k]), f(dm(B).cityblock[k])]),
    [34, 16, 16, 16, 16]),
  ...figure("reports/figures/B_distance.png", "LaBSE embeddings: the four criteria under each metric.", 540),
  H2("6.2 Hierarchical clustering"),
  ...table("Best valid setting for each linkage (Euclidean).",
    ["Feature set", "Linkage", "k", "Silhouette", "Largest group"],
    [...["ward", "average", "complete"].map((l) => ["A: TF-IDF + LSA", l, hbA[l].k, f(hbA[l].silhouette), pct(hbA[l].largest_share)]),
      ...["ward", "average", "complete"].map((l) => ["B: LaBSE", l, hbB[l].k, f(hbB[l].silhouette), pct(hbB[l].largest_share)])],
    [26, 16, 10, 16, 16], { highlight: (r) => r === 4 }),
  P(`On TF-IDF + LSA all three linkages give the same seven groups (silhouette ${f(hA.final.silhouette)}), one per script, with Hindi and Sanskrit together in Devanagari. On LaBSE, average linkage with k = 3 scores highest (${f(hB.final.silhouette)}). Silhouettes for whole-book text embeddings are low by nature; above zero means books sit closer to their own group than to the next.`),
  ...figure("reports/figures/B_hier_silhouette.png", "LaBSE: silhouette against k for each linkage; the chosen setting is marked.", 520),
  ...figure("reports/figures/B_dendrogram.png", "LaBSE, average linkage: the last 30 merges, with the cut for k = 3.", 600),
  H2("6.3 DBSCAN"),
  ...table("LaBSE: every eps and MinPts combination tried (eps from the k-distance curve).",
    ["MinPts", "eps", "Clusters", "Noise", "Silhouette", "Valid"],
    dB.grid.map((r) => [r.min_pts, f(r.eps), r.n_clusters, pct(r.noise_share), f(r.silhouette), r.valid ? "yes" : "no"]),
    [12, 14, 14, 14, 16, 10], { highlight: (ri) => dB.grid[ri].min_pts === dB.final.min_pts && Math.abs(dB.grid[ri].eps - dB.final.eps) < 1e-6 }),
  P(`Only 5 of 24 LaBSE combinations pass the validity rule. The chosen one, MinPts ${dB.final.min_pts} with eps ${f(dB.final.eps)}, finds ${dB.final.n_clusters} dense groups and leaves ${pct(dB.final.noise_share)} of books as noise (silhouette ${f(dB.final.silhouette)} on the grouped books). Smaller eps values produce mostly noise; larger ones merge everything into one cluster. On TF-IDF + LSA, MinPts ${dA.final.min_pts} with eps ${f(dA.final.eps)} gives ${dA.final.n_clusters} groups and ${pct(dA.final.noise_share)} noise (silhouette ${f(dA.final.silhouette)}).`),
  ...figure("reports/figures/B_kdistance.png", "LaBSE: k-distance curves for each MinPts, with the chosen eps.", 520),
  ...figure("reports/figures/B_dbscan_grid.png", "LaBSE: clusters, noise and silhouette across the DBSCAN grid.", 600),
  H2("6.4 The two methods compared, and PCA"),
  P(`On TF-IDF + LSA the two methods agree almost completely (ARI ${f(A.comparison.ari_non_noise, 2)} on non-noise books): both recover the scripts. On LaBSE they barely agree (ARI ${f(B.comparison.ari_non_noise, 2)}, NMI ${f(B.comparison.nmi_non_noise, 2)}). DBSCAN finds one large dense core and one small dense group and declines to group the sparse remainder, while hierarchical clustering must place every book and so cuts a continuum into three parts. PCA keeps ${pct(B.pca.explained[0] + B.pca.explained[1])} of LaBSE's variance in two dimensions and ${pct(A.pca.explained[0] + A.pca.explained[1])} of TF-IDF + LSA's, so the maps show shape rather than exact distance.`),
  ...figure("reports/figures/B_pca_compare.png", "LaBSE: both methods on the same PCA projection. Group 1 = English-language books, 2 = religious and classical texts, 3 = modern prose (hierarchical); grey = DBSCAN noise.", 620),
  ...figure("reports/figures/A_pca_compare.png", "TF-IDF + LSA: each line of points is one script; both methods find the same groups.", 620),
  H2("6.5 Stability"),
  ...table("Bootstrap and neighbouring-setting agreement (ARI with the full-data labels).",
    ["Grouping", "Bootstrap median", "10th–90th percentile", "Neighbouring settings"],
    [["A hierarchical", f(med(hA.bootstrap_ari), 2), `${f(hA.bootstrap_ari.p10, 2)}–${f(hA.bootstrap_ari.p90, 2)}`, hA.neighbours.map((x) => `k=${x.k}: ${f(x.ari, 2)}`).join("; ")],
      ["A DBSCAN", f(med(dA.bootstrap_ari), 2), `${f(dA.bootstrap_ari.p10, 2)}–${f(dA.bootstrap_ari.p90, 2)}`, dA.neighbours.map((x) => f(x.ari, 2)).join("; ")],
      ["B hierarchical", f(med(hB.bootstrap_ari), 2), `${f(hB.bootstrap_ari.p10, 2)}–${f(hB.bootstrap_ari.p90, 2)}`, hB.neighbours.map((x) => `k=${x.k}: ${f(x.ari, 2)}`).join("; ")],
      ["B DBSCAN", f(med(dB.bootstrap_ari), 2), `${f(dB.bootstrap_ari.p10, 2)}–${f(dB.bootstrap_ari.p90, 2)}`, dB.neighbours.map((x) => f(x.ari, 2)).join("; ")]],
    [20, 16, 20, 44]),
  P("The LaBSE hierarchical groups are reasonably stable: a random fifth of the books can be removed and they come back with ARI around 0.71, and k = 4 mostly splits one group (0.81). DBSCAN on LaBSE is sensitive to eps, as expected when the density is nearly uniform."),
  H2("6.6 What drives the groups, and the metadata check"),
  ...table("Normalised mutual information of each grouping with script, era and catalogue subject (0 none, 1 complete).",
    ["Grouping", "Script", "Era", "Catalogue subject"],
    [["A hierarchical", hA.effects], ["A DBSCAN", dA.effects], ["B hierarchical", hB.effects], ["B DBSCAN", dB.effects]]
      .map(([k, e]) => [k, f(e.nmi_script, 2), f(e.nmi_era, 2), f(e.nmi_classification, 2)]),
    [30, 20, 20, 20], { highlight: (r) => r === 2 }),
  P(`Word-based groups are script groups. LaBSE groups depend on script far less (${f(hB.effects.nmi_script, 2)}), so LaBSE is the final feature set under the pre-set rule. Neither depends on era. Among usable books, low OCR confidence barely predicts DBSCAN noise (AUC ${f(dB.ocr_noise.auc_low_conf_predicts_noise, 2)} for LaBSE, ${f(dA.ocr_noise.auc_low_conf_predicts_noise, 2)} for TF-IDF), because the readability filter had already removed the worst scans.`),
  ...table("Sensitivity: the encoded metadata block added to the text features (chosen hierarchical setting refitted).",
    ["Feature set", "Weight", "Silhouette", "NMI script", "ARI with text-only", "Largest group"],
    ["A", "B"].flatMap((k) => sens.feature_sets[k].rows.map((r) => [k === "A" ? "TF-IDF + LSA" : "LaBSE", f(r.weight, 2), f(r.silhouette), f(r.nmi_script, 2), f(Math.abs(r.ari_vs_text_only) < 0.005 ? 0 : r.ari_vs_text_only, 2), pct(r.largest_share, 1)])),
    [20, 12, 14, 14, 20, 16]),
  P("Adding the metadata leaves the TF-IDF script groups unchanged but destroys the LaBSE groups: at weight 0.5, 99.7% of books fall into one group. The weak topical structure is easily swamped by strong low-dimensional covariates, which is why the study clusters text alone."),
);

// 7 Interpretation
const prof = (p, nm) => [nm, n(p.size), pct(p.share), Object.entries(p.script_mix).filter(([, v]) => v >= 0.01).slice(0, 4).map(([s, v]) => `${s} ${pct(v)}`).join(", "), p.median_year ? Math.round(p.median_year) : "n/a", f(p.median_conf, 0)];
content.push(pageBreak(), H1("7. Interpretation of the groups"),
  P("Each group was named by reading its most distinctive terms (ranked by lift, so that merely common words do not win) and its five most typical books (those closest to the group's centre). No language model was used. Names are our reading, not subject headings."),
  ...table("LaBSE, hierarchical (average linkage, k = 3).",
    ["Group", "Books", "Share", "Main scripts", "Median year", "Median OCR conf."],
    hB.profiles.map((p) => prof(p, names.B_hier[String(p.cluster)])), [24, 9, 9, 34, 11, 13]),
  bullet([b("English-language books. "), "History, travel and essays (typical: Robert Owen; The History of Civilization; A Narrative of the Expedition to the River Niger). Separated by language, as expected: few English books sit near Indian-language ones in meaning space."]),
  bullet([b("Religious and classical texts. "), "Across Tamil, Hindi/Sanskrit, Telugu, Gujarati and Kannada (typical: a Telugu Ramayana, the Bhagavad Gita, a puja manual, the Andhra Champu Bhagavatam, a Tamil purana). Older (median year 1919), with catalogue subjects led by literature, religion and devotional works."]),
  bullet([b("Modern prose and essays. "), "Across Bengali, Hindi, Kannada and Gujarati (typical: Dekha Socha Samjha, 1951; Patrabali 1912–1932; Tanavana, 1946). Later (median year 1930), with higher OCR confidence."]),
  ...table("LaBSE, DBSCAN (MinPts 20, eps 1.029).",
    ["Group", "Books", "Share", "Main scripts", "Median year", "Median OCR conf."],
    dB.profiles.map((p) => prof(p, names.B_dbscan[String(p.cluster)])), [24, 9, 9, 34, 11, 13]),
  P("DBSCAN's small dense group is modern fiction and stories in Bengali and Kannada (typical: a Bengali Grimm collection, Kannada novels of the 1930s–50s); its main body holds classical, scholarly and English books; the rest is noise."),
  H2("7.1 Responsible reading"),
  bullet("The classical and modern groups differ in era and OCR quality as well as subject (median confidence 63 against 76). Some of the split may reflect how well each script is read rather than what the books are about."),
  bullet("Groups are tendencies with uncertain borders. The application shows a closeness level and the nearest books so that a reader can judge each placement."),
  bullet("Catalogue subjects exist for about half the books and are inconsistent; they were used only to check, never to form or name groups."),
);

// 8 Application
content.push(H1("8. The application"),
  H2("8.1 Checking a new page without retraining"),
  (newList(), numbered("The upload is OCR'd as in the study (orientation, then the language model). If the language is left on detect, the script detector's guess is kept only if it reads the first page at confidence 70 or more; otherwise all eight models read the first page and the most confident wins. This was added after the detector called a real Tamil scan Latin (confidence 23); it now reads as Tamil at 73.")),
  numbered("The text is cleaned and turned into the same 100 features by the saved transformers."),
  numbered("Hierarchical: the nearest centroid, with the distance compared with that group's own books (closer than its median book, within its 90th percentile, within its farthest book, or outside)."),
  numbered("DBSCAN: the page joins a group only if it lies within eps of one of that group's core books; otherwise it is noise."),
  numbered("The five nearest archive books are listed with the words they share and links to their scans; the page is placed on the PCA map."),
  numbered("Fewer than 20 readable words: the tool abstains. Fewer than 100 words, or confidence below 50 (the bar archive books had to meet): it answers with a caution."),
  ...figure("web/assets/check-screen.png", "The check screen after a Tamil page from outside the sample was uploaded with the language left on detect. Its nearest books are classical Tamil works (Kuruntokai, Tolkappiyam).", 600),
  H2("8.2 Pages"),
  bullet("Landing: what the tool does, a worked example on a real page, and the two paths (check a page, browse the groups)."),
  bullet("Check a page: upload or paste, then the result."),
  bullet("Browse the groups: each group's distinctive words, typical books, language mix and place on the map."),
  bullet("The study: every result in this report, each section opening with its finding in plain words, numbers in collapsible panels, and the limits."),
  bullet("About: data source, rights and limits."),
  H2("8.3 Docker and running it"),
  P("docker compose up runs the image heritage-topics:1.0 on port 8000. The image (6.1 GB) holds Tesseract with the eight languages, CPU PyTorch, LaBSE, the fitted models, the study results and the website, and holds no page scans. Run with networking disabled, it served the health check, every page and a Tamil scan check in about six seconds. The pipeline service reruns every step of the study for reproducibility; the steps are listed in the README."),
  H2("8.4 Testing"),
  P("30 pytest tests cover sampling, OCR (rotated pages, a wrong catalogue tag, automatic language choice), text cleaning, the full study on a synthetic corpus, the checker and the API."),
);

// 9 Limits
content.push(H1("9. Limitations"),
  bullet("Printed books only; handwritten manuscripts are out of scope."),
  bullet("OCR quality differs by script (Telugu and Sanskrit lowest), and weaker scripts lose more books to the readability filter."),
  bullet("Five pages stand in for each book; a preface or an index page can pull a book toward the wrong group."),
  bullet("The sample follows the archive's own mix of subjects within each language and era."),
  bullet("Silhouettes are low (0.107 for the final setting) and DBSCAN leaves 37% of books as noise; the groups are exploratory."),
  bullet("The application image is 6.1 GB, larger than the 2–3 GB planned, because PyTorch and LaBSE together take about 3 GB."),
  H2("Future work"),
  bullet("More pages per book; an Indic-specific sentence model (IndicSBERT) compared with LaBSE; HDBSCAN for varying density."),
  bullet("A few hundred books labelled by subject experts to measure the groups against."),
  bullet("Handwriting recognition for manuscripts."),
);

// 10 Team
content.push(H1("10. Team contributions"),
  ...table("Areas, branches and parts of this report.",
    ["", "Rajith Sundar", "Etikala Sai Pranav", "Vemuri Rohan"],
    [["Area", "Data and OCR", "Clustering study", "Application and delivery"],
      ["Work", "Harvest, OCR container and routing, pilot quality, text cleaning, missing values, encoding, scaling, preprocessing log", "Feature sets, distance study, hierarchical and DBSCAN grids, stability, comparison, PCA, profiles, sensitivity check", "FastAPI, new-page checker, upload OCR, web pages and charts, Docker, plan and documents"],
      ["Report", "Sections 2, 3; DFD level 2 for process 3", "Sections 5, 6, 7; DFD level 2 for process 4", "Sections 1, 4, 8; DFD levels 0, 1 and level 2 for process 5"]],
    [12, 29, 29, 30]),
);

// References
content.push(H1("References"),
  ...[
    "Feng, F., Yang, Y., Cer, D., Arivazhagan, N., Wang, W. (2022). Language-agnostic BERT Sentence Embedding. Proceedings of ACL.",
    "Ester, M., Kriegel, H.-P., Sander, J., Xu, X. (1996). A density-based algorithm for discovering clusters in large spatial databases with noise. Proceedings of KDD.",
    "Deerwester, S., Dumais, S. T., Furnas, G. W., Landauer, T. K., Harshman, R. (1990). Indexing by latent semantic analysis. Journal of the American Society for Information Science.",
    "Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation and validation of cluster analysis. Journal of Computational and Applied Mathematics.",
    "Hubert, L., Arabie, P. (1985). Comparing partitions. Journal of Classification.",
    "Ward, J. H. (1963). Hierarchical grouping to optimize an objective function. Journal of the American Statistical Association.",
    "Smith, R. (2007). An overview of the Tesseract OCR engine. Proceedings of ICDAR.",
    "Aggarwal, C. C., Hinneburg, A., Keim, D. A. (2001). On the surprising behavior of distance metrics in high dimensional space. Proceedings of ICDT.",
    "Internet Archive. Digital Library of India collection (digitallibraryindia). https://archive.org/details/digitallibraryindia",
  ].map((t, k) => (k === 0 && newList(), numbered(t))));

const doc = new Document({
  creator: "Heritage Topic Finder team", title: "Heritage Topic Finder: project report",
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 32, bold: true, color: "3B2A1A" }, paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: "3B2A1A" }, paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 23, bold: true }, paragraph: { spacing: { before: 200, after: 100 }, keepNext: true, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] },
  features: { updateFields: true },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Heritage Topic Finder, SIH26096    ", size: 16, color: "808080" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "808080" })] })] }) },
    children: content,
  }],
});

const out = path.join(ROOT, "docs", "Heritage_Topic_Finder_Report.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(out, buf); console.log("wrote", out, figNo, "figures", tabNo, "tables"); });
