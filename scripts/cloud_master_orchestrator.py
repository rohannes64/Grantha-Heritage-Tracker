"""
Grantha Heritage Tracker - Autonomous Cloud Master Orchestrator
Runs as a systemd service on grantha-worker-eng (Master VM) on port 8000.

Lifecycle:
1. FLEET_HARVEST_OCR: Serves live web dashboard, tracks all 7 workers until harvest & OCR complete.
2. SHARD_MERGE: Fetches all remote corpus databases, merges into master SQLite, cleanly powers down worker VMs.
3. PIPELINE_RUN: Runs quality, preprocess, Gemini feature extraction, study, evaluate, and export.
4. LAUNCH_APP: Yields port 8000 and seamlessly replaces process with production FastAPI Grantha app (os.execv).
"""
import http.server
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request

WORK_DIR = "/opt/grantha"
DATA_DIR = os.path.join(WORK_DIR, "data")
SHARDS_DIR = os.path.join(DATA_DIR, "shards")
CORPUS_DB = os.path.join(DATA_DIR, "corpus.sqlite")
BUNDLE_FILE = os.path.join(DATA_DIR, "model", "bundle.joblib")
ORCH_LOG = os.path.join(WORK_DIR, "orchestrator.log")

WORKERS = [
    {"name": "grantha-worker-eng", "lang": "English (eng)", "ip": "127.0.0.1", "target": 2000, "is_master": True},
    {"name": "grantha-worker-hin", "lang": "Hindi (hin)", "ip": "10.128.0.8", "target": 2000, "is_master": False},
    {"name": "grantha-worker-san", "lang": "Sanskrit (san)", "ip": "10.128.0.9", "target": 2000, "is_master": False},
    {"name": "grantha-worker-ben", "lang": "Bengali (ben)", "ip": "10.128.0.10", "target": 2000, "is_master": False},
    {"name": "grantha-worker-guj", "lang": "Gujarati (guj)", "ip": "10.128.0.11", "target": 2000, "is_master": False},
    {"name": "grantha-worker-tel", "lang": "Telugu (tel)", "ip": "10.128.0.12", "target": 2000, "is_master": False},
    {"name": "grantha-worker-kan-tam", "lang": "Kannada + Tamil", "ip": "10.128.0.13", "target": 4000, "is_master": False},
]

STATE = {
    "stage": "FLEET_HARVEST_OCR",
    "stage_detail": "Distributed Harvest & Parallel OCR across 7 Cloud VMs",
    "start_time": time.time(),
    "workers": {},
    "total_harvested": 0,
    "total_pages": 0,
    "target_books": 16000,
    "eta_seconds": None,
    "recent_logs": [],
}

server_instance = None

def log(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry, flush=True)
    try:
        with open(ORCH_LOG, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass
    STATE["recent_logs"].append(entry)
    if len(STATE["recent_logs"]) > 50:
        STATE["recent_logs"].pop(0)

def poll_worker(worker):
    ip = worker["ip"]
    url = f"http://{ip}:8080/status"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GranthaMaster/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "name": worker["name"],
                "lang": worker["lang"],
                "target": worker["target"],
                "harvested": data.get("harvested", 0),
                "ocr_pages": data.get("ocr_pages", 0),
                "state": data.get("state", "Running"),
                "is_done": data.get("is_done", False),
                "online": True
            }
    except Exception:
        return {
            "name": worker["name"],
            "lang": worker["lang"],
            "target": worker["target"],
            "harvested": 0,
            "ocr_pages": 0,
            "state": "Node Active",
            "is_done": False,
            "online": False
        }

