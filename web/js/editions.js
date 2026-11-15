import { getJSON, el, fmt, LANG, params } from "./common.js";

const form = document.getElementById("finder");
const input = document.getElementById("q");
const listbox = document.getElementById("q-options");
const qStatus = document.getElementById("q-status");
const bookEl = document.getElementById("book");
const result = document.getElementById("result");
const statusEl = document.getElementById("result-status");
const noMatch = document.getElementById("q-none");
const emptyState = document.getElementById("state-empty");

const MAX_OPTIONS = 8;
const RELATED_K = 10;
// Page language for screen readers and font fallback, used only when a title is written in a non-Latin script.
const BCP47 = { eng: "en", hin: "hi", san: "sa", ben: "bn", guj: "gu", tel: "te", kan: "kn", tam: "ta" };
const NON_LATIN = /(?!\p{Script=Latin})\p{L}/u;
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);
const fixtureMode = () => LOCAL_HOSTS.has(location.hostname) && params().has("fixture");

const announce = (msg) => { statusEl.textContent = msg; };
// LANG names the study's main languages; any other code is shown as a code, not passed off as a name.
const langName = (tag) => (tag ? LANG[tag] || `language code ${tag}` : null);

// ---------- the book picker: a combobox over web/data/corpus.json

// Accents are dropped from Latin letters only ("Candrarēkhā" finds "candrarekha"); in Indian scripts the
// vowel signs and virama are combining marks that change the word, so they are kept.
const fold = (s) => String(s ?? "").normalize("NFKD").replace(/(\p{Script=Latin})\p{M}+/gu, "$1")
  .normalize("NFC").toLocaleLowerCase("en");
let books = null;            // [{doc, hay}] once corpus.json has loaded
let booksLoading = null;
let options = [];            // the docs currently offered
let active = -1;

function loadBooks() {
  if (!booksLoading) {
    booksLoading = getJSON("data/corpus.json").then((c) => {
      books = (c.docs || []).map((d) => ({ doc: d, title: fold(d.title), words: fold(d.title).split(/[\s\p{P}]+/u),
        hay: fold(`${d.title || ""} ${d.creator || ""} ${d.identifier || ""}`) }));
      return books;
    }).catch(() => {
      qStatus.textContent = "The list of book titles did not load, so search is unavailable.";
      document.getElementById("q-hint").textContent = "The list of book titles did not load. A link with a book's identifier still works.";
      books = [];
      return books;
    });
  }
  return booksLoading;
}

function closeOptions() {
  listbox.hidden = true;
  input.setAttribute("aria-expanded", "false");
  input.removeAttribute("aria-activedescendant");
  active = -1;
}

function setActive(i) {
  const items = listbox.querySelectorAll('[role="option"]');
  items.forEach((it, n) => it.setAttribute("aria-selected", n === i ? "true" : "false"));
  active = i;
  if (i >= 0 && items[i]) {
    input.setAttribute("aria-activedescendant", items[i].id);
    items[i].scrollIntoView({ block: "nearest" });
  } else input.removeAttribute("aria-activedescendant");
}

function optionMeta(d) {
  const bits = [langName(d.lang_tag), d.year ? String(Math.round(d.year)) : null, d.creator].filter(Boolean);
  return bits.length ? el("span", { class: "opt-meta small muted", dir: "auto", text: bits.join(", ") }) : null;
}

async function search() {
  noMatch.hidden = true;
  const terms = fold(input.value).split(/\s+/).filter(Boolean);
  if (!terms.length) { closeOptions(); qStatus.textContent = ""; return; }
  await loadBooks();
  if (fold(input.value).split(/\s+/).filter(Boolean).join(" ") !== terms.join(" ")) return;   // typed on meanwhile
  // Titles that start with the query first, then titles that contain it, then matches on author or identifier only.
  // Exact title, then title starting with the query, then a title word starting with each term, then titles
  // containing it, then matches on author or identifier only.
  const q = terms.join(" ");
  const rank = (b) => (b.title === q ? 0 : b.title.startsWith(q) ? 1
    : terms.every((t) => b.words.some((w) => w.startsWith(t))) ? 2 : terms.every((t) => b.title.includes(t)) ? 3 : 4);
  options = books.filter((b) => terms.every((t) => b.hay.includes(t)))
    .map((b) => [rank(b), b]).sort((x, y) => x[0] - y[0]).slice(0, MAX_OPTIONS).map(([, b]) => b.doc);
  if (!options.length) {
    listbox.replaceChildren();
    closeOptions();
    qStatus.textContent = "No book in the study matches that.";
    noMatch.hidden = false;
    return;
  }
  listbox.replaceChildren(...options.map((d, i) => el("li", {
    id: `q-opt-${i}`, role: "option", class: "opt", "aria-selected": "false",
    onpointerdown: (e) => e.preventDefault(),        // keep focus in the input
    onclick: () => choose(d),
  }, titleNode(d, "span", { class: "opt-title" }), optionMeta(d))));
  listbox.hidden = false;
  input.setAttribute("aria-expanded", "true");
  setActive(-1);
  qStatus.textContent = options.length === 1 ? "One matching book. Use the down arrow to reach it." : `${options.length} matching books shown. Use the arrow keys to move through them.`;
}

