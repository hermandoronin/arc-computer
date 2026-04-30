#!/usr/bin/env python3
"""ARK Linker — Create Project↔Device donor links.

For every extracted project, the linker loads a ranked sample of devices,
builds compact summaries, and asks Claude to decide which concrete devices
from the sample are viable donors for the project's BOM. Results are
validated as ``List[ProjectDonorLink]`` and appended to a JSONL file.

Features
--------
- **Resume-safe**: skips projects already present in the JSONL output.
- **Relevance pruning**: selects top-N devices per project via keyword
  overlap (salvage recommendations + component classes), keeping prompts
  within token limits.
- **Batch or direct API**: configurable via ``--batch``.
- **Appending JSONL**: results are appended, not overwritten, so partial
  runs can be resumed safely.

Usage
-----
    python run_linker.py --resume --subset 10
    python run_linker.py --batch --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
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
    load_config,
    load_prompt,
    load_jsonl,
    log_extra,
    safe_parse_json,
    setup_logging,
    Device,
    Project,
    ProjectDonorLink,
    ID_PREFIX_DEVICE,
    ID_PREFIX_PROJECT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEVICES_DIR = Path("/home/user/aisurvive/kb/output/extracted/devices")
PROJECTS_DIR = Path("/home/user/aisurvive/kb/output/extracted/projects")
OUT_FILE = Path("/home/user/aisurvive/kb/output/linked/project-donors.jsonl")
PROMPT_FILE = "03-linker.md"
CONSOLE = Console()
DEFAULT_TOP_N = 200

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_devices() -> List[Device]:
    """Load and validate all extracted devices, sorted by popularity descending.

    Returns:
        Sorted list of ``Device`` models.
    """
    devices: List[Device] = []
    if not DEVICES_DIR.exists():
        return devices
    for path in sorted(DEVICES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            dev_data = data.get("device", data)
            devices.append(Device.model_validate(dev_data))
        except (json.JSONDecodeError, ValidationError) as exc:
            # Silently skip malformed files during linking
            continue
    devices.sort(key=lambda d: d.popularity_score, reverse=True)
    return devices


def _load_projects() -> List[Project]:
    """Load and validate all extracted projects.

    Returns:
        List of ``Project`` models.
    """
    projects: List[Project] = []
    if not PROJECTS_DIR.exists():
        return projects
    for path in sorted(PROJECTS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            prj_data = data.get("project", data)
            projects.append(Project.model_validate(prj_data))
        except (json.JSONDecodeError, ValidationError):
            continue
    return projects


def _already_linked(project_id: str, existing: Dict[str, bool]) -> bool:
    """Check whether a project already has links in the JSONL file.

    Args:
        project_id: Project ID to check.
        existing: Set-like dict of known linked project IDs.

    Returns:
        ``True`` if already linked.
    """
    return existing.get(project_id, False)


def _load_existing_links() -> Dict[str, bool]:
    """Scan the JSONL output and collect already-linked project IDs.

    Returns:
        Dict mapping ``project_id → True`` for all IDs found.
    """
    existing: Dict[str, bool] = {}
    if not OUT_FILE.exists():
        return existing
    for record in load_jsonl(OUT_FILE):
        pid = record.get("project_id", "")
        if pid:
            existing[pid] = True
    return existing


def _build_device_summary(device: Device) -> Dict[str, Any]:
    """Create a compact dict representation of a device for the linker prompt.

    Keeps the summary to ~100 tokens by focusing on identifiers,
    category, and component class names.

    Args:
        device: Full ``Device`` model.

    Returns:
        Compact dict with the most linker-relevant fields.
    """
    component_names = [c.component_canonical for c in device.components_inside[:8]]
    return {
        "id": device.id,
        "name": device.name,
        "category": device.category,
        "popularity_score": device.popularity_score,
        "teardown_difficulty": device.teardown_difficulty,
        "components": component_names,
    }


def _collect_keywords(project: Project) -> Set[str]:
    """Collect search keywords from a project for device relevance scoring.

    Sources: salvage_recommendations (salvage_from_devices + rationale),
    bom_logical component_class, and goals.

    Args:
        project: The project to analyze.

    Returns:
        Normalized set of keyword tokens.
    """
    keywords: Set[str] = set()
    for rec in project.salvage_recommendations:
        for dev in rec.salvage_from_devices:
            keywords.update(re.findall(r"[A-Za-z0-9_]+", dev.lower()))
        keywords.update(re.findall(r"[A-Za-z0-9_]+", rec.rationale.lower()))
        keywords.add(rec.component_class.lower())
    for bom in project.bom_logical:
        keywords.add(bom.component_class.lower())
        for ex in bom.specific_examples:
            keywords.update(re.findall(r"[A-Za-z0-9_]+", ex.lower()))
    for goal in project.goals:
        keywords.add(goal.lower())
    return {k for k in keywords if len(k) > 2}


def _score_relevance(project: Project, device: Device, project_keywords: Set[str]) -> float:
    """Score how relevant a device is for a project.

    Computes Jaccard-like overlap between project keywords and device
    component canonical names / category.

    Args:
        project: The project needing components.
        device: Candidate donor device.
        project_keywords: Pre-computed keyword set for the project.

    Returns:
        Relevance score (0.0–1.0, higher is better).
    """
    dev_keywords: Set[str] = set()
    dev_keywords.add(device.category.lower())
    for c in device.components_inside:
        dev_keywords.add(c.component_canonical.lower())
        dev_keywords.add(c.type.lower())
    if not project_keywords:
        return 0.0
    intersection = project_keywords & dev_keywords
    union = project_keywords | dev_keywords
    return len(intersection) / len(union) if union else 0.0


def _select_relevant_devices(
    project: Project,
    all_devices: List[Device],
    top_n: int = DEFAULT_TOP_N,
) -> List[Device]:
    """Select the top-N most relevant devices for a given project.

    Args:
        project: Project to match against.
        all_devices: All available devices (pre-sorted by popularity).
        top_n: Maximum devices to return.

    Returns:
        Sub-list of devices, highest relevance first.
    """
    keywords = _collect_keywords(project)
    scored = [(dev, _score_relevance(project, dev, keywords)) for dev in all_devices]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [dev for dev, score in scored[:top_n] if score > 0]


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
    """Direct API call (non-batch)."""
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
    """Build a batch request payload."""
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
    logger.info("Submitting linker batch", extra=log_extra(batch_size=len(requests)))
    batch = client.messages.batches.create(requests=requests)
    return batch.id


def _poll_batch(
    client: Any,
    batch_id: str,
    logger: Any,
    poll_interval: int = 30,
    timeout: int = 3600,
) -> Any:
    """Poll until batch completes."""
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
# Core linking
# ---------------------------------------------------------------------------


def _link_single_project(
    project: Project,
    devices: List[Device],
    client: Any,
    model: str,
    max_tokens: int,
    prompt_text: str,
    logger: Any,
    dry_run: bool = False,
    top_n: int = DEFAULT_TOP_N,
) -> Optional[List[Dict[str, Any]]]:
    """Link one project to its relevant devices.

    Args:
        project: Project to link.
        devices: All available devices.
        client: Anthropic client.
        model: Model name.
        max_tokens: Generation limit.
        prompt_text: Prompt template.
        logger: Logger.
        dry_run: Skip API call if ``True``.
        top_n: Number of devices to consider.

    Returns:
        List of validated link dicts, or ``None`` on failure.
    """
    selected = _select_relevant_devices(project, devices, top_n=top_n)
    if not selected:
        logger.info("No relevant devices found", extra=log_extra(project_id=project.id))
        return []

    device_summaries = [_build_device_summary(d) for d in selected]
    project_json = project.model_dump_json(indent=None)

    user_block = (
        f"PROJECT: {project_json}\n\n"
        f"DEVICES_SAMPLE: {json.dumps(device_summaries, ensure_ascii=False)}"
    )

    if dry_run:
        logger.info("[dry-run] Would link", extra=log_extra(
            project_id=project.id,
            devices_considered=len(selected),
        ))
        return []

    full_prompt = prompt_text.replace("{project_json}", project_json).replace(
        "[{device_json}, {device_json}, ...]", json.dumps(device_summaries)
    )
    # If replacement failed (placeholder format mismatch), use direct substitution
    if "{project_json}" in full_prompt:
        full_prompt = prompt_text.replace("{project_json}", project_json)
    if "[{device_json}, {device_json}, ...]" in full_prompt:
        full_prompt = full_prompt.replace(
            "[{device_json}, {device_json}, ...]",
            json.dumps(device_summaries),
        )

    messages = [{"role": "user", "content": full_prompt}]

    try:
        raw_response = _call_anthropic_direct(client, model, max_tokens, messages)
    except Exception as exc:
        logger.error("API call failed", extra=log_extra(project_id=project.id, error=str(exc)))
        return None

    try:
        parsed = safe_parse_json(raw_response)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON", extra=log_extra(project_id=project.id, error=str(exc)))
        return None

    if not isinstance(parsed, list):
        logger.error("Expected array response", extra=log_extra(project_id=project.id))
        return None

    valid_links: List[Dict[str, Any]] = []
    for item in parsed:
        try:
            link = ProjectDonorLink.model_validate(item)
            valid_links.append(link.model_dump())
        except ValidationError as exc:
            logger.warning("Link validation failed", extra=log_extra(project_id=project.id, error=str(exc)))

    return valid_links


def _link_projects_batch(
    projects: List[Project],
    devices: List[Device],
    client: Any,
    config: Dict[str, Any],
    prompt_text: str,
    logger: Any,
    dry_run: bool = False,
    top_n: int = DEFAULT_TOP_N,
) -> Tuple[int, float]:
    """Link multiple projects via the Message Batches API.

    Args:
        projects: Projects to link.
        devices: All available devices.
        client: Anthropic client.
        config: Loaded config.
        prompt_text: Prompt template.
        logger: Logger.
        dry_run: Skip API calls if ``True``.
        top_n: Devices per project.

    Returns:
        ``(success_count, total_estimated_cost)``.
    """
    if dry_run:
        for p in projects:
            logger.info("[dry-run] Would batch-link", extra=log_extra(project_id=p.id))
        return len(projects), 0.0

    anthro_cfg = config.get("anthropic", {})
    model = anthro_cfg.get("model", "claude-sonnet-4-7-20250225")
    max_tokens = anthro_cfg.get("max_tokens_linker", 8192)

    requests: List[Dict[str, Any]] = []
    proj_map: Dict[str, Project] = {}
    total_est_cost = 0.0

    for project in projects:
        selected = _select_relevant_devices(project, devices, top_n=top_n)
        if not selected:
            continue
        summaries = [_build_device_summary(d) for d in selected]
        proj_json = project.model_dump_json(indent=None)
        full_prompt = prompt_text.replace("{project_json}", proj_json).replace(
            "[{device_json}, {device_json}, ...]", json.dumps(summaries)
        )
        total_est_cost += estimate_cost(
            len(full_prompt), len(prompt_text),
            config.get("cost", {}).get("input_price_per_1k", 3.0),
            config.get("cost", {}).get("output_price_per_1k", 15.0),
        )
        custom_id = f"link_{project.id}"
        proj_map[custom_id] = project
        requests.append(_create_batch_request(custom_id, model, max_tokens, [
            {"role": "user", "content": full_prompt},
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
        project = proj_map.get(custom_id)
        if not project:
            continue
        if error:
            logger.error("Batch error", extra=log_extra(project_id=project.id, error=error))
            continue
        if result_text is None:
            logger.error("Empty result", extra=log_extra(project_id=project.id))
            continue
        try:
            parsed = safe_parse_json(result_text)
        except json.JSONDecodeError as exc:
            logger.error("JSON parse failed", extra=log_extra(project_id=project.id, error=str(exc)))
            continue
        if not isinstance(parsed, list):
            logger.error("Expected array", extra=log_extra(project_id=project.id))
            continue
        valid_links = []
        for item in parsed:
            try:
                link = ProjectDonorLink.model_validate(item)
                valid_links.append(link.model_dump())
            except ValidationError as exc:
                logger.warning("Validation failed", extra=log_extra(project_id=project.id, error=str(exc)))
        if valid_links:
            _append_links(valid_links)
            success += 1

    return success, total_est_cost


def _append_links(links: List[Dict[str, Any]]) -> None:
    """Append validated links to the JSONL output file.

    Args:
        links: List of link dicts.
    """
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("a", encoding="utf-8") as fh:
        for link in links:
            fh.write(json.dumps(link, ensure_ascii=False) + "\n")


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
    table = Table(title=f"Linker Progress  ({processed}/{total})")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Projects/min", f"{rate:.1f}")
    table.add_row("Elapsed", f"{elapsed/60:.1f} min")
    table.add_row("ETA", f"{eta:.1f} min" if eta != math.inf else "∞")
    table.add_row("Est. cost", f"${total_est_cost:.2f}")
    CONSOLE.print(table)


def main(argv: List[str] | None = None) -> int:
    """Entry point for the linker.

    Args:
        argv: CLI args.

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(description="ARK Project↔Device Linker")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--subset", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N, help="Devices per project")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    logger = setup_logging(
        level=config.get("logging", {}).get("level", "INFO"),
        log_dir=Path(config.get("paths", {}).get("linked", OUT_FILE.parent)) / "logs",
        script_name="linker",
    )
    logger.info("Starting linker", extra=log_extra(dry_run=args.dry_run, subset=args.subset, resume=args.resume))

    prompt_text = load_prompt(PROMPT_FILE)
    devices = _load_devices()
    projects = _load_projects()
    if not devices:
        CONSOLE.print("[red]No devices loaded — cannot link.[/red]")
        return 1
    if not projects:
        CONSOLE.print("[red]No projects loaded — nothing to link.[/red]")
        return 1

    CONSOLE.print(f"[dim]Loaded {len(devices)} devices, {len(projects)} projects[/dim]")

    existing = _load_existing_links() if args.resume else {}
    pending = [p for p in projects if not _already_linked(p.id, existing)]
    if args.subset:
        pending = pending[:args.subset]

    if not pending:
        CONSOLE.print("[yellow]All projects already linked.[/yellow]")
        return 0

    client = get_anthropic_client()
    anthro_cfg = config.get("anthropic", {})
    model = anthro_cfg.get("model", "claude-sonnet-4-7-20250225")
    max_tokens = anthro_cfg.get("max_tokens_linker", 8192)
    batch_size = anthro_cfg.get("batch_size", 10000)

    total = len(pending)
    processed = 0
    total_est_cost = 0.0
    start_time = time.time()
    successes = 0

    use_batch = args.batch or (not args.dry_run and total > 1)

    if use_batch and not args.dry_run:
        for i in range(0, total, batch_size):
            chunk = pending[i : i + batch_size]
            chunk_success, chunk_cost = _link_projects_batch(
                chunk, devices, client, config, prompt_text, logger,
                dry_run=args.dry_run, top_n=args.top_n,
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
            task = progress.add_task("Linking projects...", total=total)
            for project in pending:
                links = _link_single_project(
                    project, devices, client, model, max_tokens,
                    prompt_text, logger, dry_run=args.dry_run, top_n=args.top_n,
                )
                if links is not None:
                    if links:
                        _append_links(links)
                    successes += 1
                processed += 1
                progress.update(task, advance=1)
                if processed % 100 == 0:
                    _print_progress(processed, total, start_time, total_est_cost)

    elapsed = time.time() - start_time
    CONSOLE.print(f"[green]Linker done![/green] Successes: {successes}/{total}  "
                  f"Elapsed: {elapsed/60:.1f} min  Est. cost: ${total_est_cost:.2f}")
    logger.info(
        "Linker finished",
        extra=log_extra(successes=successes, total=total, elapsed_sec=elapsed, est_cost=total_est_cost),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
