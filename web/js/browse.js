import { getJSON, el, esc, fmt, scatter, hbar, LANG, params, setParam } from "./common.js";

const SCRIPT_LANG = { Latin: "Latin script", Devanagari: "Devanagari", Bengali: "Bengali", Gujarati: "Gujarati", Telugu: "Telugu", Kannada: "Kannada", Tamil: "Tamil" };
const [study, corpus] = await Promise.all([getJSON("data/study.json"), getJSON("data/corpus.json")]).catch((e) => {
  document.querySelector("#groups tbody").replaceChildren(el("tr", {}, el("td", { colspan: 3 },
    el("div", { class: "state state--error" }, el("p", { text: "The study results could not be loaded. Run the pipeline export, then reload." })))));
  throw e;
});
const set = study.sets[study.final];
let method = params().get("m") === "dbscan" ? "dbscan" : "hierarchical";
let current = params().has("g") ? Number(params().get("g")) : null;
document.getElementById(method === "dbscan" ? "m-d" : "m-h").checked = true;

function topScripts(mix) {
  return Object.entries(mix).sort((a, b) => b[1] - a[1]).slice(0, 2)
    .map(([s, v]) => `${SCRIPT_LANG[s] || s} ${fmt.p(v)}`).join(", ");
}

function table() {
  const r = set[method];
  const body = document.querySelector("#groups tbody");
  const profiles = [...r.profiles].sort((a, b) => (a.cluster === -1) - (b.cluster === -1) || b.size - a.size);
  body.replaceChildren(...profiles.map((p) => {
    const name = p.cluster === -1 ? "Noise: no dense group" : r.names[String(p.cluster)];
    const tr = el("tr", { class: "group-row", "aria-selected": String(p.cluster === current) },
      el("td", {}, el("button", { type: "button", text: name, onclick: () => pick(p.cluster) }),
        el("div", { class: "small muted", text: p.terms.slice(0, 5).map((t) => t.term).join(", ") })),
      el("td", { class: "num", text: fmt.n(p.size) }),
      el("td", { class: "small", text: topScripts(p.script_mix) }));
    tr.addEventListener("click", (e) => { if (e.target.tagName !== "BUTTON" && e.target.tagName !== "A") pick(p.cluster); });
    return tr;
  }));
}

function pick(c) {
  current = c;
  setParam("g", c);
  table();
  detail();
}

function detail() {
  const r = set[method];
  const box = document.getElementById("detail");
  const p = r.profiles.find((x) => x.cluster === current);
  if (!p) { box.replaceChildren(el("div", { class: "state" }, el("h2", { text: "Pick a group" }), el("p", { class: "ink-2", text: "Its words, its typical books and where it sits on the map appear here." }))); return; }
  const name = p.cluster === -1 ? "Noise" : r.names[String(p.cluster)];
  const key = method === "dbscan" ? "dbscan" : "hier";
  const mapEl = el("div", { role: "figure", "aria-label": `Map with the ${name} group lit` });
  const langs = Object.entries(p.script_mix).sort((a, b) => b[1] - a[1]);
  box.replaceChildren(
    el("div", {}, el("h2", { text: name }),
      el("p", { class: "ink-2 mt-xs", text: `${fmt.n(p.size)} books, ${fmt.p(p.share)} of the sample. Median year ${p.median_year ? Math.round(p.median_year) : "unknown"}; median OCR confidence ${fmt.f(p.median_conf, 0)}.` }),
      p.cluster === -1 ? el("p", { class: "note mt-md", text: "DBSCAN leaves these books out: none sits in a dense neighbourhood of similar books. Many are hard-to-read scans or one-off subjects." }) : null),
    el("div", {}, el("h3", { text: "Most distinctive words" }), el("ul", { class: "terms mt-sm" }, p.terms.map((t) => el("li", { text: t.term })))),
    el("div", {}, mapEl),
    el("div", {}, el("h3", { text: "Typical books" }), el("div", { class: "table-wrap mt-sm" }, el("table", {},
      el("thead", {}, el("tr", {}, el("th", { scope: "col", text: "Book" }), el("th", { scope: "col", class: "num", text: "Year" }), el("th", { scope: "col", text: "Script" }))),
      el("tbody", {}, p.typical.map((t) => el("tr", {},
        el("td", {}, el("a", { href: `https://archive.org/details/${t.identifier}`, text: t.title || t.identifier })),
        el("td", { class: "num", text: t.year ? Math.round(t.year) : "undated" }),
        el("td", { text: t.script }))))))),
    el("div", {}, el("h3", { text: "Scripts in this group" }), el("table", { class: "mt-sm" },
      el("tbody", {}, langs.map(([s, v]) => el("tr", {}, el("td", { text: SCRIPT_LANG[s] || s }), el("td", { class: "num", text: fmt.p(v) }), el("td", {}, hbar(v))))))),
    Object.keys(p.classification_top || {}).length ? el("div", {}, el("h3", { text: "Catalogue subjects, where recorded" }),
      el("p", { class: "small muted mt-xs", text: `Only ${fmt.p(p.classified_share)} of these books carry a subject in the catalogue; shown as a check, not used to form the group.` }),
      el("ul", { class: "terms mt-sm" }, Object.entries(p.classification_top).map(([k, v]) => el("li", { text: `${k} (${v})` })))) : null);
  scatter(mapEl, corpus.docs.map((d) => ({ x: d.x, y: d.y, hi: d[key] === current, noise: d[key] === -1,
    label: `${esc(d.title || d.identifier)}<br>${esc(LANG[d.lang_tag] || "")} ${d.year ? Math.round(d.year) : ""}` })), { height: 360 });
}

for (const input of document.querySelectorAll('#method input')) {
  input.addEventListener("change", () => { method = input.value; setParam("m", method); current = null; setParam("g", null); table(); detail(); });
}
table();
detail();
