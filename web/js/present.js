// Presenter mode: the site's story as full-screen slides. Every figure comes from data/facts.json
// (scripts/deliverable_facts.py) or a recorded response in fixtures/; the copy in present.html has no numbers.
import { getJSON, el, fmt, hbar, headlineResults, resultFigure } from "./common.js";

const deck = document.getElementById("deck");
const bar = deck.querySelector(".deck-bar");
const countEl = document.getElementById("deck-count");
const prevBtn = document.getElementById("deck-prev");
const nextBtn = document.getElementById("deck-next");
const fullBtn = document.getElementById("deck-full");
const leaveLink = document.getElementById("deck-leave");
const fill = (name) => deck.querySelector(`[data-fill="${name}"]`);

document.documentElement.classList.add("deck-on");
bar.hidden = false;
document.getElementById("deck-help").textContent =
  "Arrow keys, Page Up and Page Down or the space bar move between slides. F goes full screen; Escape leaves.";

// Leave for the page the presenter came from when it is on this site, else the study.
try {
  const ref = document.referrer ? new URL(document.referrer) : null;
  if (ref && ref.origin === location.origin && !ref.pathname.endsWith("/present.html")) leaveLink.href = ref.href;
} catch { /* keep study.html */ }

// ---------- slides

const slides = () => [...deck.querySelectorAll(".slide")];
let at = 0;
let mapLoaded = false;
const startId = location.hash.slice(1);   // read before go() rewrites the hash; slides built later may be the target

function go(n, { focus = true } = {}) {
  const list = slides();
  at = Math.max(0, Math.min(list.length - 1, n));
  list.forEach((s, k) => {
    s.hidden = k !== at;
    s.classList.toggle("is-current", k === at);
    s.setAttribute("aria-roledescription", "slide");
  });
  const cur = list[at];
  countEl.textContent = `${fmt.n(at + 1)} / ${fmt.n(list.length)}`;
  prevBtn.disabled = at === 0;
  nextBtn.disabled = at === list.length - 1;
  history.replaceState(null, "", `#${cur.id}`);
  if (cur.id === "s-map") loadMap();
  const head = cur.querySelector("h1, h2");
  if (focus && head) head.focus({ preventScroll: true });
  cur.scrollTop = 0;
}

function leave() { location.href = leaveLink.href; }

function toggleFull() {
  if (!document.fullscreenEnabled) return;
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen().catch(() => {});
}
if (!document.fullscreenEnabled) fullBtn.hidden = true;
document.addEventListener("fullscreenchange", () => {
  fullBtn.textContent = document.fullscreenElement ? "Leave full screen" : "Full screen";
});

prevBtn.addEventListener("click", () => go(at - 1));
nextBtn.addEventListener("click", () => go(at + 1));
fullBtn.addEventListener("click", toggleFull);

document.addEventListener("keydown", (e) => {
  if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
  const t = e.target;
  const control = t && t.closest && t.closest("a, button, input, select, textarea, summary, [contenteditable]");
  switch (e.key) {
    case "ArrowRight": case "ArrowDown": case "PageDown": go(at + 1); break;
    case "ArrowLeft": case "ArrowUp": case "PageUp": go(at - 1); break;
    case " ": if (control) return; go(e.shiftKey ? at - 1 : at + 1); break;
    case "Home": go(0); break;
    case "End": go(slides().length - 1); break;
    case "Escape": leave(); break;
    case "f": case "F": if (control && t.matches("input, textarea, [contenteditable]")) return; toggleFull(); break;
    default: return;
  }
  e.preventDefault();
});

// Show one slide at once, before the data loads, so the static slides never stack up while it does.
go(Math.max(0, slides().findIndex((s) => s.id === startId)), { focus: false });

/** A slide built here, inserted after another. */
function addSlide(after, id, title, ...body) {
  const s = el("section", { class: "slide", id, "aria-labelledby": `${id}-h` },
    el("div", { class: "slide-body" }, el("h2", { id: `${id}-h`, tabindex: "-1", text: title }), ...body));
  after.after(s);
  return s;
}

// ---------- the archive map (galaxy.html, built separately; a link until it exists)

