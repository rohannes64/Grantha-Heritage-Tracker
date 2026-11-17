// Renders manuscript.html (three.js, palm-leaf manuscript) to docs/assets/manuscript_model.png with a transparent ground.
//
//   1. Start headless Edge with a debugging port (from PowerShell; it cannot be launched from a sandboxed node):
//        Start-Process msedge.exe -ArgumentList "--headless=new","--remote-debugging-port=9333",
//          "--user-data-dir=<a new temp dir>","--enable-unsafe-swiftshader","about:blank"
//   2. node docs/build/manuscript/render.mjs [port]
//
// Needs Node 18+ (global fetch and WebSocket) and internet for three.js from jsDelivr (the site loads the same file).
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const page = pathToFileURL(resolve(here, "manuscript.html")).href;
const out = resolve(here, "..", "..", "assets", "manuscript_model.png");
const port = process.argv[2] || "9333";

const target = await (await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(page)}`, { method: "PUT" })).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((ok) => ws.addEventListener("open", ok, { once: true }));
let id = 0;
const pending = new Map();
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
});
const call = (method, params = {}) => new Promise((ok) => { const i = ++id; pending.set(i, ok); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expression) => (await call("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result?.result?.value;

for (let t = 0; t < 120; t++) {                     // up to a minute for the module and the render
  if (await evaluate("window.__done === true")) break;
  if (t === 119) throw new Error("the page never finished rendering: " + JSON.stringify(await evaluate("document.title")));
  await new Promise((r) => setTimeout(r, 500));
}
const url = await evaluate("document.querySelector('canvas').toDataURL('image/png')");
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, Buffer.from(url.split(",")[1], "base64"));
console.log(`wrote ${out}`);
await call("Page.close");
ws.close();
