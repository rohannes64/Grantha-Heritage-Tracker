// The landing page's palm-leaf manuscript (olai chuvadi), drawn live in three.js.
// Same model as the deck's title slide (docs/build/manuscript/manuscript.html), sized to its frame,
// with a slow sway and a gentle tilt toward the pointer. With reduced motion it renders one still frame.
// The leaves carry the opening of the Tirukkural (couplets 1 to 3), a public-domain classical Tamil text.
// If WebGL or the module fails, the static picture already in the frame stays.

const TEXT = "அகர முதல எழுத்தெல்லாம் ஆதி பகவன் முதற்றே உலகு ॥ கற்றதனால் ஆய பயனென்கொல் வாலறிவன் நற்றாள் தொழாஅர் எனின் ॥ "
           + "மலர்மிசை ஏகினான் மாணடி சேர்ந்தார் நிலமிசை நீடுவாழ் வார் ॥ ";
const LEAF = { len: 42, wid: 4.1, thick: 0.055 };
const BOARD = { len: 44, wid: 4.7, thick: 0.85 };
const HOLES = [-0.30, 0.30];
const N_LEAVES = 34, N_FAN = 7;
const TAMIL_FONT = "'Noto Serif Tamil', 'Nirmala UI', 'Latha', serif";

export async function mountManuscript(frame) {
  const THREE = await import("three");
  await document.fonts.load(`42px ${TAMIL_FONT}`, "அகர").catch(() => {});

  let seed = 26096;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const jitter = (a) => (rnd() * 2 - 1) * a;

  function texture(c) {
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
  }

  function leafCanvas(withText, offset) {
    const c = document.createElement("canvas"); c.width = 3072; c.height = 300;
    const g = c.getContext("2d");
    const base = g.createLinearGradient(0, 0, 0, c.height);
    base.addColorStop(0, "#b8935a"); base.addColorStop(0.12, "#d6b77c"); base.addColorStop(0.5, "#dcc088");
    base.addColorStop(0.88, "#d2b276"); base.addColorStop(1, "#a9834c");
    g.fillStyle = base; g.fillRect(0, 0, c.width, c.height);
    for (let i = 0; i < 700; i++) {
      const y = rnd() * c.height, x = rnd() * c.width, len = 220 + rnd() * 1800;
      g.strokeStyle = rnd() < 0.55 ? `rgba(110,80,40,${0.04 + rnd() * 0.1})` : `rgba(250,232,190,${0.05 + rnd() * 0.12})`;
      g.lineWidth = 0.5 + rnd() * 1.4;
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + len, y + jitter(2)); g.stroke();
    }
    for (let i = 0; i < 30; i++) {
      const x = rnd() * c.width, y = rnd() * c.height, r = 8 + rnd() * 45;
      const s = g.createRadialGradient(x, y, 0, x, y, r);
      s.addColorStop(0, `rgba(120,80,35,${0.08 + rnd() * 0.12})`); s.addColorStop(1, "rgba(120,80,35,0)");
      g.fillStyle = s; g.fillRect(x - r, y - r, 2 * r, 2 * r);
    }
    for (const h of HOLES) {
      const x = (0.5 + h) * c.width, y = c.height / 2, r = 34;
      const s = g.createRadialGradient(x, y, 10, x, y, r);
      s.addColorStop(0, "rgba(70,45,20,0.55)"); s.addColorStop(1, "rgba(70,45,20,0)");
      g.fillStyle = s; g.fillRect(x - r, y - r, 2 * r, 2 * r);
    }
    if (withText) {
      const segs = [[0.035, 0.5 + HOLES[0] - 0.035], [0.5 + HOLES[0] + 0.035, 0.5 + HOLES[1] - 0.035], [0.5 + HOLES[1] + 0.035, 0.965]];
      const lines = 8, top = 30, step = (c.height - 2 * top) / (lines - 1);
      g.font = `31px ${TAMIL_FONT}`; g.textBaseline = "middle";
      const long = TEXT.repeat(6);
      for (let l = 0; l < lines; l++) {
        const y = top + l * step;
        for (const [a, b] of segs) {
          g.save(); g.beginPath(); g.rect(a * c.width, y - 30, (b - a) * c.width, 60); g.clip();
          g.fillStyle = "rgba(38,24,12,0.86)";
          g.fillText(long, a * c.width - ((offset + l * 683 + a * 2250) % 1950), y);
          g.restore();
        }
      }
    }
    return texture(c);
  }

  function woodCanvas() {
    const c = document.createElement("canvas"); c.width = 3072; c.height = 345;
    const g = c.getContext("2d");
    g.fillStyle = "#5a2f1a"; g.fillRect(0, 0, c.width, c.height);
    for (let i = 0; i < 200; i++) {
      const y0 = rnd() * c.height, amp = 3 + rnd() * 14, f = 0.002 + rnd() * 0.004;
      g.strokeStyle = rnd() < 0.6 ? `rgba(30,14,6,${0.12 + rnd() * 0.25})` : `rgba(150,85,45,${0.08 + rnd() * 0.18})`;
      g.lineWidth = 1 + rnd() * 2.6;
      g.beginPath();
      for (let x = 0; x <= c.width; x += 24) { const y = y0 + Math.sin(x * f + i) * amp; x ? g.lineTo(x, y) : g.moveTo(x, y); }
      g.stroke();
    }
    g.strokeStyle = "rgba(215,170,95,0.55)"; g.lineWidth = 5;
    g.strokeRect(52, 45, c.width - 104, c.height - 90);
    return texture(c);
  }

  function strip(len, wid, thick, holeR, bevel) {
    const r = wid * 0.42, x0 = -len / 2, x1 = len / 2, y0 = -wid / 2, y1 = wid / 2;
    const s = new THREE.Shape();
    s.moveTo(x0 + r, y0); s.lineTo(x1 - r, y0); s.quadraticCurveTo(x1, y0, x1, y0 + r); s.lineTo(x1, y1 - r);
    s.quadraticCurveTo(x1, y1, x1 - r, y1); s.lineTo(x0 + r, y1); s.quadraticCurveTo(x0, y1, x0, y1 - r);
    s.lineTo(x0, y0 + r); s.quadraticCurveTo(x0, y0, x0 + r, y0);
    for (const h of HOLES) { const p = new THREE.Path(); p.absarc(h * LEAF.len, 0, holeR, 0, Math.PI * 2, true); s.holes.push(p); }
    const geo = new THREE.ExtrudeGeometry(s, { depth: thick, bevelEnabled: bevel > 0, bevelSize: bevel, bevelThickness: bevel,
                                              bevelSegments: 3, curveSegments: 20 });
    const pos = geo.attributes.position, uv = geo.attributes.uv;
    for (let i = 0; i < pos.count; i++) uv.setXY(i, (pos.getX(i) - x0) / len, (pos.getY(i) - y0) / wid);
    geo.rotateX(-Math.PI / 2);
    return geo;
  }

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.08;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(25, 1, 1, 400);
  camera.position.set(3.5, 35, 51); camera.lookAt(0, 0, 0.6);         // closer than the slide render: the frame is tighter

  scene.add(new THREE.HemisphereLight(0xfff4e2, 0x6a4a2a, 0.85));
  const key = new THREE.DirectionalLight(0xffe6c4, 2.8);
  key.position.set(-24, 54, 26); key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048); key.shadow.radius = 6; key.shadow.bias = -0.0004;
  Object.assign(key.shadow.camera, { left: -36, right: 36, top: 26, bottom: -26, near: 1, far: 140 });
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xdfe6ff, 0.55); rim.position.set(30, 20, -40); scene.add(rim);

  const floor = new THREE.Mesh(new THREE.PlaneGeometry(300, 300), new THREE.ShadowMaterial({ color: 0x000000, opacity: 0.45 }));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);

  const wood = new THREE.MeshStandardMaterial({ map: woodCanvas(), roughness: 0.55, metalness: 0 });
  const woodEdge = new THREE.MeshStandardMaterial({ color: 0x3e1f10, roughness: 0.6 });
  const plain = leafCanvas(false, 0), inked = [leafCanvas(true, 0), leafCanvas(true, 520), leafCanvas(true, 1120)];
  const leafEdge = new THREE.MeshStandardMaterial({ color: 0xb08a52, roughness: 0.9 });
  const leafMat = (t) => new THREE.MeshStandardMaterial({ map: t, bumpMap: t, bumpScale: 0.02, roughness: 0.82, metalness: 0 });

  const bundle = new THREE.Group(); scene.add(bundle);
  const add = (geo, mats, x, y, z, yaw) => {
    const m = new THREE.Mesh(geo, mats); m.position.set(x, y, z); m.rotation.y = yaw; m.castShadow = m.receiveShadow = true;
    bundle.add(m); return m;
  };
  const boardGeo = strip(BOARD.len, BOARD.wid, BOARD.thick, 0.32, 0.12);
  add(boardGeo, [wood, woodEdge], 0, 0.12, 0, 0);
  const leafGeo = strip(LEAF.len, LEAF.wid, LEAF.thick, 0.3, 0);
  let y = 0.12 + BOARD.thick + 0.12;
  const stackLeaf = leafMat(plain);
  for (let i = 0; i < N_LEAVES; i++) { add(leafGeo, [stackLeaf, leafEdge], jitter(0.12), y, jitter(0.07), jitter(0.006)); y += LEAF.thick + 0.004; }
  const pivot = HOLES[0] * LEAF.len;
  const fan = [];
  for (let i = 0; i < N_FAN; i++) {
    const g = new THREE.Group(); g.position.set(pivot, y, 0); g.rotation.y = -(i + 1) * 0.032; bundle.add(g);
    const m = new THREE.Mesh(leafGeo, [leafMat(inked[i % 3]), leafEdge]);
    m.position.set(-pivot, 0, 0); m.castShadow = m.receiveShadow = true; g.add(m); fan.push(g);
    y += LEAF.thick + 0.012;
  }
  add(boardGeo, [wood, woodEdge], 2.5, 0.12, -6.4, 0.035);
  const cordPts = [
    [pivot, -0.2, 0], [pivot, y + 0.3, 0], [pivot - 2.2, y + 0.55, 0.25], [pivot - 6.6, y + 0.3, 0.55], [pivot - 8.9, y - 0.5, 1.0],
    [pivot - 9.7, 0.6, 2.3], [pivot - 8.8, 0.14, 4.4], [pivot - 5.8, 0.14, 6.0], [pivot - 2.4, 0.14, 6.3],
  ].map(([a, b, c]) => new THREE.Vector3(a, b, c));
  const cord = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(cordPts), 160, 0.13, 10, false),
    new THREE.MeshStandardMaterial({ color: 0x4a2a17, roughness: 0.95 }));
  cord.castShadow = true; bundle.add(cord);
  const knot = new THREE.Mesh(new THREE.SphereGeometry(0.3, 18, 12), cord.material);
  knot.position.copy(cordPts[cordPts.length - 1]); knot.castShadow = true; bundle.add(knot);
  bundle.rotation.y = -0.1;

  const canvas = renderer.domElement;
  canvas.setAttribute("aria-hidden", "true");
  canvas.className = "manuscript-canvas";
  frame.append(canvas);

  function resize() {
    const w = frame.clientWidth, h = frame.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // keep the whole bundle in view: widen the lens on narrow frames
    camera.fov = w / h < 1.6 ? 25 * (1.6 / (w / h)) ** 0.85 : 25;
    camera.updateProjectionMatrix();
  }
  resize();
  new ResizeObserver(() => { resize(); if (still) renderer.render(scene, camera); }).observe(frame);

  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let tx = 0, ty = 0, cx = 0, cy = 0, visible = true;
  frame.addEventListener("pointermove", (e) => {
    const r = frame.getBoundingClientRect();
    tx = ((e.clientX - r.left) / r.width - 0.5); ty = ((e.clientY - r.top) / r.height - 0.5);
  });
  frame.addEventListener("pointerleave", () => { tx = 0; ty = 0; });
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(frame);

  const clock = new THREE.Clock();
  function frameLoop() {
    requestAnimationFrame(frameLoop);
    if (!visible) return;
    const t = clock.getElapsedTime();
    cx += (tx - cx) * 0.05; cy += (ty - cy) * 0.05;
    bundle.rotation.y = -0.1 + Math.sin(t * 0.25) * 0.05 + cx * 0.18;
    bundle.rotation.x = cy * 0.06;
    fan.forEach((g, i) => { g.rotation.y = -(i + 1) * (0.032 + Math.sin(t * 0.4) * 0.004); });
    renderer.render(scene, camera);
  }
  if (still) renderer.render(scene, camera); else frameLoop();
  frame.dataset.live = "true";                     // CSS fades the still picture out once the model has drawn
}
