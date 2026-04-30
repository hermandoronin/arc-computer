#!/usr/bin/env bash
# deploy.sh — manual deploy to Fly.io with KB validation + post-deploy smoke test.
#
# Usage:
#   bash scripts/deploy.sh [--skip-kb-upload]
#
# Steps:
#   1. validate KB schemas
#   2. (re)build the tar.zst KB package via kb/pipeline/scripts/package.sh
#   3. upload it to the Fly volume mounted at /data
#   4. trigger flyctl deploy
#   5. curl /health on the public hostname

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_DIR="${REPO_ROOT}/product/server"
KB_OUTPUT="${REPO_ROOT}/kb/output"
FINAL_ARTIFACT="${KB_OUTPUT}/final/ark-kb-v0.1.tar.zst"
PYTHON="${PYTHON:-python3}"
FLY_APP="${FLY_APP:-ark-solver}"
SKIP_KB_UPLOAD="${SKIP_KB_UPLOAD:-false}"

for arg in "$@"; do
    case "$arg" in
        --skip-kb-upload) SKIP_KB_UPLOAD=true ;;
        *) echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

command -v flyctl >/dev/null 2>&1 || {
    echo "flyctl not found — install from https://fly.io/docs/hands-on/install-flyctl/" >&2
    exit 1
}

echo "[deploy] step 1/5 — validate KB schemas"
"${PYTHON}" "${REPO_ROOT}/kb/pipeline/scripts/validate_schema.py"

if [[ "${SKIP_KB_UPLOAD}" != "true" ]]; then
    echo "[deploy] step 2/5 — repackage KB"
    PYTHON="${PYTHON}" bash "${REPO_ROOT}/kb/pipeline/scripts/package.sh"

    echo "[deploy] step 3/5 — upload KB to Fly volume"
    if [[ ! -f "${FINAL_ARTIFACT}" ]]; then
        echo "[deploy] missing artifact ${FINAL_ARTIFACT}" >&2
        exit 1
    fi
    flyctl ssh sftp shell --app "${FLY_APP}" <<EOF
put ${FINAL_ARTIFACT} /data/ark-kb-v0.1.tar.zst
EOF
    flyctl ssh console --app "${FLY_APP}" --command \
        "sh -lc 'cd /data && rm -rf extracted extracted-bulk packs INDEX.json && tar --use-compress-program=zstd -xf ark-kb-v0.1.tar.zst'"
else
    echo "[deploy] step 2-3/5 — skipped (SKIP_KB_UPLOAD=true)"
fi

echo "[deploy] step 4/5 — flyctl deploy"
flyctl deploy --config "${SERVER_DIR}/fly.toml" --remote-only

echo "[deploy] step 5/5 — smoke /health"
HOST="$(flyctl status --app "${FLY_APP}" --json | "${PYTHON}" -c 'import json,sys; print(json.load(sys.stdin)["Hostname"])')"
URL="https://${HOST}/health"
for _ in 1 2 3 4 5; do
    if curl -fsS "${URL}" >/dev/null; then
        echo "[deploy] /health OK at ${URL}"
        curl -s "${URL}"
        exit 0
    fi
    sleep 5
done

echo "[deploy] /health did not return 200 within 25 s — check flyctl logs --app ${FLY_APP}" >&2
exit 1
