// Archive map: every book of web/data/galaxy.json as one dot in three dimensions, coloured by language.
// Two coordinate sets per book (views.uncentred, views.centred); the switch animates between them in the shader.
import { getJSON, el, esc, fmt, LANG, params, setParam, tip } from "./common.js";

const K = 10;                       // related books asked for per pick: GET /api/related/{id}?k=K
const MAX_MARKS = 50;               // the API's upper limit for k
const DURATION = 1000;              // ms for the view change
const PICK_PX = 10;                 // a click within this many CSS pixels of a dot picks it
const CAMERA_DIST = 2.7;
const BCP47 = { eng: "en", hin: "hi", san: "sa", ben: "bn", guj: "gu", tel: "te", kan: "kn", tam: "ta" };
const NON_LATIN = /(?!\p{Script=Latin})\p{L}/u;
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);
const VIEW_NAME = { uncentred: "Raw", centred: "Language removed" };
const LANG_ORDER = Object.keys(LANG);

const $ = (id) => document.getElementById(id);
const wrap = $("canvas-wrap"), gl = $("gl"), statusEl = $("gx-status"), axisLabels = $("axis-labels");
const axesList = $("axes"), langsList = $("langs"), find = $("find"), findList = $("find-list"), bookPanel = $("book");
const radios = [...document.querySelectorAll('#view input[name="view"]')];
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
const fixtureParam = params().get("fixture");
const fixtureMode = fixtureParam != null && LOCAL_HOSTS.has(location.hostname);

const S = {
  view: "uncentred", t: 0, anim: null,
  focusLang: null, picked: -1, related: [], hover: -1,
  galaxy: null, A: null, B: null, langIdx: null, idIndex: new Map(),
  docs: null, docsById: new Map(), titlesLower: null,
  dirty: true, autoRotate: false, relSeq: 0,
};
let THREE, renderer, scene, camera, controls, dots, marks, links, axesGroup, axisEnds = [];

// ---------- small helpers

const langName = (tag) => (tag ? LANG[tag] || tag : "language not recorded");
const langColorVar = (tag) => (LANG[tag] ? `var(--lang-${tag})` : "var(--color-muted)");
const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

function titleAttrs(title, tag) {
  const a = { dir: "auto", text: title };
  if (NON_LATIN.test(title) && BCP47[tag]) a.lang = BCP47[tag];
  return a;
}

/** A CSS colour token resolved to sRGB 0-1 by painting it on a one-pixel canvas (handles oklch). */
function tokenRGB(name) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const c = document.createElement("canvas");
  c.width = c.height = 1;
  const x = c.getContext("2d", { willReadFrequently: true });
  x.fillStyle = "#808080";
  if (v) x.fillStyle = v;
  x.fillRect(0, 0, 1, 1);
  const d = x.getImageData(0, 0, 1, 1).data;
  return [d[0] / 255, d[1] / 255, d[2] / 255];
}

function setStatus(text) {
  statusEl.className = "gx-status";
  statusEl.replaceChildren(text || "");
  statusEl.hidden = !text;
}

function fail(title, msg) {
  statusEl.className = "gx-status is-error";
  statusEl.hidden = false;
  statusEl.replaceChildren(el("strong", { text: title }), el("span", { class: "ink-2", text: msg }),
    el("a", { href: "browse.html", text: "Browse the books by topic group instead" }));
  gl.setAttribute("aria-label", title);
  for (const r of radios) r.disabled = true;
}

function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch { return false; }
}

/** Centre a view on its mean and scale it so nearly every book sits inside the unit sphere. */
function normalise(rows) {
  const n = rows.length, out = new Float32Array(n * 3), mean = [0, 0, 0];
  for (const r of rows) for (let j = 0; j < 3; j++) mean[j] += (r[j] || 0) / n;
  const dist = new Float64Array(n);
  rows.forEach((r, i) => {
    let s = 0;
    for (let j = 0; j < 3; j++) { const v = (r[j] || 0) - mean[j]; out[i * 3 + j] = v; s += v * v; }
    dist[i] = Math.sqrt(s);
  });
  const sorted = Float64Array.from(dist).sort();
  const r99 = sorted[Math.floor(0.99 * (n - 1))] || 1;
  for (let i = 0; i < out.length; i++) out[i] /= r99;
  return out;
}

