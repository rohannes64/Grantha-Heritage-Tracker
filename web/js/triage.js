import { getJSON, el, fmt, LANG, params, setParam } from "./common.js";

// The API's page-size bound (app/routes/triage.py MAX_LIMIT) and the batch endpoint's bound are the same.
const MAX = 500;
const SIZES = [50, 100, MAX];
const DEFAULT_SIZE = 100;
const REVOKE_MS = 1000;   // how long the saved file's object URL stays alive after the click
const VERDICTS = ["fine", "re-ocr", "re-scan"];
const VERDICT = {
  fine: { name: "Fine", short: "fine", plain: "The text we have can be used as it is." },
  "re-ocr": { name: "Read the scan again", short: "read again", plain: "The scan is there but too little readable text came out of it; run character recognition again." },
  "re-scan": { name: "Photograph again", short: "photograph again", plain: "Our reading of the scan is missing or unreliable, and the archive has no text of its own; the pages need new photographs." },
};
const BCP47 = { eng: "en", hin: "hi", san: "sa", ben: "bn", guj: "gu", tel: "te", kan: "kn", tam: "ta" };
const NON_LATIN = /(?!\p{Script=Latin})\p{L}/u;
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const fLang = $("f-lang"), fVerdict = $("f-verdict"), fLimit = $("f-limit");
const downloadBtn = $("download"), downloadNote = $("download-note"), verdictWhy = $("verdict-why");
const booksBody = $("books-body"), pager = $("pager"), prevBtn = $("prev"), nextBtn = $("next"), rangeEl = $("range");

// Python writes a None language key as "null": both mean the language was not recorded.
const noLang = (tag) => tag == null || tag === "" || tag === "null";
const langName = (tag) => (noLang(tag) ? "language not recorded" : LANG[tag] || tag);
const announce = (msg) => { statusEl.textContent = msg; };
const books = (n) => (n === 1 ? "one book" : `${fmt.n(n)} books`);

let fixture = null;          // {index, name} when replaying recorded responses on localhost
let uncalibrated = false;    // the model predates scan-quality data: verdicts are not available
let current = { rows: [] };
let seq = 0;
let loading = false;        // the table is being fetched
let downloading = false;

/** Unusable but still focusable, so a keyboard user never loses their place. */
function setOff(btn, off) { if (off) btn.setAttribute("aria-disabled", "true"); else btn.removeAttribute("aria-disabled"); }
const isOff = (btn) => btn.getAttribute("aria-disabled") === "true";

// ---------- data

function triageURL({ lang = "", verdict = "", limit = DEFAULT_SIZE, offset = 0 } = {}) {
  const q = new URLSearchParams();
  if (lang) q.set("lang", lang);
  if (verdict) q.set("verdict", verdict);
  q.set("limit", String(limit));
  q.set("offset", String(offset));
  return `/api/triage?${q}`;
}

async function api(url) {
  if (fixture) {
    const hit = Object.entries(fixture.index.fixtures || {}).find(([, m]) => m.method === "GET" && m.path === url);
    if (!hit) throw new Error(`No recorded response for ${url} in fixtures/_index.json.`);
    const fx = await getJSON(`fixtures/${hit[0]}.json`);
    if (fx.status !== 200) throw new Error((fx.body && fx.body.detail) || `The server answered ${fx.status}.`);
    return fx.body;
  }
  let r;
  try { r = await fetch(url, { headers: { Accept: "application/json" } }); } catch {
    throw new Error("The server could not be reached. Check the connection and try again.");
  }
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || `The server answered ${r.status}.`);
  return body;
}

// ---------- builders

function failed(target, title, msg, retry = null) {
  target.removeAttribute("aria-busy");
  target.replaceChildren(el("div", { class: "state state--error" },
    el("h3", { tabindex: "-1", text: title }), el("p", { class: "ink-2 mt-xs", text: msg }),
    retry ? el("div", { class: "actions mt-md" }, el("button", { class: "btn", type: "button", text: "Try again", onclick: retry })) : null));
}

