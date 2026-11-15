import { getJSON, el, esc, fmt, hbar, scatter, LANG, params } from "./common.js";

const form = document.getElementById("check-form");
const fileIn = document.getElementById("file");
const textIn = document.getElementById("text");
const langIn = document.getElementById("lang");
const drop = document.getElementById("drop");
const errorEl = document.getElementById("form-error");
const submit = document.getElementById("submit");
const result = document.getElementById("result");
const statusEl = document.getElementById("result-status");

const LEVEL = {
  strong: ["Sits well inside", "closer to the group's centre than half of its own books"],
  good: ["Inside", "as close as nine in ten of the group's own books"],
  weak: ["At the edge", "farther than most of the group's books, but within its range"],
  outside: ["Outside every group", "farther from the nearest centre than any of that group's books"],
};
// Page language for screen readers and font fallback, used only when a title is written in a non-Latin script.
const BCP47 = { eng: "en", hin: "hi", san: "sa", ben: "bn", guj: "gu", tel: "te", kan: "kn", tam: "ta" };
const NON_LATIN = /(?!\p{Script=Latin})\p{L}/u;
const LOCAL_HOSTS =new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

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
function announce(msg) { statusEl.textContent = msg; }

function loading() {
  result.setAttribute("aria-busy", "true");
  result.replaceChildren(el("div", { class: "state" },
    el("h2", { text: "Reading the page" }),
    el("p", { class: "ink-2", text: "OCR takes a few seconds a page; the comparison is instant after that." }),
    el("div", { class: "skeleton skeleton--block mt-lg" })));
}

function failed(title, msg, hint) {
  result.removeAttribute("aria-busy");
  result.replaceChildren(el("div", { class: "state state--error" },
    el("h2", { text: title }),
    el("p", { class: "ink-2", text: msg }),
    hint ? el("p", { class: "ink-2", text: hint }) : null));
  announce(title);
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
    await render(body, { focus: true });
  } catch (err) {
    failed("The check did not run", String(err.message || err), "Try a clearer scan, a smaller PDF, or paste the text instead.");
  } finally {
    submit.disabled = false; submit.removeAttribute("aria-busy");
  }
});

// ---------- small builders

const has = (o, k) => o != null && Object.prototype.hasOwnProperty.call(o, k);
const langName = (tag) => (tag ? LANG[tag] || tag : null);

/** A book title as a link, tagged with its language when it is written in a non-Latin script. */
function bookLink(b) {
  const title = b.title || b.identifier || "Untitled";
  const attrs = { href: b.url || null, dir: "auto", text: title };
  if (NON_LATIN.test(title) && BCP47[b.lang_tag]) attrs.lang = BCP47[b.lang_tag];
  return b.url ? el("a", attrs) : el("span", attrs);
}

/** Language and year after a title, from whatever the row carries; nothing when it carries neither. */
function bookMeta(b) {
  const bits = [langName(b.lang_tag), b.year ? Math.round(b.year) : null].filter(Boolean);
  return bits.length ? el("span", { class: "small muted", text: ` ${bits.join(", ")}` }) : null;
}

/** A distance with its word beside it, so the figure is labelled on screen and not only on hover. */
function distanceTag(x) {
  return el("span", { class: "num" }, el("span", { class: "dist-word", text: "distance " }), fmt.f(x, 3));
}

function field(label, ...value) {
  return el("div", {}, el("dt", { text: label }), el("dd", {}, ...value));
}

function recordedNote(rec) {
  if (!rec) return null;
  const when = rec.generated_at ? new Date(rec.generated_at) : null;
  const shown = when && !Number.isNaN(when.getTime())
    ? when.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC"
    : rec.generated_at || "an unrecorded date";
  return el("p", { class: "recorded" },
    el("strong", { text: "Recorded result" }),
    el("span", {}, "Replayed from ", el("code", { text: rec.name }),
      `, a real ${rec.method || "POST"} ${rec.path || "/api/check"} response recorded on `,
      el("time", { datetime: rec.generated_at || null, text: shown }),
      rec.feature_set ? ` with feature set ${rec.feature_set}.` : "."));
}