/** PCA signs are arbitrary: flip each axis of B that runs against the same axis of A, so books travel less. */
function alignSigns(A, B) {
  const n = A.length / 3;
  for (let j = 0; j < 3; j++) {
    let s = 0;
    for (let i = 0; i < n; i++) s += A[i * 3 + j] * B[i * 3 + j];
    if (s < 0) for (let i = 0; i < n; i++) B[i * 3 + j] = -B[i * 3 + j];
  }
}

function posAt(i, out = [0, 0, 0]) {
  const t = S.t, a = S.A, b = S.B, k = i * 3;
  out[0] = a[k] + (b[k] - a[k]) * t; out[1] = a[k + 1] + (b[k + 1] - a[k + 1]) * t; out[2] = a[k + 2] + (b[k + 2] - a[k + 2]) * t;
  return out;
}

// ---------- start

async function main() {
  if (!webglAvailable()) {
    fail("This browser cannot draw the 3-D map", "It needs WebGL, which is turned off or not supported here.");
    return;
  }
  try {
    THREE = await import("three");
    var { OrbitControls } = await import("three/addons/controls/OrbitControls.js");
  } catch {
    fail("The map could not load", "The 3-D drawing library did not download. Check the connection and reload the page.");
    return;
  }
  let g;
  try {
    g = await getJSON("data/galaxy.json");
    if (!g || !g.views || !Array.isArray(g.views.uncentred) || !Array.isArray(g.views.centred) || !Array.isArray(g.books)
        || g.views.uncentred.length !== g.books.length || g.views.centred.length !== g.books.length) throw new Error("data/galaxy.json does not have the expected shape.");
  } catch (err) {
    fail("The map data did not load", String(err.message || err));
    return;
  }
  S.galaxy = g;
  S.A = normalise(g.views.uncentred);
  S.B = normalise(g.views.centred);
  alignSigns(S.A, S.B);
  g.books.forEach((b, i) => S.idIndex.set(b.identifier, i));

  try { build(OrbitControls); } catch (err) {
    fail("This browser cannot draw the 3-D map", String(err.message || err));
    return;
  }
  buildLegend();
  shareSentences();
  const initial = params().get("view") === "centred" ? "centred" : "uncentred";
  setView(initial, { instant: true });
  setStatus("");
  requestAnimationFrame(frame);

  // titles for search, hover and the picked book (a larger file; the map does not wait for it)
  getJSON("data/corpus.json").then((c) => {
    S.docs = c.docs || [];
    for (const d of S.docs) S.docsById.set(d.identifier, d);
    S.titlesLower = S.docs.map((d) => `${d.title || ""} ${d.identifier}`.toLowerCase());
    find.disabled = false;
    if (S.picked >= 0) renderBookHead();
  }).catch(() => { find.placeholder = "Titles did not load"; });

  let want = params().get("book");
  if (fixtureMode && fixtureParam.startsWith("get_related__")) want = fixtureParam.slice("get_related__".length);
  if (want && S.idIndex.has(want)) pick(S.idIndex.get(want));
}

// ---------- scene

