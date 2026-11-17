# Home server: deploy only commits that passed CI

Instructions for Claude Code running on the Linux machine that hosts the live Grantha app.
Karthik will start you there with something like: *"Read docs/ops/home-server-cd.md and do it."*

## Context

- **Repo:** `github.com/rohannes64/Grantha-Heritage-Tracker`. Owner: Karthik (GitHub `rohannes64`, commits as "Vemuri Rohan").
- **Live app:** runs on this machine and is served at `https://grantha.tail7ee38f.ts.net/` (Tailscale).
- **Current deploy:** a **systemd service polls GitHub every 60 s** and redeploys when `main` gets a new commit.
- **CI:** the `ci/github-actions` branch adds GitHub Actions (`.github/workflows/`):
  - `ci.yml` (workflow name **CI**): on every push to `main` it runs two jobs. `test` covers lint, pytest with Tesseract and `scripts/check_claims.py`; `image` builds the Docker image, waits for its health check and runs `scripts/ci_smoke.sh`.
  - `publish.yml`: after CI passes on `main`, pushes `ghcr.io/rohannes64/grantha:<sha>` and `:latest`.
  - `deploy.yml`: deploys to an old GCE VM. It is **not used for this machine** and stays inactive, because its repository variables are never set. Don't set them.
- **The problem:** the poller deploys every new commit, even one CI failed on. GitHub can't push to a home PC behind NAT, so the gate belongs in the poller. This is pull-based delivery, the same model GitOps tools such as Argo CD use.

## Goal

Change the existing poller so that it:
1. Deploys a new `main` commit only after its **CI** run for that commit has **succeeded**.
2. Checks the app after each deploy and **rolls back** to the previous commit if the check fails.
3. Reinstalls Python packages only when the app's requirements files changed.
4. Records each deploy as a GitHub **deployment** in environment `production`. Then `python scripts/dora_metrics.py --repo rohannes64/Grantha-Heritage-Tracker` reports the DORA metrics: deployment frequency, lead time, change failure rate and time to restore.

Keep what already works: the service name, the 60 s cadence, the app's run command, its data folders and how it is served.

## Step 1: Read the current setup before changing anything

Find out and write down (in your final report):
- **The unit:** `systemctl list-units --type=service --all | grep -i -E 'grantha|heritage|poll|deploy'`, then `systemctl cat <unit>` for the poller and for the app. There may be one unit or two, plus a timer.
- **The poller script:**
  - Which branch does it watch?
  - How does it detect a new commit (`git fetch`/`ls-remote` or the GitHub API)?
  - How does it update the code (`git pull`, `reset --hard`, or a fresh clone)?
  - How does it restart the app?
  - Does it run `pip install`?
- **How the app runs:** a venv plus uvicorn, or `docker compose`? Which user runs it, and from which folder?
- **Local, untracked data the deploy must never touch:**
  - for example `data/`, `reports/`, `web/data/galaxy_umap.json`, `.env`;
  - `git status --short --ignored` in the deploy folder lists them.
- **Tokens:** is a GitHub token already used? Note where it is stored, never its value.

If the poller does something these instructions don't cover, adapt the plan to it. If the setup is very different (for example, no git checkout at all), stop and ask Karthik.

## Step 2: GitHub access

- **Polling:** keep using `git ls-remote origin refs/heads/main` (or `git fetch`). That costs no API quota.
- **When to call the API:** only when a new SHA appears. Without a token the API allows 60 requests an hour.
- **Token, needed for step 5:**
  - Karthik should create a **fine-grained personal access token** limited to this one repository, with **Actions: read**, **Contents: read** and **Deployments: read and write**.
  - Store it in a root-owned file such as `/etc/grantha/github.env` (`GITHUB_TOKEN=...`, `chmod 600`) and load it with `EnvironmentFile=` in the poller unit.
  - **Never** write it into the repo, a script, the unit's `Environment=` line, logs or chat. Ask Karthik to create the token and paste it into the file himself.

## Step 3: The CI gate

For a new commit `SHA` on `main`:

```
GET https://api.github.com/repos/rohannes64/Grantha-Heritage-Tracker/actions/runs?head_sha=SHA&event=push&branch=main
```

1. Pick the run whose `path` is `.github/workflows/ci.yml`. If there are several (re-runs), use the newest by `run_number`.
2. Act on its state:

| Run state | Action |
|---|---|
| no run yet, or `status` != `completed` | **wait**: deploy nothing, check again next cycle (CI takes a few minutes) |
| `conclusion == "success"` | **deploy** |
| any other conclusion (`failure`, `cancelled`, `timed_out`, …) | **skip**: keep the running version, log it, remember the SHA so it is not checked again |
| still not completed after 60 minutes | **skip** and log "CI did not finish" |

3. **Handle the switch-over:**
   - Commits from before CI existed have no run.
   - If `git cat-file -e SHA:.github/workflows/ci.yml` fails, that commit has no CI. Deploy it the old way and log "no CI in this commit".
   - Once `ci.yml` is on `main`, every commit must pass the gate.