function suggestedBlock(r) {
  if (!has(r, "suggested_classes")) {
    return el("div", {}, el("span", { class: "label", text: "Suggested class" }),
      el("p", { class: "ink-2 mt-xs", text: "This server did not send a class suggestion with the result." }));
  }
  const list = (r.suggested_classes || []).filter((s) => s && s.class);
  if (!list.length) {
    return el("div", {}, el("span", { class: "label", text: "Suggested class" }),
      el("p", { class: "ink-2 mt-xs", text: "No class to suggest: none of the books that went into the vote carries a catalogue class." }));
  }
  const top = list[0];
  return el("div", {},
    el("span", { class: "label", id: "sugg-label", text: "Suggested class" }),
    el("span", { class: "figure mt-xs", dir: "auto", text: top.class }),
    el("p", { class: "small muted mt-xs", text: "Share of a distance-weighted vote among the nearest books in the model that carry a catalogue class." }),
    el("ol", { class: "classes mt-md", "aria-labelledby": "sugg-label" }, list.map((s) => {
      const bar = hbar(Number(s.score) || 0);
      bar.setAttribute("aria-hidden", "true"); bar.removeAttribute("role"); bar.removeAttribute("aria-label");
      return el("li", {},
        el("span", { class: "name", dir: "auto", text: s.class }),
        bar,
        el("span", { class: "pct", text: s.score == null ? "n/a" : fmt.p(s.score) }));
    })));
}

function qualityBlock(r) {
  const cautions = (r.cautions || []).filter(Boolean);
  const conf = r.ocr_conf != null
    ? `OCR confidence ${fmt.f(r.ocr_conf, 0)}.`
    : r.input === "text" ? "Pasted as text, so there is no OCR confidence." : "No OCR confidence was reported.";
  return el("div", { class: "quality" },
    el("h3", { text: "Scan quality" }),
    cautions.length
      ? el("ul", { class: "cautions" }, cautions.map((c) => el("li", { class: "note", text: c })))
      : el("p", { class: "ink-2", text: "No cautions: the text was long and clear enough to compare with confidence." }),
    el("p", { class: "small muted", text: conf }));
}

function editionsBlock(r) {
  if (!has(r, "editions")) return null;   // the field arrives with the editions feature; until then, nothing
  const e = r.editions;
  const list = Array.isArray(e) ? e : (e && Array.isArray(e.candidates) ? e.candidates : []);
  return el("div", { class: "quality" },
    el("h3", { text: "Possible editions" }),
    e && e.method ? el("p", { class: "small muted", text: e.method }) : null,
    list.length
      ? el("ul", { class: "editions" }, list.map((b) => el("li", {},
          el("span", { class: "book" }, bookLink(b), bookMeta(b)),
          b.distance != null ? distanceTag(b.distance) : null)))
      : el("p", { class: "ink-2", text: "No other edition of this text was found in the archive." }));
}

function cardSheet(r) {
  const h = r.hierarchical, d = r.dbscan;
  const rows = [];
  if (r.script) rows.push(field("Script", r.script));
  if (r.tokens != null) rows.push(field("Readable words", fmt.n(r.tokens)));
  if (r.input) rows.push(field("Read from", r.input === "scan" ? (r.ocr && r.ocr.pages != null ? `a scan, ${fmt.n(r.ocr.pages)} page(s)` : "a scan") : "pasted text"));
  if (h && h.name) rows.push(field("Topic group", `${h.name}${LEVEL[h.level] ? `, ${LEVEL[h.level][0].toLowerCase()}` : ""}`));
  if (d) rows.push(field("Dense group", d.in_dense_group
    ? (d.name || "within reach of a dense group that has no name")
    : "none, the page is noise to density-based clustering"));
  if (r.feature_name) rows.push(field("Compared by", r.feature_name));
  return rows.length ? el("dl", { class: "sheet" }, rows) : null;
}

function card(r) {
  const headId = "card-title";
  return el("article", { class: "card", "aria-labelledby": headId },
    el("div", { class: "card-head" },
      el("h2", { id: headId, tabindex: "-1", text: "Catalogue card" }),
      el("p", { class: "ink-2", text: "A draft entry for this page, built from the archive books it sits closest to. Check it before it goes into a catalogue." })),
    suggestedBlock(r),
    cardSheet(r),
    qualityBlock(r),
    editionsBlock(r));
}

