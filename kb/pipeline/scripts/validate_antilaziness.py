#!/usr/bin/env python3
"""validate_antilaziness.py — Section 8.1 forbidden-phrase auditor.

Scans every KB JSON file for the generic-placeholder phrases banned by
``agents/kimi/briefs/KIMI-MEGA-BRIEF.md`` Section 8.1. Each match is
collected with file, phrase, and a short context excerpt.

Output: ``kb/output/validation-reports/antilaziness.json``.
Exit code: ``1`` when violation count > 5% of files, ``0`` otherwise.
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

# (label, compiled_regex) — patterns are case-insensitive and lookaround-aware
# so generic phrases on their own trip the rule but qualifiers excuse them.
FORBIDDEN: list[tuple[str, re.Pattern[str]]] = [
    ("remove screws (no qualifier)", re.compile(r"\bremove\s+screws?\b(?!\s+(of|with|using|sized|number|that|on|from\s+\w+\s+with))", re.I)),
    ("disconnect wires (no qualifier)", re.compile(r"\bdisconnect\s+wires?\b(?!\s+(labeled|colour|color|marked|to|from\s+\w+\s+(at|on|with)))", re.I)),
    ("internal as location", re.compile(r"\"location_in_device\"\s*:\s*\"internal\"", re.I)),
    ("see datasheet as steps", re.compile(r"\"extraction_steps\"\s*:\s*\[[^\]]*\bsee\s+datasheet\b", re.I)),
    ("any 5V regulator (no conditions)", re.compile(r"\bany\s+5\s*v\s+regulator\b(?!\s+(rated|with|that|capable))", re.I)),
    ("about N minutes", re.compile(r"\babout\s+\d+\s+minutes?\b", re.I)),
    ("various (no qualifier)", re.compile(r"\bvarious\b(?!\s+(types|sizes|of|including))", re.I)),
    ("depends on model", re.compile(r"\bdepends\s+on\s+(the\s+)?model\b", re.I)),
    ("consult a professional", re.compile(r"\bconsult\s+(a|the)\s+(professional|expert|specialist)\b", re.I)),
    ("YMMV", re.compile(r"\bYMMV\b")),
    ("best practices (filler)", re.compile(r"\bbest\s+practices\b(?!\s+for\s+\w+)", re.I)),
]

MAX_SAMPLES_PER_RULE = 25
MAX_TOTAL_DETAILS = 500
PASS_THRESHOLD = 0.05


def _scan_text(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for label, regex in FORBIDDEN:
        m = regex.search(text)
        if m:
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            excerpt = text[start:end].replace("\n", " ")
            out.append((label, excerpt))
    return out


def main() -> int:
    files = list(iter_json_files())
    total = len(files)

    by_rule_count: dict[str, int] = {label: 0 for label, _ in FORBIDDEN}
    by_rule_samples: dict[str, list[dict[str, Any]]] = {label: [] for label, _ in FORBIDDEN}
    flagged_files = 0

    for category, path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        hits = _scan_text(text)
        if not hits:
            continue
        flagged_files += 1
        for label, excerpt in hits:
            by_rule_count[label] += 1
            samples = by_rule_samples[label]
            if len(samples) < MAX_SAMPLES_PER_RULE:
                samples.append(
                    {
                        "file": str(path),
                        "category": category,
                        "excerpt": excerpt,
                    }
                )

    total_violations = sum(by_rule_count.values())
    ratio = flagged_files / total if total else 0.0

    report = {
        "total_files": total,
        "flagged_files": flagged_files,
        "total_violations": total_violations,
        "ratio": round(ratio, 6),
        "pass": ratio < PASS_THRESHOLD,
        "by_rule": {
            label: {"count": by_rule_count[label], "samples": by_rule_samples[label]}
            for label, _ in FORBIDDEN
        },
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "antilaziness.json"
    out.write_text(json.dumps(report, indent=2))

    status = "PASS" if report["pass"] else "FAIL"
    print(
        f"validate_antilaziness: {status} — {flagged_files}/{total} files "
        f"({ratio*100:.2f}%), {total_violations} violations → {out}"
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
