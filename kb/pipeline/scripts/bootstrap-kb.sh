#!/usr/bin/env bash
# =============================================================================
# ARK Knowledge Base Pipeline — Stage 1 Bootstrap
# =============================================================================
# This is the ONE script a user runs to populate /mnt/staging/ark-kb/raw/
# with all source content needed for the reverse-BOM (off-grid electronics)
# knowledge base.
#
# Usage:
#   bash scripts/bootstrap-kb.sh [STAGING_DIR]
#
# Environment:
#   STAGING_DIR   — override default staging path
#   SKIP_IFIXIT   — set to "1" to skip iFixit download
#   SKIP_INSTRUCTABLES — set to "1" to skip Instructables download
#   SKIP_HACKADAY — set to "1" to skip Hackaday download
#   SKIP_YOUTUBE  — set to "1" to skip YouTube transcripts download
#   SKIP_SURVIVOR — set to "1" to skip Survivor Library section
#   PARALLEL      — set to "1" to attempt parallel downloads (advanced)
#   DRY_RUN       — set to "1" to print commands without executing
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
STAGING_DIR="${STAGING_DIR:-/mnt/staging/ark-kb}"
RAW_DIR="${STAGING_DIR}/raw"
LOG_DIR="${STAGING_DIR}/logs"
LOG_FILE="${LOG_DIR}/bootstrap-$(date +%Y%m%d-%H%M%S).log"

SKIP_IFIXIT="${SKIP_IFIXIT:-0}"
SKIP_INSTRUCTABLES="${SKIP_INSTRUCTABLES:-0}"
SKIP_HACKADAY="${SKIP_HACKADAY:-0}"
SKIP_YOUTUBE="${SKIP_YOUTUBE:-0}"
SKIP_SURVIVOR="${SKIP_SURVIVOR:-0}"
PARALLEL="${PARALLEL:-0}"
DRY_RUN="${DRY_RUN:-0}"

# Disk-space safety threshold (MB)
MIN_FREE_MB=5120   # 5 GB
WARN_FREE_MB=10240 # 10 GB

# Script directory (where this file lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Project root is one level above scripts/
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ---------------------------------------------------------------------------
# Colours for progress reporting
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
    C_RESET='\033[0m'
    C_BOLD='\033[1m'
    C_GREEN='\033[32m'
    C_YELLOW='\033[33m'
    C_RED='\033[31m'
    C_CYAN='\033[36m'
else
    C_RESET=''
    C_BOLD=''
    C_GREEN=''
    C_YELLOW=''
    C_RED=''
    C_CYAN=''