function verdict(r) {
  const h = r.hierarchical, d = r.dbscan;
  if (!h && !d) return null;
  const lv = (h && LEVEL[h.level]) || [h && h.level ? h.level : "", ""];
  return el("div", {},
    el("h2", { text: "Where it belongs" }),
    el("div", { class: "verdict-grid mt-lg" },
      h ? el("div", {},
        el("span", { class: "label", text: "Hierarchical clustering" }),
        el("span", { class: "figure", text: h.name || "unnamed group" }),
        lv[0] ? el("span", { class: "level", text: lv[0] }) : null,
        lv[1] ? el("span", { class: "small muted", text: lv[1] }) : null,
        (h.also_close_to && h.also_close_to.length)
          ? el("span", { class: "small", text: `Also close to: ${h.also_close_to.map((a) => a.name).join("; ")}` })
          : (h.runner_up_name ? el("span", { class: "small muted", text: `Next closest: ${h.runner_up_name}` }) : null)) : null,
      d ? el("div", {},
        el("span", { class: "label", text: "Density-based clustering" }),
        el("span", { class: "figure", text: d.in_dense_group ? (d.name || "Unnamed dense group") : "No dense group" }),
        el("span", { class: "level", text: d.in_dense_group ? "Within reach of the group's core books" : "Noise: not close to any dense group" }),
        el("span", { class: "small muted", text: `Nearest core book at ${fmt.f(d.nearest_core_distance, 3)}; the reach is ${fmt.f(d.eps, 3)}` })) : null));
}

function termsCell(m) {
  const terms = (m.shared_terms || []).slice(0, 6).join(", ");
  const attrs = { class: "small", dir: "auto", text: terms || "character patterns only" };
  if (terms && NON_LATIN.test(terms) && BCP47[m.lang_tag]) attrs.lang = BCP47[m.lang_tag];
  return el("td", attrs);
}

function matchesBlock(r) {
  const matches = r.matches || [];
  if (!matches.length) return el("div", {}, el("h2", { text: "Closest archive books" }), el("p", { class: "ink-2 mt-md", text: "The result lists no archive books." }));
  const rows = matches.map((m, i) => el("tr", {},
    el("td", { class: "num", text: String(i + 1) }),
    el("td", {}, el("span", { class: "book" }, bookLink(m)),
      el("div", { class: "small muted", text: `${langName(m.lang_tag) || "language not recorded"}, ${m.year ? Math.round(m.year) : "undated"}` })),
    termsCell(m),
    el("td", { class: "num", text: fmt.f(m.distance, 3) })));
  return el("div", {},
    el("h2", { text: "Closest archive books" }),
    el("div", { class: "table-wrap mt-md" }, el("table", {},
      el("thead", {}, el("tr", {}, el("th", { class: "num", scope: "col", text: "#" }), el("th", { scope: "col", text: "Book" }),
        el("th", { scope: "col", text: "Words in common" }), el("th", { class: "num", scope: "col", text: "Distance" }))),
      el("tbody", {}, rows))));
}

function otherScriptsBlock(r) {
  if (!has(r, "related_other_scripts")) return null;
  const books = (r.related_other_scripts || []).filter(Boolean);
  const head = [el("h2", { text: "In other scripts" }),
    el("p", { class: "ink-2 mt-xs", text: `The archive books closest to the page among those not written in ${r.script || "its script"}, grouped by script, nearest first.` })];
  if (!books.length) return el("div", {}, ...head, el("p", { class: "ink-2 mt-md", text: "The result returned no book in another script." }));
  const groups = new Map();
  for (const b of books) {
    const key = b.script || langName(b.lang_tag) || "Script not recorded";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(b);
  }
  return el("div", {}, ...head,
    el("dl", { class: "scripts mt-md" }, [...groups].map(([script, list]) => el("div", {},
      el("dt", {}, script, el("span", { class: "small", text: list.length === 1 ? "one book" : `${fmt.n(list.length)} books` })),
      el("dd", {}, el("ul", {}, list.map((b) => el("li", {},
        el("span", { class: "book" }, bookLink(b), bookMeta(b)),
        distanceTag(b.distance)))))))));
}

