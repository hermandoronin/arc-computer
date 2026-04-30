#!/usr/bin/env python3
"""
Test subset script: downloads just 1 video from each channel to verify
the transcript pipeline works end-to-end.

This is a thin wrapper around download_youtube_transcripts.py with
--max-per-channel 1.

Usage:
    python download_test_subset.py [--output-root /path/to/root]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
MAIN_SCRIPT = SCRIPT_DIR / "download_youtube_transcripts.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Test YouTube transcript pipeline (1 video per channel)")
    parser.add_argument(
        "--output-root",
        type=str,
        default="/home/user/aisurvive/kb/output/raw/youtube",
        help="Root output directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List videos but do not download",
    )
    args = parser.parse_args()

    cmd = [
        sys.executable,
        str(MAIN_SCRIPT),
        "--max-per-channel", "1",
        "--channels", "eevblog,bigclive,mrcarlson",
        "--output-root", args.output_root,
    ]
    if args.dry_run:
        cmd.append("--dry-run")

    print(f"Running test subset command:\n  {' '.join(cmd)}\n")
    env = os.environ.copy()
    env["YT_DLP_BIN"] = "yt-dlp"
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    sys.exit(main())
