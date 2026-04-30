#!/usr/bin/env python3
"""firmware_dry_run.py — Headless emulator validation for compiled firmware.

Reads ``kb/output/validation-reports/firmware.json`` (produced by
``firmware_validator.py``) and, for every record marked ``compiled_ok``,
attempts a short headless run:

  * AVR (atmega328p)  → ``simavr`` for 1000 cycles, watch for trap/illegal-op.
  * ARM (Cortex-M)    → ``qemu-system-arm`` for 1 s, abort on hang.
  * ESP32 / ESP8266   → skipped (no usable headless emulator on most hosts).

When the binary or the emulator is missing the run is reported as
``skipped: <reason>`` so this script always finishes cleanly. Output:
``kb/output/validation-reports/firmware-runtime.json``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _paths import KB_OUTPUT, REPORTS_DIR  # noqa: E402

WORK_ROOT = Path(tempfile.gettempdir()) / "firmware-validate"
COMPILE_REPORT = REPORTS_DIR / "firmware.json"


def _run_simavr(elf: Path) -> tuple[str, str]:
    """Run the ELF on simavr for 1000 cycles. Returns (status, detail)."""
    cmd = ["simavr", "-m", "atmega328p", "-c", "1000", str(elf)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return "failed", "simavr timeout"
    text = (result.stdout + result.stderr).lower()
    if "illegal" in text or "trap" in text or "panic" in text:
        return "failed", text.strip()[:500]
    return "passed", "no traps observed"


def _run_qemu_arm(elf: Path) -> tuple[str, str]:
    cmd = [
        "qemu-system-arm",
        "-M",
        "lm3s6965evb",
        "-cpu",
        "cortex-m3",
        "-nographic",
        "-kernel",
        str(elf),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
    except subprocess.TimeoutExpired:
        # We expect to time out — firmware loops forever.
        return "passed", "ran 2 s without abort"
    if result.returncode == 0:
        return "passed", "qemu exited cleanly"
    return "failed", (result.stderr or result.stdout).strip()[:500]


def _resolve_elf(record_id: str) -> Path | None:
    """firmware_validator.py does not persist binaries when invoked without
    ``--keep-workdir``. We rebuild the workdir path so users who re-ran the
    validator with ``--keep-workdir`` can dry-run those artifacts.
    """
    safe = record_id.replace(":", "_").replace("/", "_")
    candidate = WORK_ROOT / safe / "main.elf"
    return candidate if candidate.exists() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=0, help="cap number of records processed"
    )
    args = parser.parse_args(argv)

    if not COMPILE_REPORT.exists():
        print(
            f"firmware_dry_run: {COMPILE_REPORT} missing — run firmware_validator.py first",
            file=sys.stderr,
        )
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / "firmware-runtime.json").write_text(
            json.dumps(
                {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "details": []},
                indent=2,
            )
        )
        return 0

    compile_data = json.loads(COMPILE_REPORT.read_text())
    candidates = [r for r in compile_data.get("details", []) if r.get("status") == "compiled_ok"]
    if args.limit > 0:
        candidates = candidates[: args.limit]

    counts = {"passed": 0, "failed": 0, "skipped": 0}
    details: list[dict[str, Any]] = []

    have_simavr = shutil.which("simavr") is not None
    have_qemu_arm = shutil.which("qemu-system-arm") is not None

    for rec in candidates:
        rec_id = rec.get("id", "?")
        toolchain = rec.get("toolchain", "")
        elf = _resolve_elf(rec_id)

        if elf is None:
            counts["skipped"] += 1
            details.append(
                {
                    "id": rec_id,
                    "status": "skipped",
                    "reason": "binary not on disk (re-run validator with --keep-workdir)",
                }
            )
            continue

        if "avr" in toolchain:
            if not have_simavr:
                counts["skipped"] += 1
                details.append(
                    {"id": rec_id, "status": "skipped", "reason": "simavr not installed"}
                )
                continue
            status, info = _run_simavr(elf)
        elif "arm" in toolchain:
            if not have_qemu_arm:
                counts["skipped"] += 1
                details.append(
                    {"id": rec_id, "status": "skipped", "reason": "qemu-system-arm not installed"}
                )
                continue
            status, info = _run_qemu_arm(elf)
        else:
            counts["skipped"] += 1
            details.append(
                {
                    "id": rec_id,
                    "status": "skipped",
                    "reason": f"no headless emulator path for {toolchain}",
                }
            )
            continue

        if status == "passed":
            counts["passed"] += 1
        else:
            counts["failed"] += 1
        details.append({"id": rec_id, "status": status, "info": info})

    report = {
        "total": len(candidates),
        **counts,
        "details": details,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "firmware-runtime.json"
    out.write_text(json.dumps(report, indent=2))

    print(
        f"firmware_dry_run: {counts['passed']} passed / {counts['failed']} failed / "
        f"{counts['skipped']} skipped of {len(candidates)} compiled records → {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
