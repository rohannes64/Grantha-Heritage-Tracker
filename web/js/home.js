import { getJSON, el, esc, fmt, scatter, LANG } from "./common.js";

const sample = await getJSON("data/sample_page.json").catch(() => null);

// The demo page: a scan from outside the study sample, read by the same OCR.
if (sample) {
  for (const id of ["hero-img", "crop-img"]) {
    const img = document.getElementById(id);
    if (img) img.src = sample.image_url;
  }
  document.getElementById("hero-caption").textContent =
    `${sample.title}, ${LANG[sample.lang] || sample.lang}, ${sample.year ?? "undated"}. Page ${sample.leaf + 1} of an unindexed scan.`;
  const ocr = document.getElementById("ocr-text");
  ocr.lang = sample.html_lang;
  ocr.textContent = sample.excerpt;
  document.getElementById("ocr-conf").textContent = `${fmt.f(sample.ocr_conf, 0)} of 100`;
  document.querySelector("#ocr-sheet dd").textContent = `${LANG[sample.lang]} (${sample.model}), Tesseract 5`;
}

// Languages table from the study.
getJSON("data/study.json").then((st) => {
  const rows = st.corpus.by_language;
  const order = ["eng", "hin", "san", "ben", "guj", "tel", "kan", "tam"];
  const body = document.querySelector("#lang-table tbody");
  body.replaceChildren(...order.map((code) => {
    const r = rows.find((x) => x.lang === code);
    return el("tr", {}, el("td", { text: LANG[code] }),
      el("td", { class: "num", text: r ? fmt.n(r.harvested) : "0" }),
      el("td", { class: "num", text: r ? fmt.n(r.usable) : "0" }),
      el("td", { class: "num", text: r ? fmt.f(r.median_conf, 0) : "n/a" }));
  }));
}).catch(() => {});

// Live check of the demo page against the archive groups.
async function run() {
  const list = document.getElementById("neighbours");
  if (!sample) { list.replaceChildren(el("li", {}, el("span"), el("p", { class: "why", text: "The demo page is not prepared yet. Use Check a page." }), el("span"))); return; }
  const form = new FormData();
  form.append("text", sample.text);
  form.append("lang", sample.lang);
  let res;
  try {
    const r = await fetch("/api/check", { method: "POST", body: form });
    if (!r.ok) throw new Error(await r.text());
    res = await r.json();
  } catch (e) {
    list.replaceChildren(el("li", {}, el("span"), el("p", { class: "why", text: "The checker is not running here. Start the app server to see this live." }), el("span")));
    return;
  }
  if (res.status === "abstain") { list.replaceChildren(el("li", {}, el("span"), el("p", { class: "why", text: res.message }), el("span"))); return; }
  list.replaceChildren(...res.matches.map((m, i) => el("li", {},
    el("span", { class: "figure", text: String(i + 1) }),
    el("div", {},
      el("h3", {}, el("a", { href: m.url, text: m.title || m.identifier })),
      el("p", { class: "why", text: `${LANG[m.lang_tag] || m.lang_tag}, ${m.year ? Math.round(m.year) : "undated"}. Shares: ${m.shared_terms.slice(0, 5).join(", ") || "character patterns rather than whole words"}` })),
    el("span", { class: "group-name", text: res.hierarchical.cluster === m.hier ? "same group" : "nearby group" }))));
  const corpus = await getJSON("data/corpus.json");
  const pts = corpus.docs.map((d) => ({ x: d.x, y: d.y, hi: d.hier === res.hierarchical.cluster,
    label: `${esc(d.title || d.identifier)}<br>${esc(LANG[d.lang_tag] || "")} ${d.year ? Math.round(d.year) : ""}` }));
  scatter(document.getElementById("map"), pts, { you: { ...res.pca, label: "this page" }, height: 420,
    ariaLabel: `Map of ${corpus.docs.length} archive books; the page sits in the group ${res.hierarchical.name}` });
}
run();