function recordedNote() {
  if (!fixture) return null;
  const at = fixture.index.generated_at;
  const when = at ? new Date(at) : null;
  const shown = when && !Number.isNaN(when.getTime())
    ? when.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC" : at || "an unrecorded date";
  return el("p", { class: "recorded" }, el("strong", { text: "Recorded result" }),
    el("span", {}, "Replayed from ", el("code", { text: fixture.name }), ", real GET /api/triage responses recorded on ",
      el("time", { datetime: at || null, text: shown }), "."));
}

function share(n, total) { return total ? n / total : 0; }

function summary(body) {
  const total = body.total || 0;
  const counts = body.counts || {};
  const parts = [recordedNote()];
  if (uncalibrated) {
    parts.push(el("div", { class: "state tri-notice" },
      el("h3", { text: "Verdicts are not available yet" }),
      el("p", { class: "ink-2 mt-xs", text: "The model on this server was built before scan-quality data was added to it. The books it returned carry no record of where their text came from, which the verdicts depend on, so most books come out as fine by default. That is a gap in the data, not a finding about the scans." }),
      el("p", { class: "ink-2 mt-xs" }, "Books covered: ", el("span", { class: "num", text: fmt.n(total) }), ".")));
    return parts;
  }
  parts.push(el("p", { class: "lead ink-2" }, "Out of ", el("strong", { class: "num", text: fmt.n(total) }), " digitised books checked:"));
  parts.push(el("div", { class: "figures-row tri-figures" }, VERDICTS.map((v) => el("div", { class: `tri-fig tri-fig--${v}` },
    el("span", { class: "label", text: VERDICT[v].name }),
    el("span", { class: "figure", text: fmt.n(counts[v] || 0) }),
    el("span", { class: "small ink-2", text: `${fmt.p(share(counts[v] || 0, total), 1)} of the books` }),
    el("p", { class: "small muted mt-xs", text: VERDICT[v].plain })))));
  return parts;
}

/** Language keys, named ones in name order, then the not-recorded key last. */
function sortedTags(by) {
  return Object.keys(by).sort((a, b) => (noLang(a) - noLang(b)) || langName(a).localeCompare(langName(b)));
}

function languages(body) {
  const by = body.by_language || {};
  const tags = sortedTags(by);
  if (!tags.length) return [el("p", { class: "ink-2", text: "The server returned no languages." })];
  if (uncalibrated) {
    return [el("p", { class: "ink-2", text: "The split by language appears here once the verdicts are available. Until then, the number of books covered in each language:" }),
      el("dl", { class: "sheet mt-md tri-covered" }, tags.map((t) => {
        const n = VERDICTS.reduce((s, v) => s + (by[t][v] || 0), 0);
        return el("div", {}, el("dt", { text: langName(t) }), el("dd", { class: "num", text: fmt.n(n) }));
      }))];
  }
  const legend = el("ul", { class: "legend tri-legend" }, VERDICTS.map((v) =>
    el("li", {}, el("span", { class: `tri-sw tri-seg--${v}`, "aria-hidden": "true" }), VERDICT[v].name)));
  const list = el("ul", { class: "tri-langs mt-md" }, tags.map((t) => {
    const c = by[t];
    const n = VERDICTS.reduce((s, v) => s + (c[v] || 0), 0);
    const bar = el("span", { class: "tri-bar", "aria-hidden": "true" }, VERDICTS.filter((v) => c[v]).map((v) =>
      el("i", { class: `tri-seg--${v}`, style: `flex-grow:${c[v]}` })));
    return el("li", {},
      el("span", { class: "tri-lang-name" }, el("span", { text: langName(t) }), el("span", { class: "small muted num", text: ` ${books(n)}` })),
      bar,
      el("span", { class: "small ink-2 tri-lang-counts" }, VERDICTS.map((v) =>
        el("span", {}, el("span", { class: `tri-key tri-key--${v}`, "aria-hidden": "true" }),
          el("span", { class: "num", text: fmt.n(c[v] || 0) }), ` ${VERDICT[v].short}`))));
  }));
  return [legend, list];
}

const SOURCE = {
  tesseract_pages: "our reading of sampled pages",
  none: "no text",
};
function sourceText(s) {
  if (s == null) return "not recorded";
  return SOURCE[s] || `the archive's own text (${s})`;
}

