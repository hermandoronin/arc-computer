#!/usr/bin/env python3
"""ARK Cost Estimator — Pre-flight token and cost estimation.

Scans all raw source files (iFixit JSON, Instructables HTML, Hackaday JSON),
estimates token counts using a mixed English/CJK heuristic, applies pricing
from ``config.toml``, and prints a formatted cost table. Also shows the
savings from using Anthropic's Message Batches API (50%% discount).

Token heuristic
---------------
- English / ASCII: ~4 characters per token
- CJK characters: ~2 characters per token

Output assumption
-----------------
- Estimated output tokens = 1/3 of input tokens (conservative for JSON
  extraction tasks).

Usage
-----
    python cost_estimate.py
    python cost_estimate.py --config /path/to/config.toml
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rich.console import Console
from rich.table import Table

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from common import (
    estimate_tokens,
    load_config,
    load_prompt,
    setup_logging,
    log_extra,
    clean_ifixit_text,
    strip_html,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_IFIXIT = Path("/home/user/aisurvive/kb/output/raw/ifixit")
RAW_INSTRUCTABLES = Path("/home/user/aisurvive/kb/output/raw/instructables")
RAW_HACKADAY = Path("/home/user/aisurvive/kb/output/raw/hackaday")
CONSOLE = Console()

PROMPT_DEVICES = "01-device-extractor.md"
PROMPT_PROJECTS = "02-project-extractor.md"
PROMPT_LINKER = "03-linker.md"
PROMPT_SUBSTITUTION = "04-substitution.md"

# ---------------------------------------------------------------------------
# File scanners
# ---------------------------------------------------------------------------


def _scan_ifixit() -> Tuple[int, int, int]:
    """Scan all iFixit JSON files and estimate tokens.

    Returns:
        ``(file_count, total_chars, total_tokens)``
    """
    count = 0
    chars = 0
    tokens = 0
    if not RAW_IFIXIT.exists():
        return count, chars, tokens
    for path in RAW_IFIXIT.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            text = clean_ifixit_text(data)
        except (json.JSONDecodeError, OSError):
            continue
        count += 1
        chars += len(text)
        tokens += estimate_tokens(text)
    return count, chars, tokens


def _scan_instructables() -> Tuple[int, int, int]:
    """Scan all Instructables HTML files.

    Returns:
        ``(file_count, total_chars, total_tokens)``
    """
    count = 0
    chars = 0
    tokens = 0
    if not RAW_INSTRUCTABLES.exists():
        return count, chars, tokens
    for path in RAW_INSTRUCTABLES.glob("*.html"):
        try:
            text = strip_html(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        count += 1
        chars += len(text)
        tokens += estimate_tokens(text)
    return count, chars, tokens


def _scan_hackaday() -> Tuple[int, int, int]:
    """Scan all Hackaday JSON files.

    Returns:
        ``(file_count, total_chars, total_tokens)``
    """
    count = 0
    chars = 0
    tokens = 0
    if not RAW_HACKADAY.exists():
        return count, chars, tokens
    for path in RAW_HACKADAY.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            parts = [
                data.get("title", ""),
                data.get("summary", ""),
                data.get("description", ""),
                data.get("body", ""),
                data.get("content", ""),
            ]
            text = "\n\n".join(p for p in parts if p)
            text = strip_html(text)
        except (json.JSONDecodeError, OSError):
            continue
        count += 1
        chars += len(text)
        tokens += estimate_tokens(text)
    return count, chars, tokens


# ---------------------------------------------------------------------------
# Cost math
# ---------------------------------------------------------------------------


def _compute_costs(
    tokens: int,
    prompt_tokens: int,
    input_price: float,
    output_price: float,
    output_ratio: float = 1 / 3,
) -> Tuple[float, float, float]:
    """Compute estimated API costs.

    Args:
        tokens: Estimated input tokens (content only).
        prompt_tokens: Estimated system / prompt tokens.
        input_price: USD per 1k input tokens.
        output_price: USD per 1k output tokens.
        output_ratio: Assumed output/input token ratio.

    Returns:
        ``(input_cost, output_cost, total_cost)`` in USD.
    """
    total_input = tokens + prompt_tokens
    output_tokens = int(total_input * output_ratio)
    input_cost = total_input / 1000 * input_price
    output_cost = output_tokens / 1000 * output_price
    return input_cost, output_cost, input_cost + output_cost


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------


def main(argv: List[str] | None = None) -> int:
    """Entry point for the cost estimator.

    Args:
        argv: CLI args.

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(description="ARK Cost Estimator")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    logger = setup_logging(
        level="INFO",
        log_dir=Path(config.get("paths", {}).get("final", "/home/user/aisurvive/kb/output/final")) / "logs",
        script_name="cost_estimate",
    )
    logger.info("Starting cost estimation")

    cost_cfg = config.get("cost", {})
    input_price = cost_cfg.get("input_price_per_1k", 3.0)
    output_price = cost_cfg.get("output_price_per_1k", 15.0)

    # Load prompt templates for prompt-token estimation
    prompt_devices = load_prompt(PROMPT_DEVICES)
    prompt_projects = load_prompt(PROMPT_PROJECTS)
    prompt_linker = load_prompt(PROMPT_LINKER)
    prompt_substitution = load_prompt(PROMPT_SUBSTITUTION)

    # Scan sources
    sources: List[Dict[str, Any]] = []

    # iFixit
    count_i, chars_i, tokens_i = _scan_ifixit()
    prompt_tok_i = estimate_tokens(prompt_devices)
    in_i, out_i, tot_i = _compute_costs(tokens_i, prompt_tok_i, input_price, output_price)
    sources.append({
        "source": "iFixit",
        "files": count_i,
        "chars": chars_i,
        "tokens": tokens_i + prompt_tok_i,
        "input_cost": in_i,
        "output_cost": out_i,
        "total": tot_i,
    })

    # Instructables
    count_in, chars_in, tokens_in = _scan_instructables()
    prompt_tok_in = estimate_tokens(prompt_projects)
    in_in, out_in, tot_in = _compute_costs(tokens_in, prompt_tok_in, input_price, output_price)
    sources.append({
        "source": "Instructables",
        "files": count_in,
        "chars": chars_in,
        "tokens": tokens_in + prompt_tok_in,
        "input_cost": in_in,
        "output_cost": out_in,
        "total": tot_in,
    })

    # Hackaday
    count_h, chars_h, tokens_h = _scan_hackaday()
    prompt_tok_h = estimate_tokens(prompt_projects)  # same prompt as instructables
    in_h, out_h, tot_h = _compute_costs(tokens_h, prompt_tok_h, input_price, output_price)
    sources.append({
        "source": "Hackaday",
        "files": count_h,
        "chars": chars_h,
        "tokens": tokens_h + prompt_tok_h,
        "input_cost": in_h,
        "output_cost": out_h,
        "total": tot_h,
    })

    # Totals
    total_files = sum(s["files"] for s in sources)
    total_tokens = sum(s["tokens"] for s in sources)
    total_input = sum(s["input_cost"] for s in sources)
    total_output = sum(s["output_cost"] for s in sources)
    grand_total = total_input + total_output
    batch_total = grand_total * 0.5  # 50% batch API discount
    savings = grand_total - batch_total

    # Print table
    table = Table(title="ARK Pipeline — Cost Estimate")
    table.add_column("Source", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("Est. Tokens", justify="right")
    table.add_column("Input $", justify="right")
    table.add_column("Output $", justify="right")
    table.add_column("Total $", justify="right", style="green")

    for s in sources:
        table.add_row(
            s["source"],
            str(s["files"]),
            f"{s['tokens']:,}",
            f"${s['input_cost']:.2f}",
            f"${s['output_cost']:.2f}",
            f"${s['total']:.2f}",
        )

    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_files}[/bold]",
        f"[bold]{total_tokens:,}[/bold]",
        f"[bold]${total_input:.2f}[/bold]",
        f"[bold]${total_output:.2f}[/bold]",
        f"[bold]${grand_total:.2f}[/bold]",
    )
    CONSOLE.print(table)

    # Batch savings
    savings_table = Table(title="Batch API Savings (50% discount)")
    savings_table.add_column("Metric", style="cyan")
    savings_table.add_column("Value", justify="right", style="magenta")
    savings_table.add_row("Standard cost", f"${grand_total:.2f}")
    savings_table.add_row("Batch API cost", f"${batch_total:.2f}")
    savings_table.add_row("Savings", f"${savings:.2f}")
    CONSOLE.print(savings_table)

    logger.info(
        "Cost estimation complete",
        extra=log_extra(
            total_files=total_files,
            total_tokens=total_tokens,
            standard_cost=grand_total,
            batch_cost=batch_total,
            savings=savings,
        ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
