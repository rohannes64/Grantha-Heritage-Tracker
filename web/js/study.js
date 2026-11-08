import { getJSON, el, esc, fmt, scatter, lines, dendrogram, hbar, LANG, params, setParam } from "./common.js";

const root = document.getElementById("study");
let st;
try { st = await getJSON("data/study.json"); } catch (e) {
  root.replaceChildren(el("div", { class: "state state--error" }, el("p", { text: "The study results could not be loaded. Run the pipeline and export, then reload." })));
  throw e;
}
const METRIC = { euclidean: "Euclidean", cityblock: "Manhattan" };
const NAME = { A: "TF-IDF + LSA", B: "LaBSE embeddings" };
let fs = params().get("set");
if (!st.sets[fs]) fs = st.final;
for (const k of ["A", "B"]) {
  const input = document.getElementById(`fs-${k.toLowerCase()}`);
  input.disabled = !st.sets[k];
  input.checked = k === fs;
  input.addEventListener("change", () => { fs = k; setParam("set", k); draw(); });
}

const section = (id, title, summary, ...body) => el("section", { class: "study-section", id, "aria-labelledby": `${id}-h` },
  el("h2", { id: `${id}-h`, text: title }), el("p", { class: "summary" }, ...summary), ...body);
const more = (title, ...body) => el("details", { class: "more" }, el("summary", { text: title }), el("div", { class: "more-body" }, ...body));
const strong = (t) => el("strong", { text: t });
const table = (heads, rows, { chosen } = {}) => el("div", { class: "table-wrap" }, el("table", {},
  el("thead", {}, el("tr", {}, heads.map(([h, num]) => el("th", { scope: "col", class: num ? "num" : null, text: h })))),
  el("tbody", {}, rows.map((r, i) => el("tr", { class: chosen && chosen(i) ? "is-chosen" : null },
    r.map((c, j) => el("td", { class: heads[j][1] ? "num" : null }, c ?? "n/a")))))));
const figs = (...items) => el("div", { class: "figures-row" }, items.map(([v, label]) =>
  el("div", {}, el("span", { class: "figure", text: v }), el("span", { class: "small muted", text: label }))));

