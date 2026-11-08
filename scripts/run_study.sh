#!/usr/bin/env bash
# Everything after OCR, in order, inside the pipeline image. Log: data/logs/study_run.log
set -euo pipefail
cd "$(dirname "$0")/.."
run() { MSYS_NO_PATHCONV=1 docker compose run --rm -T pipeline "$@"; }
run python -m pipeline.ocr --ingest
run python -m pipeline.quality
run python -m pipeline.preprocess
run python -m pipeline.features
run python -m pipeline.study
run python -m pipeline.export
run python -m pipeline.figures
echo "STUDY RUN COMPLETE"
