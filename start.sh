#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"
else
  export PYTHONPATH="$PROJECT_ROOT/src"
fi

echo "PYTHONPATH set to: $PYTHONPATH"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Error: docker compose (or docker-compose) is required to start Redis."
  exit 1
fi

echo "Starting Redis container..."
"${COMPOSE_CMD[@]}" up -d redis

if [[ ! -d "venv" ]]; then
  echo "Creating virtual environment at venv..."
  python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

if [[ -f "requirements.txt" ]]; then
  echo "Installing dependencies from requirements.txt..."
  pip3 install -r requirements.txt
else
  echo "requirements.txt not found. Skipping dependency installation."
fi

echo "Running tests..."
pytest

echo "Starting ACTS..."
python3 -m acts
