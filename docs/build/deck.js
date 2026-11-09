// Builds docs/Grantha_Deck.pptx. Run from the project root: node docs/build/deck.js
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const sizeOf = (() => { const m = require("image-size"); return m.imageSize || m.default || m; })();

const ROOT = path.resolve(__dirname, "..", "..");
const J = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const A = J("reports/study/results_A.json"), G = J("reports/study/results_G.json");
const enc = J("reports/study/encoder_comparison.json"), sel = J("reports/study/selection.json");
const val = J("reports/eval/evaluation_val.json"), test = J("reports/eval/evaluation_test.json"), checks = J("reports/eval/app_checks.json");
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

// ---------- slides (v2)
const T1 = test.T1_upload_check, T2 = test.T2_subject;
const bestGuess = (t2) => Math.max(t2.baseline_most_common, t2.baseline_script_only);
const hG = G.hierarchical, dG = G.dbscan, tsel = sel.train_selection;
const p1 = (x) => `${(100 * x).toFixed(1)}%`;

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
    { text: "Output: its topic group from two methods, other groups it is close to, the 5 closest archive books (often in other languages), and its place on the PCA map.", bold: true },
    "It abstains when the OCR is too weak to judge.",
  ], { w: 7.4 });
  stat(s, "2,578", "printed books grouped, in 8 languages", 8.8, 1.6);
  stat(s, "0", "labels used to form the groups", 8.8, 3.4);
  stat(s, p1(T2.accuracy_groups), `subject right on unseen test books (simple guess ${p1(bestGuess(T2))})`, 8.8, 5.2);
}

// 3. Data
{
  const s = slide("Data: a stratified sample of 3,000 real books", "Rajith. Source, sample design, splits. About 434,000 eligible books in the 8 languages; equal shares per language so English (58% of the pool) does not dominate.");
  body(s, [
    "Digital Library of India scans on the Internet Archive: ~434,000 eligible books in our 8 languages.",
    "375 books per language, seeded draw across 5 era bands (to 1960, plus undated).",
    "Text: the archive's whole-book OCR for 2,971 books; 5 pages per book re-read with Tesseract for quality and upload tests.",
    "Split 60 / 20 / 20 into train, validation, test before any result; every fit on train only.",
    "Rights: only OCR text, catalogue fields and links are kept. No scans are redistributed.",
  ], { w: 6.6, size: 16 });
  table(s, [["Language", "Readable", "Median OCR conf."], ...study.corpus.by_language.map((x) => [x.name, `${x.usable} of ${x.harvested}`, f(x.median_conf, 0)])],
    { x: 7.6, y: 1.5, w: 5.1, colW: [1.7, 1.8, 1.6], size: 13 });
}

// 4. OCR and preprocessing
{
  const s = slide("OCR and preprocessing", "Rajith. Tesseract's script detector misroutes Gujarati and once called a Tamil scan Latin; both fixes choose the model by OCR confidence. Tokeniser keeps vowel signs; stopwords learned per language; subject field = scanning centre, dropped.");
  stat(s, "3 → 43", "Gujarati pilot books read with the Gujarati model, out of 50, after the confidence check", M, 1.5, 4.0);
  stat(s, "23 → 73", "OCR confidence on a Tamil upload the script detector had called Latin", 4.9, 1.5, 4.0);
  stat(s, "2,578", "of 3,000 books readable (confidence ≥ 50, ≥ 100 clean words)", 9.2, 1.5, 3.6);
  body(s, [
    "Tokens: [\\p{L}\\p{M}]+ keeps Indic vowel signs inside words; stopwords learned per language (a term in > 30% of that language's books).",
    "Relevance: the archive's subject field is the scanning centre, so it was dropped as leakage. Missing years: median plus a flag. Scaling: standardise.",
    `Metadata added to the text swamps it (${pct(sens.feature_sets.G.rows[3].largest_share)} of books in one group at weight 1), so the study clusters text alone.`,
  ], { y: 3.9, h: 2.9, size: 16 });
}

