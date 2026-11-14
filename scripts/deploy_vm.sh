#!/usr/bin/env bash
# Deploy the app and pipeline code to the GCP worker, restart the live app, and smoke-test it.
#
#   bash scripts/deploy_vm.sh              # deploy committed HEAD, restart grantha-app, smoke test
#   bash scripts/deploy_vm.sh --no-restart # copy code only (e.g. while a protocol run is going)
#   bash scripts/deploy_vm.sh --check      # smoke test the live app only
#
# Ships the tracked files of HEAD under app/ pipeline/ scripts/ tests/ web/ (git archive: LF line endings, no
# untracked or uncommitted files). It never touches data/, reports/, web/data/ or web/fixtures/ on the VM. Before overwriting, every file
# that would change is copied to /opt/grantha/backup/pre_deploy_<time>/ on the VM.
set -euo pipefail

PROJECT=${GRANTHA_PROJECT:-project-dab42af9-0f52-4527-b40}
ZONE=${GRANTHA_ZONE:-us-central1-a}
VM=${GRANTHA_VM:-grantha-worker-eng}
REMOTE=/opt/grantha
PATHS=(app pipeline scripts tests web)
cd "$(git rev-parse --show-toplevel)"

ssh_vm() { gcloud compute ssh "$VM" --zone "$ZONE" --project "$PROJECT" --quiet --command "$1" 2>&1 | grep -v -iE "^(Updating|Waiting)" || true; }

smoke() {
  local ip; ip=$(gcloud compute instances describe "$VM" --zone "$ZONE" --project "$PROJECT" \
                 --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
  local base="http://$ip:8000" fail=0
  echo "smoke test $base"
  local id; id=$(curl -s --max-time 30 "$base/api/clusters" >/dev/null && \
                 curl -s --max-time 30 "$base/api/triage?limit=1" | python -c "import json,sys; print(json.load(sys.stdin)['rows'][0]['identifier'])" 2>/dev/null || true)
  for path in /api/health /api/clusters "/api/triage?limit=5" /check.html /index.html \
              ${id:+"/api/documents/$id" "/api/related/$id" "/api/suggest/$id" "/api/triage/$id" "/api/editions/$id"}; do
    local code; code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 60 "$base$path")
    printf '  %-60s %s\n' "$path" "$code"; [ "$code" = 200 ] || fail=1
  done
  local code; code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 60 -X POST "$base/api/batch" \
                     -H "Content-Type: application/json" -d "{\"identifiers\": [\"${id:-none}\", \"no-such-book\"]}")
  printf '  %-60s %s\n' "POST /api/batch" "$code"; [ "$code" = 200 ] || fail=1
  [ "$fail" = 0 ] && echo "smoke test passed" || { echo "SMOKE TEST FAILED"; return 1; }
}

[ "${1:-}" = "--check" ] && { smoke; exit; }

[ -z "$(git status --porcelain -- "${PATHS[@]}")" ] || echo "note: uncommitted changes under ${PATHS[*]} are NOT deployed (HEAD only)"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
# web/data and web/fixtures are written on the VM by the pipeline (export, make_fixtures): never overwrite them
git archive --format=tar.gz -o "$tmp/code.tgz" HEAD "${PATHS[@]}" ':(exclude)web/data' ':(exclude)web/fixtures'
echo "deploying $(git rev-parse --short HEAD) ($(tar tzf "$tmp/code.tgz" | grep -vc '/$') files) to $VM"
gcloud compute scp --zone "$ZONE" --project "$PROJECT" --quiet "$tmp/code.tgz" "$VM:/tmp/grantha_code.tgz" >/dev/null

ssh_vm "set -e; cd $REMOTE; B=backup/pre_deploy_\$(date -u +%Y%m%dT%H%M%S); n=0
  for f in \$(tar tzf /tmp/grantha_code.tgz | grep -v '/\$'); do
    if [ -f \"\$f\" ]; then mkdir -p \"\$B/\$(dirname \"\$f\")\"; cp -p \"\$f\" \"\$B/\$f\"; n=\$((n+1)); fi
  done
  tar xzf /tmp/grantha_code.tgz && rm /tmp/grantha_code.tgz
  echo \"backup of \$n files in $REMOTE/\$B\"; echo '$(git rev-parse HEAD)' > DEPLOYED_COMMIT"

if [ "${1:-}" != "--no-restart" ]; then
  ssh_vm "sudo systemctl restart grantha-app && sleep 8 && systemctl is-active grantha-app && \
          journalctl -u grantha-app -n 5 --no-pager | cut -c1-160"
  smoke
fi
