#!/usr/bin/env python3
"""validate_schema.py — Pydantic-validate every KB JSON record.

Walks ``kb/output/{extracted,extracted-bulk,packs}/<category>/*.json`` and
runs each file through the matching Permissive wrapper from
``product/server/kb/index.py``. Records that fail validation are flagged
but the process never crashes — the run produces a structured JSON report
under ``kb/output/validation-reports/schema.json``.

Pass criteria: ``errors / total < 5%``.

Performance: uses ``multiprocessing.Pool`` (default 8 workers) to keep
wall-clock tolerable on 50 k+ component files.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path
from typing import Any

# Bootstrap sys.path so we can import the server's permissive wrappers.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _paths import REPORTS_DIR, iter_json_files  # noqa: E402

sys.path.insert(0, str(SCRIPT_DIR.parents[2] / "product" / "server"))
from kb.index import (  # noqa: E402
    PermissiveComponent,
    PermissiveDevice,
    PermissiveMaterial,
    PermissiveProject,
    PermissiveSimple,
    _unwrap_bulk_device,
)
from pydantic import BaseModel, ValidationError  # noqa: E402

PASS_THRESHOLD: float = 0.05  # max acceptable error ratio

_CATEGORY_TO_MODEL: dict[str, type[BaseModel]] = {
    "devices": PermissiveDevice,
    "projects": PermissiveProject,
    "components": PermissiveComponent,
    "materials": PermissiveMaterial,
    "phenomena": PermissiveSimple,
    "tools": PermissiveSimple,
    "skills": PermissiveSimple,
    "procedures": PermissiveSimple,
    "safety": PermissiveSimple,
    "substitutions": PermissiveSimple,
    "links": PermissiveSimple,
    "regional": PermissiveSimple,
    "goals": PermissiveSimple,
}


def _validate_one(args: tuple[str, str]) -> tuple[bool, dict[str, Any] | None]:
    """Worker: validate a single file. Returns (ok, error_record | None)."""
    category, path_str = args
    path = Path(path_str)
    model_cls = _CATEGORY_TO_MODEL.get(category, PermissiveSimple)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, {"file": str(path), "category": category, "error": f"read/parse: {exc}"}

    if category == "devices":
        payload, _ = _unwrap_bulk_device(payload)

    payload.setdefault("id", path.stem)

    try:
        model_cls.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {"msg": str(exc)}
        return False, {
            "file": str(path),
            "category": category,
            "error": f"{first.get('loc', '')}: {first.get('msg', '')}",
        }

    return True, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8, help="multiprocessing pool size")
    parser.add_argument(
        "--max-error-samples",
        type=int,
        default=200,
        help="cap the number of error rows persisted in the report",
    )
    args = parser.parse_args(argv)

    work: list[tuple[str, str]] = [(c, str(p)) for c, p in iter_json_files()]
    total = len(work)

    if total == 0:
        print("validate_schema: no JSON files found under kb/output/", file=sys.stderr)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / "schema.json").write_text(
            json.dumps({"total": 0, "errors": 0, "ratio": 0.0, "details": []}, indent=2)
        )
        return 0

    started = time.time()
    workers = max(1, min(args.workers, os.cpu_count() or 1))
    errors: list[dict[str, Any]] = []
    by_cat_errors: dict[str, int] = {}
    by_cat_total: dict[str, int] = {}

    with mp.Pool(workers) as pool:
        for (cat, _path), (ok, err) in zip(work, pool.imap_unordered(_validate_one, work, chunksize=64)):
            by_cat_total[cat] = by_cat_total.get(cat, 0) + 1
            if not ok and err is not None:
                by_cat_errors[err["category"]] = by_cat_errors.get(err["category"], 0) + 1
                if len(errors) < args.max_error_samples:
                    errors.append(err)

    elapsed = round(time.time() - started, 2)
    error_count = sum(by_cat_errors.values())
    ratio = error_count / total if total else 0.0

    report = {
        "total": total,
        "errors": error_count,
        "ratio": round(ratio, 6),
        "pass": ratio < PASS_THRESHOLD,
        "elapsed_seconds": elapsed,
        "workers": workers,
        "by_category": {
            cat: {"total": by_cat_total.get(cat, 0), "errors": by_cat_errors.get(cat, 0)}
            for cat in sorted(by_cat_total)
        },
        "details": errors,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "schema.json"
    out.write_text(json.dumps(report, indent=2))

    status = "PASS" if report["pass"] else "FAIL"
    print(
        f"validate_schema: {status} — {error_count}/{total} errors "
        f"({ratio*100:.2f}%) in {elapsed}s → {out}"
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
