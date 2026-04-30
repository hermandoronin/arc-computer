#!/usr/bin/env python3
"""ARK Device Extractor — Extract structured Device + ComponentInstance data from iFixit guides.

This script consumes raw iFixit JSON teardown guides, sends them to the Claude API
(via the Anthropic Message Batches API for 50%% cost savings), validates the
returned JSON against the CDPO Pydantic schemas, and writes individual
``.json`` files per device.

Features
--------
- **Resume-safe**: skips already-extracted devices.
- **Batch API**: uses ``client.messages.batches`` when possible, falls back to
  direct ``client.messages.create`` for small subsets.
- **Cost tracking**: prints estimated cost every 100 guides.
- **Robust error handling**: single-guide failures are logged and skipped; the
  pipeline continues.
- **Structured logging**: JSON logs to file + human-readable console output.
- **Rich progress bar**: visual feedback during long runs.

Usage
-----
    python run_device_extractor.py --resume --subset 50
    python run_device_extractor.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
# Ensure schema / common imports work
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from common import (
    clean_ifixit_text,
    estimate_cost,
    estimate_tokens,
    get_anthropic_client,
    load_config,
    load_prompt,
    log_extra,
    safe_parse_json,
    setup_logging,
    Device,
    ComponentInstance,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_DIR = Path("/home/user/aisurvive/kb/output/raw/ifixit")
OUT_DIR = Path("/home/user/aisurvive/kb/output/extracted/devices")
PROMPT_FILE = "01-device-extractor.md"
CONSOLE = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _already_extracted(device_id: str) -> bool:
    """Check whether a device JSON already exists in the output directory.

    Args:
        device_id: Expected output stem (e.g. ``dev:epson-stylus-c88``).

    Returns:
        ``True`` if the file exists, ``False`` otherwise.
    """
    return (OUT_DIR / f"{device_id}.json").exists()


def _estimate_cost(text_length: int, prompt_length: int, config: Dict[str, Any]) -> float:
    """Estimate API call cost for a single guide.

    Args:
        text_length: Character length of the cleaned guide text.
        prompt_length: Character length of the prompt template.
        config: Loaded TOML config (used for pricing).

    Returns:
        Estimated USD cost.
    """
    cost_cfg = config.get("cost", {})
    return estimate_cost(
        text_length=text_length,
        prompt_length=prompt_length,
        input_price=cost_cfg.get("input_price_per_1k", 3.0),
        output_price=cost_cfg.get("output_price_per_1k", 15.0),
        output_ratio=0.33,
    )


def _write_device(device_id: str, data: Dict[str, Any]) -> None:
    """Persist a validated device record to disk.

    Args:
        device_id: Device identifier used as the file stem.
        data: Raw dict (already validated) to serialize.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{device_id}.json"
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Anthropic API interaction
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
    """Send a single request via the direct (non-batch) Anthropic API.

    Args:
        client: ``anthropic.Anthropic`` instance.
        model: Model identifier string.
        max_tokens: Maximum tokens to generate.
        messages: Anthropic-style message list.

    Returns:
        Raw text content of the assistant's response.
    """
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    # Anthropic SDK v0.28+ returns content as list of blocks
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
    """Build a single request payload for the Message Batches API.

    Args:
        custom_id: Unique identifier for correlation.
        model: Model identifier.
        max_tokens: Maximum tokens to generate.
        messages: Anthropic-style message list.

    Returns:
        Request dict compatible with ``client.messages.batches.create``.
    """
    return {
        "custom_id": custom_id,
        "params": {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        },
    }


def _submit_batch(
    client: Any,
    requests: List[Dict[str, Any]],
    logger: Any,
) -> str:
    """Submit a list of requests to the Anthropic Message Batches API.

    Args:
        client: ``anthropic.Anthropic`` instance.
        requests: List of batch request dicts.
        logger: Logger for progress / errors.

    Returns:
        Batch ID string.
    """
    logger.info("Submitting batch", extra=log_extra(batch_size=len(requests)))
    batch = client.messages.batches.create(requests=requests)
    return batch.id