function titleCell(r) {
  const title = r.title || r.identifier || "Untitled";
  const attrs = { href: r.url || `https://archive.org/details/${encodeURIComponent(r.identifier)}`, dir: "auto", text: title };
  if (NON_LATIN.test(title) && BCP47[r.lang_tag]) attrs.lang = BCP47[r.lang_tag];
  return el("td", { class: "tri-title" }, el("a", attrs), el("span", { class: "small muted tri-id", text: r.identifier }));
}

function verdictCell(r) {
  if (uncalibrated) return el("td", { class: "muted", "data-label": "Verdict", text: "not available" });
  const v = VERDICT[r.verdict];
  return el("td", { class: `tri-verdict tri-verdict--${r.verdict}`, "data-label": "Verdict" },
    el("span", {}, el("span", { class: `tri-key tri-key--${r.verdict}`, "aria-hidden": "true" }), v ? v.name : r.verdict || "not given"));
}

function booksTable(rows) {
  return el("div", { class: "table-wrap" }, el("table", { class: "tri-table" },
    el("caption", { class: "visually-hidden", text: "Books with their scan-quality verdict" }),
    el("thead", {}, el("tr", {},
      el("th", { scope: "col", text: "Book" }), el("th", { scope: "col", text: "Language" }),
      el("th", { scope: "col", text: "Verdict" }), el("th", { scope: "col", text: "Reasons" }),
      el("th", { scope: "col", class: "num", text: "OCR confidence" }), el("th", { scope: "col", text: "Text used" }))),
    el("tbody", {}, rows.map((r) => {
      const s = r.signals || {};
      const reasons = (r.reasons || []).filter(Boolean);
      return el("tr", {},
        titleCell(r),
        el("td", { "data-label": "Language", text: langName(r.lang_tag) }),
        verdictCell(r),
        el("td", { class: "tri-reasons", "data-label": "Reasons" }, reasons.length
          ? el("ul", {}, reasons.map((x) => el("li", { text: x }))) : el("span", { class: "muted", text: "none" })),
        el("td", { class: "num", "data-label": "OCR confidence", text: s.mean_conf == null ? "not recorded" : fmt.f(s.mean_conf, 0) }),
        el("td", { "data-label": "Text used", text: sourceText(s.text_source) }));
    }))));
}

// ---------- the table, its filters and paging

function state() {
  const p = params();
  const limit = Number(p.get("limit"));
  const offset = Number(p.get("offset"));
  return {
    lang: p.get("lang") || "",
    verdict: VERDICTS.includes(p.get("verdict")) ? p.get("verdict") : "",
    limit: SIZES.includes(limit) ? limit : DEFAULT_SIZE,
    offset: Number.isInteger(offset) && offset > 0 ? offset : 0,
  };
}

function writeState(s) {
  setParam("lang", s.lang || null);
  setParam("verdict", s.verdict || null);
  setParam("limit", s.limit === DEFAULT_SIZE ? null : String(s.limit));
  setParam("offset", s.offset ? String(s.offset) : null);
}

function filterWords(s) {
  const bits = [s.lang ? langName(s.lang) : null, s.verdict ? VERDICT[s.verdict].name.toLowerCase() : null].filter(Boolean);
  return bits.length ? bits.join(", ") : "all books";
}

