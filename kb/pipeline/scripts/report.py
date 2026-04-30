#!/usr/bin/env python3
"""report.py — Aggregate every validation artifact into REPORT.md.

Reads:
  - kb/output/INDEX.json
  - kb/output/validation-reports/{schema,xref,antilaziness,coverage}.json
  - agents/deepseek/budget.json
  - kb/output/final/ark-kb-v0.1.tar.zst (size only)

Writes:
  - kb/output/REPORT.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _paths import FINAL_DIR, KB_OUTPUT, REPO_ROOT, REPORTS_DIR  # noqa: E402

BAR_WIDTH = 30


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _bar(pct: float) -> str:
    pct = min(max(pct, 0.0), 1.0)
    filled = int(pct * BAR_WIDTH)
    return "[" + "#" * filled + "." * (BAR_WIDTH - filled) + f"] {pct*100:5.1f}%"


def _format_bytes(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def main() -> int:
    index = _read_json(KB_OUTPUT / "INDEX.json") or {}
    schema = _read_json(REPORTS_DIR / "schema.json") or {}
    xref = _read_json(REPORTS_DIR / "xref.json") or {}
    anti = _read_json(REPORTS_DIR / "antilaziness.json") or {}
    coverage = _read_json(REPORTS_DIR / "coverage.json") or {}
    budget = _read_json(REPO_ROOT / "agents" / "deepseek" / "budget.json") or {}

    artifact = FINAL_DIR / "ark-kb-v0.1.tar.zst"
    artifact_size = artifact.stat().st_size if artifact.exists() else 0
    sha256_file = artifact.with_suffix(artifact.suffix + ".sha256")
    sha256_line = sha256_file.read_text().strip().split()[0] if sha256_file.exists() else "—"

    lines: list[str] = []
    lines.append("# ARK Knowledge-Base — build report")
    lines.append("")
    lines.append(f"_Generated: {index.get('generated_at', 'unknown')}_")
    lines.append("")

    # Records by category
    lines.append("## Records by category")
    lines.append("")
    lines.append("| Category | Actual | Target | Progress |")
    lines.append("|---|---:|---:|---|")
    for row in coverage.get("rows", []):
        lines.append(
            f"| `{row['category']}` | {row['actual']:,} | {row['target']:,} | `{_bar(row['ratio'])}` |"
        )
    lines.append("")

    # Validation pass rates
    lines.append("## Validation pass rates")
    lines.append("")
    lines.append("| Check | Result | Detail |")
    lines.append("|---|---|---|")

    schema_pass = "PASS" if schema.get("pass") else "FAIL"
    schema_detail = (
        f"{schema.get('errors', 0)}/{schema.get('total', 0)} errors "
        f"({schema.get('ratio', 0)*100:.2f}%)"
    )
    lines.append(f"| Schema (Pydantic) | **{schema_pass}** | {schema_detail} |")

    xref_ratio = xref.get("ratio", 0.0)
    xref_pass = "PASS" if xref_ratio < 0.05 else "FAIL"
    xref_detail = (
        f"{xref.get('missing_refs', 0)}/{xref.get('total_refs', 0)} broken "
        f"({xref_ratio*100:.2f}%) · {xref.get('total_ids_indexed', 0):,} ids indexed"
    )
    lines.append(f"| Cross-references | **{xref_pass}** | {xref_detail} |")

    anti_pass = "PASS" if anti.get("pass") else "FAIL"
    anti_detail = (
        f"{anti.get('flagged_files', 0)}/{anti.get('total_files', 0)} flagged "
        f"({anti.get('ratio', 0)*100:.2f}%) · {anti.get('total_violations', 0)} hits"
    )
    lines.append(f"| Anti-laziness | **{anti_pass}** | {anti_detail} |")

    coverage_pass = "PASS" if coverage.get("all_targets_met") else "FAIL"
    gaps = coverage.get("gap_categories", [])
    coverage_detail = "all Tier-A targets ≥80%" if not gaps else f"gaps: {', '.join(gaps)}"
    lines.append(f"| Coverage (Tier A) | **{coverage_pass}** | {coverage_detail} |")
    lines.append("")

    # Cost summary
    lines.append("## Cost spent across agents")
    lines.append("")
    if budget:
        lines.append(
            f"- DeepSeek: ${budget.get('spent_usd', 0):.4f} / ${budget.get('cap_usd', 0):.2f} "
            f"cap · {budget.get('calls', 0)} calls · model `{budget.get('model_default', '?')}`"
        )
        lines.append(
            f"- Forecast end-state: ${budget.get('expected_total_usd', 0):.2f}"
        )
    else:
        lines.append("_No budget records available._")
    lines.append("")

    # Package
    lines.append("## Final package")
    lines.append("")
    if artifact.exists():
        lines.append(f"- Artifact: `kb/output/final/{artifact.name}`")
        lines.append(f"- Size: {_format_bytes(artifact_size)}")
        lines.append(f"- SHA-256: `{sha256_line}`")
    else:
        lines.append("_Artifact not built — run `bash kb/pipeline/scripts/package.sh`._")
    lines.append("")

    # Known gaps
    lines.append("## Known gaps (categories <80% target)")
    lines.append("")
    if gaps:
        for cat in gaps:
            row = next((r for r in coverage.get("rows", []) if r["category"] == cat), {})
            lines.append(
                f"- `{cat}` — {row.get('actual', 0):,} / {row.get('target', 0):,} "
                f"({row.get('ratio', 0)*100:.1f}%)"
            )
    else:
        lines.append("_None — every Tier-A category at or above the 80% threshold._")
    lines.append("")

    out = KB_OUTPUT / "REPORT.md"
    out.write_text("\n".join(lines))
    print(f"report: → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