def _poll_batch(
    client: Any,
    batch_id: str,
    logger: Any,
    poll_interval: int = 30,
    timeout: int = 3600,
) -> Any:
    """Poll a batch until it completes or times out.

    Args:
        client: ``anthropic.Anthropic`` instance.
        batch_id: Batch ID to poll.
        logger: Logger for status updates.
        poll_interval: Seconds between polls.
        timeout: Maximum seconds to wait.

    Returns:
        Final batch object.

    Raises:
        TimeoutError: If the batch does not finish within ``timeout``.
    """
    start = time.time()
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        status = getattr(batch, "processing_status", "unknown")
        logger.info("Batch status", extra=log_extra(batch_id=batch_id, status=status))
        if status in ("ended", "completed", "succeeded"):
            return batch
        if status in ("cancelled", "expired", "errored"):
            raise RuntimeError(f"Batch {batch_id} failed with status: {status}")
        if time.time() - start > timeout:
            raise TimeoutError(f"Batch {batch_id} did not complete within {timeout}s")
        time.sleep(poll_interval)


def _retrieve_batch_results(
    client: Any,
    batch_id: str,
) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """Retrieve all results from a completed batch.

    Args:
        client: ``anthropic.Anthropic`` instance.
        batch_id: Completed batch ID.

    Returns:
        List of ``(custom_id, result_text, error)`` tuples.  ``error`` is
        ``None`` on success; ``result_text`` is ``None`` on failure.
    """
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
            results.append((custom_id, None, "Empty response"))
    return results


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------