input.addEventListener("focus", loadBooks, { once: true });
input.addEventListener("input", search);
input.addEventListener("keydown", (e) => {
  const open = !listbox.hidden && options.length > 0;
  if (e.key === "ArrowDown") {
    e.preventDefault();
    if (listbox.hidden) { search(); return; }
    if (open) setActive((active + 1) % options.length);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (open) setActive(active <= 0 ? options.length - 1 : active - 1);
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (open) choose(options[active >= 0 ? active : 0]);
  } else if (e.key === "Escape") {
    if (!listbox.hidden) { e.preventDefault(); closeOptions(); }
  }
});
input.addEventListener("blur", () => setTimeout(closeOptions, 0));
form.addEventListener("submit", (e) => e.preventDefault());

function choose(d) {
  if (!d) return;
  input.value = d.title || d.identifier;
  closeOptions();
  qStatus.textContent = "";
  pushBook(d.identifier);
  show(d.identifier, { focus: true });
}

// ---------- small builders

/** A title, tagged with its language when it is written in a non-Latin script. */
function titleNode(b, tag = "span", extra = {}) {
  const title = b.title || b.identifier || "Untitled";
  const attrs = { ...extra, dir: "auto", text: title };
  if (NON_LATIN.test(title) && BCP47[b.lang_tag]) attrs.lang = BCP47[b.lang_tag];
  return el(tag, attrs);
}

function bookLink(b) {
  return b.url ? titleNode(b, "a", { href: b.url }) : titleNode(b, "span");
}

function distanceTag(x) {
  return el("span", { class: "num" }, el("span", { class: "dist-word", text: "distance " }), x == null ? "n/a" : fmt.f(x, 3));
}

function field(label, ...value) {
  return el("div", {}, el("dt", { text: label }), el("dd", {}, ...value));
}

function recordedNote(rec) {
  const when = rec.generated_at ? new Date(rec.generated_at) : null;
  const shown = when && !Number.isNaN(when.getTime())
    ? when.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC"
    : rec.generated_at || "an unrecorded date";
  return el("p", { class: "recorded" },
    el("strong", { text: "Recorded result" }),
    el("span", {}, "Replayed from real API responses in ", el("code", { text: "fixtures/" }), " recorded on ",
      el("time", { datetime: rec.generated_at || null, text: shown }),
      rec.feature_set ? ` with feature set ${rec.feature_set}.` : "."));
}

function stateBox(title, msg, { error = false, headingId = null } = {}) {
  return el("div", { class: error ? "state state--error" : "state" },
    el("h2", { id: headingId, tabindex: headingId ? "-1" : null, text: title }),
    msg ? el("p", { class: "ink-2", text: msg }) : null);
}

function bookList(list, { marker = false } = {}) {
  return el("ol", { class: "hits" }, list.map((b) => {
    const lang = langName(b.lang_tag);
    const meta = [lang, b.script && b.script !== lang ? `${b.script} script` : null].filter(Boolean);
    return el("li", {},
      el("div", { class: "hit-text" },
        el("span", { class: "book" }, bookLink(b)),
        meta.length ? el("span", { class: "small muted", text: meta.join(", ") }) : null,
        marker && b.same_title_author ? el("span", { class: "same", text: "same title and author" }) : null),
      distanceTag(b.distance));
  }));
}

// ---------- the three parts of the answer

