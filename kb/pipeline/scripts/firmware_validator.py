#!/usr/bin/env python3
"""firmware_validator.py — Compile-check firmware records.

Walks every KB directory that may carry firmware metadata (``firmware-genome``
trees plus ``packs/*/firmware/``) and dispatches each record to the right
toolchain by ``target_mcus[0].chip_family`` (or ``chip_canonical``). Records
without an embedded ``code`` field — for example the overview entries under
``firmware-genome/fwo/`` — are surfaced as ``skipped: overview-only`` rather
than failing.

When the required toolchain is not installed, the record is marked as
``skipped: toolchain-missing`` and the report flags the missing tool. This
keeps the script CI-friendly: a clean run on a host with no MCU compilers
still produces a structured report instead of crashing.

Output: ``kb/output/validation-reports/firmware.json``
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

# chip_family / chip_canonical → ("toolchain-cli-name", build-fn-key)
DISPATCH: dict[str, tuple[str, str]] = {
    "AVR": ("avr-gcc", "avr"),
    "atmega328p": ("avr-gcc", "avr"),
    "atmega2560": ("avr-gcc", "avr"),
    "ESP32": ("xtensa-esp32-elf-gcc", "esp32"),
    "ESP8266": ("xtensa-lx106-elf-gcc", "esp8266"),
    "ARM": ("arm-none-eabi-gcc", "arm"),
    "STM32": ("arm-none-eabi-gcc", "arm"),
    "RP2040": ("arm-none-eabi-gcc", "arm"),
    "Arduino": ("arduino-cli", "arduino"),
}


def iter_firmware_files() -> list[tuple[Path, str]]:
    """Yield (path, source_label) for every firmware-shaped JSON in KB output."""
    out: list[tuple[Path, str]] = []

    candidate_roots = [
        KB_OUTPUT / "extracted" / "firmware-genome",
        KB_OUTPUT / "firmware-genome",
    ]
    for root in candidate_roots:
        if root.exists():
            for jf in sorted(root.rglob("*.json")):
                out.append((jf, str(jf.relative_to(KB_OUTPUT))))

    packs_root = KB_OUTPUT / "packs"
    if packs_root.exists():
        for pack in sorted(packs_root.iterdir()):
            firmware_dir = pack / "firmware"
            if firmware_dir.is_dir():
                for jf in sorted(firmware_dir.glob("*.json")):
                    out.append((jf, str(jf.relative_to(KB_OUTPUT))))

    return out


def pick_target(record: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (chip_family, chip_canonical) for the primary target MCU."""
    targets = record.get("target_mcus") or []
    if not targets:
        return None, None
    primary = targets[0]
    if isinstance(primary, str):
        return primary, primary
    if isinstance(primary, dict):
        return primary.get("chip_family"), primary.get("chip_canonical")
    return None, None


def select_toolchain(family: str | None, canonical: str | None) -> tuple[str, str] | None:
    for key in (family, canonical):
        if key and key in DISPATCH:
            return DISPATCH[key]
    return None


