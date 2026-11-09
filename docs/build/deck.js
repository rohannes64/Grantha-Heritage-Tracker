// Builds docs/Grantha_Deck.pptx. Run from the project root: node docs/build/deck.js
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const sizeOf = (() => { const m = require("image-size"); return m.imageSize || m.default || m; })();

const ROOT = path.resolve(__dirname, "..", "..");
const J = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const A = J("reports/study/results_A.json"), B = J("reports/study/results_B.json");
const study = J("web/data/study.json");
const sens = J("reports/study/sensitivity.json");
const names = J("reports/cluster_names.json");
const f = (x, d = 2) => Number(x).toFixed(d);
const pct = (x) => `${Math.round(100 * x)}%`;

// Colours from the app's Darkroom theme
const C = { bg: "16120F", panel: "221C17", ink: "EDE6D8", ink2: "B9AE9C", mute: "857A6A", amber: "E8913A", rule: "3A3129" };
const FONT = "Arial";

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";            // 13.33 x 7.5 in
pptx.title = "Grantha";
pptx.author = "Rajith Sundar, Etikala Sai Pranav, Vemuri Rohan";

const SW = 13.33, M = 0.6;

function slide(title, notes) {
  const s = pptx.addSlide();
  s.background = { color: C.bg };
  if (title) {
    s.addText(title, { x: M, y: 0.4, w: SW - 2 * M, h: 0.8, fontFace: FONT, fontSize: 30, bold: true, color: C.ink, margin: 0 });
  }
  s.addText("Grantha  ·  SIH26096", { x: M, y: 7.0, w: 6, h: 0.3, fontFace: FONT, fontSize: 10, color: C.mute, margin: 0 });
  if (notes) s.addNotes(notes);
  return s;
}
function body(s, lines, { x = M, y = 1.45, w = SW - 2 * M, h = 5.2, size = 18 } = {}) {
  s.addText(lines.map((t, k) => ({ text: typeof t === "string" ? t : t.text,
    options: { bullet: { indent: 18 }, breakLine: k < lines.length - 1, bold: typeof t !== "string" && t.bold, color: C.ink, paraSpaceAfter: 10 } })),
  { x, y, w, h, fontFace: FONT, fontSize: size, color: C.ink, valign: "top", margin: 0 });
}
function image(s, rel, { x, y, w, h }) {
  const d = sizeOf(fs.readFileSync(path.join(ROOT, rel)));
  const r = d.width / d.height;
  let iw = w, ih = w / r;
  if (ih > h) { ih = h; iw = h * r; }
  s.addImage({ path: path.join(ROOT, rel), x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih });
}
function stat(s, value, label, x, y, w = 3.6) {
  s.addText(value, { x, y, w, h: 0.9, fontFace: FONT, fontSize: 40, bold: true, color: C.amber, margin: 0 });
  s.addText(label, { x, y: y + 0.9, w, h: 0.7, fontFace: FONT, fontSize: 14, color: C.ink2, margin: 0, valign: "top" });
}
function table(s, rows, { x = M, y = 1.5, w = SW - 2 * M, colW, size = 14, hi } = {}) {
  const data = rows.map((r, ri) => r.map((c) => ({ text: String(c), options: {
    bold: ri === 0, color: ri === 0 ? C.ink2 : C.ink,
    fill: { color: ri === 0 ? C.panel : hi && hi(ri) ? "3A2A18" : C.bg },
  } })));
  s.addTable(data, { x, y, w, colW, fontFace: FONT, fontSize: size, border: { type: "solid", pt: 0.5, color: C.rule }, margin: 0.06 });
}

// 1. Title
{
  const s = pptx.addSlide();
  s.background = { color: C.bg };
  s.addText("Grantha", { x: M, y: 2.0, w: 12, h: 1.2, fontFace: FONT, fontSize: 48, bold: true, color: C.ink, margin: 0 });
  s.addText("An unsupervised grouping study of heritage documents by topic", { x: M, y: 3.2, w: 12, h: 0.6, fontFace: FONT, fontSize: 22, color: C.amber, margin: 0 });
  s.addText("SIH26096  ·  Hierarchical and density clustering, PCA visualisation", { x: M, y: 3.9, w: 12, h: 0.5, fontFace: FONT, fontSize: 16, color: C.ink2, margin: 0 });
  s.addText("Rajith Sundar  ·  Etikala Sai Pranav  ·  Vemuri Rohan", { x: M, y: 5.6, w: 12, h: 0.5, fontFace: FONT, fontSize: 16, color: C.ink, margin: 0 });
  s.addNotes("Introduce the team and the problem in one line: old scanned Indian books have no subject labels; we group them by topic without labels and let anyone place a new page among the groups.");
}