// 5. System
{
  const s = slide("System design", "Rohan. Walk the Level 1 DFD: harvest, OCR, preprocess and features, clustering study, check a new page, browse. Level 0 and Level 2 diagrams are in the report.");
  image(s, "reports/figures/dfd_level1.png", { x: M, y: 1.3, w: 7.6, h: 5.5 });
  body(s, [
    "Python 3.12, Tesseract 5, scikit-learn, SciPy.",
    "Gemini Embedding 001 through Google's API; local encoders compared on a GPU.",
    "FastAPI serves the API and a static website.",
    "Docker: app image (1.1 GB) and a pipeline image that reruns the study.",
    "40 pytest tests; 66 app checks.",
  ], { x: 8.6, y: 1.5, w: 4.2, size: 15 });
}

// 6. The problem we found
{
  const s = slide("First result: groups followed language, not topic", "Pranav. The brief asks for grouping by TOPIC. Version 1 grouped by language. TF-IDF groups were exactly the scripts; LaBSE groups beat a 'subject from script' guess by only 3 points. Silhouette made it worse: language groups are far apart, so they score higher.");
  stat(s, "1.00", "TF-IDF groups vs script (NMI): every group is one script", M, 1.5);
  stat(s, "+3 pts", "v1 subject accuracy over guessing from the script", 4.6, 1.5);
  stat(s, "0.14", "silhouette of the language-like groups: higher, for the wrong reason", 8.6, 1.5);
  body(s, [
    "Multilingual encoders place each language in its own region; the biggest distances are language distances.",
    { text: "Fix 1: subtract each language's average position (train books only). A new page is centred by its OCR language.", bold: true },
    { text: "Fix 2: choose the encoder by how much topic it carries, measured before clustering.", bold: true },
    "The clustering methods and the silhouette-based choice stay exactly as the brief asks.",
  ], { y: 3.9, h: 2.9, size: 16 });
}

// 7. Encoder choice
{
  const s = slide("Choosing the encoder", "Pranav. Score: how often a book's subject matches its 7 nearest neighbours, on labelled train and validation books only. It is the ceiling for any grouping. Removing the language helps every model; Gemini carries the most topic. Trade-off: it is closed and online.");
  const rows = Object.entries(enc.encoders).sort((x, y) => y[1].knn_centred - x[1].knn_centred);
  table(s, [["Encoder", "As is", "Language removed"], ...rows.map(([, e]) => [e.model, p1(e.knn_plain), p1(e.knn_centred)]),
    ["multilingual-e5-large (325 books)", "57.2%", "65.8%"]],
    { y: 1.5, colW: [6.4, 2.6, 3.1], size: 15, hi: (ri) => ri === 1 });
  body(s, [
    "Removing the language adds 4 to 11 points to every encoder.",
    "Gemini Embedding 001 (Google, online) leads by ~7 points over the best open model.",
    "Labels only measure; they never form or choose the groups.",
  ], { y: 4.9, h: 1.9, size: 16 });
}

// 8. Methods
{
  const s = slide("Two feature sets, two methods, rules fixed in advance", "Pranav. Every choice (metric, setting, final feature set) is made by a rule written before the run. Silhouette picks, under two limits: groups must not just follow script, and must survive resampling.");
  table(s, [["", "A: TF-IDF + LSA", "G: Gemini, language removed"],
    ["Built from", "word 1–2-grams + character 3–5-grams", "10 passages per book, averaged, language mean removed"],
    ["Reduced to", `100 dims (SVD, ${pct(A.explained_variance)} of variance)`, `100 dims (PCA, ${pct(G.explained_variance)} of variance)`],
    ["Hierarchical", "Ward, average, complete; k = 2–15", "Ward, average, complete; k = 2–15"],
    ["DBSCAN", "24 eps × MinPts from k-distance curves", "24 eps × MinPts from k-distance curves"]],
  { y: 1.5, colW: [2.4, 4.8, 4.9], size: 15 });
  body(s, [
    "Metric: Euclidean vs Manhattan on 4 pre-set criteria (Euclidean wins 3 of 4 on both).",
    `Final choice: highest silhouette among settings with script NMI ≤ 0.5 and bootstrap ARI ≥ 0.5. TF-IDF (silhouette ${f(tsel.silhouette.A, 3)}) fails: its groups are scripts.`,
    "Chosen on train books, then refitted on all books without re-choosing.",
  ], { y: 4.6, h: 2.2, size: 16 });
}

