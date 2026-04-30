#!/usr/bin/env python3
"""ARK Substitution Builder — Generate component substitution chains.

Collects every unique ``component_canonical`` value found across all
extracted devices and projects, batches them into groups of 50, and sends
each batch to Claude to generate substitution chains. Results are validated
as ``List[SubstitutionChain]`` and written to a JSONL file.

Features
--------
- **Resume-safe**: tracks batches by hash; skips already-processed groups.
- **Batch API**: uses Message Batches for cost efficiency.
- **Deduplication**: collects unique component names across the entire corpus.

Usage
-----
    python run_substitution.py --resume --subset 3
    python run_substitution.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import ValidationError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from common import (
    estimate_cost,
    get_anthropic_client,
    hash_list,
    load_config,
    load_jsonl,
    load_prompt,
    log_extra,
    safe_parse_json,
    setup_logging,
    Device,
    Project,
    SubstitutionChain,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEVICES_DIR = Path("/home/user/aisurvive/kb/output/extracted/devices")
PROJECTS_DIR = Path("/home/user/aisurvive/kb/output/extracted/projects")
OUT_FILE = Path("/home/user/aisurvive/kb/output/substitutions/substitutions.jsonl")
PROMPT_FILE = "04-substitution.md"
BATCH_SIZE = 50
CONSOLE = Console()

# ---------------------------------------------------------------------------
# Component collection
# ---------------------------------------------------------------------------


def _collect_unique_components() -> List[str]:
    """Gather every unique component_canonical across devices and projects.

    Returns:
        Sorted list of unique component canonical names.
    """
    components: Set[str] = set()

    if DEVICES_DIR.exists():
        for path in DEVICES_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for comp in data.get("components_inside", []):
                    canonical = comp.get("component_canonical")
                    if canonical:
                        components.add(canonical)
            except (json.JSONDecodeError, KeyError):
                continue

    if PROJECTS_DIR.exists():
        for path in PROJECTS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for bom in data.get("bom_logical", []):
                    cls_name = bom.get("component_class")
                    if cls_name:
                        components.add(cls_name)
                for rec in data.get("salvage_recommendations", []):
                    cls_name = rec.get("component_class")
                    if cls_name:
                        components.add(cls_name)
            except (json.JSONDecodeError, KeyError):
                continue

    return sorted(components)


# ---------------------------------------------------------------------------
# Progress / resume tracking
# ---------------------------------------------------------------------------


def _load_processed_hashes() -> Set[str]:
    """Load hashes of already-processed component batches.

    Scans the JSONL output and reconstructs batch hashes from stored metadata.

    Returns:
        Set of SHA-256 hex digests.
    """
    processed: Set[str] = set()
    if not OUT_FILE.exists():
        return processed
    for record in load_jsonl(OUT_FILE):
        # We inject a "_batch_hash" field at write time
        h = record.get("_batch_hash", "")
        if h:
            processed.add(h)
    return processed


# ---------------------------------------------------------------------------
# Anthropic interaction
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _call_anthropic_direct(
    client: Any,
    model: str,
    max_tokens: int,
    messages: List[Dict[str, str]],
) -> str:
    """Direct API call."""
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    content = response.content
    if isinstance(content, list) and content:
        return content[0].text
    return str(content)


def _create_batch_request(
    custom_id: str,
    model: str,
    max_tokens: int,
    messages: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Build batch request payload."""
    return {
        "custom_id": custom_id,
        "params": {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        },
    }


def _submit_batch(client: Any, requests: List[Dict[str, Any]], logger: Any) -> str:
    """Submit to Message Batches API."""
    logger.info("Submitting substitution batch", extra=log_extra(batch_size=len(requests)))
    batch = client.messages.batches.create(requests=requests)
    return batch.id


def _poll_batch(
    client: Any,
    batch_id: str,
    logger: Any,
    poll_interval: int = 30,
    timeout: int = 3600,
) -> Any:
    """Poll batch until completion."""
    start = time.time()
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        status = getattr(batch, "processing_status", "unknown")
        logger.info("Batch status", extra=log_extra(batch_id=batch_id, status=status))
        if status in ("ended", "completed", "succeeded"):
            return batch
        if status in ("cancelled", "expired", "errored"):
            raise RuntimeError(f"Batch {batch_id} failed: {status}")
        if time.time() - start > timeout:
            raise TimeoutError(f"Batch {batch_id} timed out")
        time.sleep(poll_interval)


def _retrieve_batch_results(client: Any, batch_id: str) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """Fetch batch results."""
    results: List[Tuple[str, Optional[str], Optional[str]]] = []
    for result in client.messages.batches.results(batch_id):
        custom_id = getattr(result, "custom_id", "unknown")
        msg = getattr(result, "message", None)
        error = getattr(result, "error", None)
        if error:
            results.append((custom_id, None, str(error)))
            continue
        if msg and msg.content:
            text = msg.content[0].text if msg.content else ""
            results.append((custom_id, text, None))
        else:
            results.append((custom_id, None, "Empty"))
    return results


# ---------------------------------------------------------------------------
# Core substitution extraction
# ---------------------------------------------------------------------------