function build(OrbitControls) {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  gl.append(renderer.domElement);
  renderer.domElement.setAttribute("aria-hidden", "true");

  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(45, 4 / 3, 0.05, 50);
  camera.position.set(0.9, 0.6, CAMERA_DIST);

  const n = S.galaxy.books.length;
  const tint = new Float32Array(n * 3), lang = new Float32Array(n);
  const palette = LANG_ORDER.map((t) => tokenRGB(`--lang-${t}`)), other = tokenRGB("--color-muted");
  S.langIdx = new Int8Array(n);
  S.galaxy.books.forEach((b, i) => {
    const li = LANG_ORDER.indexOf(b.lang_tag);
    S.langIdx[i] = li;
    lang[i] = li;
    const c = li >= 0 ? palette[li] : other;
    tint.set(c, i * 3);
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(S.A, 3));
  geo.setAttribute("posB", new THREE.BufferAttribute(S.B, 3));
  geo.setAttribute("tint", new THREE.BufferAttribute(tint, 3));
  geo.setAttribute("lang", new THREE.BufferAttribute(lang, 1));
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 4);    // both views fit; skips per-frame bounds
  const dotsMat = new THREE.ShaderMaterial({
    vertexShader: $("dots-vs").textContent, fragmentShader: $("dots-fs").textContent,
    uniforms: { uT: { value: 0 }, uSize: { value: 0.016 }, uScale: { value: 600 }, uMin: { value: 2 }, uFocus: { value: -1 }, uDim: { value: 1 } },
    transparent: true, depthWrite: false,
  });
  dots = new THREE.Points(geo, dotsMat);
  scene.add(dots);

  // axes through the centre, faint, with labels placed in HTML each frame
  const axisRGB = tokenRGB("--gx-axis");
  const axisGeo = new THREE.BufferGeometry();
  const L = 1.15;
  axisGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array([-L, 0, 0, L, 0, 0, 0, -L, 0, 0, L, 0, 0, 0, -L, 0, 0, L]), 3));
  axesGroup = new THREE.LineSegments(axisGeo, new THREE.LineBasicMaterial({ color: new THREE.Color().setRGB(...axisRGB, THREE.SRGBColorSpace), transparent: true, opacity: 0.45, depthWrite: false }));
  scene.add(axesGroup);
  axisEnds = [new THREE.Vector3(L, 0, 0), new THREE.Vector3(0, L, 0), new THREE.Vector3(0, 0, L)];
  axisLabels.replaceChildren(...axisEnds.map(() => el("span")));

  // the picked book, its related books and the hovered dot
  const mGeo = new THREE.BufferGeometry();
  mGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array((MAX_MARKS + 2) * 3), 3));
  mGeo.setAttribute("tint", new THREE.BufferAttribute(new Float32Array((MAX_MARKS + 2) * 3), 3));
  mGeo.setAttribute("kind", new THREE.BufferAttribute(new Float32Array(MAX_MARKS + 2), 1));
  mGeo.setDrawRange(0, 0);
  mGeo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 4);
  marks = new THREE.Points(mGeo, new THREE.ShaderMaterial({
    vertexShader: $("marks-vs").textContent, fragmentShader: $("marks-fs").textContent,
    uniforms: { uPR: { value: renderer.getPixelRatio() }, uRing: { value: new THREE.Vector3(...tokenRGB("--gx-pick")) }, uField: { value: new THREE.Vector3(...tokenRGB("--gx-field")) } },
    transparent: true, depthTest: false, depthWrite: false,
  }));
  marks.renderOrder = 3;
  marks.userData.palette = palette; marks.userData.other = other;
  scene.add(marks);

  const lGeo = new THREE.BufferGeometry();
  lGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(MAX_MARKS * 2 * 3), 3));
  lGeo.setDrawRange(0, 0);
  lGeo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 4);
  links = new THREE.LineSegments(lGeo, new THREE.LineBasicMaterial({ color: new THREE.Color().setRGB(...tokenRGB("--gx-link"), THREE.SRGBColorSpace), transparent: true, opacity: 0.8, depthTest: false, depthWrite: false }));
  links.renderOrder = 2;
  scene.add(links);

  controls = new OrbitControls(camera, gl);
  controls.enablePan = false;
  controls.enableDamping = !reduceMotion.matches;
  controls.dampingFactor = 0.08;
  controls.minDistance = 0.4;
  controls.maxDistance = 9;
  controls.rotateSpeed = 0.7;
  controls.autoRotateSpeed = 0.5;
  S.autoRotate = !reduceMotion.matches;
  controls.autoRotate = S.autoRotate;
  controls.addEventListener("start", stopAutoRotate);
  controls.addEventListener("change", () => { S.dirty = true; });
  reduceMotion.addEventListener("change", () => {
    controls.enableDamping = !reduceMotion.matches;
    if (reduceMotion.matches) stopAutoRotate();
  });

  new ResizeObserver(resize).observe(wrap);
  resize();
  bindPointer();
}

function stopAutoRotate() {
  if (!S.autoRotate) return;
  S.autoRotate = false;
  controls.autoRotate = false;
}

