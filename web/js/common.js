// Shared helpers: data loading, formatting and inline-SVG charts (colours come from CSS classes).
document.documentElement.classList.add("js");

const cache = {};
export async function getJSON(url) {
  if (!cache[url]) {
    cache[url] = fetch(url).then((r) => {
      if (!r.ok) throw new Error(`${url}: ${r.status}`);
      return r.json();
    });
  }
  return cache[url];
}

export const LANG = { eng: "English", hin: "Hindi", san: "Sanskrit", ben: "Bengali", guj: "Gujarati", tel: "Telugu", kan: "Kannada", tam: "Tamil" };
export const fmt = {
  n: (x) => (x == null ? "n/a" : Number(x).toLocaleString("en-IN")),
  p: (x, d = 0) => (x == null ? "n/a" : `${(100 * x).toFixed(d)}%`),
  f: (x, d = 2) => (x == null ? "n/a" : Number(x).toFixed(d)),
};

export function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return e;
}

const SVGNS = "http://www.w3.org/2000/svg";
function s(tag, attrs = {}, text) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}

function scale(d0, d1, r0, r1) {
  const span = d1 - d0 || 1;
  return (v) => r0 + ((v - d0) / span) * (r1 - r0);
}

function niceTicks(lo, hi, n = 4) {
  const step = Math.pow(10, Math.floor(Math.log10((hi - lo) / n || 1)));
  const err = (hi - lo) / n / step;
  const m = err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1;
  const st = m * step, out = [];
  for (let v = Math.ceil(lo / st) * st; v <= hi + 1e-9; v += st) out.push(+v.toFixed(10));
  return out;
}

// ---- tooltip (hover; focus shows at once)
let tipEl;
export function tip(evt, html) {
  if (!tipEl) { tipEl = el("div", { class: "tip", role: "status" }); document.body.append(tipEl); }
  if (html == null) { tipEl.hidden = true; return; }
  tipEl.hidden = false;
  tipEl.innerHTML = html;
  const x = Math.min(evt.clientX + 14, window.innerWidth - 300);
  tipEl.style.transform = `translate(${x}px, ${evt.clientY + 14}px)`;
  tipEl.style.left = "0"; tipEl.style.top = "0";
}
export const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

/**
 * Scatter of the PCA map.
 * points: [{x, y, hi: bool, noise: bool, label: html}], you: {x, y} | null
 */
export function scatter(target, points, { you = null, width = 640, height = 440, ariaLabel = "PCA map", xLabel = "PC1", yLabel = "PC2", onPick } = {}) {
  const pad = { l: 40, r: 16, t: 12, b: 36 };
  const xs = points.map((p) => p.x).concat(you ? [you.x] : []);
  const ys = points.map((p) => p.y).concat(you ? [you.y] : []);
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)], [y0, y1] = [Math.min(...ys), Math.max(...ys)];
  const mx = (x1 - x0) * 0.04, my = (y1 - y0) * 0.04;
  const X = scale(x0 - mx, x1 + mx, pad.l, width - pad.r), Y = scale(y0 - my, y1 + my, height - pad.b, pad.t);
  const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart", role: "img", "aria-label": ariaLabel });
  for (const t of niceTicks(y0 - my, y1 + my)) { svg.append(s("line", { x1: pad.l, x2: width - pad.r, y1: Y(t), y2: Y(t), class: "grid" })); svg.append(s("text", { x: pad.l - 6, y: Y(t) + 4, "text-anchor": "end" }, fmt.f(t, 1))); }
  for (const t of niceTicks(x0 - mx, x1 + mx)) svg.append(s("text", { x: X(t), y: height - pad.b + 16, "text-anchor": "middle" }, fmt.f(t, 1)));
  svg.append(s("text", { x: width - pad.r, y: height - 4, "text-anchor": "end" }, xLabel));
  svg.append(s("text", { x: pad.l, y: pad.t - 2 + 10, "text-anchor": "start", transform: `rotate(-90 ${pad.l - 30} ${pad.t + 40})` }, yLabel));
  const order = [...points].sort((a, b) => (a.hi === b.hi ? 0 : a.hi ? 1 : -1));
  const g = s("g");
  for (const p of order) {
    const c = s("circle", { cx: X(p.x), cy: Y(p.y), r: p.hi ? 4 : 3, class: p.hi ? "pt-hi" : p.noise ? "pt-noise" : "pt" });
    if (p.label) {
      c.addEventListener("pointerenter", (e) => tip(e, p.label));
      c.addEventListener("pointermove", (e) => tip(e, p.label));
      c.addEventListener("pointerleave", () => tip(null));
      if (onPick) c.addEventListener("click", () => onPick(p));
    }
    g.append(c);
  }
  svg.append(g);
  if (you) {
    svg.append(s("circle", { cx: X(you.x), cy: Y(you.y), r: 14, class: "you-ring" }));
    svg.append(s("circle", { cx: X(you.x), cy: Y(you.y), r: 6, class: "you" }));
    svg.append(s("text", { x: X(you.x) + 18, y: Y(you.y) + 4, class: "lbl" }, you.label || "your page"));
  }
  target.replaceChildren(svg);
  return svg;
}