async function loadMap() {
  if (mapLoaded) return;
  mapLoaded = true;
  const slot = fill("map");
  let ok = false;
  try { ok = (await fetch("galaxy.html", { method: "HEAD", cache: "no-store" })).ok; } catch { ok = false; }
  if (!ok) {
    slot.replaceChildren(el("p", { class: "ink-2", text: "The archive map is not on this server yet." }),
      el("p", { class: "mt-md" }, el("a", { class: "btn", href: "galaxy.html", text: "Try the archive map" })));
    return;
  }
  const frame = el("iframe", { class: "map-frame", src: "galaxy.html", title: "The archive map", loading: "eager" });
  // The map keeps its arrow keys; a clicker's Page Up / Page Down and Escape still drive the slides
  // (same origin; the map's own handlers run first and may claim a key).
  frame.addEventListener("load", () => {
    try {
      frame.contentWindow.addEventListener("keydown", (e) => {
        if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
        const act = { PageDown: () => go(at + 1), PageUp: () => go(at - 1), Escape: leave }[e.key];
        if (!act) return;
        e.preventDefault();
        act();
      });
    } catch { /* another origin: the slide's hint covers it */ }
  });
  slot.replaceChildren(
    frame,
    el("p", { class: "small muted mt-sm" }, "While you use the map it takes the arrow keys; Page Up, Page Down and Escape still move the slides. Or ",
      el("a", { href: "galaxy.html", text: "open it on its own page" }), "."));
}

// ---------- results

let facts = null;
try { facts = await getJSON("data/facts.json"); } catch { facts = null; }
const results = facts ? headlineResults(facts) : [];

if (facts && facts.corpus) {
  const c = facts.corpus;
  fill("problem-lead").textContent = `The study drew ${fmt.n(c.harvested)} scanned books in ${fmt.n(c.languages)} languages from the Digital Library of India, an archive whose catalogue rarely says what a book is about.`;
  const figs = fill("problem-figures");
  figs.replaceChildren(...[[c.harvested, "books drawn from the archive"], [c.usable, "readable enough to group"], [c.ocr_pages, "pages read by our own OCR"]]
    .filter(([v]) => v != null)
    .map(([v, label]) => el("div", {}, el("span", { class: "figure", text: fmt.n(v) }), el("span", { class: "small muted", text: label }))));
  figs.hidden = false;
}

/** One result on a slide of its own: words left, bars right; the slide's heading replaces the figure's. */
function slideFigure(r) {
  const fig = resultFigure(r, { headingLevel: "h3", variant: "slide" });
  fig.querySelector(".rf-head h3").classList.add("visually-hidden");
  return fig;
}

const core = results.filter((r) => ["subject", "page", "stability"].includes(r.id));
if (core.length) {
  const judged = core.filter((r) => r.met != null), met = judged.filter((r) => r.met);
  const name = facts.encoder && facts.encoder.name;
  fill("found-lead").textContent = judged.length
    ? `${fmt.n(met.length)} of ${fmt.n(judged.length)} targets met${name ? `, for the model behind the app (${name})` : ""}. Each target was fixed before any result was seen.`
    : "None of the targets has been judged yet.";
  const main = (r) => r.rows.find((x) => x.main) || r.rows[0];
  fill("found-table").replaceChildren(el("div", { class: "table-wrap" }, el("table", { class: "found" },
    el("thead", {}, el("tr", {}, el("th", { scope: "col", text: "What was measured" }), el("th", { scope: "col", class: "num", text: "Result" }),
      el("th", { scope: "col", class: "num", text: "Compared with" }), el("th", { scope: "col", class: "num", text: "Aim" }), el("th", { scope: "col", text: "Target" }))),
    el("tbody", {}, core.map((r) => {
      const base = r.rows.filter((x) => !x.main && x.x != null);
      return el("tr", {},
        el("th", { scope: "row", text: r.title }),
        el("td", { class: "num lit", text: r.show(main(r).x) }),
        el("td", { class: "num", text: base.length ? base.map((x) => r.show(x.x)).join(" and ") : "chance scores zero" }),
        el("td", { class: "num", text: r.aim ? r.show(r.aim.x) : "none" }),
        el("td", { class: r.met == null ? "muted" : r.met ? "met" : "miss", text: r.met == null ? "not judged" : r.met ? "met" : "not met" }));
    })))));
  let after = document.getElementById("s-found");
  for (const r of core) {
    after = addSlide(after, `s-${r.id}`, r.title, slideFigure(r));
  }
  // the other features, one per slide, so each fits a projector screen
  for (const r of results.filter((x) => x.id === "suggest" || x.id === "related")) {
    after = addSlide(after, `s-${r.id}`, r.title, slideFigure(r));
  }
} else {
  fill("found-lead").textContent = "The results file could not be loaded, so the figures are on the study page.";
}
for (const [id, slot] of [["triage", "triage"], ["editions", "editions"]]) {
  const r = results.find((x) => x.id === id);
  // the slide's own sentence explains the feature, so the figure drops its paragraph
  fill(slot).replaceChildren(r ? el("div", { class: "mt-lg" }, resultFigure(r, { variant: "brief" }))
    : el("p", { class: "small muted mt-lg", text: "Not evaluated in this copy of the results yet; the evaluation appears here after the next pipeline run." }));
}