function resize() {
  const w = Math.max(1, wrap.clientWidth), h = Math.max(1, wrap.clientHeight);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  const pr = renderer.getPixelRatio();
  // pixels per world unit at distance one, so a dot keeps its size relative to the frame
  dots.material.uniforms.uScale.value = (h * pr) / (2 * Math.tan((camera.fov * Math.PI) / 360));
  dots.material.uniforms.uMin.value = (w < 560 ? 1.6 : 2) * pr;
  marks.material.uniforms.uPR.value = pr;
  S.dirty = true;
}

function frame(now) {
  requestAnimationFrame(frame);
  if (S.anim) {
    const k = Math.max(0, Math.min(1, (now - S.anim.start) / DURATION));
    S.t = S.anim.from + (S.anim.to - S.anim.from) * ease(k);
    if (k >= 1) S.anim = null;
    dots.material.uniforms.uT.value = S.t;
    updateMarks();
    S.dirty = true;
  }
  if (controls.update()) S.dirty = true;
  if (!S.dirty) return;
  S.dirty = false;
  renderer.render(scene, camera);
  placeAxisLabels();
}

const v3 = () => new THREE.Vector3();
let tmpV;
function placeAxisLabels() {
  tmpV = tmpV || v3();
  const w = wrap.clientWidth, h = wrap.clientHeight;
  axisEnds.forEach((p, i) => {
    const span = axisLabels.children[i];
    tmpV.copy(p).project(camera);
    const behind = tmpV.z > 1;
    span.hidden = behind;
    const x = Math.min(w - span.offsetWidth - 4, Math.max(4, ((tmpV.x + 1) / 2) * w + 6));
    const y = Math.min(h - span.offsetHeight - 4, Math.max(4, ((1 - tmpV.y) / 2) * h - 10));
    span.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
  });
}

// ---------- the measured result behind the two views (web/data/facts.json, features.related)

/** Share of a book's nearest neighbours written in another script, raw and with language removed.
 *  Left out when facts.json does not carry it; the plain sentences then stand alone. */
function shareSentences() {
  getJSON("data/facts.json").then((f) => {
    const r = f && f.features && f.features.related;
    const s = r && r.knn_other_script_share;
    if (!s || s.uncentred == null || s.centred == null || r.k == null) return;
    const k = fmt.n(r.k);
    $("share-uncentred").textContent = ` On average only ${fmt.p(s.uncentred)} of a book’s ${k} nearest neighbours are in another script (measured on the training books).`;
    $("share-centred").textContent = ` Now ${fmt.p(s.centred)} of a book’s ${k} nearest neighbours are in another script (measured on the training books).`;
  }).catch(() => {});
}

// ---------- the view switch

function axisWords(view) {
  const ex = (S.galaxy.explained && S.galaxy.explained[view]) || [];
  return [0, 1, 2].map((i) => (ex[i] == null ? null : fmt.p(ex[i])));
}

function setView(view, { instant = false } = {}) {
  if (view !== "centred") view = "uncentred";
  S.view = view;
  for (const r of radios) r.checked = r.value === view;
  for (const s of document.querySelectorAll("#view-note [data-view]")) s.hidden = s.dataset.view !== view;
  const target = view === "centred" ? 1 : 0;
  if (instant || reduceMotion.matches) { S.anim = null; S.t = target; dots.material.uniforms.uT.value = target; updateMarks(); }
  else S.anim = { from: S.t, to: target, start: performance.now() };
  S.dirty = true;

  const words = axisWords(view);
  [...axisLabels.children].forEach((span, i) => { span.textContent = words[i] ? `Axis ${i + 1}, ${words[i]}` : `Axis ${i + 1}`; });
  const ex = (S.galaxy.explained && S.galaxy.explained[view]) || [];
  const total = ex.length ? ex.slice(0, 3).reduce((a, b) => a + (Number(b) || 0), 0) : null;
  axesList.replaceChildren(
    ...words.map((w, i) => el("li", {}, el("strong", { text: `Axis ${i + 1}` }), ` ${w ? `${w} of the variation` : "share not recorded"}`)),
    total != null ? el("li", {}, el("strong", { text: "Together" }), ` ${fmt.p(total)}`) : null);
  gl.setAttribute("aria-label", `Map of ${fmt.n(S.galaxy.books.length)} books, coloured by language. ${VIEW_NAME[view]} view.`);
  setParam("view", view === "centred" ? "centred" : null);
}

