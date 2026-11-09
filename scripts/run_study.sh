#!/usr/bin/env bash
# Everything after OCR, in order, inside the pipeline image. Log: data/logs/study_run.log
#
#   bash scripts/run_study.sh            # evaluation run (train only) + validation numbers, then the final fit
#   bash scripts/run_study.sh --test     # also records the test-split numbers (run once; docs/evaluation_plan.md)
set -euo pipefail
cd "$(dirname "$0")/.."
run() { MSYS_NO_PATHCONV=1 docker compose run --rm -T pipeline "$@"; }
run python -m pipeline.ocr --ingest
run python -m pipeline.quality
run python -m pipeline.preprocess

# 1. Evaluation run: every fitting step on the train books only.
run python -m pipeline.features --fit train
run python -m pipeline.study
run python -m pipeline.evaluate --split val
if [ "${1:-}" = "--test" ]; then
  run python -m pipeline.evaluate --split test
fi

# 2. Final run: the same settings fitted on every usable book (the app's model and the website).
run python -m pipeline.features --fit all
run python -m pipeline.study
run python -m pipeline.sensitivity
run python -m pipeline.export
run python -m pipeline.figures
echo "STUDY RUN COMPLETE"
