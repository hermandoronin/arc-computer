#!/usr/bin/env python3
"""validate_coverage.py — Tier-A coverage progress.

Counts records per category across every KB root and compares against the
Tier-A targets in ``agents/kimi/briefs/KIMI-MEGA-BRIEF.md`` Section 6.
Prints a progress-bar summary and writes a structured report.

Output: ``kb/output/validation-reports/coverage.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _paths import REPORTS_DIR, iter_json_files  # noqa: E402

# Tier-A targets (Section 6 of KIMI-MEGA-BRIEF).
TIER_A_TARGETS: dict[str, int] = {
    "devices": 5_000,
    "components": 50_000,
    "projects": 5_000,
    "substitutions": 10_000,
    "safety": 500,
    "materials": 1_000,
    "tools": 500,
    "skills": 200,
    "goals": 50,
    "phenomena": 300,
    "procedures": 2_000,
    "regional": 50,
}

# Threshold below which a category is reported as a "gap".
GAP_THRESHOLD = 0.80
BAR_WIDTH = 30


def _bar(pct: float) -> str:
    filled = int(min(pct, 1.0) * BAR_WIDTH)
    return "[" + "#" * filled + "." * (BAR_WIDTH - filled) + f"] {pct*100:5.1f}%"


def main() -> int:
    counts: dict[str, int] = {cat: 0 for cat in TIER_A_TARGETS}
    for category, _path in iter_json_files():
        if category in counts:
            counts[category] += 1

    rows: list[dict[str, object]] = []
    gaps: list[str] = []
    for cat, target in TIER_A_TARGETS.items():
        actual = counts[cat]
        pct = (actual / target) if target else 0.0
        rows.append(
            {
                "category": cat,
                "target": target,
                "actual": actual,
                "ratio": round(pct, 6),
                "bar": _bar(pct),
            }
        )
        if pct < GAP_THRESHOLD:
            gaps.append(cat)

    report = {
        "tier": "A",
        "gap_threshold": GAP_THRESHOLD,
        "rows": rows,
        "gap_categories": gaps,
        "all_targets_met": len(gaps) == 0,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "coverage.json"
    out.write_text(json.dumps(report, indent=2))

    print(f"{'category':<14} {'actual':>8} / {'target':>8}  progress")
    print("-" * 70)
    for row in rows:
        print(f"{row['category']:<14} {row['actual']:>8} / {row['target']:>8}  {row['bar']}")
    print("-" * 70)
    print(
        f"validate_coverage: gaps={len(gaps)}/{len(rows)} "
        f"({', '.join(gaps) if gaps else 'none'}) → {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
