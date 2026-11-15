#!/usr/bin/env bash
# On the VM, after run_protocol.sh has finished: evaluate the user features, record fixtures from the new
# model, and regenerate the facts every deliverable reads. Writes reports/features/*.json, web/fixtures/,
# reports/deliverable_facts.json. Then, on the laptop: pull those, rebuild the deck, deploy_vm.sh.
#
#   cd /opt/grantha && bash scripts/post_run.sh
#
# Class suggestion and the edition finder are evaluated on the train-only fit (held-out books never seen by
# the model). run_protocol.sh overwrites that fit with the all-books refit, so snapshot_trainfit.sh copies it to
# data/processed_trainfit/ the moment the test evaluation ends; the evaluations read it from there.
set -euo pipefail
cd /opt/grantha
PY=venv/bin/python3
TRAIN=data/processed_trainfit
log() { echo "=== $(date -u +%FT%TZ) $*"; }

grep -q "DONE pipeline.figures" data/logs/protocol_20261114.log || { echo "protocol run not finished"; exit 1; }
[ -f "$TRAIN/features.joblib" ] || { echo "no train-fit snapshot in $TRAIN (see data/logs/snapshot_trainfit.log)"; exit 1; }

on_train_fit() {   # run a module's main() with config.PROCESSED pointed at the train-fit snapshot
  "$PY" - "$TRAIN" "$@" <<'PY'
import runpy, sys
from pathlib import Path
from pipeline import config
config.PROCESSED = Path(sys.argv[1]).resolve()
module, sys.argv = sys.argv[2], [sys.argv[2]] + sys.argv[3:]
runpy.run_module(module, run_name="__main__")
PY
}

log "related books (centred vs uncentred, train books)";   "$PY" -m pipeline.related_eval
log "scan triage (AUC against OCR agreement)";             "$PY" -m pipeline.triage
log "class suggestion (train-only fit, test books)";       on_train_fit pipeline.suggest_eval --split test
log "edition finder (train-only fit, test books)";         on_train_fit pipeline.editions
log "fixtures from the new model";                         "$PY" -W ignore scripts/make_fixtures.py
log "deliverable facts";                                    "$PY" scripts/deliverable_facts.py
ls -la reports/features/
log "done: on the laptop pull reports/features, reports/deliverable_facts.json, web/fixtures, web/data"