for (const r of radios) r.addEventListener("change", () => { if (r.checked && S.galaxy) setView(r.value); });

document.addEventListener("keydown", (e) => {
  if (!S.galaxy || e.ctrlKey || e.metaKey || e.altKey) return;
  const typing = e.target.closest && e.target.closest("input, textarea, select, [contenteditable]");
  if ((e.key === "v" || e.key === "V") && (!typing || e.target.type === "radio")) {
    e.preventDefault();
    setView(S.view === "centred" ? "uncentred" : "centred");
  } else if (e.key === "Escape" && !typing && S.picked >= 0) {
    clearPick();
  }
});

// keyboard turning and zoom while the map has focus
gl.addEventListener("keydown", (e) => {
  if (!controls) return;
  const step = Math.PI / 24;
  const off = camera.position.clone().sub(controls.target);
  const sph = new THREE.Spherical().setFromVector3(off);
  if (e.key === "ArrowLeft") sph.theta -= step;
  else if (e.key === "ArrowRight") sph.theta += step;
  else if (e.key === "ArrowUp") sph.phi = Math.max(0.05, sph.phi - step);
  else if (e.key === "ArrowDown") sph.phi = Math.min(Math.PI - 0.05, sph.phi + step);
  else if (e.key === "+" || e.key === "=") sph.radius = Math.max(controls.minDistance, sph.radius * 0.85);
  else if (e.key === "-" || e.key === "_") sph.radius = Math.min(controls.maxDistance, sph.radius / 0.85);
  else return;
  e.preventDefault();
  stopAutoRotate();
  camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(sph));
  camera.lookAt(controls.target);
  S.dirty = true;
});

// ---------- legend: choose a language to light only its books

function buildLegend() {
  const counts = new Map();
  for (const b of S.galaxy.books) counts.set(b.lang_tag, (counts.get(b.lang_tag) || 0) + 1);
  const tags = LANG_ORDER.filter((t) => counts.has(t)).concat([...counts.keys()].filter((t) => !LANG[t]));
  langsList.replaceChildren(...tags.map((t) => el("li", {},
    el("button", { type: "button", "aria-pressed": "false", "data-lang": t, onclick: () => focusLang(t) },
      el("span", { class: "dot", style: `--c:${langColorVar(t)}`, "aria-hidden": "true" }),
      el("span", { text: langName(t) }),
      el("span", { class: "count", text: fmt.n(counts.get(t)) })))));
}

function focusLang(tag) {
  S.focusLang = S.focusLang === tag ? null : tag;
  for (const b of langsList.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b.dataset.lang === S.focusLang));
  langsList.classList.toggle("has-focus", S.focusLang != null);
  dots.material.uniforms.uFocus.value = S.focusLang == null ? -1 : LANG_ORDER.indexOf(S.focusLang);
  S.dirty = true;
}

// ---------- picking with the pointer (screen-space nearest dot, within PICK_PX)

const proj = { m: null };
function nearestAt(clientX, clientY) {
  const rect = gl.getBoundingClientRect();
  const mx = clientX - rect.left, my = clientY - rect.top, w = rect.width, h = rect.height;
  if (!proj.m) proj.m = new THREE.Matrix4();
  camera.updateMatrixWorld();
  const e = proj.m.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse).elements;
  const n = S.galaxy.books.length, t = S.t, A = S.A, B = S.B;
  const focus = S.focusLang == null ? -1 : LANG_ORDER.indexOf(S.focusLang);
  let best = -1, bestD = PICK_PX * PICK_PX, bestW = Infinity;
  for (let i = 0; i < n; i++) {
    if (focus >= 0 && S.langIdx[i] !== focus) continue;
    const k = i * 3;
    const x = A[k] + (B[k] - A[k]) * t, y = A[k + 1] + (B[k + 1] - A[k + 1]) * t, z = A[k + 2] + (B[k + 2] - A[k + 2]) * t;
    const cw = e[3] * x + e[7] * y + e[11] * z + e[15];
    if (cw <= 0) continue;
    const sx = ((e[0] * x + e[4] * y + e[8] * z + e[12]) / cw + 1) * 0.5 * w;
    const sy = (1 - (e[1] * x + e[5] * y + e[9] * z + e[13]) / cw) * 0.5 * h;
    const d = (sx - mx) * (sx - mx) + (sy - my) * (sy - my);
    if (d < bestD || (d === bestD && cw < bestW)) { best = i; bestD = d; bestW = cw; }
  }
  return best;
}