// 2. Problem
{
  const s = slide("Old scans have no subject labels", "Rohan. The user is an archivist or researcher holding an unindexed scan. Show the input and output, and stress that nothing is retrained when a page is checked.");
  body(s, [
    "Indian digital archives hold hundreds of thousands of scanned books with a title, a language tag and the scanning centre, but no subject.",
    "A reader holding one scan cannot find the books it belongs with.",
    { text: "Input: a page image, a PDF or pasted text, in 8 languages.", bold: true },
    { text: "Output: its topic group from two methods, how sure the match is, the 5 closest archive books with shared words, and its place on the PCA map.", bold: true },
    "It abstains when the OCR is too weak to judge.",
  ], { w: 7.4 });
  stat(s, "2,578", "printed books grouped, in 8 languages", 8.8, 1.6);
  stat(s, "0", "labels used to form the groups", 8.8, 3.4);
  stat(s, "6 s", "to check one page, offline", 8.8, 5.2);
}

// 3. Data
{
  const s = slide("Data: a stratified sample of 3,000 real books", "Rajith. Source, sample design and the pilot. Explain why NDLI could not be used directly and why we never download whole PDFs.");
  body(s, [
    "Digital Library of India scans on the Internet Archive (about 578,000 items, public, no key).",
    "375 books per language: English, Hindi, Sanskrit, Bengali, Gujarati, Telugu, Kannada, Tamil.",
    "Seeded draw, round-robin across 5 era bands (to 1960, plus undated).",
    "5 body pages per book at 15–85% of its length: no covers or indexes.",
    "Pilot of 50 books per language first, with a usability rule fixed in advance.",
    "Rights: only OCR text, catalogue fields and links are kept. No scans are redistributed.",
  ], { w: 6.6, size: 16 });
  table(s, [["Language", "Readable", "Median OCR conf."], ...study.corpus.by_language.map((x) => [x.name, `${x.usable} of ${x.harvested}`, f(x.median_conf, 0)])],
    { x: 7.6, y: 1.5, w: 5.1, colW: [1.7, 1.8, 1.6], size: 13 });
}

// 4. OCR
{
  const s = slide("OCR: measured, then fixed where it failed", "Rajith. Tesseract's script detector misroutes Gujarati and, in the app, called a Tamil scan Latin. Both fixes choose the model by OCR confidence. Telugu: low confidence but 86% agreement with the archive's OCR, so kept.");
  stat(s, "3 → 43", "Gujarati pilot books read with the Gujarati model, out of 50, after the confidence check", M, 1.6, 4.0);
  stat(s, "23 → 73", "OCR confidence on a Tamil upload the script detector had called Latin", 4.9, 1.6, 4.0);
  stat(s, "86%", "Telugu agreement with the archive's own OCR, despite median confidence 55", 9.2, 1.6, 3.6);
  body(s, [
    "Tesseract 5 in Docker with 8 language models; every page turned upright first.",
    "When detected script and catalogue disagree, both models read a page and the more confident wins.",
    "Readable book: mean confidence of at least 50 and at least 100 clean words. 2,578 of 3,000 pass; the rest are flagged, not dropped silently.",
  ], { y: 3.9, h: 2.8, size: 16 });
}

// 5. Preprocessing
{
  const s = slide("Preprocessing", "Rajith. Tokeniser keeps vowel signs; stopwords learned per language. The subject field turned out to be the scanning centre: leakage. Missing years: median plus a flag. Scaling: standardise. Mention the sensitivity check result.");
  body(s, [
    "Tokens: [\\p{L}\\p{M}]+ keeps Indic vowel signs inside words (\\w+ splits them).",
    "Stopwords learned per language: a term in more than 30% of that language's books (694 in all).",
    "Variable relevance: the archive's subject field holds the scanning centre, not a topic, so it was dropped as leakage.",
    "Missing values: year missing for 19%, filled with the median (1923) plus a year-missing flag.",
    "Encoding and scaling: script one-hot; year, pages, OCR confidence and length standardised.",
    { text: `Sensitivity check: adding this metadata to the text at weight 0.5 merges ${(100 * sens.feature_sets.B.rows[2].largest_share).toFixed(1)}% of books into one group, so the study clusters text alone.`, bold: true },
  ], { size: 17 });
}