/**
 * Lines on one y-axis. series: [{name, points: [[x, y]], cls: "ser" | "ser-2" | "ser-3" | "ctx"}]
 */
export function lines(target, series, { width = 640, height = 300, xLabel = "", yLabel = "", ariaLabel = "chart", marks = [], yZero = false, hline = null } = {}) {
  const pad = { l: 48, r: 96, t: 12, b: 40 };
  const all = series.flatMap((s_) => s_.points);
  const xs = all.map((p) => p[0]), ys = all.map((p) => p[1]).filter((v) => v != null);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (yZero) y0 = Math.min(0, y0);
  if (hline != null) { y0 = Math.min(y0, hline); y1 = Math.max(y1, hline); }
  const my = (y1 - y0) * 0.08 || 0.1;
  const X = scale(Math.min(...xs), Math.max(...xs), pad.l, width - pad.r), Y = scale(y0 - (yZero ? 0 : my), y1 + my, height - pad.b, pad.t);
  const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart", role: "img", "aria-label": ariaLabel });
  for (const t of niceTicks(y0 - (yZero ? 0 : my), y1 + my)) { svg.append(s("line", { x1: pad.l, x2: width - pad.r, y1: Y(t), y2: Y(t), class: "grid" })); svg.append(s("text", { x: pad.l - 6, y: Y(t) + 4, "text-anchor": "end" }, Math.abs(t) < 10 ? fmt.f(t, Math.abs(t) < 1 ? 2 : 1) : t)); }
  for (const t of niceTicks(Math.min(...xs), Math.max(...xs), 6)) svg.append(s("text", { x: X(t), y: height - pad.b + 16, "text-anchor": "middle" }, t));
  svg.append(s("text", { x: (pad.l + width - pad.r) / 2, y: height - 4, "text-anchor": "middle" }, xLabel));
  svg.append(s("text", { x: 4, y: pad.t + 2, "text-anchor": "start" }, yLabel));
  if (hline != null) svg.append(s("line", { x1: pad.l, x2: width - pad.r, y1: Y(hline), y2: Y(hline), class: "cut" }));
  for (const se of series) {
    const pts = se.points.filter((p) => p[1] != null);
    if (!pts.length) continue;
    svg.append(s("path", { d: pts.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(""), class: se.cls || "ctx" }));
    const last = pts[pts.length - 1];
    svg.append(s("text", { x: X(last[0]) + 6, y: Y(last[1]) + 4, class: "lbl" }, se.name));
  }
  for (const m of marks) {
    svg.append(s("circle", { cx: X(m.x), cy: Y(m.y), r: 5, class: "you" }));
    if (m.label) svg.append(s("text", { x: X(m.x) + 8, y: Y(m.y) - 8, class: "lbl" }, m.label));
  }
  target.replaceChildren(svg);
}

/** Dendrogram from scipy's icoord/dcoord (truncated), with the cut height. */
export function dendrogram(target, d, { width = 900, height = 300, cut = null, ariaLabel = "dendrogram" } = {}) {
  const pad = { l: 48, r: 12, t: 12, b: 48 };
  const xs = d.icoord.flat(), ys = d.dcoord.flat();
  const X = scale(Math.min(...xs) - 5, Math.max(...xs) + 5, pad.l, width - pad.r), Y = scale(0, Math.max(...ys) * 1.05, height - pad.b, pad.t);
  const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart", role: "img", "aria-label": ariaLabel });
  for (const t of niceTicks(0, Math.max(...ys) * 1.05)) { svg.append(s("line", { x1: pad.l, x2: width - pad.r, y1: Y(t), y2: Y(t), class: "grid" })); svg.append(s("text", { x: pad.l - 6, y: Y(t) + 4, "text-anchor": "end" }, fmt.f(t, 1))); }
  d.icoord.forEach((ic, i) => {
    const dc = d.dcoord[i];
    svg.append(s("path", { d: `M${X(ic[0])},${Y(dc[0])}L${X(ic[1])},${Y(dc[1])}L${X(ic[2])},${Y(dc[2])}L${X(ic[3])},${Y(dc[3])}`, class: "dendro" }));
  });
  d.ivl.forEach((lab, i) => {
    const x = X(5 + 10 * i);
    svg.append(s("text", { x, y: height - pad.b + 14, "text-anchor": "end", transform: `rotate(-60 ${x} ${height - pad.b + 14})` }, lab));
  });
  if (cut != null) {
    svg.append(s("line", { x1: pad.l, x2: width - pad.r, y1: Y(cut), y2: Y(cut), class: "cut" }));
    svg.append(s("text", { x: width - pad.r, y: Y(cut) - 6, "text-anchor": "end", class: "lbl" }, "cut for the chosen k"));
  }
  target.replaceChildren(svg);
}

