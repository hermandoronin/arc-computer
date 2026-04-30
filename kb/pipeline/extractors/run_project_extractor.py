#!/usr/bin/env python3
"""ARK Project Extractor — Extract structured Project data from Instructables / Hackaday.

Consumes raw Instructables HTML and Hackaday JSON, extracts clean text,
sends to Claude via Anthropic Message Batches API (or direct fallback),
validates against the CDPO ``Project`` schema, and writes per-project JSON.

Features
--------
- **Multi-source**: handles both HTML (Instructables) and JSON (Hackaday).
- **Resume-safe**: skips already-extracted projects.
- **Cost tracking**: prints estimated cost every 100 projects.
- **Rich progress**: visual progress bar.
- **Structured JSON logging**.
- **Graceful degradation**: single-project failures are logged and skipped.

Usage
-----
    python run_project_extractor.py --resume --subset 20
    python run_project_extractor.py --dry-run
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
# Path setup
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from common import (
    estimate_cost,
    estimate_tokens,
    get_anthropic_client,
    load_config,
    load_prompt,
    log_extra,
    safe_parse_json,
    setup_logging,
    strip_html,
    Project,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_INSTRUCTABLES = Path("/home/user/aisurvive/kb/output/raw/instructables")
RAW_HACKADAY = Path("/home/user/aisurvive/kb/output/raw/hackaday")
OUT_DIR = Path("/home/user/aisurvive/kb/output/extracted/projects")
PROMPT_FILE = "02-project-extractor.md"
CONSOLE = Console()

RE_HTML_TAG = re.compile(r"<[^>]+>")
RE_CJK = re.compile(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _already_extracted(project_id: str) -> bool:
    """Check whether a project JSON already exists.

    Args:
        project_id: Expected file stem (e.g. ``prj:solar-charge-controller``).

    Returns:
        ``True`` if the output file exists.
    """
    return (OUT_DIR / f"{project_id}.json").exists()


def _write_project(project_id: str, data: Dict[str, Any]) -> None:
    """Persist a validated project record.

    Args:
        project_id: Project identifier used as the file stem.
        data: Validated dict to serialize.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{project_id}.json"
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _extract_instructables_text(html_path: Path) -> str:
    """Extract clean text from an Instructables HTML file.

    Uses ``beautifulsoup4`` when available; falls back to a regex-based
    tag stripper.

    Args:
        html_path: Path to the raw HTML file.

    Returns:
        Clean multi-line text.
    """
    raw_html = html_path.read_text(encoding="utf-8")
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw_html, "html.parser")
        # Remove script/style/nav/footer noise
        for tag_name in ("script", "style", "nav", "footer", "header", "aside"):
            for tag in soup.find_all(tag_name):
                tag.decompose()
        # Try to find main content area
        main = soup.find("main") or soup.find("article") or soup.find("div", class_="content")
        if main:
            text = main.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)
        # Collapse excessive blank lines
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n\n".join(lines)
    except ImportError:
        return strip_html(raw_html)


def _extract_hackaday_text(json_path: Path) -> str:
    """Extract clean text from a Hackaday JSON record.

    Args:
        json_path: Path to the raw Hackaday JSON file.

    Returns:
        Clean multi-line text.
    """
    data = json.loads(json_path.read_text(encoding="utf-8"))
    parts: List[str] = []
    title = data.get("title") or data.get("name", "")
    if title:
        parts.append(f"# {title}")
    summary = data.get("summary") or data.get("description") or ""
    if summary:
        parts.append(strip_html(summary))
    body = data.get("body") or data.get("content") or data.get("text", "")
    if body:
        parts.append(strip_html(body))
    steps = data.get("steps", [])
    if steps:
        parts.append("## Steps")
        for step in steps:
            if isinstance(step, dict):
                s_text = step.get("text") or step.get("instruction", "")
                if s_text:
                    parts.append(s_text)
            elif isinstance(step, str):
                parts.append(step)
    return "\n\n".join(parts)


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
    """Send a single request via the direct Anthropic API.

    Args:
        client: ``anthropic.Anthropic`` instance.
        model: Model identifier.
        max_tokens: Generation limit.
        messages: Anthropic-style message list.

    Returns:
        Raw assistant response text.
    """
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
    """Build a batch request payload.

    Args:
        custom_id: Unique correlation ID.
        model: Model name.
        max_tokens: Generation limit.
        messages: Anthropic messages.

    Returns:
        Batch request dict.
    """
    return {
        "custom_id": custom_id,
        "params": {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        },
    }


