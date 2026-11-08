#!/usr/bin/env bash
# Harvest every language in parallel (one polite connection per language):
# pilot sample first, then continue to the full sample. Logs: data/logs/harvest_<lang>.log
set -u
cd "$(dirname "$0")/.."
mkdir -p data/logs
PY=${PYTHON:-python}
for lang in eng hin san ben guj tel kan tam; do
  (
    PYTHONIOENCODING=utf-8 $PY -m pipeline.harvest --stage pilot --langs "$lang" &&
    PYTHONIOENCODING=utf-8 $PY -m pipeline.harvest --stage full --langs "$lang"
    echo "EXIT $?"
  ) > "data/logs/harvest_${lang}.log" 2>&1 &
done
wait
echo "all languages done"