// 6. System
{
  const s = slide("System design", "Rohan. Walk the Level 1 DFD: harvest, OCR, preprocess and features, clustering study, check a new page, browse. Level 0 and Level 2 diagrams are in the report.");
  image(s, "reports/figures/dfd_level1.png", { x: M, y: 1.3, w: 7.6, h: 5.5 });
  body(s, [
    "Python 3.12, Tesseract 5, scikit-learn, SciPy, sentence-transformers.",
    "FastAPI serves the API and a static website.",
    "SQLite corpus, joblib models, JSON results.",
    "Docker: an offline app image and a pipeline image that reruns the study.",
    "30 pytest tests.",
  ], { x: 8.6, y: 1.5, w: 4.2, size: 15 });
}

// 7. Methods
{
  const s = slide("Two feature sets, two methods, rules fixed in advance", "Pranav. Two representations, the same books. Every choice (metric, setting, final feature set) is made by a rule written before the run, so we cannot pick the result we like.");
  table(s, [["", "A: TF-IDF + LSA", "B: LaBSE embeddings"],
    ["Built from", "word 1–2-grams + character 3–5-grams", "multilingual sentence model, 109 languages"],
    ["Reduced to", `100 dims (SVD, ${pct(A.explained_variance)} of variance)`, `100 dims (PCA, ${pct(B.explained_variance)} of variance)`],
    ["Hierarchical", "Ward, average, complete; k = 2–15", "Ward, average, complete; k = 2–15"],
    ["DBSCAN", "24 eps × MinPts from k-distance curves", "24 eps × MinPts from k-distance curves"]],
  { y: 1.5, colW: [2.4, 4.8, 4.9], size: 15 });
  body(s, [
    "Metric: Euclidean vs Manhattan on 4 pre-set criteria.",
    "Setting: best silhouette among valid settings; stability by 20 bootstrap reruns.",
    "Final feature set: groups that depend least on script, among those with silhouette > 0 and bootstrap ARI ≥ 0.5.",
  ], { y: 4.6, h: 2.2, size: 16 });
}

// 8. Distance
{
  const s = slide("Euclidean, measured rather than assumed", "Pranav. On LaBSE Euclidean wins all four criteria; on TF-IDF three of four (Manhattan has higher contrast). Unit-length rows make Euclidean a monotone function of cosine similarity.");
  image(s, "reports/figures/B_distance.png", { x: M, y: 1.3, w: 7.4, h: 5.4 });
  const e = B.distance.metrics.euclidean, m = B.distance.metrics.cityblock;
  table(s, [["LaBSE", "Euclid.", "Manh."], ["Relative contrast", f(e.relative_contrast), f(m.relative_contrast)],
    ["Cophenetic, average", f(e.cophenetic_average), f(m.cophenetic_average)], ["Cophenetic, complete", f(e.cophenetic_complete), f(m.cophenetic_complete)],
    ["Best silhouette", f(e.best_silhouette_average, 3), f(m.best_silhouette_average, 3)]], { x: 8.4, y: 1.6, w: 4.3, colW: [2.3, 1.0, 1.0], size: 13 });
  s.addText("Euclidean wins 4 of 4 on LaBSE, 3 of 4 on TF-IDF.", { x: 8.4, y: 4.4, w: 4.3, h: 1, fontFace: FONT, fontSize: 16, color: C.amber, bold: true, margin: 0 });
}

// 9. Hierarchical
{
  const s = slide("Hierarchical clustering", `Pranav. On LaBSE average linkage with k=3 has the best valid silhouette (${f(B.hierarchical.final.silhouette, 3)}). Low silhouettes are normal for whole-book text. On TF-IDF every linkage gives the same 7 script groups (0.477).`);
  image(s, "reports/figures/B_hier_silhouette.png", { x: M, y: 1.3, w: 6.0, h: 3.4 });
  image(s, "reports/figures/B_dendrogram.png", { x: 6.8, y: 1.3, w: 6.0, h: 3.4 });
  body(s, [
    `LaBSE: average linkage, k = 3, silhouette ${f(B.hierarchical.final.silhouette, 3)} (Ward 0.099, complete 0.089).`,
    "TF-IDF + LSA: all three linkages give the same 7 groups, one per script (silhouette 0.477).",
    "Valid setting: k ≥ 3 and every group at least 1% of the books.",
  ], { y: 4.9, h: 1.9, size: 16 });
}