// ---------- the catalogue card: a recorded POST /api/check response, drawn as check.html draws it

const LEVEL = {
  strong: "sits well inside", good: "inside", weak: "at the edge", outside: "outside every group",
};

function recordedNote(rec) {
  const when = rec.generated_at ? new Date(rec.generated_at) : null;
  const shown = when && !Number.isNaN(when.getTime())
    ? when.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC"
    : rec.generated_at || "an unrecorded date";
  return el("p", { class: "recorded" },
    el("strong", { text: "Recorded result" }),
    el("span", {}, "Replayed from ", el("code", { text: rec.name }),
      `, a real ${rec.method} ${rec.path} response recorded on `,
      el("time", { datetime: rec.generated_at || null, text: shown }),
      rec.feature_set ? ` with feature set ${rec.feature_set}.` : "."));
}

function field(label, value) { return el("div", {}, el("dt", { text: label }), el("dd", { dir: "auto", text: value })); }

function card(r) {
  const list = (r.suggested_classes || []).filter((s) => s && s.class);
  const h = r.hierarchical, d = r.dbscan;
  const rows = [];
  if (r.script) rows.push(field("Script", r.script));
  if (r.tokens != null) rows.push(field("Readable words", fmt.n(r.tokens)));
  if (r.input) rows.push(field("Read from", r.input === "scan" ? "a scan" : "pasted text"));
  if (h && h.name) rows.push(field("Topic group", `${h.name}${LEVEL[h.level] ? `, ${LEVEL[h.level]}` : ""}`));
  if (d) rows.push(field("Dense group", d.in_dense_group ? (d.name || "a dense group with no name") : "none, the page is noise to density-based clustering"));
  if (r.feature_name) rows.push(field("Compared by", r.feature_name));
  const cautions = (r.cautions || []).filter(Boolean);
  const suggested = list.length
    ? el("div", {},
      el("span", { class: "label", id: "p-sugg", text: "Suggested class" }),
      el("span", { class: "figure mt-xs", dir: "auto", text: list[0].class }),
      el("ol", { class: "classes mt-md", "aria-labelledby": "p-sugg" }, list.map((s) => {
        const b = hbar(Number(s.score) || 0);
        b.setAttribute("aria-hidden", "true"); b.removeAttribute("role"); b.removeAttribute("aria-label");
        return el("li", {}, el("span", { class: "name", dir: "auto", text: s.class }), b,
          el("span", { class: "pct", text: s.score == null ? "n/a" : fmt.p(s.score) }));
      })))
    : el("div", {}, el("span", { class: "label", text: "Suggested class" }),
      el("p", { class: "ink-2 mt-xs", text: "No class to suggest for this page." }));
  return el("article", { class: "card present-card", "aria-label": "Catalogue card" },
    rows.length ? el("dl", { class: "sheet present-card-sheet" }, rows) : null,
    el("div", { class: "present-card-side" },
      suggested,
      el("div", { class: "quality" }, el("h3", { text: "Scan quality" }),
        cautions.length ? el("ul", { class: "cautions" }, cautions.map((c) => el("li", { class: "note", text: c })))
          : el("p", { class: "ink-2", text: "No cautions: the text was long and clear enough to compare with confidence." }),
        el("p", { class: "small muted", text: r.ocr_conf != null ? `OCR confidence ${fmt.f(r.ocr_conf, 0)}.`
          : r.input === "text" ? "Pasted as text, so there is no OCR confidence." : "No OCR confidence was reported." }))));
}

try {
  const index = await getJSON("fixtures/_index.json");
  const entry = Object.entries(index.fixtures || {}).find(([, m]) => m.path === "/api/check" && m.status === 200);
  if (!entry) throw new Error("no recorded check");
  const [name, meta] = entry;
  const fx = await getJSON(`fixtures/${name}.json`);
  if (fx.status !== 200 || !fx.body || fx.body.status === "abstain") throw new Error("the recorded check has no card");
  fill("card").replaceChildren(
    recordedNote({ name, generated_at: index.generated_at, feature_set: index.feature_set, method: meta.method, path: meta.path }),
    el("div", { class: "mt-lg" }, card(fx.body)));
} catch {
  fill("card").replaceChildren(el("p", { class: "ink-2", text: "No recorded check is on this server, so the card is shown live instead." }),
    el("p", { class: "mt-md" }, el("a", { class: "btn", href: "check.html", text: "Check a page" })));
}

// ---------- start where the address says

const start = Math.max(0, slides().findIndex((s) => s.id === startId));
go(start, { focus: false });
