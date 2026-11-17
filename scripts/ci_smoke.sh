#!/usr/bin/env bash
# Smoke-test a running app image: the routes that work from the image alone (no VM data, no API key).
#
#   bash scripts/ci_smoke.sh [base-url]      # default http://localhost:8000; exit 1 if any check fails
#
# The deeper per-book routes (triage, related, editions, batch) need the VM's reports/ folder and are
# smoke-tested after each deploy by scripts/deploy_vm.sh instead.
set -uo pipefail
base=${1:-http://localhost:8000}
PY=${PYTHON:-python3}        # set PYTHON=python where python3 is missing (Windows)
fail=0

check() {   # check <path> [python expression on the JSON body `j`]
  local path=$1 expr=${2:-} body code
  body=$(curl -s --max-time 60 -w '\n%{http_code}' "$base$path")
  code=${body##*$'\n'}; body=${body%$'\n'*}
  if [ "$code" != 200 ]; then
    printf '  %-28s %s FAIL\n' "$path" "$code"; fail=1; return
  fi
  if [ -n "$expr" ] && ! printf '%s' "$body" | "$PY" -c "import json,sys; j=json.load(sys.stdin); sys.exit(0 if ($expr) else 1)"; then
    printf '  %-28s %s FAIL (body: %s)\n' "$path" "$code" "${body:0:120}"; fail=1; return
  fi
  printf '  %-28s %s ok\n' "$path" "$code"
}

echo "smoke test $base"
check /api/health                 "j['status'] == 'ok' and j['documents'] > 0"
check /api/clusters               "len(j) > 0"
check "/api/clusters?method=dbscan"
check /api/study
check /index.html
check /check.html
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$base/api/clusters?method=nope")
printf '  %-28s %s %s\n' "/api/clusters?method=nope" "$code" "$([ "$code" = 400 ] && echo ok || echo 'FAIL (want 400)')"
[ "$code" = 400 ] || fail=1

[ "$fail" = 0 ] && echo "smoke test passed" || { echo "SMOKE TEST FAILED"; exit 1; }
