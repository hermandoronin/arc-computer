#!/usr/bin/env bash
# package.sh — Build INDEX.json then ship a single zstd-compressed tarball.
#
# Output:
#   kb/output/final/ark-kb-v0.1.tar.zst
#   kb/output/final/ark-kb-v0.1.tar.zst.sha256
#
# Idempotent: rerun overwrites the previous artifact.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
KB_OUT="${REPO_ROOT}/kb/output"
FINAL_DIR="${KB_OUT}/final"
ARTIFACT_NAME="ark-kb-v0.1.tar.zst"
ARTIFACT="${FINAL_DIR}/${ARTIFACT_NAME}"
PYTHON="${PYTHON:-python3}"

mkdir -p "${FINAL_DIR}"

echo "[package] step 1/4 — refresh INDEX.json"
"${PYTHON}" "${SCRIPT_DIR}/build_index.py"

echo "[package] step 2/4 — collect inputs"
inputs=()
for d in extracted extracted-bulk packs; do
    if [[ -d "${KB_OUT}/${d}" ]]; then
        inputs+=("${d}")
    fi
done
inputs+=("INDEX.json")

if [[ ${#inputs[@]} -eq 1 ]]; then
    echo "[package] no extracted/packs directories under ${KB_OUT} — aborting"
    exit 1
fi

echo "[package] step 3/4 — tar | zstd -19"
( cd "${KB_OUT}" && tar --create -- "${inputs[@]}" ) \
    | zstd -19 --threads=0 -q -o "${ARTIFACT}"

echo "[package] step 4/4 — sha256sum"
( cd "${FINAL_DIR}" && sha256sum "${ARTIFACT_NAME}" > "${ARTIFACT_NAME}.sha256" )

size_human=$(du -sh "${ARTIFACT}" | cut -f1)
echo "[package] done — ${ARTIFACT} (${size_human})"
echo "[package] sha256 → $(cat "${ARTIFACT}.sha256")"