def _extract_single_device(
    guide_path: Path,
    client: Any,
    model: str,
    max_tokens: int,
    prompt_text: str,
    logger: Any,
    dry_run: bool = False,
) -> Optional[Dict[str, Any]]:
    """Extract a single device record from one iFixit guide.

    Args:
        guide_path: Path to the raw iFixit JSON file.
        client: Anthropic client.
        model: Model name.
        max_tokens: Generation limit.
        prompt_text: Full prompt template (system + user structure).
        logger: Logger instance.
        dry_run: If ``True``, skip the actual API call and return a mock.

    Returns:
        Validated device dict, or ``None`` on failure.
    """
    guide_id = guide_path.stem
    try:
        raw = json.loads(guide_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error(
            "Malformed guide JSON — skipped",
            extra=log_extra(guide_id=guide_id, error=str(exc)),
        )
        return None

    text = clean_ifixit_text(raw)
    if not text or len(text) < 50:
        logger.warning(
            "Guide text too short — skipped",
            extra=log_extra(guide_id=guide_id),
        )
        return None

    if dry_run:
        logger.info("[dry-run] Would extract", extra=log_extra(guide_id=guide_id))
        return {
            "device": {
                "id": f"dev:{guide_id}",
                "name": raw.get("title", guide_id),
                "category": "unknown",
                "popularity_score": 0.5,
                "teardown_difficulty": "medium",
                "extraction_confidence": 0.5,
            },
            "components_inside": [],
            "extraction_confidence": 0.5,
        }

    user_message = prompt_text.replace("{сюда вставляется raw text guide или transcript}", text)
    messages = [
        {"role": "user", "content": user_message},
    ]

    try:
        raw_response = _call_anthropic_direct(client, model, max_tokens, messages)
    except Exception as exc:
        logger.error(
            "API call failed",
            extra=log_extra(guide_id=guide_id, error=str(exc)),
        )
        return None

    try:
        parsed = safe_parse_json(raw_response)
    except json.JSONDecodeError as exc:
        logger.error(
            "LLM response not valid JSON — skipped",
            extra=log_extra(guide_id=guide_id, error=str(exc)),
        )
        return None

    # Validate via Pydantic
    device_data = parsed.get("device", parsed)
    components = parsed.get("components_inside", [])
    extraction_confidence = parsed.get("extraction_confidence", 0.5)

    try:
        validated_device = Device.model_validate(device_data)
    except ValidationError as exc:
        logger.error(
            "Device validation failed — skipped",
            extra=log_extra(guide_id=guide_id, error=str(exc)),
        )
        return None

    validated_components: List[Dict[str, Any]] = []
    for comp in components:
        try:
            validated_components.append(ComponentInstance.model_validate(comp).model_dump())
        except ValidationError as exc:
            logger.warning(
                "Component validation failed — skipped",
                extra=log_extra(guide_id=guide_id, component=comp.get("instance_id"), error=str(exc)),
            )

    return {
        "device": validated_device.model_dump(),
        "components_inside": validated_components,
        "extraction_confidence": extraction_confidence,
    }


# ---------------------------------------------------------------------------
# Batch extraction flow
# ---------------------------------------------------------------------------


def _extract_devices_batch(
    guide_paths: List[Path],
    client: Any,
    config: Dict[str, Any],
    prompt_text: str,
    logger: Any,
    dry_run: bool = False,
) -> Tuple[int, float]:
    """Extract a group of devices using the Message Batches API.

    Args:
        guide_paths: List of iFixit JSON file paths.
        client: Anthropic client.
        config: Loaded config dict.
        prompt_text: Prompt template text.
        logger: Logger.
        dry_run: If ``True``, skip API calls.

    Returns:
        ``(success_count, total_estimated_cost)``.
    """
    if dry_run:
        for gp in guide_paths:
            logger.info("[dry-run] Would batch", extra=log_extra(guide_id=gp.stem))
        return len(guide_paths), 0.0

    anthro_cfg = config.get("anthropic", {})
    model = anthro_cfg.get("model", "claude-sonnet-4-7-20250225")
    max_tokens = anthro_cfg.get("max_tokens_device", 8192)

    requests: List[Dict[str, Any]] = []
    guide_map: Dict[str, Path] = {}
    total_est_cost = 0.0

    for gp in guide_paths:
        guide_id = gp.stem
        try:
            raw = json.loads(gp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.error("Malformed JSON — skipped", extra=log_extra(guide_id=guide_id))
            continue

        text = clean_ifixit_text(raw)
        if not text or len(text) < 50:
            logger.warning("Guide text too short — skipped", extra=log_extra(guide_id=guide_id))
            continue

        total_est_cost += _estimate_cost(len(text), len(prompt_text), config)
        user_message = prompt_text.replace("{сюда вставляется raw text guide или transcript}", text)
        custom_id = f"guide_{guide_id}"
        guide_map[custom_id] = gp
        requests.append(_create_batch_request(custom_id, model, max_tokens, [
            {"role": "user", "content": user_message},
        ]))

    if not requests:
        return 0, 0.0

    batch_id = _submit_batch(client, requests, logger)
    logger.info("Batch submitted", extra=log_extra(batch_id=batch_id, requests=len(requests)))

    proc_cfg = config.get("processing", {})
    timeout = proc_cfg.get("timeout_seconds", 3600)
    _poll_batch(client, batch_id, logger, timeout=timeout)

    results = _retrieve_batch_results(client, batch_id)
    success = 0
    for custom_id, result_text, error in results:
        gp = guide_map.get(custom_id)
        if not gp:
            continue
        guide_id = gp.stem
        if error:
            logger.error("Batch result error", extra=log_extra(guide_id=guide_id, error=error))
            continue
        if result_text is None:
            logger.error("Empty batch result", extra=log_extra(guide_id=guide_id))
            continue

        try:
            parsed = safe_parse_json(result_text)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in batch result", extra=log_extra(guide_id=guide_id, error=str(exc)))
            continue

        device_data = parsed.get("device", parsed)
        components = parsed.get("components_inside", [])
        extraction_confidence = parsed.get("extraction_confidence", 0.5)

        try:
            validated_device = Device.model_validate(device_data)
        except ValidationError as exc:
            logger.error("Device validation failed", extra=log_extra(guide_id=guide_id, error=str(exc)))
            continue

        validated_components = []
        for comp in components:
            try:
                validated_components.append(ComponentInstance.model_validate(comp).model_dump())
            except ValidationError as exc:
                logger.warning("Component validation failed", extra=log_extra(guide_id=guide_id, error=str(exc)))

        out = {
            "device": validated_device.model_dump(),
            "components_inside": validated_components,
            "extraction_confidence": extraction_confidence,
        }
        _write_device(validated_device.id, out)
        success += 1

    return success, total_est_cost


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------


def _collect_guides(raw_dir: Path, resume: bool, subset: Optional[int]) -> List[Path]:
    """Collect iFixit guide JSON files, filtering out already-extracted ones.

    Args:
        raw_dir: Directory containing ``*.json`` iFixit guides.
        resume: If ``True``, skip files whose output already exists.
        subset: If set, limit to the first ``subset`` files.

    Returns:
        Sorted list of ``Path`` objects to process.
    """
    paths = sorted(raw_dir.glob("*.json"))
    if resume:
        paths = [p for p in paths if not _already_extracted(f"dev:{p.stem}")]
    if subset:
        paths = paths[:subset]
    return paths


def _print_progress(
    processed: int,
    total: int,
    start_time: float,
    total_est_cost: float,
) -> None:
    """Print a concise progress table to the console.

    Args:
        processed: Number of guides processed so far.
        total: Total number of guides.
        start_time: ``time.time()`` at start of run.
        total_est_cost: Accumulated estimated cost.
    """
    elapsed = time.time() - start_time
    rate = processed / (elapsed / 60.0) if elapsed > 0 else 0.0
    remaining = total - processed
    eta_mins = remaining / rate if rate > 0 else math.inf

    table = Table(title=f"Device Extraction Progress  ({processed}/{total})")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Guides/min", f"{rate:.1f}")
    table.add_row("Elapsed", f"{elapsed/60:.1f} min")
    table.add_row("ETA", f"{eta_mins:.1f} min" if eta_mins != math.inf else "∞")
    table.add_row("Est. cost", f"${total_est_cost:.2f}")
    CONSOLE.print(table)


def main(argv: List[str] | None = None) -> int:
    """Entry point for the device extractor.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code (0 on success, 1 on failure).
    """
    parser = argparse.ArgumentParser(description="ARK Device Extractor")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, simulate only")
    parser.add_argument("--subset", type=int, default=None, help="Process only N guides")
    parser.add_argument("--resume", action="store_true", help="Skip already-extracted devices")
    parser.add_argument("--batch", action="store_true", help="Use Message Batches API")
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    logger = setup_logging(
        level=config.get("logging", {}).get("level", "INFO"),
        log_dir=Path(config.get("paths", {}).get("extracted", OUT_DIR)) / "logs",
        script_name="device_extractor",
    )
    logger.info("Starting device extractor", extra=log_extra(dry_run=args.dry_run, subset=args.subset, resume=args.resume))

    prompt_text = load_prompt(PROMPT_FILE)
    guide_paths = _collect_guides(RAW_DIR, args.resume, args.subset)
    if not guide_paths:
        CONSOLE.print("[yellow]No guides to process.[/yellow]")
        return 0

    client = get_anthropic_client()
    anthro_cfg = config.get("anthropic", {})
    model = anthro_cfg.get("model", "claude-sonnet-4-7-20250225")
    max_tokens = anthro_cfg.get("max_tokens_device", 8192)
    batch_size = anthro_cfg.get("batch_size", 10000)

    total = len(guide_paths)
    processed = 0
    total_est_cost = 0.0
    start_time = time.time()
    successes = 0

    # Decide strategy: batch API or direct
    use_batch = args.batch or (not args.dry_run and total > 1)

    if use_batch and not args.dry_run:
        # Chunk into batch-size groups
        for i in range(0, total, batch_size):
            chunk = guide_paths[i : i + batch_size]
            chunk_success, chunk_cost = _extract_devices_batch(
                chunk, client, config, prompt_text, logger, dry_run=args.dry_run
            )
            successes += chunk_success
            total_est_cost += chunk_cost
            processed += len(chunk)
            if processed % 100 == 0 or processed == total:
                _print_progress(processed, total, start_time, total_est_cost)
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=CONSOLE,
        ) as progress:
            task = progress.add_task("Extracting devices...", total=total)
            for gp in guide_paths:
                guide_id = gp.stem
                result = _extract_single_device(
                    gp, client, model, max_tokens, prompt_text, logger, dry_run=args.dry_run
                )
                if result:
                    _write_device(result["device"]["id"], result)
                    successes += 1
                processed += 1
                progress.update(task, advance=1)

                cost = _estimate_cost(
                    len(clean_ifixit_text(json.loads(gp.read_text(encoding="utf-8")))),
                    len(prompt_text),
                    config,
                )
                total_est_cost += cost

                if processed % 100 == 0:
                    _print_progress(processed, total, start_time, total_est_cost)

    elapsed = time.time() - start_time
    CONSOLE.print(f"[green]Done![/green] Successes: {successes}/{total}  "
                  f"Elapsed: {elapsed/60:.1f} min  Est. cost: ${total_est_cost:.2f}")
    logger.info(
        "Device extractor finished",
        extra=log_extra(successes=successes, total=total, elapsed_sec=elapsed, est_cost=total_est_cost),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