def _extract_substitutions_batch(
    component_batch: List[str],
    client: Any,
    config: Dict[str, Any],
    prompt_text: str,
    logger: Any,
    dry_run: bool = False,
) -> Tuple[Optional[List[Dict[str, Any]]], float]:
    """Request substitution chains for one batch of components.

    Args:
        component_batch: List of component canonical names.
        client: Anthropic client.
        config: Loaded config.
        prompt_text: Prompt template.
        logger: Logger.
        dry_run: Skip API if ``True``.

    Returns:
        ``(list_of_chains, estimated_cost)`` or ``(None, 0.0)`` on failure.
    """
    if dry_run:
        logger.info("[dry-run] Would substitute", extra=log_extra(batch_size=len(component_batch)))
        return [], 0.0

    anthro_cfg = config.get("anthropic", {})
    model = anthro_cfg.get("model", "claude-sonnet-4-7-20250225")
    max_tokens = anthro_cfg.get("max_tokens_substitution", 8192)

    batch_json = json.dumps(component_batch, ensure_ascii=False)
    user_message = prompt_text.replace(
        '[\n  "TL431 (programmable shunt regulator)",\n  "ATmega328P",\n  ...\n]',
        batch_json,
    )
    # Fallback if exact placeholder didn't match
    if "TL431" in user_message:
        # The placeholder wasn't replaced — try a broader replacement
        user_message = prompt_text + f"\n\nCOMPONENTS:\n{batch_json}"

    messages = [{"role": "user", "content": user_message}]
    est_cost = estimate_cost(
        len(user_message), len(prompt_text),
        config.get("cost", {}).get("input_price_per_1k", 3.0),
        config.get("cost", {}).get("output_price_per_1k", 15.0),
    )

    try:
        raw_response = _call_anthropic_direct(client, model, max_tokens, messages)
    except Exception as exc:
        logger.error("API call failed", extra=log_extra(error=str(exc)))
        return None, est_cost

    try:
        parsed = safe_parse_json(raw_response)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON", extra=log_extra(error=str(exc)))
        return None, est_cost

    if not isinstance(parsed, list):
        logger.error("Expected array response")
        return None, est_cost

    valid_chains: List[Dict[str, Any]] = []
    for item in parsed:
        try:
            chain = SubstitutionChain.model_validate(item)
            valid_chains.append(chain.model_dump())
        except ValidationError as exc:
            logger.warning("Chain validation failed", extra=log_extra(error=str(exc), item=item.get("component")))

    return valid_chains, est_cost


def _extract_substitutions_batch_api(
    batches: List[List[str]],
    client: Any,
    config: Dict[str, Any],
    prompt_text: str,
    logger: Any,
    dry_run: bool = False,
) -> Tuple[int, float]:
    """Process multiple component batches via the Message Batches API.

    Args:
        batches: List of component name lists.
        client: Anthropic client.
        config: Loaded config.
        prompt_text: Prompt template.
        logger: Logger.
        dry_run: Skip API calls if ``True``.

    Returns:
        ``(success_count, total_estimated_cost)``.
    """
    if dry_run:
        for b in batches:
            logger.info("[dry-run] Would batch-substitute", extra=log_extra(batch_size=len(b)))
        return len(batches), 0.0

    anthro_cfg = config.get("anthropic", {})
    model = anthro_cfg.get("model", "claude-sonnet-4-7-20250225")
    max_tokens = anthro_cfg.get("max_tokens_substitution", 8192)

    requests: List[Dict[str, Any]] = []
    batch_map: Dict[str, List[str]] = {}
    total_est_cost = 0.0

    for idx, component_batch in enumerate(batches):
        batch_json = json.dumps(component_batch, ensure_ascii=False)
        user_message = prompt_text.replace(
            '[\n  "TL431 (programmable shunt regulator)",\n  "ATmega328P",\n  ...\n]',
            batch_json,
        )
        if "TL431" in user_message:
            user_message = prompt_text + f"\n\nCOMPONENTS:\n{batch_json}"
        custom_id = f"sub_batch_{idx}"
        batch_map[custom_id] = component_batch
        total_est_cost += estimate_cost(
            len(user_message), len(prompt_text),
            config.get("cost", {}).get("input_price_per_1k", 3.0),
            config.get("cost", {}).get("output_price_per_1k", 15.0),
        )
        requests.append(_create_batch_request(custom_id, model, max_tokens, [
            {"role": "user", "content": user_message},
        ]))

    if not requests:
        return 0, 0.0

    batch_id = _submit_batch(client, requests, logger)
    proc_cfg = config.get("processing", {})
    timeout = proc_cfg.get("timeout_seconds", 3600)
    _poll_batch(client, batch_id, logger, timeout=timeout)

    results = _retrieve_batch_results(client, batch_id)
    success = 0
    for custom_id, result_text, error in results:
        component_batch = batch_map.get(custom_id, [])
        if error:
            logger.error("Batch error", extra=log_extra(error=error))
            continue
        if result_text is None:
            logger.error("Empty result")
            continue
        try:
            parsed = safe_parse_json(result_text)
        except json.JSONDecodeError as exc:
            logger.error("JSON parse failed", extra=log_extra(error=str(exc)))
            continue
        if not isinstance(parsed, list):
            logger.error("Expected array")
            continue
        valid_chains = []
        for item in parsed:
            try:
                chain = SubstitutionChain.model_validate(item)
                valid_chains.append(chain.model_dump())
            except ValidationError as exc:
                logger.warning("Validation failed", extra=log_extra(error=str(exc)))
        if valid_chains:
            batch_hash = hash_list(component_batch)
            _append_chains(valid_chains, batch_hash)
            success += 1

    return success, total_est_cost