def merge_sqlite_databases():
    log("Starting Shard Database Merge into master corpus.sqlite...")
    os.makedirs(DATA_DIR, exist_ok=True)
    master_con = sqlite3.connect(CORPUS_DB)
    cur = master_con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        identifier TEXT PRIMARY KEY, lang_tag TEXT NOT NULL, era TEXT NOT NULL,
        sample_rank INTEGER NOT NULL, title TEXT, creator TEXT, date_raw TEXT,
        year INTEGER, publisher TEXT, source_library TEXT, scanning_centre TEXT,
        subject_field TEXT, classification TEXT, total_pages INTEGER,
        ia_ocr_files TEXT, status TEXT NOT NULL DEFAULT 'drawn', note TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        identifier TEXT NOT NULL, leaf INTEGER NOT NULL, position REAL NOT NULL,
        image_path TEXT, ocr_model TEXT, osd_script TEXT, text TEXT,
        mean_conf REAL, n_words INTEGER, script_ratio REAL, ia_text TEXT,
        ia_similarity REAL, PRIMARY KEY (identifier, leaf)
    )""")
    master_con.commit()

    if os.path.exists(SHARDS_DIR):
        for fname in os.listdir(SHARDS_DIR):
            if fname.endswith(".sqlite"):
                shard_path = os.path.join(SHARDS_DIR, fname)
                log(f"Merging shard: {fname}...")
                try:
                    cur.execute(f"ATTACH DATABASE '{shard_path}' AS shard")
                    cur.execute("INSERT OR REPLACE INTO documents SELECT * FROM shard.documents")
                    cur.execute("INSERT OR REPLACE INTO pages SELECT * FROM shard.pages")
                    master_con.commit()
                    cur.execute("DETACH DATABASE shard")
                    log(f"Successfully merged {fname}")
                except Exception as e:
                    log(f"Error merging {fname}: {e}")

    cur.execute("SELECT COUNT(*) FROM documents WHERE status='harvested'")
    doc_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM pages WHERE text IS NOT NULL")
    page_cnt = cur.fetchone()[0]
    master_con.close()
    log(f"Merged Corpus Stats: {doc_cnt} harvested documents, {page_cnt} OCR pages.")

def run_cmd(cmd_list, desc):
    log(f"--- [Pipeline] {desc} ---")
    log(f"Command: {' '.join(cmd_list)}")
    env = os.environ.copy()
    env["PYTHONPATH"] = WORK_DIR
    env["HERITAGE_FULL_PER_LANG"] = "2000"
    p = subprocess.Popen(cmd_list, cwd=WORK_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    for line in iter(p.stdout.readline, ''):
        line = line.strip()
        if line:
            log(f"  {line}")
    p.wait()
    if p.returncode != 0:
        log(f"WARNING: Command exited with status {p.returncode}")
    else:
        log(f"--- [Pipeline] {desc} COMPLETED SUCCESSFULLY ---")

def orchestrator_loop():
    global server_instance
    log("Grantha Autonomous Master Orchestrator initialized.")
    time.sleep(2)

    # 1. FLEET_HARVEST_OCR
    last_count = 0
    start_time = time.time()
    while True:
        all_done = True
        total_h = 0
        total_p = 0
        results = {}
        for w in WORKERS:
            res = poll_worker(w)
            results[w["name"]] = res
            total_h += res["harvested"]
            total_p += res["ocr_pages"]
            if not res["is_done"]:
                all_done = False

        STATE["workers"] = results
        STATE["total_harvested"] = total_h
        STATE["total_pages"] = total_p

        elapsed = time.time() - start_time
        remaining = 16000 - total_h
        if total_h > 50 and elapsed > 10:
            rate = total_h / elapsed  # books per sec
            STATE["eta_seconds"] = int(remaining / rate) if rate > 0 else 3600
        else:
            STATE["eta_seconds"] = 3600

        if total_h != last_count:
            last_count = total_h
            eta_m = (STATE['eta_seconds'] // 60) if STATE['eta_seconds'] else 0
            log(f"Fleet Progress: {total_h}/16000 books ({total_h/160.0:.1f}%), {total_p} pages. Est ETA: ~{eta_m}m")

        if all_done and total_h >= 2500:
            log(f"ALL 7 WORKERS HAVE COMPLETED HARVEST AND OCR! ({total_h} total books)")
            break

        time.sleep(15)

    # 2. SHARD_MERGE
    STATE["stage"] = "SHARD_MERGE"
    STATE["stage_detail"] = "Ingesting distributed SQLite databases from all 7 VMs"
    log("Transitioned to stage: SHARD_MERGE")
    os.makedirs(SHARDS_DIR, exist_ok=True)

    for w in WORKERS:
        if w["is_master"]:
            continue
        ip = w["ip"]
        log(f"Downloading SQLite database from {w['name']} ({ip})...")
        shard_file = os.path.join(SHARDS_DIR, f"{w['name']}.sqlite")
        try:
            urllib.request.urlretrieve(f"http://{ip}:8080/corpus.sqlite", shard_file)
            log(f"Downloaded {shard_file} ({os.path.getsize(shard_file)} bytes).")
            log(f"Triggering shutdown for {w['name']} to release VM billing...")
            req = urllib.request.Request(f"http://{ip}:8080/shutdown", method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            log(f"Error handling worker {w['name']}: {e}")

    merge_sqlite_databases()

    # 3. PIPELINE_RUN
    STATE["stage"] = "PIPELINE_RUN"
    py = os.path.join(WORK_DIR, "venv", "bin", "python3")
    if not os.path.exists(py):
        py = sys.executable

    STATE["stage_detail"] = "Running Data Quality & Sampling Audit"
    run_cmd([py, "-m", "pipeline.quality"], "Quality Audit")

    STATE["stage_detail"] = "Running Text Preprocessing & Script Normalization"
    run_cmd([py, "-m", "pipeline.preprocess"], "Corpus Preprocessing")

    STATE["stage_detail"] = "Running Google Cloud Vertex AI Multilingual Embedding Extraction"
    run_cmd([py, "-m", "pipeline.features", "--only", "V"], "Vertex AI Multilingual Embedding Extraction")

    STATE["stage_detail"] = "Running Comparative Topic Clustering (HDBSCAN / DBSCAN)"
    run_cmd([py, "-m", "pipeline.study"], "Topic Clustering Study")

    STATE["stage_detail"] = "Evaluating Cluster Stability & Silhouette Scores"
    run_cmd([py, "-m", "pipeline.evaluate"], "Model Evaluation")

    STATE["stage_detail"] = "Exporting Deployment Bundle & Visual Artifacts"
    run_cmd([py, "-m", "pipeline.export"], "Bundle Packaging")

    # 4. LAUNCH_APP
    STATE["stage"] = "LAUNCH_APP"
    STATE["stage_detail"] = "Production FastAPI Web Application Running"
    log("Autonomous Pipeline Execution Finished! Seamlessly transitioning to FastAPI application...")

    time.sleep(2)
    if server_instance:
        try:
            server_instance.server_close()
        except Exception:
            pass

    log("Executing uvicorn app.main:app on 0.0.0.0:8000 via os.execv...")
    uvicorn_bin = os.path.join(WORK_DIR, "venv", "bin", "uvicorn")
    if not os.path.exists(uvicorn_bin):
        uvicorn_bin = "uvicorn"
    os.execv(uvicorn_bin, [uvicorn_bin, "app.main:app", "--host", "0.0.0.0", "--port", "8000"])

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Grantha Heritage Tracker - Autonomous Cloud Training</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #090d16;
    --card: #111827;
    --border: #1f293d;
    --primary: #38bdf8;
    --primary-glow: rgba(56, 189, 248, 0.25);
    --accent: #818cf8;
    --success: #34d399;
    --warn: #fbbf24;
    --text: #f3f4f6;
    --subtext: #9ca3af;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background-color: var(--bg);
    color: var(--text);
    font-family: 'Plus Jakarta Sans', sans-serif;
    padding: 30px 20px;
    min-height: 100vh;
  }
  .container { max-width: 1200px; margin: 0 auto; }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 25px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 30px;
  }
  .brand { display: flex; align-items: center; gap: 14px; }
  .logo-icon {
    width: 44px; height: 44px;
    background: linear-gradient(135deg, #38bdf8, #818cf8);
    border-radius: 12px;
    display: grid; place-items: center;
    font-size: 22px; font-weight: 800; color: #090d16;
    box-shadow: 0 0 25px var(--primary-glow);
  }
  h1 { font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }
  .subtitle { font-size: 13px; color: var(--subtext); margin-top: 2px; }
  .badge {
    padding: 8px 16px; border-radius: 9999px; font-size: 12px; font-weight: 600;
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(52, 211, 153, 0.1); color: var(--success);
    border: 1px solid rgba(52, 211, 153, 0.3);
  }
  .pulse-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 10px var(--success);
    animation: pulse 1.8s infinite;
  }
  @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.85); } }
  
  .banner {
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.08), rgba(129, 140, 248, 0.08));
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 30px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .banner-text h3 { font-size: 16px; font-weight: 600; margin-bottom: 4px; color: var(--primary); }
  .banner-text p { font-size: 13px; color: var(--subtext); }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 18px;
    margin-bottom: 30px;
  }
  .stat-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px;
  }
  .stat-label { font-size: 12px; color: var(--subtext); text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
  .stat-value { font-size: 28px; font-weight: 800; margin-top: 8px; font-family: 'JetBrains Mono', monospace; }
  .stat-sub { font-size: 12px; color: var(--primary); margin-top: 4px; }

  .stage-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 30px;
  }
  .stage-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
  .stage-title { font-size: 17px; font-weight: 600; }
  .progress-bar-bg {
    width: 100%; height: 12px; background: #1e293b; border-radius: 999px; overflow: hidden;
  }
  .progress-bar-fill {
    height: 100%; background: linear-gradient(90deg, #38bdf8, #818cf8); border-radius: 999px;
    transition: width 0.6s ease;
  }

  .workers-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
    gap: 16px;
    margin-bottom: 30px;
  }
  .worker-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px;
  }
  .worker-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .worker-lang { font-weight: 600; font-size: 15px; }
  .worker-tag { font-size: 11px; padding: 3px 8px; border-radius: 6px; background: #1e293b; color: var(--primary); }
  .worker-metric { display: flex; justify-content: space-between; font-size: 13px; color: var(--subtext); margin-bottom: 8px; }
  .worker-metric span:last-child { font-weight: 600; color: var(--text); font-family: 'JetBrains Mono', monospace; }
  .worker-bar-bg { width: 100%; height: 6px; background: #1e293b; border-radius: 999px; overflow: hidden; margin-top: 10px; }
  .worker-bar-fill { height: 100%; background: var(--primary); border-radius: 999px; transition: width 0.5s ease; }

  .log-card {
    background: #0b0f19;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px;
    font-family: 'JetBrains Mono', monospace;
  }
  .log-title { font-size: 13px; font-weight: 600; color: var(--subtext); margin-bottom: 12px; display: flex; justify-content: space-between; }
  .log-content {
    max-height: 220px; overflow-y: auto; font-size: 12px; line-height: 1.6; color: #a5b4fc;
  }
  .log-line { margin-bottom: 4px; }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="brand">
      <div class="logo-icon">&#x0950;</div>
      <div>
        <h1>Grantha Heritage Tracker</h1>
        <div class="subtitle">Cloud Autonomous Multi-Lingual Topic Pipeline (SIH26096)</div>
      </div>
    </div>
    <div class="badge">
      <div class="pulse-dot"></div>
      <span id="header-status">Cluster Active (Local Offline Ready)</span>
    </div>
  </header>

  <div class="banner">
    <div class="banner-text">
      <h3>&#x2728; Safe to Disconnect</h3>
      <p>This entire workflow is running 100% inside Google Cloud Platform (28 vCPUs across 7 instances). You can safely turn off your computer or close this window.</p>
    </div>
    <div style="font-size: 13px; color: var(--subtext); text-align: right;">
      Auto-refreshing every 3s
    </div>
  </div>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-label">Total Books Harvested</div>
      <div class="stat-value" id="total-harvested">-- / 16,000</div>
      <div class="stat-sub" id="harvest-pct">0.0% Complete</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">OCR Processed Pages</div>
      <div class="stat-value" id="total-ocr">--</div>
      <div class="stat-sub">Across 8 Languages</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Estimated Time Remaining</div>
      <div class="stat-value" id="eta-time">Calculating...</div>
      <div class="stat-sub" id="rate-sub">Real-time dynamic rate</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Active Cloud Compute</div>
      <div class="stat-value">7 VMs / 28 vCPUs</div>
      <div class="stat-sub">Google Cloud us-central1</div>
    </div>
  </div>

  <div class="stage-card">
    <div class="stage-header">
      <div>
        <div class="stage-title" id="stage-detail">Distributed Harvest & Parallel OCR</div>
        <div style="font-size: 13px; color: var(--subtext); margin-top: 4px;" id="stage-badge">Phase 1: Multi-VM Language Shard Harvesting</div>
      </div>
      <div style="font-size: 20px; font-weight: 800; font-family: 'JetBrains Mono', monospace;" id="total-pct">0%</div>
    </div>
    <div class="progress-bar-bg">
      <div class="progress-bar-fill" id="master-bar" style="width: 0%;"></div>
    </div>
  </div>

  <div class="workers-grid" id="workers-grid">
  </div>

  <div class="log-card">
    <div class="log-title">
      <span>AUTONOMOUS CLUSTER PIPELINE TELEMETRY</span>
      <span style="color: var(--success);">&#x25CF; STREAMING</span>
    </div>
    <div class="log-content" id="log-box">
    </div>
  </div>
</div>

<script>
async function update() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    
    document.getElementById('total-harvested').innerText = data.total_harvested.toLocaleString() + ' / ' + data.target_books.toLocaleString();
    const pct = ((data.total_harvested / data.target_books) * 100).toFixed(1);
    document.getElementById('harvest-pct').innerText = pct + '% Target Reached';
    document.getElementById('total-ocr').innerText = data.total_pages.toLocaleString() + ' pgs';
    document.getElementById('total-pct').innerText = pct + '%';
    document.getElementById('master-bar').style.width = pct + '%';

    document.getElementById('stage-detail').innerText = data.stage_detail;
    document.getElementById('stage-badge').innerText = 'Phase: ' + data.stage;

    if (data.eta_seconds !== null && data.eta_seconds > 0) {
      const mins = Math.floor(data.eta_seconds / 60);
      const secs = data.eta_seconds % 60;
      document.getElementById('eta-time').innerText = mins + 'm ' + secs + 's';
      document.getElementById('rate-sub').innerText = 'Auto-advancing on finish';
    }

    if (data.stage === 'LAUNCH_APP') {
      document.getElementById('header-status').innerText = 'Grantha Live Web App Ready! Reloading...';
      setTimeout(() => { window.location.reload(); }, 3000);
    }

    const grid = document.getElementById('workers-grid');
    grid.innerHTML = '';
    for (const [name, w] of Object.entries(data.workers || {})) {
      const card = document.createElement('div');
      card.className = 'worker-card';
      const wpct = Math.min(100, ((w.harvested / w.target) * 100)).toFixed(1);
      card.innerHTML = `
        <div class="worker-top">
          <div class="worker-lang">${w.lang}</div>
          <div class="worker-tag">${w.state}</div>
        </div>
        <div class="worker-metric">
          <span>Harvested</span>
          <span>${w.harvested} / ${w.target}</span>
        </div>
        <div class="worker-metric">
          <span>OCR Pages</span>
          <span>${w.ocr_pages} pgs</span>
        </div>
        <div class="worker-bar-bg">
          <div class="worker-bar-fill" style="width: ${wpct}%"></div>
        </div>
      `;
      grid.appendChild(card);
    }

    const logBox = document.getElementById('log-box');
    logBox.innerHTML = (data.recent_logs || []).map(l => `<div class="log-line">${l}</div>`).join('');
    logBox.scrollTop = logBox.scrollHeight;
  } catch (err) {
    console.error(err);
  }
}
setInterval(update, 3000);
update();
</script>
</body>
</html>
"""

class MasterHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            body = DASHBOARD_HTML.encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            body = json.dumps(STATE).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404)

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    t = threading.Thread(target=orchestrator_loop, daemon=True)
    t.start()

    server_instance = http.server.ThreadingHTTPServer(("0.0.0.0", 8000), MasterHandler)
    log("Master Live Web Dashboard listening on http://0.0.0.0:8000")
    try:
        server_instance.serve_forever()
    except Exception:
        pass
