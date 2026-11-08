import { getJSON, el, esc, fmt, scatter, LANG } from "./common.js";

const form = document.getElementById("check-form");
const fileIn = document.getElementById("file");
const textIn = document.getElementById("text");
const langIn = document.getElementById("lang");
const drop = document.getElementById("drop");
const errorEl = document.getElementById("form-error");
const submit = document.getElementById("submit");
const result = document.getElementById("result");

const LEVEL = {
  strong: ["Sits well inside", "closer to the group's centre than half of its own books"],
  good: ["Inside", "as close as nine in ten of the group's own books"],
  weak: ["At the edge", "farther than most of the group's books, but within its range"],
  outside: ["Outside every group", "farther from the nearest centre than any of that group's books"],
};

fileIn.addEventListener("change", () => {
  document.getElementById("file-name").textContent = fileIn.files[0] ? fileIn.files[0].name : "";
});
for (const ev of ["dragenter", "dragover"]) drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("is-over"); });
for (const ev of ["dragleave", "drop"]) drop.addEventListener(ev, () => drop.classList.remove("is-over"));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  if (e.dataTransfer.files[0]) { fileIn.files = e.dataTransfer.files; fileIn.dispatchEvent(new Event("change")); }
});

function showError(msg) { errorEl.textContent = msg; errorEl.hidden = !msg; }

function loading() {
  result.replaceChildren(el("div", { class: "state" },
    el("h2", { text: "Reading the page" }),
    el("p", { class: "ink-2", text: "OCR takes a few seconds a page; the comparison is instant after that." }),
    el("div", { class: "skeleton skeleton--block mt-lg" })));
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("");
  const file = fileIn.files[0];
  if (!file && !textIn.value.trim()) { showError("Choose a scan or paste some text first."); textIn.setAttribute("aria-invalid", "true"); return; }
  textIn.removeAttribute("aria-invalid");
  if (file && file.size > 20 * 1024 * 1024) { showError("That file is larger than 20 MB."); return; }
  const fd = new FormData();
  if (file) fd.append("file", file); else fd.append("text", textIn.value);
  fd.append("lang", langIn.value);
  submit.disabled = true; submit.setAttribute("aria-busy", "true");
  loading();
  try {
    const r = await fetch("/api/check", { method: "POST", body: fd });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail || `The server answered ${r.status}.`);
    await render(body);
  } catch (err) {
    result.replaceChildren(el("div", { class: "state state--error" },
      el("h2", { text: "The check did not run" }),
      el("p", { class: "ink-2", text: String(err.message || err) }),
      el("p", { class: "ink-2", text: "Try a clearer scan, a smaller PDF, or paste the text instead." })));
  } finally {
    submit.disabled = false; submit.removeAttribute("aria-busy");
  }
});

async function render(r) {
  const parts = [];
  const cautions = (r.cautions || []).map((c) => el("li", { class: "note", text: c }));
  if (r.status === "abstain") {
    parts.push(el("div", { class: "state" }, el("h2", { text: "Not enough to go on" }), el("p", { class: "ink-2", text: r.message }),
      el("ul", { class: "cautions" }, cautions)));
    if (r.ocr) parts.push(ocrBlock(r));
    result.replaceChildren(...parts);
    return;
  }
  const h = r.hierarchical, d = r.dbscan;
  const [lvl, lvlWhy] = LEVEL[h.level];
  parts.push(el("div", {},
    el("h2", { text: "Where it belongs" }),
    el("div", { class: "verdict-grid mt-lg" },
      el("div", {},
        el("span", { class: "label", text: "Hierarchical clustering" }),
        el("span", { class: "figure", text: h.name }),
        el("span", { class: "level", text: lvl }),
        el("span", { class: "small muted", text: lvlWhy }),
        h.runner_up_name ? el("span", { class: "small muted", text: `Next closest: ${h.runner_up_name}` }) : null),
      el("div", {},
        el("span", { class: "label", text: "Density-based clustering" }),
        el("span", { class: "figure", text: d.in_dense_group ? d.name : "No dense group" }),
        el("span", { class: "level", text: d.in_dense_group ? "Within reach of the group's core books" : "Noise: not close to any dense group" }),
        el("span", { class: "small muted", text: `Nearest core book at ${fmt.f(d.nearest_core_distance, 3)}; the reach is ${fmt.f(d.eps, 3)}` }))),
    cautions.length ? el("ul", { class: "cautions mt-lg" }, cautions) : null,
    el("p", { class: "small muted mt-md",
      text: `Read as ${r.script}, ${fmt.n(r.tokens)} usable words${r.ocr_conf != null ? `, OCR confidence ${fmt.f(r.ocr_conf, 0)}` : ""}. Features: ${r.feature_name}.` })));

  const rows = r.matches.map((m, i) => el("tr", {},
    el("td", { class: "num", text: String(i + 1) }),
    el("td", {}, el("a", { href: m.url, text: m.title || m.identifier }), el("div", { class: "small muted", text: `${LANG[m.lang_tag] || m.lang_tag}, ${m.year ? Math.round(m.year) : "undated"}` })),
    el("td", { class: "small", text: m.shared_terms.slice(0, 6).join(", ") || "character patterns only" }),
    el("td", { class: "num", text: fmt.f(m.distance, 3) })));
  parts.push(el("div", {},
    el("h2", { text: "Closest archive books" }),
    el("div", { class: "table-wrap mt-md" }, el("table", {},
      el("thead", {}, el("tr", {}, el("th", { class: "num", scope: "col", text: "#" }), el("th", { scope: "col", text: "Book" }),
        el("th", { scope: "col", text: "Words in common" }), el("th", { class: "num", scope: "col", text: "Distance" }))),
      el("tbody", {}, rows)))));

  const mapEl = el("div", { role: "figure", "aria-label": `Map of the archive books with the page marked in ${h.name}` });
  parts.push(el("div", {}, el("h2", { text: "On the map" }),
    el("p", { class: "ink-2 mt-xs", text: "Each dot is a book, placed by the first two principal components. The lit dots are the page's group." }),
    el("div", { class: "mt-md" }, mapEl),
    el("ul", { class: "legend" }, el("li", {}, el("span", { class: "sw sw--accent sw--dot" }), h.name),
      el("li", {}, el("span", { class: "sw sw--dot" }), "other books"))));
  if (r.ocr) parts.push(ocrBlock(r));
  result.replaceChildren(...parts);

  const corpus = await getJSON("data/corpus.json");
  scatter(mapEl, corpus.docs.map((x) => ({ x: x.x, y: x.y, hi: x.hier === h.cluster,
    label: `${esc(x.title || x.identifier)}<br>${esc(LANG[x.lang_tag] || "")} ${x.year ? Math.round(x.year) : ""}` })),
  { you: { ...r.pca, label: "your page" }, height: 420 });
}

function ocrBlock(r) {
  return el("details", { class: "more" }, el("summary", { text: "What the OCR read" }),
    el("div", { class: "more-body" },
      el("p", { class: "small muted", text: `${r.ocr.pages} page(s), model ${r.ocr.model}${r.ocr.script_detected ? " chosen from the detected script" : ""}.` }),
      el("p", { class: "pre-line", text: r.ocr.preview || "(no text found)" })));
}