// 9. Hierarchical
{
  const s = slide("Hierarchical clustering", `Pranav. Silhouette picked average linkage with ${hG.final.k} groups on the train books, with no floor on k. Silhouettes are low because topics overlap; the old 0.14 came from language separation.`);
  image(s, "reports/figures/G_hier_silhouette.png", { x: M, y: 1.3, w: 6.0, h: 3.4 });
  image(s, "reports/figures/G_dendrogram.png", { x: 6.8, y: 1.3, w: 6.0, h: 3.4 });
  body(s, [
    `Gemini: average linkage, k = ${hG.final.k}, silhouette ${f(tsel.silhouette.G, 3)} on train, ${f(hG.final.silhouette, 3)} refitted on all books.`,
    `Groups barely follow script (NMI ${f(hG.effects.nmi_script)}) and follow the catalogue subject more than any other grouping (${f(hG.effects.nmi_classification)}).`,
    "Valid setting: k ≥ 3 and every group at least 1% of the books.",
  ], { y: 4.9, h: 1.9, size: 16 });
}

// 10. DBSCAN
{
  const df = dG.final;
  const s = slide("DBSCAN: narrower dense topics", `Pranav. eps values come from the k-distance curves. ${dG.grid.filter((r) => r.valid).length} of 24 settings are valid. DBSCAN keeps the dense cores of topics and leaves the overlapping middle as noise.`);
  image(s, "reports/figures/G_kdistance.png", { x: M, y: 1.3, w: 6.0, h: 3.4 });
  image(s, "reports/figures/G_dbscan_grid.png", { x: 6.8, y: 1.3, w: 6.0, h: 3.4 });
  body(s, [
    `MinPts ${df.min_pts}, eps ${f(df.eps, 3)}: ${df.n_clusters} dense groups, ${pct(df.noise_share)} noise (version 1: 2 groups).`,
    "Groups include medicine, Buddhist scriptures, the national movement (Gandhi, Nehru, Tilak), regional dynastic history, English fiction.",
    `HDBSCAN check: ${G.extras.hdbscan.n_clusters} groups that agree with the hierarchical ones (ARI ${f(G.extras.hdbscan.ari_vs_hierarchical_non_noise)}).`,
  ], { y: 4.9, h: 1.9, size: 15 });
}

// 11. Groups
{
  const s = slide(`${hG.final.k} topic groups, each across several languages`, "Pranav. Names come from reading each group's distinctive words and typical books. Every group spans several scripts. A Hindi passage on fevers finds Tamil medical books; a devotional poem finds Krishna works in Hindi, Bengali and Gujarati.");
  const mix = (p) => Object.entries(p.script_mix).filter(([, v]) => v >= 0.05).slice(0, 4).map(([k, v]) => `${k} ${pct(v)}`).join(", ");
  table(s, [["Group", "Books", "Scripts", "Median year"], ...hG.profiles.map((p) => [names.G_hier[String(p.cluster)], p.size, mix(p), Math.round(p.median_year)])],
    { y: 1.4, colW: [3.8, 1.0, 6.0, 1.3], size: 13 });
  body(s, [
    "Cross-language neighbours: a Hindi passage on fevers finds Tamil fever-treatment books.",
    "Caution: poetry and religion are older and less legible than fiction and public life.",
  ], { y: 5.4, h: 1.4, size: 15 });
}