4. **Batches:** if several commits arrived together, only the newest matters. Gate and deploy that one. If CI failed on the newest, don't fall back to an older commit; wait for the next push.
5. **State:** keep it in a small file, for example `/var/lib/grantha-deploy/state.json`, so a restart doesn't redeploy or recheck. Record the last deployed SHA, the previous SHA (for rollback) and the skipped SHAs.

## Step 4: Deploy, check, roll back

1. **Update the code:**
   - Run `git fetch origin`, then move the working tree to `SHA` the same way the poller does now (for example `git reset --hard SHA` on the deploy branch).
   - **Never** run `git clean`. It would delete the local data from step 1.
2. **Dependencies:**
   - If `git diff --name-only OLD SHA -- requirements-app.txt requirements-pipeline.txt` is not empty, run `pip install -r requirements-pipeline.txt -r requirements-app.txt` in the app's venv.
   - Do **not** install `requirements-ci.txt` (CI-only tools) or `requirements-ml.txt` (PyTorch; only for local encoders).
   - If the app runs under Docker instead, rebuild or pull the image instead. `ghcr.io/rohannes64/grantha:<SHA>` already passed CI and a Trivy scan. If the package is private, log in with a token that has `read:packages`.
3. **Restart** the app service, using the command already in use.
4. **Check:**
   - Poll `http://127.0.0.1:<port>/api/health` for up to 90 s until it returns `"status": "ok"`.
   - Then run `bash scripts/ci_smoke.sh http://127.0.0.1:<port>`. It exits 1 on any failure.
   - Find the port from the unit; it is 8000 by default.
5. **On failure:**
   - Reset to the previous SHA, reinstall dependencies if they differ, restart, and check again.
   - Mark the new SHA as failed, so it is skipped and never retried.
   - Log both outcomes clearly (`journalctl -u <poller>`).

## Step 5: Record deployments (for DORA metrics)

Around step 4, with the token from step 2:

1. Create the deployment:
   ```
   POST /repos/rohannes64/Grantha-Heritage-Tracker/deployments
   {"ref": "SHA", "environment": "production", "auto_merge": false, "required_contexts": [], "description": "home server"}
   ```
   - `required_contexts: []` because step 3 already checked CI.
   - The response's `id` is used below.
2. Post statuses:
   - Before restarting: `POST .../deployments/{id}/statuses {"state": "in_progress"}`.
   - After the check: `{"state": "success", "environment_url": "https://grantha.tail7ee38f.ts.net/"}` or `{"state": "failure"}`.
3. A rollback is not a new deployment: the failed one stays `failure`. That is what change failure rate and time to restore count.
4. If the API is unreachable, still deploy. Log that the record was not made; don't block the deploy on it.
5. Check: `python3 scripts/dora_metrics.py --repo rohannes64/Grantha-Heritage-Tracker --days 30` should show the deploys.

## Step 6: Test before switching over

Add `--once` and `--dry-run` flags to the poller, or a test mode set by an environment variable, that run one cycle against a given SHA and print the decision without acting. Then:
1. A commit with no `ci.yml` (any commit before the CI branch was merged) → "no CI, deploy".
2. A commit whose CI succeeded → "deploy" (after the CI branch is merged, any green run on `main`).
3. A commit whose CI failed → "skip". If none exists on `main`, point the check at a failed run on another branch, or fake the API response in a unit test.
4. One real cycle: push a harmless commit to `main` (Karthik does the push). Watch the gate wait for CI, deploy, pass the check, and the deployment appear under the repo's **Deployments** tab.
5. Rollback: in a scratch copy, or by asking Karthik first, break `/api/health` on purpose and confirm the poller rolls back.

## Constraints

- Change only the poller, its unit files and the state and secret files above. Don't change the app code; if the app needs a change, tell Karthik.
- Don't push and don't commit to the repo unless Karthik asks.
- **Commits:**
  - Never add Claude as an author or co-author: no `Co-Authored-By: Claude` trailer, no "Generated with Claude Code" line.
  - Commit under Karthik's name (`git config user.name`) only.
- Never print, log or commit the token.
- After editing units, run `systemctl daemon-reload`. Restart the poller only once the dry-run tests pass, and keep a copy of the old poller script and unit (for example `*.bak-<date>`) so Karthik can go back.
- Ask Karthik before anything you can't undo.

## Also recommend to Karthik

The poller runs whatever lands on `main`, so anyone who can push there can run code on this machine. On GitHub, Karthik should go to Settings → Branches, add a rule for `main` that requires the **CI** checks (`test`, `image`) to pass before merging, and limit who can push.

## Report back

When done, give Karthik a short summary:
- what the poller looked like before (step 1 findings);
- what changed (files and units);
- where the token and state live (paths only);
- the dry-run and live test results;
- how to undo the change.