function ocrBlock(r) {
  return el("details", { class: "more" }, el("summary", { text: "What the OCR read" }),
    el("div", { class: "more-body" },
      el("p", { class: "small muted", text: `${r.ocr.pages} page(s), model ${r.ocr.model}${r.ocr.script_detected ? " chosen from the detected script" : ""}.` }),
      el("p", { class: "pre-line", text: r.ocr.preview || "(no text found)" })));
}

// ---------- the result

async function render(r, { focus = false, recorded = null } = {}) {
  const parts = [];
  if (recorded) parts.push(recordedNote(recorded));

  if (r.status === "abstain") {
    const cautions = (r.cautions || []).filter(Boolean);
    parts.push(el("div", { class: "state" }, el("h2", { tabindex: "-1", id: "card-title", text: "Not enough to go on" }),
      el("p", { class: "ink-2", text: r.message || "The page could not be compared with the archive." }),
      cautions.length ? el("ul", { class: "cautions mt-md" }, cautions.map((c) => el("li", { class: "note", text: c }))) : null));
    if (r.ocr) parts.push(ocrBlock(r));
    result.replaceChildren(...parts);
    result.removeAttribute("aria-busy");
    announce("Not enough readable text to make a catalogue card.");
    if (focus) document.getElementById("card-title").focus();
    return;
  }

  const h = r.hierarchical;
  parts.push(card(r), verdict(r), matchesBlock(r), otherScriptsBlock(r));
  let mapEl = null;
  if (r.pca && h) {
    mapEl = el("div", { role: "figure", "aria-label": `Map of the archive books with the page marked in ${h.name}` });
    parts.push(el("div", {}, el("h2", { text: "On the map" }),
      el("p", { class: "ink-2 mt-xs", text: "Each dot is a book, placed by the first two principal components. The lit dots are the page's group." }),
      el("div", { class: "mt-md" }, mapEl),
      el("ul", { class: "legend" }, el("li", {}, el("span", { class: "sw sw--accent sw--dot" }), h.name),
        el("li", {}, el("span", { class: "sw sw--dot" }), "other books"))));
  }
  if (r.ocr) parts.push(ocrBlock(r));
  result.replaceChildren(...parts.filter(Boolean));
  result.removeAttribute("aria-busy");
  const top = (r.suggested_classes || [])[0];
  announce(`Catalogue card ready${top && top.class ? `: suggested class ${top.class}` : ""}${r.status === "caution" ? ", with cautions" : ""}.`);
  if (focus) document.getElementById("card-title").focus();

  if (mapEl) {
    const corpus = await getJSON("data/corpus.json");
    scatter(mapEl, corpus.docs.map((x) => ({ x: x.x, y: x.y, hi: x.hier === h.cluster,
      label: `${esc(x.title || x.identifier)}<br>${esc(LANG[x.lang_tag] || "")} ${x.year ? Math.round(x.year) : ""}` })),
    { you: { ...r.pca, label: "your page" }, height: 420 });
  }
}

// ---------- recorded results (development only): ?fixture=<file name without .json>

async function loadFixture(name) {
  if (!/^[\w.-]+$/.test(name)) { failed("No such recorded result", `"${name}" is not a fixture name.`); return; }
  loading();
  try {
    const index = await getJSON("fixtures/_index.json");
    const meta = index.fixtures && index.fixtures[name];
    if (!meta || meta.path !== "/api/check") throw new Error(`"${name}" is not a recorded check in fixtures/_index.json.`);
    const fx = await getJSON(`fixtures/${name}.json`);
    const rec = { name, generated_at: index.generated_at, feature_set: index.feature_set, method: meta.method, path: meta.path };
    if (fx.status !== 200) {
      failed("The recorded check did not run", (fx.body && fx.body.detail) || `The server answered ${fx.status}.`);
      result.prepend(recordedNote(rec));
      return;
    }
    await render(fx.body, { recorded: rec });
  } catch (err) {
    failed("The recorded result could not be loaded", String(err.message || err));
  }
}

const fixture = params().get("fixture");
if (fixture && LOCAL_HOSTS.has(location.hostname)) loadFixture(fixture);