// 10. DBSCAN
{
  const df = B.dbscan.final;
  const s = slide("DBSCAN", `Pranav. eps values come from the k-distance curves, so they are grounded in the data. Only 5 of 24 LaBSE settings are valid: smaller eps is mostly noise, larger merges everything. Chosen: MinPts ${df.min_pts}, eps ${f(df.eps, 3)}.`);
  image(s, "reports/figures/B_kdistance.png", { x: M, y: 1.3, w: 6.0, h: 3.4 });
  image(s, "reports/figures/B_dbscan_grid.png", { x: 6.8, y: 1.3, w: 6.0, h: 3.4 });
  body(s, [
    `LaBSE: MinPts ${df.min_pts}, eps ${f(df.eps, 3)}: ${df.n_clusters} dense groups, ${pct(df.noise_share)} noise, silhouette ${f(df.silhouette, 3)}.`,
    `TF-IDF + LSA: MinPts ${A.dbscan.final.min_pts}, eps ${f(A.dbscan.final.eps, 3)}: ${A.dbscan.final.n_clusters} groups, ${pct(A.dbscan.final.noise_share)} noise.`,
    "4 MinPts values × 6 eps values (5 quantiles of the k-distance curve plus its knee).",
  ], { y: 4.9, h: 1.9, size: 16 });
}

// 11. Key finding
{
  const s = slide("The finding: words find scripts, meaning crosses them", "Pranav. This is the central result. TF-IDF groups match the scripts exactly. LaBSE groups depend on script far less, so the rule picks LaBSE.");
  image(s, "reports/figures/A_pca_compare.png", { x: M, y: 1.3, w: 6.0, h: 2.7 });
  image(s, "reports/figures/B_pca_compare.png", { x: 6.8, y: 1.3, w: 6.0, h: 2.7 });
  s.addText("TF-IDF + LSA: one line per script", { x: M, y: 4.0, w: 6, h: 0.35, fontFace: FONT, fontSize: 12, color: C.ink2, margin: 0, align: "center" });
  s.addText("LaBSE: languages mix", { x: 6.8, y: 4.0, w: 6, h: 0.35, fontFace: FONT, fontSize: 12, color: C.ink2, margin: 0, align: "center" });
  const row = (label, r) => [label, f(r.effects.nmi_script), f(r.effects.nmi_era), f(r.effects.nmi_classification)];
  table(s, [["Grouping (NMI with …)", "Script", "Era", "Catalogue subject"],
    row("TF-IDF + LSA, hierarchical", A.hierarchical), row("TF-IDF + LSA, DBSCAN", A.dbscan), row("LaBSE, hierarchical", B.hierarchical), row("LaBSE, DBSCAN", B.dbscan)],
  { y: 4.5, colW: [4.6, 2.5, 2.5, 2.5], size: 14, hi: (ri) => ri === 3 });
}

// 12. Groups
{
  const s = slide("Three groups across languages (LaBSE, hierarchical)", "Pranav. Names come from reading each group's distinctive words and typical books, not from a model. Note the confound: the classical group is older and has lower OCR confidence.");
  const P = B.hierarchical.profiles;
  const mix = (p) => Object.entries(p.script_mix).filter(([, v]) => v >= 0.01).slice(0, 4).map(([k, v]) => `${k} ${pct(v)}`).join(", ");
  table(s, [["Group", "Books", "Scripts", "Median year", "OCR conf."], ...P.map((p) => [names.B_hier[String(p.cluster)], p.size, mix(p), Math.round(p.median_year), Math.round(p.median_conf)])],
    { y: 1.5, colW: [3.2, 1.0, 5.4, 1.3, 1.2], size: 14 });
  body(s, [
    "Religious and classical: a Telugu Ramayana, the Bhagavad Gita, a puja manual, a Tamil purana.",
    "Modern prose: essays and letters of the 1930s–50s in Bengali, Hindi, Kannada and Gujarati.",
    "DBSCAN adds one small dense group: modern fiction in Bengali and Kannada (126 books).",
    "Caution: the classical group is also older and less legible (OCR 63 vs 76).",
  ], { y: 3.9, h: 2.9, size: 16 });
}