def _compile_avr(code: str, workdir: Path) -> tuple[bool, str]:
    src = workdir / "main.c"
    src.write_text(code)
    elf = workdir / "main.elf"
    cmd = [
        "avr-gcc",
        "-mmcu=atmega328p",
        "-DF_CPU=16000000UL",
        "-Os",
        "-o",
        str(elf),
        str(src),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        return True, ""
    return False, result.stderr.strip()[:1000]


def _compile_arm(code: str, workdir: Path) -> tuple[bool, str]:
    src = workdir / "main.c"
    src.write_text(code)
    elf = workdir / "main.elf"
    cmd = [
        "arm-none-eabi-gcc",
        "-mcpu=cortex-m3",
        "-mthumb",
        "-Os",
        "-nostdlib",
        "-o",
        str(elf),
        str(src),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode == 0:
        return True, ""
    return False, result.stderr.strip()[:1000]


def _compile_arduino(code: str, workdir: Path, fqbn: str = "arduino:avr:uno") -> tuple[bool, str]:
    sketch_dir = workdir / "Sketch"
    sketch_dir.mkdir(parents=True, exist_ok=True)
    (sketch_dir / "Sketch.ino").write_text(code)
    cmd = ["arduino-cli", "compile", "--fqbn", fqbn, str(sketch_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode == 0:
        return True, ""
    return False, result.stderr.strip()[:1000]


def _compile_esp(code: str, workdir: Path) -> tuple[bool, str]:
    src = workdir / "main.c"
    src.write_text(code)
    obj = workdir / "main.o"
    cmd = ["xtensa-esp32-elf-gcc", "-c", "-Os", "-o", str(obj), str(src)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode == 0:
        return True, ""
    return False, result.stderr.strip()[:1000]


_BUILDERS = {
    "avr": _compile_avr,
    "arm": _compile_arm,
    "arduino": _compile_arduino,
    "esp32": _compile_esp,
    "esp8266": _compile_esp,
}


def _binary_size(workdir: Path) -> int | None:
    for candidate in ("main.elf", "main.o"):
        p = workdir / candidate
        if p.exists():
            return p.stat().st_size
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=0, help="cap number of records processed (0 = all)"
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="leave temporary build dirs on disk for inspection",
    )
    args = parser.parse_args(argv)

    files = iter_firmware_files()
    if args.limit > 0:
        files = files[: args.limit]

    WORK_ROOT.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    counts = {
        "compiled_ok": 0,
        "failed": 0,
        "skipped_overview_only": 0,
        "skipped_no_target": 0,
        "skipped_unknown_target": 0,
        "skipped_toolchain_missing": 0,
    }
    missing_tools: set[str] = set()

    for path, rel in files:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            results.append({"file": rel, "status": "failed", "error": f"read/parse: {exc}"})
            counts["failed"] += 1
            continue

        if not isinstance(record, dict):
            counts["failed"] += 1
            results.append({"file": rel, "status": "failed", "error": "not a JSON object"})
            continue

        rec_id = record.get("id") or path.stem
        code = record.get("code")

        if not code:
            counts["skipped_overview_only"] += 1
            results.append(
                {
                    "id": rec_id,
                    "file": rel,
                    "status": "skipped",
                    "reason": "overview-only (no embedded code)",
                }
            )
            continue

        family, canonical = pick_target(record)
        if not family and not canonical:
            counts["skipped_no_target"] += 1
            results.append(
                {"id": rec_id, "file": rel, "status": "skipped", "reason": "no target_mcus"}
            )
            continue

        toolchain = select_toolchain(family, canonical)
        if toolchain is None:
            counts["skipped_unknown_target"] += 1
            results.append(
                {
                    "id": rec_id,
                    "file": rel,
                    "status": "skipped",
                    "reason": f"unsupported target {family or canonical}",
                }
            )
            continue

        cli_name, builder_key = toolchain
        if shutil.which(cli_name) is None:
            counts["skipped_toolchain_missing"] += 1
            missing_tools.add(cli_name)
            results.append(
                {
                    "id": rec_id,
                    "file": rel,
                    "status": "skipped",
                    "reason": f"toolchain-missing: {cli_name}",
                }
            )
            continue

        workdir = WORK_ROOT / rec_id.replace(":", "_").replace("/", "_")
        workdir.mkdir(parents=True, exist_ok=True)
        builder = _BUILDERS[builder_key]
        try:
            ok, err = builder(code, workdir)
        except subprocess.TimeoutExpired:
            ok, err = False, "compile timeout"
        except Exception as exc:  # pragma: no cover
            ok, err = False, f"runner crash: {exc}"

        if ok:
            counts["compiled_ok"] += 1
            results.append(
                {
                    "id": rec_id,
                    "file": rel,
                    "status": "compiled_ok",
                    "toolchain": cli_name,
                    "binary_size_bytes": _binary_size(workdir),
                }
            )
        else:
            counts["failed"] += 1
            results.append(
                {
                    "id": rec_id,
                    "file": rel,
                    "status": "failed",
                    "toolchain": cli_name,
                    "error": err,
                }
            )

        if not args.keep_workdir:
            shutil.rmtree(workdir, ignore_errors=True)

    total = len(files)
    actionable = counts["compiled_ok"] + counts["failed"]
    report = {
        "total": total,
        "counts": counts,
        "actionable": actionable,
        "compiled_ratio": (
            round(counts["compiled_ok"] / actionable, 6) if actionable else None
        ),
        "missing_toolchains": sorted(missing_tools),
        "details": results,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "firmware.json"
    out.write_text(json.dumps(report, indent=2))

    summary = (
        f"firmware_validator: {counts['compiled_ok']}/{actionable} compiled, "
        f"{counts['failed']} failed, "
        f"{counts['skipped_toolchain_missing']} skipped(toolchain), "
        f"{counts['skipped_overview_only']} overview-only, "
        f"{counts['skipped_unknown_target'] + counts['skipped_no_target']} unsupported "
        f"→ {out}"
    )
    print(summary)
    if missing_tools:
        print("  missing toolchains:", ", ".join(sorted(missing_tools)))
    # Exit 0 if no actionable records or compiled_ratio >= 0.8.
    if actionable == 0:
        return 0
    return 0 if (counts["compiled_ok"] / actionable) >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
