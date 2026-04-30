#!/usr/bin/env bash
# local_dev.sh — bootstrap a local dev server with hot reload.
#
# What it does:
#   1. create / reuse a virtualenv at product/server/.venv
#   2. install requirements
#   3. boot uvicorn with --reload + watch on api/, kb/, solver/, deps.py
#
# Env overrides:
#   PORT          (default 8181)
#   HOST          (default 127.0.0.1)
#   PYTHON        (default python3)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_DIR="${REPO_ROOT}/product/server"
VENV="${SERVER_DIR}/.venv"
PYTHON="${PYTHON:-python3}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8181}"

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    if [[ -f "${SERVER_DIR}/.env" ]]; then
        # shellcheck disable=SC1090
        set -a; source "${SERVER_DIR}/.env"; set +a
    fi
fi
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "[local_dev] ANTHROPIC_API_KEY is unset — solver will fall back to KB-only plans"
    export ANTHROPIC_API_KEY="dev-no-key"
fi

if [[ ! -d "${VENV}" ]]; then
    echo "[local_dev] creating venv at ${VENV}"
    "${PYTHON}" -m venv "${VENV}"
fi

VENV_PY="${VENV}/bin/python"

echo "[local_dev] installing requirements"
"${VENV_PY}" -m pip install --quiet --upgrade pip
"${VENV_PY}" -m pip install --quiet -r "${SERVER_DIR}/requirements.txt"

echo "[local_dev] booting uvicorn on http://${HOST}:${PORT}"
cd "${SERVER_DIR}"
exec "${VENV_PY}" -m uvicorn main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --reload \
    --reload-dir api \
    --reload-dir kb \
    --reload-dir solver \
    --reload-dir templates \
    --reload-include "*.py" \
    --reload-include "*.html" \
    --reload-include "deps.py" \
    --reload-include "config.py" \
    --reload-dir "${REPO_ROOT}/kb/output/extracted" \
    --reload-include "*.json"