// 13. Stability
{
  const s = slide("How far to trust the groups", "Pranav. Bootstrap: 20 reruns on 80% samples. Hierarchical groups come back well; DBSCAN is sensitive to eps. The two methods barely agree on LaBSE: hierarchical cuts a continuum, DBSCAN finds one dense region.");
  const hb = B.hierarchical.bootstrap_ari, db = B.dbscan.bootstrap_ari;
  stat(s, f(hb.median), `hierarchical: median bootstrap ARI (${f(hb.p10)}–${f(hb.p90)})`, M, 1.5);
  stat(s, f(db.median), `DBSCAN: median bootstrap ARI (${f(db.p10)}–${f(db.p90)})`, 4.6, 1.5);
  stat(s, f(B.comparison.ari_non_noise), "agreement between the two methods (ARI, non-noise books)", 8.6, 1.5);
  body(s, [
    "k = 4 mostly splits one group (ARI 0.81 with k = 3); k = 2 merges two (0.41).",
    "DBSCAN moves with eps (ARI 0.09 and 0.17 one grid step either way).",
    `Among readable books, low OCR confidence barely predicts DBSCAN noise (AUC ${f(B.dbscan.ocr_noise.auc_low_conf_predicts_noise)}).`,
    "Silhouette 0.107: groups are tendencies, not categories.",
  ], { y: 3.9, h: 2.9, size: 16 });
}

// 14. App
{
  const s = slide("The app: check a page", "Rohan. Live demo if possible: upload a page, leave the language on detect. The screenshot is a Tamil page from outside the sample; its nearest books are classical Tamil works.");
  image(s, "web/assets/check-screen.png", { x: M, y: 1.3, w: 7.8, h: 5.5 });
  body(s, [
    "Nearest centroid, judged against the group's own books.",
    "DBSCAN: joins a group only within eps of a core book.",
    "5 nearest books, shared words, archive links.",
    "Abstains under 20 words; cautions on weak OCR.",
    "No retraining, nothing stored.",
  ], { x: 8.8, y: 1.5, w: 4.0, size: 15 });
}

// 15. Delivery
{
  const s = slide("Delivered", "Rohan. Show docker compose up; mention the offline test and the 6.1 GB size and why.");
  stat(s, "1 command", "docker compose up: the site and API on port 8000", M, 1.5);
  stat(s, "Offline", "tested with networking off: health, pages and a scan check", 4.6, 1.5);
  stat(s, "30", "pytest tests, all passing", 8.6, 1.5);
  body(s, [
    "Image heritage-topics:1.0, 6.1 GB: Tesseract with 8 languages, CPU PyTorch, LaBSE, models, results, website. No scans.",
    "Pipeline service reruns every step from harvest to figures.",
    "Pages: landing, check, browse, study (every result, plain summary first), about.",
    "Report, this deck, viva notes and a short-paper draft.",
  ], { y: 3.9, h: 2.9, size: 16 });
}

// 16. Limits
{
  const s = slide("Limits and next steps", "Everyone. State the limits plainly; they are also on the Study page.");
  body(s, [
    "Printed books only, not handwritten manuscripts.",
    "OCR quality differs by script and is entangled with era and subject.",
    "Five pages stand in for a book.",
    "Low silhouettes; 37% DBSCAN noise; group names are our reading.",
    { text: "Next: more pages per book, IndicSBERT vs LaBSE, HDBSCAN, a small expert-labelled set, handwriting recognition.", bold: true },
  ], { size: 18 });
}

// 17. Team
{
  const s = slide("Team", "Each person answers questions on their own area.");
  table(s, [["", "Rajith Sundar", "Etikala Sai Pranav", "Vemuri Rohan"],
    ["Area", "Data and OCR", "Clustering study", "App and delivery"],
    ["Built", "Harvest, OCR and routing, pilot, cleaning, missing values, encoding, scaling", "Features, distance study, hierarchical and DBSCAN grids, stability, PCA, profiles, sensitivity", "API, new-page checker, web pages, Docker, plan and documents"]],
  { y: 1.6, colW: [1.6, 3.5, 3.5, 3.5], size: 15 });
}

pptx.writeFile({ fileName: path.join(ROOT, "docs", "Grantha_Deck.pptx") }).then((p) => console.log("wrote", p));