function hoverLabel(i) {
  const b = S.galaxy.books[i], d = S.docsById.get(b.identifier);
  const title = (d && d.title) || b.identifier;
  return `${esc(title)}<br><span class="muted">${esc(langName(b.lang_tag))}${d && d.year ? `, ${Math.round(d.year)}` : ""}</span>`;
}

function bindPointer() {
  let down = null, pending = null;
  gl.addEventListener("pointerdown", (e) => { down = { x: e.clientX, y: e.clientY, t: performance.now() }; tip(null); });
  gl.addEventListener("pointerup", (e) => {
    if (!down) return;
    const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
    const quick = performance.now() - down.t < 600;
    down = null;
    if (moved > 5 || !quick) return;
    const i = nearestAt(e.clientX, e.clientY);
    stopAutoRotate();
    if (i >= 0) pick(i); else if (S.picked >= 0) clearPick();
  });
  gl.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse" || e.buttons) return;
    if (pending) { pending = e; return; }
    pending = e;
    requestAnimationFrame(() => {
      const ev = pending; pending = null;
      const i = nearestAt(ev.clientX, ev.clientY);
      if (i !== S.hover) { S.hover = i; updateMarks(); S.dirty = true; }
      gl.classList.toggle("is-over", i >= 0);
      if (i >= 0) tip(ev, hoverLabel(i)); else tip(null);
    });
  });
  gl.addEventListener("pointerleave", () => {
    tip(null); gl.classList.remove("is-over");
    if (S.hover >= 0) { S.hover = -1; updateMarks(); S.dirty = true; }
  });
}

// ---------- the picked book: marks and lines in the scene

function updateMarks() {
  if (!marks) return;
  const pos = marks.geometry.attributes.position, tint = marks.geometry.attributes.tint, kind = marks.geometry.attributes.kind;
  const pal = marks.userData.palette, other = marks.userData.other;
  const list = [];
  if (S.picked >= 0) {
    list.push([S.picked, 0]);
    for (const r of S.related.slice(0, MAX_MARKS)) list.push([r, 1]);
  }
  if (S.hover >= 0 && S.hover !== S.picked) list.push([S.hover, 2]);
  const p = [0, 0, 0];
  list.forEach(([i, k], j) => {
    posAt(i, p);
    pos.setXYZ(j, p[0], p[1], p[2]);
    const c = S.langIdx[i] >= 0 ? pal[S.langIdx[i]] : other;
    tint.setXYZ(j, c[0], c[1], c[2]);
    kind.setX(j, k);
  });
  pos.needsUpdate = tint.needsUpdate = kind.needsUpdate = true;
  marks.geometry.setDrawRange(0, list.length);

  const lp = links.geometry.attributes.position, a = [0, 0, 0], b = [0, 0, 0];
  let m = 0;
  if (S.picked >= 0) {
    posAt(S.picked, a);
    for (const r of S.related.slice(0, MAX_MARKS)) {
      posAt(r, b);
      lp.setXYZ(m++, a[0], a[1], a[2]);
      lp.setXYZ(m++, b[0], b[1], b[2]);
    }
  }
  lp.needsUpdate = true;
  links.geometry.setDrawRange(0, m);
  dots.material.uniforms.uDim.value = S.picked >= 0 ? 0.55 : 1;
}

// ---------- the picked book: the side panel

function pick(i, { focus = false } = {}) {
  if (i < 0 || !S.galaxy) return;
  S.picked = i;
  S.related = [];
  updateMarks();
  S.dirty = true;
  const id = S.galaxy.books[i].identifier;
  setParam("book", id);
  renderBookHead();
  if (focus) $("book-title").focus();
  loadRelated(id);
}