export function hbar(share) {
  const w = Math.max(0, Math.min(1, share)) * 100;
  return el("span", { class: "hbar", role: "img", "aria-label": fmt.p(share) }, el("i", { style: `width:${w.toFixed(1)}%` }));
}

export function params() { return new URLSearchParams(location.search); }
export function setParam(k, v) {
  const p = params();
  if (v == null) p.delete(k); else p.set(k, v);
  history.replaceState(null, "", `${location.pathname}${p.toString() ? "?" + p : ""}${location.hash}`);
}

// ---------- headline results (web/data/facts.json, a copy of reports/deliverable_facts.json)

// The evaluation's intervals are the central 95% of its bootstrap (pipeline/evaluate.py, interval()).
export const CI_LEVEL = 95;
const ci = (v) => (Array.isArray(v) && v.length === 2 && v[0] != null && v[1] != null ? v : null);
const pct = (x) => fmt.p(x);
const dec = (x) => fmt.f(x, 2);
const COIN_TOSS_AUC = 0.5;
const signed = (x, d) => fmt.f(x, d).replace(/^-/, "−");   // a true minus sign

/** The study's headline results and the feature evaluations, each with what it is compared against.
 *  Returns [{id, title, meaning, scale, show, rows: [{label, x, ci, main}], aim, met, extra, measured}];
 *  a result the facts do not hold is left out. */