// 12. Accuracy
{
  const s = slide("Accuracy on unseen books", "Pranav. Targets fixed before any result. Two validation rounds (language removal + encoder; then tags). Test books measured once; validation and test agree, so no overfitting. T2 met; T1 and T3 missed, reported as misses.");
  table(s, [["Target (test books, measured once)", "Result", "Aim", "Met"],
    ["T1: one page lands with its own book's group", `${p1(T1.agreement)} (with tags ${p1(T1.tagged.agreement_tagged)})`, "80%", test.met.T1 ? "yes" : "no"],
    ["T2: subject from the group vs best simple guess", `${p1(T2.accuracy_groups)} vs ${p1(bestGuess(T2))}`, "+10 pts", test.met.T2 ? "yes" : "no"],
    ["T3: stability (bootstrap ARI)", f(test.T3_bootstrap_median), "0.60", test.met.T3 ? "yes" : "no"]],
  { y: 1.5, colW: [5.6, 3.6, 1.4, 1.5], size: 15 });
  body(s, [
    `Version 1 beat the script guess by 3 points; version 2 by ${f(T2.points_above_best_baseline, 1)} (p ${f(T2.permutation_p, 4)}).`,
    `With tags, a book's subject is among its tags ${p1(T2.tagged.accuracy_tagged)} of the time, but only ${pct(T2.tagged.tag_precision)} of tags are right: a hint, not a second answer.`,
    `Validation agrees with test within ~2 points. Test rests on ${T2.labelled_heldout} labelled books (±6 points).`,
  ], { y: 4.1, h: 2.7, size: 16 });
}

// 13. App
{
  const s = slide("The app: check a page", "Rohan. Live demo if possible: paste or upload a page. The screenshot: a Hindi passage on fevers lands in science and medicine; its nearest books include Tamil medical works.");
  image(s, "web/assets/check-screen.png", { x: M, y: 1.3, w: 7.8, h: 5.5 });
  body(s, [
    "Nearest group centre, judged against the group's own books, plus 'also close to'.",
    "DBSCAN: joins a group only within eps of a core book.",
    "5 nearest books, shared words, archive links.",
    "Abstains under 20 words; cautions on weak OCR.",
    "No retraining, nothing stored.",
  ], { x: 8.8, y: 1.5, w: 4.0, size: 15 });
}

// 14. Delivery
{
  const s = slide("Delivered", "Rohan. Show docker compose up. The key lives in a git-ignored .env and enters only at run time. The one failed check: a Sanskrit page read with the Hindi model (same script), same group either way.");
  stat(s, "1 command", "docker compose up: the site and API on port 8000", M, 1.5);
  stat(s, `${checks.passed}/${checks.total}`, "app checks passed on the container, all 8 languages", 4.6, 1.5);
  stat(s, "1.1 GB", "app image (was 6.1 GB)", 8.6, 1.5);
  body(s, [
    "Tesseract with 8 languages, fitted model, results, website; no scans. Needs internet for Gemini.",
    "Pipeline service reruns every step; README lists them.",
    "Pages: landing, check, browse, study (every result, plain summary first), about.",
    "Report, this deck, viva notes and a short-paper draft.",
  ], { y: 3.9, h: 2.9, size: 16 });
}

// 15. Limits
{
  const s = slide("Limits and next steps", "Everyone. State the limits plainly; they are also on the Study page.");
  body(s, [
    "Printed books only, not handwritten manuscripts.",
    "The encoder is closed and online: text goes to Google; the best open model is ~7 points lower.",
    "T1 (72.5% vs 80%) and T3 (0.58 vs 0.60) missed; silhouettes are low because topics overlap.",
    "Subject labels made by the assistant, to be spot-checked by the team.",
    { text: "Next: more books per language, an open encoder fine-tuned on the archive's own text, expert-checked labels, handwriting recognition.", bold: true },
  ], { size: 18 });
}

// 16. Team
{
  const s = slide("Team", "Each person answers questions on their own area.");
  table(s, [["", "Rajith Sundar", "Etikala Sai Pranav", "Vemuri Rohan"],
    ["Area", "Data and OCR", "Clustering study", "App and delivery"],
    ["Built", "Harvest, whole-book text, OCR and routing, pilot, cleaning, missing values, encoding, scaling, splits", "Features, language removal, encoder choice, distance study, hierarchical and DBSCAN grids, stability, evaluation, tags", "API, new-page checker, web pages, Docker, plan and documents"]],
  { y: 1.6, colW: [1.6, 3.5, 3.5, 3.5], size: 15 });
}

pptx.writeFile({ fileName: path.join(ROOT, "docs", "Grantha_Deck.pptx") }).then((p) => console.log("wrote", p));
