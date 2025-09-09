#!/usr/bin/env bash
set -euo pipefail

cd /var/www/html

# venv aktiválás
if [[ -d ".venv" ]]; then
  source .venv/bin/activate
else
  echo "ERROR: .venv nem található: /var/www/html/.venv" >&2
  exit 1
fi

export PYTHONPATH=src

# .env betöltés (ha fontos a moduloknak)
if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

echo "[`date '+%F %T'`] Pipeline start"

# 1) Ingest
python -m herculesbet.ingest_theodds || { echo "ingest_theodds FAILED"; exit 1; }

# 2) Model
python -m herculesbet.run_model_poisson || { echo "run_model_poisson FAILED"; exit 1; }

# 3) Pick generálás
python -m herculesbet.generate_picks || { echo "generate_picks FAILED"; exit 1; }

echo "[`date '+%F %T'`] Pipeline OK"