def _append_chains(chains: List[Dict[str, Any]], batch_hash: str) -> None:
    """Append substitution chains to JSONL, tagging with the batch hash.

    Args:
        chains: Validated chain dicts.
        batch_hash: SHA-256 of the component batch for resume tracking.
    """
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("a", encoding="utf-8") as fh:
        for chain in chains:
            chain["_batch_hash"] = batch_hash
            fh.write(json.dumps(chain, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------


def _print_progress(
    processed: int,
    total: int,
    start_time: float,
    total_est_cost: float,
) -> None:
    """Print progress table."""
    elapsed = time.time() - start_time
    rate = processed / (elapsed / 60.0) if elapsed > 0 else 0.0
    remaining = total - processed
    eta = remaining / rate if rate > 0 else math.inf
    table = Table(title=f"Substitution Progress  ({processed}/{total})")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Batches/min", f"{rate:.1f}")
    table.add_row("Elapsed", f"{elapsed/60:.1f} min")
    table.add_row("ETA", f"{eta:.1f} min" if eta != math.inf else "∞")
    table.add_row("Est. cost", f"${total_est_cost:.2f}")
    CONSOLE.print(table)


def main(argv: List[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: CLI args.

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(description="ARK Substitution Builder")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--subset", type=int, default=None, help="Process only N batches")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    logger = setup_logging(
        level=config.get("logging", {}).get("level", "INFO"),
        log_dir=Path(config.get("paths", {}).get("substitutions", OUT_FILE.parent)) / "logs",
        script_name="substitution",
    )
    logger.info("Starting substitution builder", extra=log_extra(dry_run=args.dry_run, subset=args.subset, resume=args.resume))

    prompt_text = load_prompt(PROMPT_FILE)
    components = _collect_unique_components()
    if not components:
        CONSOLE.print("[red]No components found — nothing to substitute.[/red]")
        return 1

    CONSOLE.print(f"[dim]Found {len(components)} unique components[/dim]")

    processed_hashes = _load_processed_hashes() if args.resume else set()
    batches = [components[i : i + BATCH_SIZE] for i in range(0, len(components), BATCH_SIZE)]
    # Filter out already-processed
    if args.resume:
        batches = [b for b in batches if hash_list(b) not in processed_hashes]
    if args.subset:
        batches = batches[:args.subset]

    if not batches:
        CONSOLE.print("[yellow]All batches already processed.[/yellow]")
        return 0

    client = get_anthropic_client()
    anthro_cfg = config.get("anthropic", {})
    model = anthro_cfg.get("model", "claude-sonnet-4-7-20250225")
    max_tokens = anthro_cfg.get("max_tokens_substitution", 8192)
    api_batch_size = anthro_cfg.get("batch_size", 10000)

    total = len(batches)
    processed = 0
    total_est_cost = 0.0
    start_time = time.time()
    successes = 0

    use_batch = args.batch or (not args.dry_run and total > 1)

    if use_batch and not args.dry_run:
        # Group batches into API-sized chunks
        for i in range(0, total, api_batch_size):
            chunk = batches[i : i + api_batch_size]
            chunk_success, chunk_cost = _extract_substitutions_batch_api(
                chunk, client, config, prompt_text, logger, dry_run=args.dry_run,
            )
            successes += chunk_success
            total_est_cost += chunk_cost
            processed += len(chunk)
            if processed % 10 == 0 or processed == total:
                _print_progress(processed, total, start_time, total_est_cost)
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=CONSOLE,
        ) as progress:
            task = progress.add_task("Building substitutions...", total=total)
            for component_batch in batches:
                chains, cost = _extract_substitutions_batch(
                    component_batch, client, config, prompt_text, logger, dry_run=args.dry_run,
                )
                if chains is not None and chains:
                    batch_hash = hash_list(component_batch)
                    _append_chains(chains, batch_hash)
                    successes += 1
                total_est_cost += cost
                processed += 1
                progress.update(task, advance=1)
                if processed % 10 == 0:
                    _print_progress(processed, total, start_time, total_est_cost)

    elapsed = time.time() - start_time
    CONSOLE.print(f"[green]Done![/green] Successes: {successes}/{total}  "
                  f"Elapsed: {elapsed/60:.1f} min  Est. cost: ${total_est_cost:.2f}")
    logger.info(
        "Substitution builder finished",
        extra=log_extra(successes=successes, total=total, elapsed_sec=elapsed, est_cost=total_est_cost),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