def _submit_batch(client: Any, requests: List[Dict[str, Any]], logger: Any) -> str:
    """Submit requests to the Message Batches API.

    Args:
        client: Anthropic client.
        requests: List of request dicts.
        logger: Logger.

    Returns:
        Batch ID.
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
    """Poll a batch until completion.

    Args:
        client: Anthropic client.
        batch_id: Batch ID.
        logger: Logger.
        poll_interval: Seconds between polls.
        timeout: Max wait in seconds.

    Returns:
        Final batch object.

    Raises:
        TimeoutError: If batch does not finish in time.
        RuntimeError: If batch fails.
    """
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


def _retrieve_batch_results(
    client: Any,
    batch_id: str,
) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """Fetch results from a completed batch.

    Args:
        client: Anthropic client.
        batch_id: Completed batch ID.

    Returns:
        List of ``(custom_id, text, error)`` tuples.
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


def _extract_single_project(
    source_path: Path,
    source_type: str,
    client: Any,
    model: str,
    max_tokens: int,
    prompt_text: str,
    logger: Any,
    dry_run: bool = False,
) -> Optional[Dict[str, Any]]:
    """Extract a single project record.

    Args:
        source_path: Path to the raw file.
        source_type: ``instructables`` or ``hackaday``.
        client: Anthropic client.
        model: Model name.
        max_tokens: Generation limit.
        prompt_text: Prompt template.
        logger: Logger.
        dry_run: Skip API call if ``True``.

    Returns:
        Validated project dict, or ``None`` on failure.
    """
    project_id_stub = source_path.stem
    if source_type == "instructables":
        text = _extract_instructables_text(source_path)
    else:
        text = _extract_hackaday_text(source_path)

    if not text or len(text) < 50:
        logger.warning(
            "Project text too short — skipped",
            extra=log_extra(project_id=project_id_stub, source_type=source_type),
        )
        return None

    if dry_run:
        logger.info("[dry-run] Would extract", extra=log_extra(project_id=project_id_stub))
        return {
            "project": {
                "id": f"prj:{project_id_stub}",
                "name": project_id_stub,
                "summary": "Dry-run mock",
                "difficulty": "basic",
                "extraction_confidence": 0.5,
            },
            "bom_logical": [],
            "salvage_recommendations": [],
            "extraction_confidence": 0.5,
        }

    user_message = prompt_text.replace("{сюда полный текст проекта}", text)
    messages = [{"role": "user", "content": user_message}]

    try:
        raw_response = _call_anthropic_direct(client, model, max_tokens, messages)
    except Exception as exc:
        logger.error(
            "API call failed",
            extra=log_extra(project_id=project_id_stub, error=str(exc)),
        )
        return None

    try:
        parsed = safe_parse_json(raw_response)
    except json.JSONDecodeError as exc:
        logger.error(
            "LLM response not valid JSON",
            extra=log_extra(project_id=project_id_stub, error=str(exc)),
        )
        return None

    project_data = parsed.get("project", parsed)
    bom = parsed.get("bom_logical", [])
    salvage = parsed.get("salvage_recommendations", [])
    extraction_confidence = parsed.get("extraction_confidence", 0.5)

    try:
        validated_project = Project.model_validate(project_data)
    except ValidationError as exc:
        logger.error(
            "Project validation failed",
            extra=log_extra(project_id=project_id_stub, error=str(exc)),
        )
        return None

    return {
        "project": validated_project.model_dump(),
        "bom_logical": bom,
        "salvage_recommendations": salvage,
        "extraction_confidence": extraction_confidence,
    }