export function headlineResults(facts) {
  const out = [];
  const evs = (facts && facts.evaluation) || {};
  const ev = evs.test || evs.val;
  const split = evs.test ? "test" : "validation";
  if (ev) {
    const T = ev.targets || {}, met = ev.met || {};
    if (ev.t2_accuracy != null) {
      const best = Math.max(ev.t2_baseline_common ?? 0, ev.t2_baseline_script ?? 0);
      const aim = T.T2_points_above_baseline != null ? best + T.T2_points_above_baseline / 100 : null;
      const pci = ci(ev.t2_points_ci95);
      out.push({ id: "subject", title: "Guessing a book's subject", show: pct, scale: "share",
        meaning: "Each group is given the subject most of its training books have. A book the model never saw is then given the subject of the group it lands in. The two simple guesses use no grouping at all; the study's guess has to beat the better of them by a margin set in advance.",
        rows: [{ label: "The study's guess", x: ev.t2_accuracy, ci: ci(ev.t2_accuracy_ci95), main: true },
          { label: "Always the most common subject", x: ev.t2_baseline_common },
          { label: "The most common subject of the book's script", x: ev.t2_baseline_script }],
        aim: aim == null ? null : { x: aim, label: `aim: ${pct(aim)}, the better simple guess plus ${fmt.f(T.T2_points_above_baseline, 0)} points` },
        met: met.T2 ?? null,
        extra: ev.t2_points != null ? `${signed(ev.t2_points, 1)} points above the better simple guess${pci ? ` (${CI_LEVEL}% interval ${signed(pci[0], 1)} to ${signed(pci[1], 1)})` : ""}.` : null,
        measured: ev.t2_labelled_heldout != null ? `Tested on ${fmt.n(ev.t2_labelled_heldout)} labelled ${split} books.` : null });
    }
    if (ev.t1_agreement != null) {
      out.push({ id: "page", title: "One page finds its own book's group", show: pct, scale: "share",
        meaning: "A single page from a book the model never saw is checked exactly as an upload would be. It counts as right when the page lands in the same group as its whole book. Chance is what placing pages at random, in groups of these sizes, would score.",
        rows: [{ label: "Pages placed with their own book", x: ev.t1_agreement, ci: ci(ev.t1_agreement_ci95), main: true },
          { label: "Chance", x: ev.t1_chance }],
        aim: T.T1_page_agreement != null ? { x: T.T1_page_agreement, label: `aim: ${pct(T.T1_page_agreement)}` } : null,
        met: met.T1 ?? null,
        extra: ev.t1_abstain_rate != null ? `${pct(ev.t1_abstain_rate)} of pages had too little text and were declined, as the app would.` : null,
        measured: ev.held_out_books != null ? `Pages from ${fmt.n(ev.held_out_books)} ${split} books.` : null });
    }
    if (ev.t3_bootstrap != null) {
      out.push({ id: "stability", title: "The groups come back when the books change", show: dec, scale: "score",
        meaning: "The grouping is rerun on random samples of the books, and each new grouping is compared with the original using the adjusted Rand index: zero is what chance gives, one means exactly the same groups. A high score means the groups belong to the books, not to one lucky run.",
        rows: [{ label: "Agreement between reruns (median)", x: ev.t3_bootstrap, main: true }],
        aim: T.T3_bootstrap_ari != null ? { x: T.T3_bootstrap_ari, label: `aim: ${dec(T.T3_bootstrap_ari)}` } : null,
        met: met.T3 ?? null, extra: "No interval is recorded for this result.",
        measured: "Measured on the training books." });
    }
  }
  const f = (facts && facts.features) || {};
  const s = f.suggest;
  if (s && s.top1 != null) {
    out.push({ id: "suggest", title: "Suggesting a catalogue class", show: pct, scale: "share",
      meaning: "For a book the model never saw, the nearest books that carry a catalogue class vote on its class, the closer ones counting more. The simple guess always names the most common class.",
      rows: [{ label: "Right class suggested first", x: s.top1, ci: ci(s.top1_ci95), main: true },
        { label: "Right class among the suggestions", x: s.top3, ci: ci(s.top3_ci95) },
        { label: "Always the most common class", x: s.baseline_most_common }],
      aim: null, met: null, measured: s.heldout_books != null ? `Tested on ${fmt.n(s.heldout_books)} held-out books that carry a class.` : null });
  }
  const e = f.editions;
  if (e && (e.precision != null || e.recall != null)) {
    out.push({ id: "editions", title: "Finding other editions of a book", show: pct, scale: "share",
      meaning: "Books with the same title and author are taken as editions of one text. The first bar is the share of suggested editions that really are one; the second is the share of real editions that get suggested.",
      rows: [{ label: "Suggestions that are real editions", x: e.precision, ci: ci(e.precision_ci95), main: true },
        { label: "Real editions that are found", x: e.recall, ci: ci(e.recall_ci95) }],
      aim: null, met: null, measured: e.heldout_books != null ? `Tested on ${fmt.n(e.heldout_books)} held-out books${e.groups_heldout != null ? `, of which only ${fmt.n(e.groups_heldout)} title-and-author groups have more than one edition, so the intervals are wide` : ""}.` : null });
  }
  const t = f.triage;
  if (t) {
    out.push({ id: "triage", title: "Spotting books with poor scans", show: dec, scale: "score",
      meaning: "The scan-quality rule gives every book a score. It is tested on books where our reading of the page can be compared with the archive's own reading. The score shown is the chance that a badly read book is rated worse than a well read one, so a coin toss would sit at one half.",
      // a coin toss scores one half on this measure by definition (no file holds it; it is not a result)
      rows: t.auc != null ? [{ label: "The scan-quality rule", x: t.auc, ci: ci(t.auc_ci95), main: true }, { label: "A coin toss", x: COIN_TOSS_AUC }] : [],
      aim: null, met: null, empty: t.auc == null ? "Not measured yet: too few books have both readings." : null,
      measured: t.books != null ? `Tested on ${fmt.n(t.books)} books with both readings.` : null });
  }
  const r = f.related;
  if (r && r.knn_other_script_share) {
    const k = r.knn_other_script_share;
    out.push({ id: "related", title: "Related books in other scripts", show: pct, scale: "share",
      meaning: "Of each book's nearest neighbours, the share written in a different script. Removing each language's average position is what lets a book find neighbours in other scripts at all.",
      rows: [{ label: "With each language's average removed", x: k.centred, main: true },
        { label: "As the encoder gives them", x: k.uncentred }],
      aim: null, met: null, measured: r.books != null ? `Measured on ${fmt.n(r.books)} training books, ${fmt.n(r.k)} neighbours each.` : null });
  }
  return out;
}

const clamp01 = (x) => Math.max(0, Math.min(1, Number(x) || 0));

/** One result as a labelled bar chart: a bar per row, a whisker for its interval, a dashed line for the aim.
 *  Every value is printed beside its bar, so the bars themselves are hidden from screen readers. */