function clearPick() {
  S.picked = -1; S.related = []; S.relSeq++;
  updateMarks(); S.dirty = true;
  setParam("book", null);
  bookPanel.replaceChildren(
    el("h2", { id: "book-title", class: "gx-h", tabindex: "-1", text: "No book picked" }),
    el("p", { class: "ink-2", text: "Pick a dot or find a title. Its closest books in other scripts are joined to it on the map." }));
}

function renderBookHead() {
  const b = S.galaxy.books[S.picked], d = S.docsById.get(b.identifier) || {};
  const title = d.title || b.identifier;
  const head = el("h2", { id: "book-title", class: "gx-h", tabindex: "-1", ...titleAttrs(title, b.lang_tag) });
  const meta = el("p", { class: "meta" },
    el("span", {}, el("span", { class: "dot", style: `--c:${langColorVar(b.lang_tag)}`, "aria-hidden": "true" }), langName(b.lang_tag)),
    d.year ? el("span", { text: String(Math.round(d.year)) }) : null,
    d.url ? el("a", { href: d.url, text: "Open in the archive" }) : null);
  const old = bookPanel.querySelector("#book-rel");
  bookPanel.replaceChildren(head, meta, old || el("div", { id: "book-rel" }),
    el("button", { class: "btn clear", type: "button", text: "Clear the book", onclick: () => { clearPick(); find.focus(); } }));
}

function relBlock(...kids) {
  const box = bookPanel.querySelector("#book-rel");
  if (box) box.replaceChildren(el("h3", { text: "Closest books in other scripts" }), ...kids);
}