fi

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log()  { printf "${C_BOLD}[%s]${C_RESET} %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
info() { printf "${C_GREEN}[INFO]${C_RESET}  %s\n" "$*"; }
warn() { printf "${C_YELLOW}[WARN]${C_RESET}  %s\n" "$*" >&2; }
err()  { printf "${C_RED}[ERR]${C_RESET}   %s\n" "$*" >&2; }
step() { printf "\n${C_CYAN}▶ %s${C_RESET}\n" "$*"; }

# Redirect all stdout/stderr to log file as well as terminal
e_setup_logging() {
    mkdir -p "$LOG_DIR"
    exec > >(tee -a "$LOG_FILE")
    exec 2> >(tee -a "$LOG_FILE" >&2)
}

# ---------------------------------------------------------------------------
# Disk space check
# ---------------------------------------------------------------------------
check_disk_space() {
    local dir="$1"
    local required_mb="${2:-$MIN_FREE_MB}"
    local available_mb
    available_mb=$(df -m "$dir" | awk 'NR==2 {print $4}')

    if [[ -z "$available_mb" ]]; then
        err "Could not determine free disk space for $dir"
        return 1
    fi

    if (( available_mb < required_mb )); then
        err "Insufficient disk space on $(dirname "$dir"): ${available_mb} MB free, ${required_mb} MB required."
        err "Free up space or set STAGING_DIR to a volume with more capacity."
        return 1
    fi

    if (( available_mb < WARN_FREE_MB )); then
        warn "Disk space is low: ${available_mb} MB free (warning threshold: ${WARN_FREE_MB} MB)."
    else
        info "Disk space OK: ${available_mb} MB available."
    fi
}

# ---------------------------------------------------------------------------
# Resume-safe helpers
# ---------------------------------------------------------------------------
marker_file() {
    echo "${RAW_DIR}/.done-$1"
}

mark_done() {
    touch "$(marker_file "$1")"
}

is_done() {
    [[ -f "$(marker_file "$1")" ]]
}

# ---------------------------------------------------------------------------
# Dry-run wrapper
# ---------------------------------------------------------------------------
run() {
    if [[ "$DRY_RUN" == "1" ]]; then
        info "[DRY-RUN] $*"
    else
        log "CMD: $*"
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# Stage: iFixit
# ---------------------------------------------------------------------------
stage_ifixit() {
    if [[ "$SKIP_IFIXIT" == "1" ]]; then
        warn "Skipping iFixit (SKIP_IFIXIT=1)."
        return 0
    fi
    if is_done "ifixit"; then
        info "iFixit already downloaded (marker exists). Remove $(marker_file ifixit) to re-download."
        return 0
    fi

    step "Stage 1/5 — iFixit Repair Guides"
    check_disk_space "$RAW_DIR" 2048

    mkdir -p "${RAW_DIR}/ifixit"
    run python3 "${PROJECT_ROOT}/scripts/download_ifixit.py" \
        --max-guides 5000 \
        --output-dir "${RAW_DIR}/ifixit" \
        --resume

    mark_done "ifixit"
    info "iFixit stage complete."
}

# ---------------------------------------------------------------------------
# Stage: Instructables
# ---------------------------------------------------------------------------
stage_instructables() {
    if [[ "$SKIP_INSTRUCTABLES" == "1" ]]; then
        warn "Skipping Instructables (SKIP_INSTRUCTABLES=1)."
        return 0
    fi
    if is_done "instructables"; then
        info "Instructables already downloaded (marker exists). Remove $(marker_file instructables) to re-download."
        return 0
    fi

    step "Stage 2/5 — Instructables Projects"
    check_disk_space "$RAW_DIR" 2048

    mkdir -p "${RAW_DIR}/instructables"
    run python3 "${PROJECT_ROOT}/scripts/download_instructables.py" \
        --max-projects 500 \
        --output-dir "${RAW_DIR}/instructables" \
        --resume

    mark_done "instructables"
    info "Instructables stage complete."
}

# ---------------------------------------------------------------------------
# Stage: Hackaday
# ---------------------------------------------------------------------------
stage_hackaday() {
    if [[ "$SKIP_HACKADAY" == "1" ]]; then
        warn "Skipping Hackaday (SKIP_HACKADAY=1)."
        return 0
    fi
    if is_done "hackaday"; then
        info "Hackaday already downloaded (marker exists). Remove $(marker_file hackaday) to re-download."
        return 0
    fi

    step "Stage 3/5 — Hackaday Projects"
    check_disk_space "$RAW_DIR" 2048

    mkdir -p "${RAW_DIR}/hackaday"
    run python3 "${PROJECT_ROOT}/scripts/download_hackaday.py" \
        --max-projects 500 \
        --output-dir "${RAW_DIR}/hackaday" \
        --resume

    mark_done "hackaday"
    info "Hackaday stage complete."
}

# ---------------------------------------------------------------------------
# Stage: YouTube Transcripts
# ---------------------------------------------------------------------------
stage_youtube() {
    if [[ "$SKIP_YOUTUBE" == "1" ]]; then
        warn "Skipping YouTube (SKIP_YOUTUBE=1)."
        return 0
    fi
    if is_done "youtube"; then
        info "YouTube transcripts already downloaded (marker exists). Remove $(marker_file youtube) to re-download."
        return 0
    fi

    step "Stage 4/5 — YouTube Transcripts"
    check_disk_space "$RAW_DIR" 1024

    mkdir -p "${RAW_DIR}/youtube"
    run python3 "${PROJECT_ROOT}/scripts/download_youtube_transcripts.py" \
        --max-videos 200 \
        --output-dir "${RAW_DIR}/youtube" \
        --resume

    mark_done "youtube"
    info "YouTube stage complete."
}

# ---------------------------------------------------------------------------
# Stage: Survivor Library (documented / optional)
# ---------------------------------------------------------------------------
stage_survivor() {
    if [[ "$SKIP_SURVIVOR" == "1" ]]; then
        warn "Skipping Survivor Library (SKIP_SURVIVOR=1)."
        return 0
    fi
    if is_done "survivor"; then
        info "Survivor Library already processed (marker exists). Remove $(marker_file survivor) to re-process."
        return 0
    fi

    step "Stage 5/5 — Survivor Library"

    mkdir -p "${RAW_DIR}/survivorbib"

    info "Survivor Library source: https://www.survivorlibrary.com/"
    info "This collection contains thousands of public-domain PDFs on"
    info "old-school engineering, farming, medicine, and electronics."
    info "Full download is ~150-300 GB; uncomment the wget block below to enable."

    # -------------------------------------------------------------------
    # Uncomment the following block to actually download PDFs.
    # WARNING: this is a large, slow operation. Test with a single
    # category first (e.g., just the Radio/Electronics folder).
    # -------------------------------------------------------------------
    : <<'WGET_BLOCK'
    SURVIVOR_SRC="https://www.survivorlibrary.com/library/"
    SURVIVOR_DST="${RAW_DIR}/survivorbib"

    info "Starting Survivor Library download from ${SURVIVOR_SRC} …"
    check_disk_space "$RAW_DIR" 307200  # 300 GB

    # wget options:
    #   --mirror         : recursive download
    #   --convert-links  : make links suitable for offline viewing
    #   --adjust-extension : add .html where missing
    #   --page-requisites : get images/css
    #   --no-parent      : don't ascend to parent dir
    #   -P               : destination prefix
    #   --reject="*.zip,*.exe"  : skip large binaries we don't need
    #   --limit-rate=2m  : throttle so we don't hammer the server
    #   -N               : timestamping (resume-safe)
    wget --mirror \
         --convert-links \
         --adjust-extension \
         --page-requisites \
         --no-parent \
         -P "$SURVIVOR_DST" \
         --reject="*.zip,*.exe,*.dmg,*.pkg" \
         --limit-rate=2m \
         -N \
         "$SURVIVOR_SRC" \
         2>&1 | tee "${LOG_DIR}/survivorlibrary.log"

    # Alternative: if you have an rsync endpoint (e.g. a mirror),
    # replace the wget block with:
    #   rsync -avz --partial --progress \
    #         survivor-mirror.example.com::survivorlibrary/ \
    #         "$SURVIVOR_DST"
WGET_BLOCK

    info "Survivor Library stage documented (download commented out)."
    info "To enable full download, edit $0 and uncomment the WGET_BLOCK."

    mark_done "survivor"
}

# ---------------------------------------------------------------------------
# Summary reporter
# ---------------------------------------------------------------------------
print_summary() {
    step "Bootstrap Summary"

    local total_bytes=0
    local total_files=0
    local src_bytes src_files
    local -a sources=(ifixit instructables hackaday youtube survivorbib)

    printf "\n${C_BOLD}%-15s %12s %12s${C_RESET}\n" "SOURCE" "FILES" "SIZE"
    printf "%-15s %12s %12s\n" "------" "-----" "----"

    for src in "${sources[@]}"; do
        if [[ -d "${RAW_DIR}/${src}" ]]; then
            src_files=$(find "${RAW_DIR}/${src}" -type f | wc -l)
            src_bytes=$(du -sb "${RAW_DIR}/${src}" 2>/dev/null | awk '{print $1}')
        else
            src_files=0
            src_bytes=0
        fi

        # Format size human-readable
        local size_hr
        size_hr=$(numfmt --to=iec-i --suffix=B "$src_bytes" 2>/dev/null || echo "${src_bytes}B")

        printf "%-15s %12d %12s\n" "$src" "$src_files" "$size_hr"

        total_files=$((total_files + src_files))
        total_bytes=$((total_bytes + src_bytes))
    done

    local total_hr
    total_hr=$(numfmt --to=iec-i --suffix=B "$total_bytes" 2>/dev/null || echo "${total_bytes}B")

    printf "%-15s %12s %12s\n" "" "" ""
    printf "${C_BOLD}%-15s %12d %12s${C_RESET}\n" "TOTAL" "$total_files" "$total_hr"

    # -----------------------------------------------------------------
    # Rough API-cost estimate for Stage 2 (extraction)
    # -----------------------------------------------------------------
    # Assumptions:
    #   - Each file ~10k tokens average after cleanup
    #   - Claude Sonnet @ $3 / MTok input
    #   - We process roughly 60% of downloaded files (filtering)
    # -----------------------------------------------------------------
    local est_tokens est_cost
    est_tokens=$((total_files * 10000))
    est_cost=$(awk "BEGIN {printf \"%.2f\", $est_tokens * 3 / 1e9 * 0.6}")

    printf "\n${C_BOLD}Estimated Stage-2 (extract) LLM cost:${C_RESET}\n"
    printf "  • Files likely to be extracted: ~%d\n" "$((total_files * 6 / 10))"
    printf "  • Estimated input tokens:         ~%s\n" "$(numfmt --to=si "$est_tokens")"
    printf "  • Claude Sonnet 3 / MTok input: ~\$%s USD\n" "$est_cost"
    printf "  • Claude Haiku 0.25 / MTok:    ~\$%.2f USD\n" "$(awk "BEGIN {printf \"%.2f\", $est_tokens * 0.25 / 1e9 * 0.6}")"

    # -----------------------------------------------------------------
    # Next-stage prompt
    # -----------------------------------------------------------------
    printf "\n${C_BOLD}${C_GREEN}Next steps:${C_RESET}\n"
    printf "  1. Review downloaded content in %s\n" "$RAW_DIR"
    printf "  2. Run extractors:  bash %s/run-extractors.sh\n" "$SCRIPT_DIR"
    printf "  3. Or run the full pipeline:  bash %s/run-pipeline.sh\n" "$SCRIPT_DIR"

    info "Bootstrap complete. Log written to: $LOG_FILE"
}

# ---------------------------------------------------------------------------
# Parallel download variant (advanced)
# ---------------------------------------------------------------------------
run_parallel() {
    step "Parallel download mode enabled — running all downloaders concurrently."
    warn "This mode is memory-intensive and may hit rate limits."

    # Background each downloader that isn't skipped or already done
    local pids=()

    if [[ "$SKIP_IFIXIT" != "1" ]] && ! is_done "ifixit"; then
        check_disk_space "$RAW_DIR" 2048
        python3 "${PROJECT_ROOT}/scripts/download_ifixit.py" \
            --max-guides 5000 --output-dir "${RAW_DIR}/ifixit" --resume &
        pids+=($!)
    fi

    if [[ "$SKIP_INSTRUCTABLES" != "1" ]] && ! is_done "instructables"; then
        python3 "${PROJECT_ROOT}/scripts/download_instructables.py" \
            --max-projects 500 --output-dir "${RAW_DIR}/instructables" --resume &
        pids+=($!)
    fi

    if [[ "$SKIP_HACKADAY" != "1" ]] && ! is_done "hackaday"; then
        python3 "${PROJECT_ROOT}/scripts/download_hackaday.py" \
            --max-projects 500 --output-dir "${RAW_DIR}/hackaday" --resume &
        pids+=($!)
    fi

    if [[ "$SKIP_YOUTUBE" != "1" ]] && ! is_done "youtube"; then
        python3 "${PROJECT_ROOT}/scripts/download_youtube_transcripts.py" \
            --max-videos 200 --output-dir "${RAW_DIR}/youtube" --resume &
        pids+=($!)
    fi

    # Wait for all background jobs
    local exit_code=0
    for pid in "${pids[@]}"; do
        if ! wait "$pid"; then
            err "Background job PID $pid failed."
            exit_code=1
        fi
    done

    return "$exit_code"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    # Allow overriding STAGING_DIR from positional arg
    if [[ -n "${1:-}" ]]; then
        STAGING_DIR="$1"
        RAW_DIR="${STAGING_DIR}/raw"
        LOG_DIR="${STAGING_DIR}/logs"
        LOG_FILE="${LOG_DIR}/bootstrap-$(date +%Y%m%d-%H%M%S).log"
    fi

    info "ARK KB Pipeline — Stage 1 Bootstrap"
    info "Staging directory: $STAGING_DIR"
    info "Log file: $LOG_FILE"

    # Create directory tree
    mkdir -p "${RAW_DIR}"/ifixit
    mkdir -p "${RAW_DIR}"/instructables
    mkdir -p "${RAW_DIR}"/hackaday
    mkdir -p "${RAW_DIR}"/youtube
    mkdir -p "${RAW_DIR}"/survivorbib
    mkdir -p "$LOG_DIR"

    # Start logging
    e_setup_logging

    # Pre-flight disk check
    check_disk_space "$RAW_DIR"

    # Run stages
    if [[ "$PARALLEL" == "1" ]]; then
        run_parallel
    else
        stage_ifixit
        stage_instructables
        stage_hackaday
        stage_youtube
        stage_survivor
    fi

    # Report
    print_summary
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
main "$@"