export function resultFigure(r0, { headingLevel = "h3", variant = null } = {}) {
  // rows without a value are left out, except the main one, which then reads "n/a"
  const r = { ...r0, rows: r0.rows.filter((x) => x.main || x.x != null) };
  const head = `${r.id}-result-h`;
  const status = r.met === true ? ["Target met", "rf-status--met"] : r.met === false ? ["Target not met", "rf-status--miss"]
    : [r.aim ? "Not judged against its target" : "No target was set in advance", "rf-status--none"];
  const main = r.rows.find((x) => x.main) || r.rows[0];
  const row = (x) => el("li", { class: x.main ? "rf-row is-main" : "rf-row" },
    el("span", { class: "rf-label" }, x.label,
      x.ci ? el("span", { class: "rf-ci-text", text: `${CI_LEVEL}% interval ${r.show(x.ci[0])} to ${r.show(x.ci[1])}` }) : null),
    el("span", { class: "rf-track", "aria-hidden": "true" },
      el("i", { class: "rf-bar", style: `--x:${clamp01(x.x)}` }),
      x.ci ? el("i", { class: "rf-ci", style: `--lo:${clamp01(x.ci[0])};--hi:${clamp01(x.ci[1])}` }) : null,
      r.aim ? el("i", { class: "rf-aim", style: `--x:${clamp01(r.aim.x)}` }) : null),
    el("span", { class: "rf-value", text: x.x == null ? "n/a" : r.show(x.x) }));
  return el("article", { class: variant ? `rf rf--${variant}` : "rf", "aria-labelledby": head },
    el("div", { class: "rf-head" },
      el(headingLevel, { id: head, text: r.title }),
      el("p", { class: `rf-status ${status[1]}`, text: status[0] })),
    main && main.x != null ? el("p", { class: "rf-figure" }, el("span", { class: "figure", text: r.show(main.x) }), el("span", { class: "small muted", text: main.label })) : null,
    r.rows.length ? el("ul", { class: "rf-rows" }, r.rows.map(row)) : el("p", { class: "ink-2", text: r.empty || "Not measured yet." }),
    r.rows.length ? el("ul", { class: "legend rf-legend" },
      el("li", {}, el("span", { class: "sw sw--accent" }), r.scale === "share" ? "each bar runs from none to all" : "each bar runs from zero to one"),
      r.rows.some((x) => x.ci) ? el("li", {}, el("span", { class: "sw sw--whisker" }), `${CI_LEVEL}% interval`) : null,
      r.aim ? el("li", {}, el("span", { class: "sw sw--aim" }), r.aim.label) : null) : null,
    el("p", { class: "rf-meaning", text: r.meaning }),
    r.extra || r.measured ? el("p", { class: "small muted", text: [r.extra, r.measured].filter(Boolean).join(" ") }) : null);
}

// ---- shared shell chrome: semi-light / darkroom toggle + GPU reading progress
(function initShellChrome() {
  const KEY = "grantha-theme";
  const apply = (mode) => {
    if (mode === "dark") document.documentElement.dataset.theme = "dark";
    else delete document.documentElement.dataset.theme;
  };
  let saved = null;
  try { saved = localStorage.getItem(KEY); } catch {}
  apply(saved);

  const mount = () => {
    const slab = document.querySelector(".slab");
    const box = slab && slab.querySelector(".container");
    if (!slab || !box) return;
    if (!slab.querySelector("#theme-toggle")) {
      const btn = el("button", {
        type: "button",
        id: "theme-toggle",
        class: "theme-toggle",
        "aria-pressed": String(saved === "dark"),
        text: saved === "dark" ? "Semi-light" : "Darkroom",
        onclick: () => {
          const dark = document.documentElement.dataset.theme !== "dark";
          apply(dark ? "dark" : "light");
          try { localStorage.setItem(KEY, dark ? "dark" : "light"); } catch {}
          btn.setAttribute("aria-pressed", String(dark));
          btn.textContent = dark ? "Semi-light" : "Darkroom";
        },
      });
      box.append(btn);
    }
    if (!slab.querySelector(".read-progress")) {
      const bar = el("span", { class: "read-progress", "aria-hidden": "true" });
      slab.append(bar);
      const update = () => {
        const max = document.documentElement.scrollHeight - window.innerHeight;
        const p = max > 0 ? Math.max(0, Math.min(1, window.scrollY / max)) : 0;
        bar.style.transform = `scaleX(${p.toFixed(4)})`;
      };
      window.addEventListener("scroll", update, { passive: true });
      window.addEventListener("resize", update, { passive: true });
      update();
    }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
})();
