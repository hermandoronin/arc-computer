#!/usr/bin/env python3
"""build_index.py — Snapshot of every record in the KB layout.

Walks ``kb/output/{extracted,extracted-bulk,packs}/`` and writes
``kb/output/INDEX.json`` containing per-record metadata (id, category,
relative path, size, sha256 prefix). The index is what the package script
ships next to the tarball so downstream consumers can stream-verify
individual records without unpacking the whole archive.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _paths import KB_OUTPUT, iter_json_files  # noqa: E402

SCHEMA_VERSION = "0.1.0"


def _sha256_short(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def main() -> int:
    records: list[dict[str, Any]] = []
    by_category: dict[str, int] = {}
    total_bytes = 0

    for category, path in iter_json_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}

        if category == "devices" and isinstance(payload, dict) and "device" in payload:
            payload = payload["device"]

        rec_id = payload.get("id") if isinstance(payload, dict) else None
        rec_id = rec_id or path.stem

        size = path.stat().st_size
        total_bytes += size

        records.append(
            {
                "id": rec_id,
                "type": category,
                "path": str(path.relative_to(KB_OUTPUT)),
                "size_bytes": size,
                "sha256_short": _sha256_short(path),
            }
        )
        by_category[category] = by_category.get(category, 0) + 1

    records.sort(key=lambda r: (r["type"], r["id"]))

    index = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_records": len(records),
        "total_bytes": total_bytes,
        "by_category": by_category,
        "records": records,
    }

    out = KB_OUTPUT / "INDEX.json"
    out.write_text(json.dumps(index, indent=2))
    print(
        f"build_index: {len(records)} records, "
        f"{total_bytes/1024/1024:.1f} MiB → {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