def _extract_projects_batch(
    items: List[Tuple[Path, str]],
    client: Any,
    config: Dict[str, Any],
    prompt_text: str,
    logger: Any,
    dry_run: bool = False,
) -> Tuple[int, float]:
    """Extract a group of projects via the Message Batches API.

    Args:
        items: List of ``(path, source_type)`` tuples.
        client: Anthropic client.
        config: Loaded config.
        prompt_text: Prompt template.
        logger: Logger.
        dry_run: Skip API calls if ``True``.

    Returns:
        ``(success_count, total_estimated_cost)``.
    """
    if dry_run:
        for path, stype in items:
            logger.info("[dry-run] Would batch", extra=log_extra(project_id=path.stem, source=stype))
        return len(items), 0.0

    anthro_cfg = config.get("anthropic", {})
    model = anthro_cfg.get("model", "claude-sonnet-4-7-20250225")
    max_tokens = anthro_cfg.get("max_tokens_project", 8192)

    requests: List[Dict[str, Any]] = []
    item_map: Dict[str, Tuple[Path, str]] = {}
    total_est_cost = 0.0

    for path, stype in items:
        if stype == "instructables":
            text = _extract_instructables_text(path)
        else:
            text = _extract_hackaday_text(path)
        if not text or len(text) < 50:
            logger.warning("Text too short", extra=log_extra(project_id=path.stem))
            continue
        total_est_cost += estimate_cost(
            len(text), len(prompt_text),
            config.get("cost", {}).get("input_price_per_1k", 3.0),
            config.get("cost", {}).get("output_price_per_1k", 15.0),
        )
        custom_id = f"{stype}_{path.stem}"
        item_map[custom_id] = (path, stype)
        user_msg = prompt_text.replace("{сюда полный текст проекта}", text)
        requests.append(_create_batch_request(custom_id, model, max_tokens, [
            {"role": "user", "content": user_msg},
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
        path, stype = item_map.get(custom_id, (None, None))
        if not path:
            continue
        pid = path.stem
        if error:
            logger.error("Batch result error", extra=log_extra(project_id=pid, error=error))
            continue
        if result_text is None:
            logger.error("Empty batch result", extra=log_extra(project_id=pid))
            continue
        try:
            parsed = safe_parse_json(result_text)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON", extra=log_extra(project_id=pid, error=str(exc)))
            continue
        project_data = parsed.get("project", parsed)
        try:
            validated = Project.model_validate(project_data)
        except ValidationError as exc:
            logger.error("Validation failed", extra=log_extra(project_id=pid, error=str(exc)))
            continue
        out = {
            "project": validated.model_dump(),
            "bom_logical": parsed.get("bom_logical", []),
            "salvage_recommendations": parsed.get("salvage_recommendations", []),
            "extraction_confidence": parsed.get("extraction_confidence", 0.5),
        }
        _write_project(validated.id, out)
        success += 1

    return success, total_est_cost


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------


def _collect_projects(
    resume: bool,
    subset: Optional[int],
) -> List[Tuple[Path, str]]:
    """Collect all raw project files from both sources.

    Args:
        resume: Skip already-extracted.
        subset: Limit to first ``subset`` files total.

    Returns:
        List of ``(path, source_type)`` tuples.
    """
    items: List[Tuple[Path, str]] = []
    for html_path in sorted(RAW_INSTRUCTABLES.glob("*.html")):
        pid = f"prj:{html_path.stem}"
        if resume and _already_extracted(pid):
            continue
        items.append((html_path, "instructables"))
    for json_path in sorted(RAW_HACKADAY.glob("*.json")):
        pid = f"prj:{json_path.stem}"
        if resume and _already_extracted(pid):
            continue
        items.append((json_path, "hackaday"))
    if subset:
        items = items[:subset]
    return items


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
    table = Table(title=f"Project Extraction Progress  ({processed}/{total})")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Projects/min", f"{rate:.1f}")
    table.add_row("Elapsed", f"{elapsed/60:.1f} min")
    table.add_row("ETA", f"{eta:.1f} min" if eta != math.inf else "∞")
    table.add_row("Est. cost", f"${total_est_cost:.2f}")
    CONSOLE.print(table)


def main(argv: List[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: CLI args (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(description="ARK Project Extractor")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--subset", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--batch", action="store_true", help="Use Message Batches API")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    logger = setup_logging(
        level=config.get("logging", {}).get("level", "INFO"),
        log_dir=Path(config.get("paths", {}).get("extracted", OUT_DIR)) / "logs",
        script_name="project_extractor",
    )
    logger.info(
        "Starting project extractor",
        extra=log_extra(dry_run=args.dry_run, subset=args.subset, resume=args.resume),
    )

    prompt_text = load_prompt(PROMPT_FILE)
    items = _collect_projects(args.resume, args.subset)
    if not items:
        CONSOLE.print("[yellow]No projects to process.[/yellow]")
        return 0

    client = get_anthropic_client()
    anthro_cfg = config.get("anthropic", {})
    model = anthro_cfg.get("model", "claude-sonnet-4-7-20250225")
    max_tokens = anthro_cfg.get("max_tokens_project", 8192)
    batch_size = anthro_cfg.get("batch_size", 10000)

    total = len(items)
    processed = 0
    total_est_cost = 0.0
    start_time = time.time()
    successes = 0

    use_batch = args.batch or (not args.dry_run and total > 1)

    if use_batch and not args.dry_run:
        for i in range(0, total, batch_size):
            chunk = items[i : i + batch_size]
            chunk_success, chunk_cost = _extract_projects_batch(
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
            task = progress.add_task("Extracting projects...", total=total)
            for path, stype in items:
                result = _extract_single_project(
                    path, stype, client, model, max_tokens, prompt_text, logger, dry_run=args.dry_run
                )
                if result:
                    _write_project(result["project"]["id"], result)
                    successes += 1
                processed += 1
                progress.update(task, advance=1)

                # rough cost
                text_len = len(_extract_instructables_text(path)) if stype == "instructables" else len(_extract_hackaday_text(path))
                total_est_cost += estimate_cost(
                    text_len, len(prompt_text),
                    config.get("cost", {}).get("input_price_per_1k", 3.0),
                    config.get("cost", {}).get("output_price_per_1k", 15.0),
                )
                if processed % 100 == 0:
                    _print_progress(processed, total, start_time, total_est_cost)

    elapsed = time.time() - start_time
    CONSOLE.print(f"[green]Done![/green] Successes: {successes}/{total}  "
                  f"Elapsed: {elapsed/60:.1f} min  Est. cost: ${total_est_cost:.2f}")
    logger.info(
        "Project extractor finished",
        extra=log_extra(successes=successes, total=total, elapsed_sec=elapsed, est_cost=total_est_cost),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