async function loadBooks(s, { preloaded = null, focus = false } = {}) {
  const mine = ++seq;
  loading = true;
  booksBody.setAttribute("aria-busy", "true");
  setOff(downloadBtn, true);
  // the pager stays in place while loading, so a focused Previous or Next keeps focus
  pager.setAttribute("aria-busy", "true"); setOff(prevBtn, true); setOff(nextBtn, true);
  booksBody.replaceChildren(el("div", { class: "skeleton skeleton--block" }));
  let body;
  try {
    body = preloaded || await api(triageURL(s));
  } catch (err) {
    if (mine !== seq) return;
    loading = false;
    current = { rows: [] };
    failed(booksBody, "The books did not load", String(err.message || err), () => loadBooks(state(), { focus }));
    leavePager(booksBody);
    announce("The books did not load.");
    return;
  }
  if (mine !== seq) return;
  loading = false;
  pager.removeAttribute("aria-busy");
  const rows = (body.rows || []).filter((r) => r && r.identifier);
  const total = body.total || 0;
  current = { rows, s };
  booksBody.removeAttribute("aria-busy");
  if (!rows.length) {
    const beyond = total > 0 && s.offset >= total;
    booksBody.replaceChildren(el("div", { class: "state" },
      el("h3", { tabindex: "-1", text: beyond ? "No books on this page" : "No books match" }),
      el("p", { class: "ink-2 mt-xs", text: beyond ? `The filter (${filterWords(s)}) has fewer books than this page starts at.` : `Nothing matches ${filterWords(s)}.` }),
      el("div", { class: "actions mt-md" }, beyond
        ? el("button", { class: "btn", type: "button", text: "Go to the first page", onclick: () => apply({ offset: 0 }) })
        : el("button", { class: "btn", type: "button", text: "Show all books", onclick: () => apply({ lang: "", verdict: "", offset: 0 }) }))));
    leavePager(booksBody);
    announce(beyond ? "No books on this page." : `No books match ${filterWords(s)}.`);
    return;
  }
  booksBody.replaceChildren(booksTable(rows));
  const first = s.offset + 1, last = s.offset + rows.length;
  rangeEl.textContent = `Books ${fmt.n(first)} to ${fmt.n(last)} of ${fmt.n(total)}, ${filterWords(s)}`;
  setOff(prevBtn, s.offset <= 0);
  setOff(nextBtn, last >= total);
  pager.hidden = false;
  if (!downloading) setOff(downloadBtn, false);
  downloadNote.textContent = uncalibrated ? CSV_CAVEAT : "";
  announce(`Showing books ${fmt.n(first)} to ${fmt.n(last)} of ${fmt.n(total)}.`);
  // after paging, focus goes to the section heading: the new page is read from its top, and Tab carries on
  // through the filters and the table to the pager
  if (focus) $("books-title").focus();
}

/** Hide the pager when there is nothing to page; if focus was in it, put focus on the state's heading. */
function leavePager(target) {
  const had = pager.contains(document.activeElement);
  pager.removeAttribute("aria-busy");
  pager.hidden = true;
  if (had) { const h = target.querySelector("h3"); if (h) h.focus(); }
}

function apply(patch, opts) {
  const s = { ...state(), ...patch };
  if (!("offset" in patch)) s.offset = 0;
  fLang.value = s.lang; fVerdict.value = s.verdict; fLimit.value = String(s.limit);
  writeState(s);
  return loadBooks(s, opts);
}

fLang.addEventListener("change", () => apply({ lang: fLang.value }));
fVerdict.addEventListener("change", () => apply({ verdict: fVerdict.value }));
fLimit.addEventListener("change", () => apply({ limit: Number(fLimit.value) }));
$("filters").addEventListener("submit", (e) => e.preventDefault());
prevBtn.addEventListener("click", () => { if (isOff(prevBtn)) return; const s = state(); apply({ offset: Math.max(0, s.offset - s.limit) }, { focus: true }); });
nextBtn.addEventListener("click", () => { if (isOff(nextBtn)) return; const s = state(); apply({ offset: s.offset + s.limit }, { focus: true }); });

// ---------- download as CSV: the visible books, through POST /api/batch

// While the model has no scan verdicts, the batch file's triage_verdict column reads "fine" for every book.
const CSV_CAVEAT = "This model has no scan verdicts yet: the file lists the books, but its triage_verdict column says fine for every book and means nothing until the verdicts are available.";