function bookSlip(doc, rec) {
  const rows = [];
  if (doc.creator) rows.push(field("Author", el("span", { dir: "auto", text: doc.creator })));
  rows.push(field("Language", langName(doc.lang_tag) || "not recorded"));
  if (doc.script) rows.push(field("Script", doc.script));
  rows.push(field("Year", doc.year ? String(Math.round(doc.year)) : "undated"));
  rows.push(field("Identifier", el("code", { text: doc.identifier })));
  return el("article", { class: "slip", "aria-labelledby": "book-title" },
    rec ? recordedNote(rec) : null,
    el("span", { class: "label", text: "The book" }),
    titleNode(doc, "h2", { id: "book-title", tabindex: "-1", class: "slip-title" }),
    el("dl", { class: "sheet" }, rows),
    doc.url ? el("p", {}, el("a", { href: doc.url, class: "archive-link" }, "Open this book in the archive")) : null);
}

function editionsBlock(ed) {
  const head = el("h2", { id: "ed-head", text: "Possible editions" });
  if (ed.missing) return el("section", { "aria-labelledby": "ed-head" }, head, el("p", { class: "ink-2 mt-md", text: ed.missing }));
  if (ed.error) return el("section", { "aria-labelledby": "ed-head" }, head, el("p", { class: "note note--error mt-md", text: ed.error }));
  const r = ed.body;
  if (r.threshold == null) {
    return el("section", { "aria-labelledby": "ed-head" }, head,
      el("p", { class: "ink-2 mt-md", text: "The edition finder is not calibrated in the current model yet, so no editions are listed. The related books below still come from the model." }),
      r.method ? el("p", { class: "small muted mt-xs", text: r.method }) : null);
  }
  const list = (r.candidates || []).filter(Boolean);
  const same = list.filter((b) => b.same_title_author).length;
  return el("section", { "aria-labelledby": "ed-head" }, head,
    el("p", { class: "ink-2 mt-xs" },
      "Books closer than ", el("strong", { class: "thr", text: fmt.f(r.threshold, 3) }),
      " were matched as other editions on the books we could check. Below are the closest books within that distance, nearest first, as many as the finder returns. A smaller distance means more alike text."),
    r.method ? el("p", { class: "small muted mt-xs", text: r.method }) : null,
    list.length
      ? el("div", { class: "mt-md" },
          same ? el("p", { class: "small ink-2", text: same === 1 ? "One of these has the same title and author in the catalogue." : `${same} of these have the same title and author in the catalogue.` })
            : el("p", { class: "small ink-2", text: "None of these has the same title and author in the catalogue: they may be editions under another spelling, or simply close in subject." }),
          bookList(list, { marker: true }))
      : el("p", { class: "ink-2 mt-md", text: "No other edition found within the threshold." }));
}

function relatedBlock(rel, script) {
  const head = el("h2", { id: "rel-head", text: "In other scripts" });
  const lead = el("p", { class: "ink-2 mt-xs", text: `The nearest books written in a script other than ${script || "this book's"}: possibly translations, or books on the same subject.` });
  if (rel.missing) return el("section", { "aria-labelledby": "rel-head" }, head, el("p", { class: "ink-2 mt-md", text: rel.missing }));
  if (rel.error) return el("section", { "aria-labelledby": "rel-head" }, head, el("p", { class: "note note--error mt-md", text: rel.error }));
  const list = (rel.body.neighbours || []).filter(Boolean);
  return el("section", { "aria-labelledby": "rel-head" }, head, lead,
    list.length ? el("div", { class: "mt-md" }, bookList(list)) : el("p", { class: "ink-2 mt-md", text: "The model returned no book in another script." }));
}

// ---------- loading one book

let current = 0;

function loading() {
  bookEl.replaceChildren(el("div", { class: "slip", "aria-hidden": "true" }, el("div", { class: "skeleton skeleton--block" })));
  result.setAttribute("aria-busy", "true");
  result.replaceChildren(el("div", { class: "state" },
    el("h2", { text: "Looking the book up" }),
    el("p", { class: "ink-2", text: "Comparing it with every book in the study." }),
    el("div", { class: "skeleton skeleton--block mt-lg" })));
  announce("Looking the book up.");
}

/** GET a JSON endpoint; resolves to {status, body} and never throws for an HTTP error. */
async function live(path) {
  try {
    const r = await fetch(path, { headers: { Accept: "application/json" } });
    const body = await r.json().catch(() => ({}));
    return { status: r.status, body };
  } catch (err) {
    return { status: 0, body: { detail: "The server could not be reached." } };
  }
}

