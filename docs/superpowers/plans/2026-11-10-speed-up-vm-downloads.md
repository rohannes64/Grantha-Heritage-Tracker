# Speed Up VM Harvesting and Download Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accelerate Grantha book harvesting from Internet Archive by 7x–10x across the 7-node GCP cluster by eliminating sequential bottlenecks, parallelizing book-level downloads, tuning request pacing per IP, and optimizing image download sizes without triggering 429 rate limits.

**Architecture:** 
1. Refactor `pipeline/harvest.py` from sequential single-book harvesting to a multi-threaded producer-consumer book pipeline (`ThreadPoolExecutor` across books and pages).
2. Tune `pipeline/ia.py` rate-limiter and connection pooling (`HTTPAdapter` pool size, adaptive exponential backoff on 429/503, reduced baseline request interval from 1.0s to 0.15s–0.25s per distinct VM IP).
3. Switch page downloads from on-the-fly resized images (`_w1200.jpg`, which triggers slow server-side re-rendering on Archive.org) to pre-generated fast thumbs or direct stream downloads.
4. Distribute the updated pipeline across all 7 cloud VMs and benchmark throughput.

**Tech Stack:** Python 3.10+, `requests` (Session, HTTPAdapter, urllib3 retry), `concurrent.futures.ThreadPoolExecutor`, SQLite3 (WAL mode for concurrent writes), Google Cloud Platform compute instances.

**Spec:** Codebase in `D:\int396proj\Grantha-Heritage-Tracker-main\Grantha-Heritage-Tracker-main` (`pipeline/harvest.py`, `pipeline/ia.py`, `pipeline/config.py`).

## Global Constraints

- Must respect Archive.org's terms of service and not trigger permanent IP bans (adaptive backoff on HTTP 429/503).
- Each VM has a distinct external IP address (7 separate public IPs), allowing per-node rate budgets up to 5–8 req/sec (35–50 req/sec cluster-wide).
- Preserve SQLite database integrity: when multiple threads harvest books concurrently, database writes must either use WAL mode with timeouts or route writes through a single queue/writer thread.
- Ensure all 8 languages can scale to 2,000 books without memory leaks or open file descriptor exhaustion (`ulimit`).

## Review Focus

1. **SQLite concurrency lock contention**: Multiple threads writing to `data/corpus.sqlite` simultaneously can cause `sqlite3.OperationalError: database is locked`. (Mitigation: enable WAL mode + connection timeout, or use a serialized thread writer).
2. **Archive.org HTTP 429 / 503 Rate Limiting**: If bursts exceed Archive.org's threshold, client must exponentially back off without failing the entire batch.
3. **Connection pool exhaustion**: Default `requests.Session` has a pool size of 10. Multi-threading across books + pages will exhaust this unless `HTTPAdapter(pool_maxsize=32)` is configured.
4. **Memory growth under multi-threading**: Downloading multiple book page images simultaneously could cause OOM on `e2-standard-4` (16 GB RAM) if buffered in RAM. (Must stream directly to disk).
5. **Partial / Corrupted Page Downloads**: High-speed network streaming could occasionally truncate JPEGs. (Must verify file size and image validity before marking harvested).

---

### Task 1: Optimize IAClient Connection Pooling & Adaptive Pacing

**Files:**
- Modify: `pipeline/config.py:30-40`
- Modify: `pipeline/ia.py:10-50`
- Test: `tests/test_ia_speed.py`

**Interfaces:**
- Consumes: `config.REQUEST_INTERVAL`, `config.USER_AGENT`
- Produces: `IAClient(interval=0.2, max_pool=32)` with adaptive throttling and HTTP connection reuse.

- [x] **Step 1: Write the failing test for optimized connection pool and pacing**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Implement optimized pool and pacing in `pipeline/ia.py` and `pipeline/config.py`**
- [x] **Step 4: Run test to verify it passes**
- [x] **Step 5: Commit changes**

```bash
git add pipeline/config.py pipeline/ia.py tests/test_ia_speed.py
git commit -m "perf: optimize IAClient connection pool and adaptive rate pacing"
```

---

### Task 2: Implement Multi-Book Concurrent Harvesting & Thread-Safe SQLite WAL

**Files:**
- Modify: `pipeline/db.py:40-51`
- Modify: `pipeline/harvest.py:120-190`
- Test: `tests/test_concurrent_harvest.py`

**Interfaces:**
- Consumes: `sampling.stratified_order()`, `harvest_one()`
- Produces: `harvest_language(client, con, lang, target, book_workers=4)` parallel book downloader.

- [x] **Step 1: Write the failing test for concurrent harvesting**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Implement WAL mode in `pipeline/db.py` and multi-book worker pool in `pipeline/harvest.py`**
- [x] **Step 4: Run test to verify it passes**
- [x] **Step 5: Commit changes**

---

### Task 3: Deploy Accelerated Harvester to GCP Fleet & Benchmark Speed

**Files:**
- Create: `scripts/deploy_accelerated_harvester.py`
- Modify: `scripts/cloud_worker_daemon.py`

**Interfaces:**
- Consumes: Updated `pipeline/` package on local workspace
- Produces: 7 live workers running the accelerated multi-threaded downloader with real-time speed benchmarking.

- [x] **Step 1: Write deployment script `scripts/deploy_accelerated_harvester.py`**
- [x] **Step 2: Test script on a single worker (`grantha-worker-hin`) in dry-run mode**
- [x] **Step 3: Roll out across the remaining 6 instances**
- [x] **Step 4: Verify live cluster throughput and rate stability**