downloadBtn.addEventListener("click", async () => {
  if (downloading || loading || isOff(downloadBtn)) return;
  const ids = current.rows.map((r) => r.identifier).slice(0, MAX);
  if (!ids.length) return;
  const s = current.s || state();
  downloading = true;
  setOff(downloadBtn, true); downloadBtn.setAttribute("aria-busy", "true");
  downloadNote.textContent = "Preparing the file.";
  try {
    const r = await fetch("/api/batch", { method: "POST", headers: { "Content-Type": "application/json", Accept: "text/csv" }, body: JSON.stringify({ identifiers: ids }) });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail || `The server answered ${r.status}.`);
    }
    const blob = await r.blob();
    const name = ["grantha-scan-quality", s.lang || "all-languages", s.verdict || "all-verdicts", "from-" + String(s.offset + 1)].join("_") + ".csv";
    const href = URL.createObjectURL(blob);
    const a = el("a", { href, download: name, hidden: true });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(href), REVOKE_MS);
    downloadNote.textContent = `Saved ${books(ids.length)} as ${name}.` + (uncalibrated ? ` ${CSV_CAVEAT}` : "");
  } catch (err) {
    downloadNote.textContent = `The download did not run: ${err.message || err}`;
  } finally {
    downloading = false;
    downloadBtn.removeAttribute("aria-busy");
    setOff(downloadBtn, loading || !current.rows.length);
  }
});

// ---------- start

async function start() {
  for (const n of SIZES) fLimit.append(el("option", { value: String(n), text: fmt.n(n) }));
  setOff(downloadBtn, true);
  await loadAll();
}

async function loadAll() {
  const s = state();
  fVerdict.value = s.verdict; fLimit.value = String(s.limit);
  const summaryBody = $("summary-body"), langBody = $("languages-body");
  for (const t of [summaryBody, langBody, booksBody]) { t.setAttribute("aria-busy", "true"); t.replaceChildren(el("div", { class: "skeleton skeleton--block" })); }
  const base = triageURL({});
  let all;
  try {
    all = await api(base);
  } catch (err) {
    const msg = String(err.message || err);
    const retry = () => loadAll().then(() => $("summary-title").focus());
    failed(summaryBody, "The verdicts did not load", msg, retry);
    failed(langBody, "The languages did not load", msg);
    failed(booksBody, "The books did not load", msg);
    announce("The scan-quality data did not load.");
    return;
  }
  const rows = (all.rows || []).filter(Boolean);
  // A model built before scan-quality data has no text source on any book, whatever its counts say.
  uncalibrated = (all.total || 0) > 0 && rows.length > 0 && rows.every((r) => !r.signals || r.signals.text_source == null);
  document.body.classList.toggle("is-uncalibrated", uncalibrated);
  fVerdict.disabled = uncalibrated;
  verdictWhy.hidden = !uncalibrated;
  if (uncalibrated) { fVerdict.value = ""; s.verdict = ""; fVerdict.setAttribute("aria-describedby", "verdict-why"); }
  else fVerdict.removeAttribute("aria-describedby");
  downloadBtn.textContent = uncalibrated ? "Download book list" : "Download as CSV";

  fLang.replaceChildren(el("option", { value: "", text: "All languages" }));
  for (const t of sortedTags(all.by_language || {})) {
    if (!noLang(t)) fLang.append(el("option", { value: t, text: langName(t) }));   // the API cannot filter on a missing tag
  }
  if (s.lang && ![...fLang.options].some((o) => o.value === s.lang)) fLang.append(el("option", { value: s.lang, text: langName(s.lang) }));
  fLang.value = s.lang;

  summaryBody.removeAttribute("aria-busy");
  summaryBody.replaceChildren(...summary(all).filter(Boolean));
  langBody.removeAttribute("aria-busy");
  langBody.replaceChildren(...languages(all));
  writeState(s);
  await loadBooks(s, { preloaded: triageURL(s) === base ? all : null });
}

const fx = params().get("fixture");
if (fx && LOCAL_HOSTS.has(location.hostname)) {
  if (!/^[\w.-]+$/.test(fx)) {
    failed($("summary-body"), "No such recorded result", "That is not a fixture name.");
  } else {
    getJSON("fixtures/_index.json").then((index) => {
      if (!index.fixtures || !index.fixtures[fx]) throw new Error(`"${fx}" is not in fixtures/_index.json.`);
      fixture = { index, name: fx };
      return start();
    }).catch((err) => failed($("summary-body"), "The recorded result could not be loaded", String(err.message || err)));
  }
} else {
  start();
}
