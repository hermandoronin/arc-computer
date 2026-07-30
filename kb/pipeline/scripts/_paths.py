"""Shared paths + sys.path bootstrap for KB pipeline scripts."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
KB_OUTPUT = REPO_ROOT / "kb" / "output"
KB_ROOTS = (
    KB_OUTPUT / "extracted",
    KB_OUTPUT / "extracted-bulk",
    KB_OUTPUT / "packs",
)
REPORTS_DIR = KB_OUTPUT / "validation-reports"
FINAL_DIR = KB_OUTPUT / "final"

# Make the CDPO models importable.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CATEGORY_DIRS = (
    "devices",
    "projects",
    "components",
    "materials",
    "phenomena",
    "tools",
    "skills",
    "procedures",
    "safety",
    "substitutions",
    "links",
    "regional",
    "goals",
)


def iter_category_dirs():
    """Yield (category_name, directory_path) for every category in every KB root."""
    for root in KB_ROOTS:
        if not root.exists():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            if child.name in CATEGORY_DIRS:
                yield child.name, child
            else:
                # Pack root: peek one level deeper.
                for grand in sorted(child.iterdir()):
                    if grand.is_dir() and grand.name in CATEGORY_DIRS:
                        yield grand.name, grand


def iter_json_files():
    """Yield (category_name, json_path) across the entire KB layout."""
    for cat, directory in iter_category_dirs():
        for jf in directory.glob("*.json"):
            yield cat, jf
