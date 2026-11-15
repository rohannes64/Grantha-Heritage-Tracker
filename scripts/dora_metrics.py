"""DORA metrics from this repository's GitHub deployments (the `production` environment of .github/workflows/deploy.yml).

    python scripts/dora_metrics.py --repo rohannes64/Grantha-Heritage-Tracker [--days 30] [--env production]

Prints a Markdown table (the deploy workflow appends it to the run summary). GITHUB_TOKEN is used if set.

  Deployment frequency   successful deploys per week in the window
  Lead time for changes  median time from the deployed commit to its successful deploy
  Change failure rate    failed deploys / finished deploys
  Time to restore        median time from a failed deploy to the next successful one

Lead time uses the deployed (head) commit only, so it understates the wait of older commits in the same deploy.
Standard library only, so it runs on a bare CI runner.
"""
import argparse
import json
import os
import statistics
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"


def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fetch(repo, env, since):
    """One record per deployment in the window: created time, final state, commit time."""
    out = []
    for d in _get(f"{API}/repos/{repo}/deployments?environment={env}&per_page=100"):
        created = _ts(d["created_at"])
        if created < since:
            continue
        statuses = _get(d["statuses_url"] + "?per_page=20")       # newest first
        state = statuses[0]["state"] if statuses else "pending"
        finished = _ts(statuses[0]["created_at"]) if statuses else None
        commit = _get(f"{API}/repos/{repo}/commits/{d['sha']}")
        out.append({"created": created, "finished": finished, "state": state,
                    "commit_time": _ts(commit["commit"]["committer"]["date"])})
    return out


def compute(deploys, days):
    """deploys: dicts with created, finished, state, commit_time. Returns the four metrics (None if no data)."""
    done = sorted((d for d in deploys if d["state"] in ("success", "failure", "error")), key=lambda d: d["created"])
    ok = [d for d in done if d["state"] == "success"]
    failed = [d for d in done if d["state"] != "success"]
    lead = [(d["finished"] - d["commit_time"]).total_seconds() / 3600 for d in ok if d["finished"]]
    restore, open_failure = [], None
    for d in done:
        if d["state"] != "success":
            open_failure = open_failure or d["created"]
        elif open_failure and d["finished"]:
            restore.append((d["finished"] - open_failure).total_seconds() / 3600)
            open_failure = None
    return {
        "deploys": len(done),
        "per_week": round(len(ok) / (days / 7), 2),
        "lead_time_h": round(statistics.median(lead), 2) if lead else None,
        "change_failure_rate": round(len(failed) / len(done), 3) if done else None,
        "time_to_restore_h": round(statistics.median(restore), 2) if restore else None,
    }


def markdown(m, days, env):
    fmt = lambda v, unit="": "no data" if v is None else f"{v}{unit}"
    cfr = "no data" if m["change_failure_rate"] is None else f"{m['change_failure_rate'] * 100:.1f}%"
    return "\n".join([
        f"### DORA metrics: `{env}`, last {days} days ({m['deploys']} finished deploys)",
        "", "| Metric | Value |", "|---|---|",
        f"| Deployment frequency | {m['per_week']} per week |",
        f"| Lead time for changes (median) | {fmt(m['lead_time_h'], ' h')} |",
        f"| Change failure rate | {cfr} |",
        f"| Time to restore (median) | {fmt(m['time_to_restore_h'], ' h')} |", ""])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--env", default="production")
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args()
    since = datetime.now(timezone.utc) - timedelta(days=a.days)
    print(markdown(compute(fetch(a.repo, a.env, since), a.days), a.days, a.env))


if __name__ == "__main__":
    main()
