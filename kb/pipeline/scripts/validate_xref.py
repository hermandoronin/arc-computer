#!/usr/bin/env python3
"""validate_xref.py — Cross-reference integrity check.

Builds a global ID set across every collection, then walks each Project /
Device record and verifies that every id-shaped reference resolves to
something we have on disk. The Kimi extractions only sometimes include a
``component_id`` field (some files use a free-text ``component_class`` or
just an ID-shaped string in ``contains[]``), so the check is lenient: a
reference is only flagged when it is clearly an ID (pattern ``^[a-z]+:``)
that does not exist in the global set.

Output: ``kb/output/validation-reports/xref.json``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _paths import REPORTS_DIR, iter_json_files  # noqa: E402

ID_RE = re.compile(r"^[a-z][a-z0-9_]*:[A-Za-z0-9_\-: ]+$")
MAX_DETAIL_ROWS = 500


def _load(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _is_id_like(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_RE.match(value))


def _collect_required_component_ids(project: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("required_components", "optional_components", "bom_logical"):
        for entry in project.get(key, []) or []:
            if isinstance(entry, dict):
                cid = entry.get("component_id") or entry.get("id")
                if _is_id_like(cid):
                    out.append(cid)
    return out


def _collect_device_contains(device: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for entry in device.get("contains", []) or []:
        if _is_id_like(entry):
            out.append(entry)
        elif isinstance(entry, dict):
            cid = entry.get("component_id")
            if _is_id_like(cid):
                out.append(cid)
    return out


def main() -> int:
    files = list(iter_json_files())

    # Pass 1 — collect every id we have.
    all_ids: set[str] = set()
    project_files: list[tuple[Path, dict[str, Any]]] = []
    device_files: list[tuple[Path, dict[str, Any]]] = []

    for category, path in files:
        data = _load(path)
        if data is None:
            continue

        # Devices ship as either flat CDPO or {device:..., components_inside:...}.
        if category == "devices" and "device" in data and isinstance(data["device"], dict):
            device_payload = data["device"]
            for inst in data.get("components_inside", []) or []:
                if isinstance(inst, dict):
                    iid = inst.get("instance_id")
                    if _is_id_like(iid):
                        all_ids.add(iid)
                    cid = inst.get("component_id")
                    if _is_id_like(cid):
                        all_ids.add(cid)
            payload_for_xref = device_payload
        else:
            payload_for_xref = data

        rec_id = payload_for_xref.get("id")
        if _is_id_like(rec_id):
            all_ids.add(rec_id)

        if category == "projects":
            project_files.append((path, payload_for_xref))
        elif category == "devices":
            device_files.append((path, payload_for_xref))

    # Pass 2 — check references.
    missing: list[dict[str, Any]] = []
    project_refs = 0
    device_refs = 0

    for path, project in project_files:
        for cid in _collect_required_component_ids(project):
            project_refs += 1
            if cid not in all_ids:
                if len(missing) < MAX_DETAIL_ROWS:
                    missing.append({"file": str(path), "kind": "project_bom", "missing": cid})

    for path, device in device_files:
        for cid in _collect_device_contains(device):
            device_refs += 1
            if cid not in all_ids:
                if len(missing) < MAX_DETAIL_ROWS:
                    missing.append({"file": str(path), "kind": "device_contains", "missing": cid})

    total_refs = project_refs + device_refs
    miss_count = sum(1 for _ in missing)
    # Note: missing may be capped — recount full set:
    miss_count_full = (
        sum(1 for path, project in project_files for cid in _collect_required_component_ids(project) if cid not in all_ids)
        + sum(1 for path, device in device_files for cid in _collect_device_contains(device) if cid not in all_ids)
    )

    report = {
        "total_ids_indexed": len(all_ids),
        "projects_scanned": len(project_files),
        "devices_scanned": len(device_files),
        "project_refs": project_refs,
        "device_refs": device_refs,
        "total_refs": total_refs,
        "missing_refs": miss_count_full,
        "ratio": round(miss_count_full / total_refs, 6) if total_refs else 0.0,
        "details_truncated": miss_count_full > MAX_DETAIL_ROWS,
        "details": missing,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "xref.json"
    out.write_text(json.dumps(report, indent=2))

    print(
        f"validate_xref: {miss_count_full}/{total_refs} broken references "
        f"({report['ratio']*100:.2f}%) — {len(all_ids)} ids indexed → {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