async function recorded(id) {
  const index = await getJSON("fixtures/_index.json");
  const fx = index.fixtures || {};
  const one = async (kind) => {
    const name = `get_${kind}__${id}`;
    if (!fx[name]) return null;
    return getJSON(`fixtures/${name}.json`);
  };
  const [doc, ed, rel] = await Promise.all([one("documents"), one("editions"), one("related")]);
  return { doc, ed, rel, rec: { generated_at: index.generated_at, feature_set: index.feature_set } };
}

function part(res, what) {
  if (!res) return { missing: `There is no recorded ${what} response for this book.` };
  if (res.status === 200) return { body: res.body };
  const detail = res.body && res.body.detail;
  return { error: `The ${what} lookup did not run. ${sentence(typeof detail === "string" ? detail : `The server answered ${res.status || "nothing"}`)}` };
}

async function show(id, { focus = false } = {}) {
  const ticket = ++current;
  loading();
  let doc, ed, rel, rec = null;
  try {
    if (fixtureMode()) {
      if (!/^[\w.-]+$/.test(id)) throw new Error(`"${id}" is not a recorded book identifier.`);
      ({ doc, ed, rel, rec } = await recorded(id));
      if (!doc) throw new Error(`No recorded response for "${id}" in fixtures/_index.json.`);
    } else {
      const enc = encodeURIComponent(id);
      [doc, ed, rel] = await Promise.all([live(`/api/documents/${enc}`), live(`/api/editions/${enc}`),
        live(`/api/related/${enc}?k=${RELATED_K}`)]);
    }
  } catch (err) {
    if (ticket !== current) return;
    bookEl.replaceChildren();
    failed("The book could not be looked up", String(err.message || err), focus);
    return;
  }
  if (ticket !== current) return;

  if (doc.status === 404) {
    bookEl.replaceChildren();
    failed("Not in the study", `No book with the identifier "${id}" is in the study sample. Check the identifier, or search for a book by title.`, focus);
    return;
  }
  if (doc.status !== 200) {
    bookEl.replaceChildren();
    const d = doc.body && doc.body.detail;
    failed("The book could not be looked up", typeof d === "string" ? d : `The server answered ${doc.status || "nothing"}.`, focus);
    return;
  }

  const book = doc.body;
  bookEl.replaceChildren(bookSlip(book, rec));
  if (!input.value) input.value = book.title || book.identifier;
  const edPart = part(ed, "edition"), relPart = part(rel, "related books");
  result.replaceChildren(editionsBlock(edPart), relatedBlock(relPart, book.script));
  result.removeAttribute("aria-busy");
  const n = edPart.body && edPart.body.threshold != null ? (edPart.body.candidates || []).length : null;
  const edSaid = edPart.error ? "the edition lookup could not load"
    : edPart.missing ? "no recorded edition response"
    : n == null ? "edition finder not calibrated" : n === 0 ? "no other edition found" : n === 1 ? "one possible edition" : `${n} possible editions`;
  announce(`${String(book.title || book.identifier).replace(/[.\s]+$/, "")}: ${edSaid}${relPart.error ? "; the related books could not load" : ""}.`);
  if (focus) document.getElementById("book-title").focus();
}

/** A server message as a sentence: capital first letter, one full stop at the end. */
function sentence(t) {
  const x = String(t).trim();
  return x ? x[0].toUpperCase() + x.slice(1) + (/[.!?]$/.test(x) ? "" : ".") : "";
}

function failed(title, msg, focus) {
  result.removeAttribute("aria-busy");
  result.replaceChildren(stateBox(title, msg, { error: true, headingId: "fail-title" }));
  announce(title);
  if (focus) document.getElementById("fail-title").focus();
}

// ---------- start: ?id=<identifier>, or on localhost ?fixture=<identifier> to replay recorded responses

const urlBook = () => ((fixtureMode() ? params().get("fixture") : params().get("id")) || "").trim();

/** A pick is a new history entry, so Back returns to the previous book. */
function pushBook(id) {
  const p = params();
  p.set(fixtureMode() ? "fixture" : "id", id);
  history.pushState({ book: id }, "", `${location.pathname}?${p}${location.hash}`);
}

function reset() {
  current++;
  bookEl.replaceChildren();
  result.removeAttribute("aria-busy");
  result.replaceChildren(emptyState);
  input.value = "";
  announce("No book chosen.");
}

window.addEventListener("popstate", () => {
  closeOptions();
  const id = urlBook();
  if (!id) { reset(); return; }
  input.value = "";
  show(id);
});

const start = urlBook();
if (start) show(start);