function recordedNote(rec) {
  return el("p", { class: "recorded" }, el("strong", { text: "Recorded result" }),
    el("span", {}, "Replayed from ", el("code", { text: rec.name }), `, a real ${rec.method} ${rec.path} response recorded on `,
      el("time", { datetime: rec.generated_at || null, text: rec.generated_at ? new Date(rec.generated_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC" : "an unrecorded date" }), "."));
}

async function loadRelated(id) {
  const seq = ++S.relSeq;
  relBlock(el("p", { class: "ink-2", text: "Looking up its closest books in other scripts." }), el("div", { class: "skeleton skeleton--block" }));
  let body, rec = null;
  try {
    if (fixtureMode) {
      const index = await getJSON("fixtures/_index.json");
      const name = `get_related__${id}`;
      const meta = index.fixtures && index.fixtures[name];
      if (seq !== S.relSeq) return;
      if (!meta) { noRecording(index); return; }
      const fx = await getJSON(`fixtures/${name}.json`);
      rec = { name, generated_at: index.generated_at, method: meta.method, path: meta.path };
      if (fx.status !== 200) throw new Error((fx.body && fx.body.detail) || `The server answered ${fx.status}.`);
      body = fx.body;
    } else {
      const r = await fetch(`/api/related/${encodeURIComponent(id)}?k=${K}`);
      const j = await r.json().catch(() => ({}));
      if (r.status === 404) throw new Error("The model this server runs does not include this book.");
      if (!r.ok) throw new Error(j.detail || `The server answered ${r.status}.`);
      body = j;
    }
  } catch (err) {
    if (seq !== S.relSeq) return;
    relBlock(el("p", { class: "state state--error", text: `The related books did not load. ${String(err.message || err)}` }));
    return;
  }
  if (seq !== S.relSeq) return;
  const list = (body.neighbours || []).filter((x) => x && x.identifier);
  S.related = list.map((x) => S.idIndex.get(x.identifier)).filter((x) => x != null);
  updateMarks(); S.dirty = true;
  if (!list.length) { relBlock(rec ? recordedNote(rec) : null, el("p", { class: "ink-2", text: "The server returned no related book in another script." })); return; }
  relBlock(rec ? recordedNote(rec) : null,
    el("p", { class: "small muted", text: `Nearest first, each joined to the book by a line on the map. Smaller distance means closer.` }),
    el("ol", { class: "gx-rel" }, list.map((x) => {
      const at = S.idIndex.get(x.identifier);
      const title = x.title || x.identifier;
      return el("li", {},
        el("span", { class: "dot", style: `--c:${langColorVar(x.lang_tag)}`, "aria-hidden": "true" }),
        el("span", { class: "t" },
          el("button", { type: "button", disabled: at == null, onclick: () => pick(at, { focus: true }), ...titleAttrs(title, x.lang_tag) }),
          el("span", { class: "small muted", text: [langName(x.lang_tag), x.script && x.script !== langName(x.lang_tag) ? `${x.script} script` : null, at == null ? "not on the map" : null].filter(Boolean).join(", ") })),
        el("span", { class: "num" }, el("span", { class: "visually-hidden", text: "distance " }), fmt.f(x.distance, 3)));
    })));
}

function noRecording(index) {
  const names = Object.keys(index.fixtures || {}).filter((k) => k.startsWith("get_related__"))
    .map((k) => k.slice("get_related__".length)).filter((id) => S.idIndex.has(id));
  relBlock(el("p", { class: "ink-2", text: "No recorded result for this book. These books have one:" }),
    el("ul", { class: "gx-rel" }, names.map((id) => {
      const i = S.idIndex.get(id), d = S.docsById.get(id) || {}, tag = S.galaxy.books[i].lang_tag;
      return el("li", {}, el("span", { class: "dot", style: `--c:${langColorVar(tag)}`, "aria-hidden": "true" }),
        el("span", { class: "t" }, el("button", { type: "button", onclick: () => pick(i, { focus: true }), ...titleAttrs(d.title || id, tag) }),
          el("span", { class: "small muted", text: langName(tag) })), el("span"));
    })));
}

// ---------- find a book by title (a combobox over web/data/corpus.json titles)

let options = [], active = -1;
function closeFind() { findList.hidden = true; find.setAttribute("aria-expanded", "false"); find.removeAttribute("aria-activedescendant"); active = -1; }
function setActive(j) {
  active = j;
  [...findList.children].forEach((li, k) => li.setAttribute("aria-selected", String(k === j)));
  const li = findList.children[j];
  if (li && li.id) { find.setAttribute("aria-activedescendant", li.id); li.scrollIntoView({ block: "nearest" }); }
}
function choose(j) {
  const i = options[j];
  if (i == null) return;
  const d = S.docs[i];
  find.value = d.title || d.identifier;
  closeFind();
  const at = S.idIndex.get(d.identifier);
  if (at != null) { stopAutoRotate(); pick(at, { focus: true }); }
}

find.addEventListener("input", () => {
  const q = find.value.trim().toLowerCase();
  if (!S.titlesLower || q.length < 2) { closeFind(); return; }
  const first = [], rest = [];
  for (let i = 0; i < S.titlesLower.length && first.length < 8; i++) {
    const p = S.titlesLower[i].indexOf(q);
    if (p === 0) first.push(i); else if (p > 0 && rest.length < 8) rest.push(i);
  }
  options = first.concat(rest).slice(0, 8);
  findList.replaceChildren(...(options.length ? options.map((i, j) => {
    const d = S.docs[i];
    return el("li", { role: "option", id: `find-opt-${j}`, "aria-selected": "false",
      onmousedown: (e) => { e.preventDefault(); choose(j); } },
      el("span", titleAttrs(d.title || d.identifier, d.lang_tag)),
      el("span", { class: "small muted", text: [langName(d.lang_tag), d.year ? Math.round(d.year) : null].filter(Boolean).join(", ") }));
  }) : [el("li", { class: "is-empty", role: "option", "aria-disabled": "true", text: "No title matches" })]));
  findList.hidden = false;
  find.setAttribute("aria-expanded", "true");
  active = -1;
});
find.addEventListener("keydown", (e) => {
  if (findList.hidden) return;
  if (e.key === "ArrowDown") { e.preventDefault(); if (options.length) setActive((active + 1) % options.length); }
  else if (e.key === "ArrowUp") { e.preventDefault(); if (options.length) setActive((active - 1 + options.length) % options.length); }
  else if (e.key === "Enter") { e.preventDefault(); choose(active >= 0 ? active : 0); }
  else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeFind(); }
});
find.addEventListener("blur", () => setTimeout(closeFind, 0));

main();