function draw() {
  const r = st.sets[fs];
  const H = r.hierarchical, D = r.dbscan, C = r.comparison;
  const hf = H.final, df = D.final;
  const parts = [];

  // 1. sample
  const c = st.corpus;
  parts.push(section("sample", "The sample",
    [`${fmt.n(c.harvested)} scanned books were drawn at random from the Digital Library of India, stratified by language and era. `,
      strong(`${fmt.n(c.usable)} were readable enough to group`), `; the rest are kept, flagged and used to study OCR noise. `,
      `${fmt.n(c.tag_mismatch)} books were catalogued under a language whose script did not match the page.`],
    el("div", { class: "more-wrap" },
      more("Books per language",
        table([["Language"], ["Harvested", 1], ["Readable", 1], ["Readable share", 1], ["Median OCR confidence", 1]],
          c.by_language.map((x) => [x.name, fmt.n(x.harvested), fmt.n(x.usable), fmt.p(x.usable / x.harvested), fmt.f(x.median_conf, 0)]))),
      st.pilot ? more("Pilot OCR quality (50 books per language, before the full run)",
        el("p", { class: "small muted", text: "Usable means median word confidence of 60 or more and a median script ratio of 0.80 or more, a rule fixed before the pilot ran. Agreement with the archive's own OCR is a consistency check, not ground truth." }),
        table([["Language"], ["Pages", 1], ["Median confidence", 1], ["Pages at 70+", 1], ["Script ratio", 1], ["Agreement with archive OCR", 1], ["Usable"]],
          st.pilot.map((p) => [p.name, fmt.n(p.pages), fmt.f(p.median_conf, 1), `${fmt.f(p.pages_conf_ge_70_pct, 0)}%`, fmt.f(p.median_script_ratio, 2),
            p.median_ia_similarity == null ? "n/a" : fmt.f(p.median_ia_similarity, 0), p.usable ? "yes" : "no"]))) : null)));

  // 2. preprocessing
  parts.push(section("prep", "Preprocessing",
    ["Text was cleaned in each book's own script without splitting words at vowel signs. ",
      strong("Fields that describe the scan rather than the content were dropped"), ", including the archive's subject field, which turned out to hold the scanning centre. Missing years were filled with the median and flagged."],
    el("div", { class: "more-wrap" },
      more("Variable relevance review",
        table([["Field"], ["Missing", 1], ["Distinct", 1], ["Decision"], ["Reason"]],
          st.relevance.map((v) => [v.field, `${fmt.f(v.missing_pct, 1)}%`, fmt.n(v.distinct), v.decision, v.reason]))),
      more("Features used",
        el("p", { class: "prose", text: fs === "A"
          ? `Word 1-2-grams and character 3-5-grams, weighted by TF-IDF (terms found in more than 30% of one language’s books dropped as that language’s stopwords), reduced to ${r.dims} dimensions with truncated SVD, which keeps ${fmt.p(r.explained_variance)} of the variance. Rows scaled to unit length.`
          : `LaBSE sentence embeddings (109 languages) of up to 4 evenly spaced 64-word chunks per book (128 word-pieces each), averaged, reduced to ${r.dims} dimensions with PCA, which keeps ${fmt.p(r.explained_variance)} of the variance. Rows scaled to unit length.` })))));

  // 3. distance
  const dm = r.distance.metrics;
  const crit = [["relative_contrast", "Relative contrast (farthest vs nearest neighbour)"], ["cophenetic_average", "Cophenetic correlation, average linkage"],
    ["cophenetic_complete", "Cophenetic correlation, complete linkage"], ["best_silhouette_average", "Best silhouette, average linkage"],
    ["knn_same_script", "10 nearest neighbours in the same script"], ["knn_same_classification", "10 nearest neighbours with the same catalogue subject"]];
  parts.push(section("distance", "Euclidean or Manhattan",
    [strong(`${METRIC[r.distance.chosen]} was chosen`), `, winning ${({4: "all four", 3: "three", 2: "two", 1: "one", 0: "none"})[r.distance.wins[r.distance.chosen]]}${r.distance.wins[r.distance.chosen] === 4 ? "" : " of the four"} criteria set in advance (a tie would go to Euclidean, which Ward linkage needs). The last two rows are context, not criteria.`],
    el("div", { class: "more-wrap" }, more("The four criteria and two checks",
      table([["Measure"], ["Euclidean", 1], ["Manhattan", 1]],
        crit.map(([k, label]) => [label, fmt.f(dm.euclidean[k], 3), fmt.f(dm.cityblock[k], 3)]), { chosen: (i) => i < 4 && (dm[r.distance.chosen][crit[i][0]] ?? -1) >= (dm[r.distance.chosen === "euclidean" ? "cityblock" : "euclidean"][crit[i][0]] ?? -1) }),
      el("p", { class: "small muted", text: "Higher is better on every row. Highlighted rows are criteria the chosen metric won." })))));

  // 4. hierarchical
  const silChart = el("div", { role: "figure", "aria-label": "Silhouette by number of clusters for three linkages" });
  const dendro = el("div", { role: "figure", "aria-label": "Dendrogram of the chosen linkage, last 30 merges" });
  parts.push(section("hier", "Hierarchical clustering",
    [strong(`${hf.linkage[0].toUpperCase() + hf.linkage.slice(1)} linkage with ${hf.k} groups`), ` scored the highest silhouette (${fmt.f(hf.silhouette, 3)}) among settings that pass the rule: at least three groups, none smaller than 1% of the books. `,
      `Text silhouettes are low by nature; above zero means books sit closer to their own group than to the next.`],
    el("div", { class: "two mt-xl" },
      el("div", {}, el("h3", { text: "Silhouette by k" }), silChart,
        el("ul", { class: "legend" }, ["ward", "average", "complete"].map((l) => el("li", {}, el("span", { class: `sw ${l === hf.linkage ? "sw--accent" : l === "ward" || (hf.linkage === "ward" && l === "average") ? "sw--ink" : "sw--dash"}` }), `${l}${l === hf.linkage ? " (chosen)" : ""}`)))),
      el("div", {}, el("h3", { text: "Dendrogram" }), dendro,
        el("p", { class: "small muted mt-xs", text: "Last 30 merges; numbers in brackets are how many books a leaf holds. The dashed line cuts the tree into the chosen groups." }))),
    el("div", { class: "more-wrap" }, more("Every setting tried",
      table([["Linkage"], ["Metric"], ["k", 1], ["Silhouette", 1], ["Largest group", 1], ["Smallest", 1], ["Passes the rule"]],
        H.grid.map((g) => [g.linkage, METRIC[g.metric], String(g.k), fmt.f(g.silhouette, 3), fmt.p(g.largest_share), fmt.n(g.smallest), g.valid ? "yes" : "no"]),
        { chosen: (i) => H.grid[i].linkage === hf.linkage && H.grid[i].k === hf.k })))));

  // 5. dbscan
  const kd = el("div", { role: "figure", "aria-label": "k-distance curves for four MinPts values" });
  const dgrid = D.grid;
  parts.push(section("dbscan", "DBSCAN",
    [strong(`MinPts ${df.min_pts} with eps ${fmt.f(df.eps, 3)}`), ` found ${df.n_clusters} dense groups and left ${fmt.p(df.noise_share)} of books as noise, with a silhouette of ${fmt.f(df.silhouette, 3)} on the grouped books. `,
      `${dgrid.length} combinations were tried; eps came from the k-distance curves, so every value is grounded in the data.`, D.rule_met ? "" : " No combination met the rule of two or more groups with at most half the books as noise; the closest is shown."],
    el("div", { class: "mt-xl" }, el("h3", { text: "k-distance curves" }), kd,
      el("ul", { class: "legend" }, Object.keys(D.kdist).map((mp) => el("li", {}, el("span", { class: `sw ${Number(mp) === df.min_pts ? "sw--accent" : "sw--ink"}` }), `MinPts ${mp}${Number(mp) === df.min_pts ? " (chosen)" : ""}`)),
        el("li", {}, el("span", { class: "sw sw--dash" }), "chosen eps"))),
    el("div", { class: "more-wrap" }, more("Every combination tried",
      table([["MinPts", 1], ["eps", 1], ["From the knee"], ["Groups", 1], ["Noise", 1], ["Silhouette", 1], ["Passes the rule"]],
        dgrid.map((g) => [String(g.min_pts), fmt.f(g.eps, 4), g.eps_is_knee ? "yes" : "", String(g.n_clusters), fmt.p(g.noise_share), fmt.f(g.silhouette, 3), g.valid ? "yes" : "no"]),
        { chosen: (i) => dgrid[i].min_pts === df.min_pts && dgrid[i].eps === df.eps })))));

  // 6. comparison
  const left = el("div", { role: "figure", "aria-label": "PCA map coloured by the hierarchical group" });
  const right = el("div", { role: "figure", "aria-label": "PCA map coloured by the matching DBSCAN group" });
  const sel = el("select", { class: "input", id: "cmp-group" }, H.profiles.map((p) => el("option", { value: p.cluster, text: H.names[String(p.cluster)] })));
  const ct = C.crosstab;
  parts.push(section("compare", "The two methods, side by side",
    [`On the books DBSCAN groups, the two methods agree with an adjusted Rand index of `, strong(fmt.f(C.ari_non_noise, 2)), ` (1 is identical, 0 is chance) and normalised mutual information of ${fmt.f(C.nmi_non_noise, 2)}. `,
      `PCA keeps ${fmt.p(r.pca.explained[0] + r.pca.explained[1])} of the variance in two dimensions, so the maps show the shape, not the full distances.`],
    el("div", { class: "field mt-xl" }, el("label", { for: "cmp-group", text: "Light a hierarchical group and its closest DBSCAN group" }), sel),
    el("div", { class: "two mt-lg" }, el("div", {}, el("h3", { text: "Hierarchical" }), left), el("div", {}, el("h3", { text: "DBSCAN" }), right)),
    el("ul", { class: "legend" }, el("li", {}, el("span", { class: "sw sw--accent sw--dot" }), "the lit group"), el("li", {}, el("span", { class: "sw sw--dot" }), "other groups")),
    el("div", { class: "more-wrap" }, more("Cross-table: hierarchical groups (rows) by DBSCAN groups (columns)",
      table([["Hierarchical"], ...ct.cols.map((c_) => [c_ === -1 ? "noise" : D.names[String(c_)] || String(c_), 1])],
        ct.rows.map((row, i) => [H.names[String(row)] || String(row), ...ct.values[i].map(String)]))))));

  // 7. stability
  const hb = H.bootstrap_ari, db = D.bootstrap_ari;
  parts.push(section("stability", "Stability",
    [`Re-running each method on 20 random samples of 80% of the books, the hierarchical groups come back with a median adjusted Rand index of `, strong(fmt.f(hb.median, 2)),
      ` and DBSCAN's with ${fmt.f(db.median, 2)}. DBSCAN is expected to move more: fewer books means thinner neighbourhoods at the same eps.`],
    el("div", { class: "mt-xl" }, figs([fmt.f(hb.median, 2), `hierarchical, median ARI (10th to 90th percentile ${fmt.f(hb.p10, 2)} to ${fmt.f(hb.p90, 2)})`],
      [fmt.f(db.median, 2), `density-based, median ARI (${fmt.f(db.p10, 2)} to ${fmt.f(db.p90, 2)})`],
      [fmt.f(Math.min(...H.neighbours.map((n) => n.ari)), 2), "hierarchical, lowest agreement with k one up or down"])),
    el("div", { class: "more-wrap" }, more("Neighbouring settings",
      table([["Method"], ["Setting"], ["Agreement with the chosen one (ARI)", 1]],
        [...H.neighbours.map((n) => ["Hierarchical", `k = ${n.k}`, fmt.f(n.ari, 3)]),
          ...D.neighbours.map((n) => ["Density-based", `MinPts ${n.min_pts}, eps ${fmt.f(n.eps, 4)}`, fmt.f(n.ari, 3)])])))));

  // 8. drivers
  const eff = (m) => [fmt.f(m.effects.nmi_script, 2), fmt.f(m.effects.nmi_era, 2), fmt.f(m.effects.nmi_classification, 2)];
  const on = D.ocr_noise;
  parts.push(section("drivers", "What drives the groups",
    [`How much each grouping follows the script, the era and the catalogue subject (normalised mutual information, 0 none, 1 complete). With this feature set the hierarchical groups follow script at `, strong(fmt.f(H.effects.nmi_script, 2)),
      `. DBSCAN's noise books have a median OCR confidence of ${fmt.f(on.median_conf_noise, 0)} against ${fmt.f(on.median_conf_clustered, 0)} for grouped books.`],
    el("div", { class: "mt-xl" }, table([["Grouping"], ["Script", 1], ["Era", 1], ["Catalogue subject", 1]],
      Object.entries(st.sets).flatMap(([k, s_]) => [[`${NAME[k]}, hierarchical`, ...eff(s_.hierarchical)], [`${NAME[k]}, density-based`, ...eff(s_.dbscan)]]),
      { chosen: (i) => Object.keys(st.sets)[Math.floor(i / 2)] === fs })),
    el("div", { class: "more-wrap" },
      more("OCR quality and DBSCAN noise",
        el("p", { class: "prose", text: `Area under the ROC curve for low OCR confidence predicting that a book is noise: ${fmt.f(on.auc_low_conf_predicts_noise, 2)} (0.5 would mean no link). ${on.auc_low_conf_predicts_noise > 0.6 ? "Weaker scans are more often left out: DBSCAN's noise partly measures reading quality, not only unusual topics." : "Noise is not mainly a matter of scan quality here."}` })),
      r.pca.loadings ? more("Words that pull the map apart (PCA loadings)",
        table([["Axis"], ["One end"], ["Other end"]], r.pca.loadings.map((l) => [`PC${l.pc}`, l.positive.slice(0, 8).join(", "), l.negative.slice(0, 8).join(", ")]))) : null)));

  // 9. choice
  const sel_ = st.selection;
  parts.push(section("choice", "The model behind the app",
    [`The app uses `, strong(NAME[sel_.chosen]), `. The rule, fixed in advance: among feature sets whose hierarchical groups have a silhouette above zero and a median bootstrap agreement of 0.5 or more, take the one whose groups depend least on script. `,
      `Script dependence: ${Object.entries(sel_.nmi_script).map(([k, v]) => `${NAME[k]} ${fmt.f(v, 2)}`).join(", ")}.`]));

  // 10. limits
  parts.push(section("limits", "Limits",
    ["These are exploratory groups of ", strong("printed"), " books, not a catalogue and not handwritten manuscripts, which Tesseract cannot read."],
    el("ul", { class: "prose mt-lg" },
      el("li", { text: `OCR quality differs by script; weaker scripts lose more books to the readability filter and to DBSCAN noise.` }),
      el("li", { text: "The sample follows the Digital Library of India's own mix: some languages, eras and subjects are better represented than others." }),
      el("li", { text: "Five pages stand in for each book; a page from the preface or an index can pull a book toward the wrong group." }),
      el("li", { text: "Group names are our reading of each group’s distinctive words and typical books, not subject headings. Read the typical books before trusting a name." }),
      el("li", { text: "Silhouette scores for text are low by nature; the groups are tendencies, and borders between them are uncertain." }))));

  root.replaceChildren(...parts);

  // charts
  const chosenL = hf.linkage;
  const clsFor = (l) => (l === chosenL ? "ser" : l === "ward" || (chosenL === "ward" && l === "average") ? "ser-2" : "ser-3");
  lines(silChart, ["ward", "average", "complete"].map((l) => ({ name: l, cls: clsFor(l),
    points: H.grid.filter((g) => g.linkage === l).map((g) => [g.k, g.silhouette]) })),
  { xLabel: "number of groups k", yLabel: "silhouette", marks: [{ x: hf.k, y: hf.silhouette, label: "chosen" }], height: 320 });
  if (H.dendrogram) dendrogram(dendro, H.dendrogram, { cut: H.dendrogram.cut, height: 320 });
  lines(kd, Object.entries(D.kdist).map(([mp, curve]) => ({ name: `MinPts ${mp}`, cls: Number(mp) === df.min_pts ? "ser" : "ctx",
    points: curve.map((v, i) => [i, v]) })), { xLabel: "books, sorted by distance (sampled)", yLabel: "distance to the (MinPts-1)th neighbour", hline: df.eps, height: 320 });

  const hl = st.sets[fs].labels.hierarchical, dl = st.sets[fs].labels.dbscan, xy = r.pca.coords;
  const drawPair = () => {
    const g = Number(sel.value);
    const counts = {};
    hl.forEach((h, i) => { if (h === g && dl[i] !== -1) counts[dl[i]] = (counts[dl[i]] || 0) + 1; });
    const match = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
    const dg = match ? Number(match[0]) : null;
    const lab = (i) => `${esc(H.names[String(hl[i])])}${dl[i] === -1 ? "<br>density-based: noise" : `<br>density-based: ${esc(D.names[String(dl[i])] || "")}`}`;
    scatter(left, xy.map(([x, y], i) => ({ x, y, hi: hl[i] === g, label: lab(i) })), { height: 340 });
    scatter(right, xy.map(([x, y], i) => ({ x, y, hi: dg != null && dl[i] === dg, noise: dl[i] === -1, label: lab(i) })), { height: 340 });
  };
  sel.addEventListener("change", drawPair);
  drawPair();
  if (location.hash) document.querySelector(location.hash)?.scrollIntoView();
}
draw();
