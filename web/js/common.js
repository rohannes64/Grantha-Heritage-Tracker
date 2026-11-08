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
