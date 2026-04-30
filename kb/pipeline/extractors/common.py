"""Shared utilities for the ARK knowledge extraction pipeline.

Provides common helpers for:
- Configuration loading (TOML)
- Structured JSON logging
- Retry policies (tenacity)
- Anthropic SDK setup
- Schema imports (sys.path manipulation)
- Rich progress reporting
- Token / cost estimation
- File I/O helpers
"""

from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

import httpx
import tomli
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# ---------------------------------------------------------------------------
# Schema import — inject schemas directory into sys.path
# ---------------------------------------------------------------------------

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"
if str(_SCHEMAS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCHEMAS_DIR.parent))

try:
    from schemas.cdpo import (
        ComponentInstance,
        Device,
        Project,
        ProjectDonorLink,
        SubstitutionChain,
        KnowledgeBase,
        KBMetadata,
        ID_PREFIX_DEVICE,
        ID_PREFIX_PROJECT,
        ID_PREFIX_INSTANCE,
    )
except ImportError as _e:
    raise ImportError(
        f"Could not import schemas from {_SCHEMAS_DIR}: {_e}"
    ) from _e

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).resolve().parent / "config.toml"


def load_config(path: Path | None = None) -> Dict[str, Any]:
    """Load the pipeline configuration from a TOML file.

    Args:
        path: Path to the TOML config file. Defaults to ``config.toml``
            next to this module.

    Returns:
        Parsed TOML as a nested dict.
    """
    target = path or CONFIG_PATH
    if not target.exists():
        raise FileNotFoundError(f"Config file not found: {target}")
    with target.open("rb") as fh:
        return tomli.load(fh)


# ---------------------------------------------------------------------------
# Token / cost estimation
# ---------------------------------------------------------------------------

RE_HTML_TAG = re.compile(r"<[^>]+>")
RE_CJK = re.compile(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]")


def estimate_tokens(text: str) -> int:
    """Rough token estimate for mixed English/CJK text.

    Rule of thumb:
    - English: ~4 chars / token
    - CJK: ~2 chars / token

    Args:
        text: Raw text string.

    Returns:
        Estimated token count.
    """
    if not text:
        return 0
    cjk_chars = len(RE_CJK.findall(text))
    non_cjk_chars = len(text) - cjk_chars
    return max(1, non_cjk_chars // 4 + cjk_chars // 2)


def estimate_cost(
    text_length: int,
    prompt_length: int,
    input_price: float,
    output_price: float,
    output_ratio: float = 0.33,
) -> float:
    """Rough cost estimate in USD.

    Args:
        text_length: Length of input text (chars).
        prompt_length: Length of system prompt (chars).
        input_price: Price per 1k input tokens (USD).
        output_price: Price per 1k output tokens (USD).
        output_ratio: Assumed output tokens / input tokens ratio.

    Returns:
        Estimated cost in USD.
    """
    input_tokens = estimate_tokens("x" * text_length) + estimate_tokens("x" * prompt_length)
    output_tokens = int(input_tokens * output_ratio)
    return (input_tokens / 1000 * input_price) + (output_tokens / 1000 * output_price)


# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            payload.update(record.extra)  # type: ignore[attr-defined]
        return json.dumps(payload, default=str)


def setup_logging(
    level: str = "INFO",
    log_dir: Path | None = None,
    script_name: str = "pipeline",
) -> logging.Logger:
    """Configure structured JSON logging to both console and file.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_dir: Directory for log files. Created if missing.
        script_name: Used to build the log file name.

    Returns:
        A configured ``logging.Logger``.
    """
    logger = logging.getLogger("ark_kb")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    # Console — human readable (Rich is used elsewhere; keep simple here)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
    )
    logger.addHandler(console)

    # File — JSON structured
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{script_name}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.log"
        fh = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10_000_000, backupCount=5
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(JSONFormatter())
        logger.addHandler(fh)

    return logger


def log_extra(**kwargs: Any) -> Dict[str, Any]:
    """Build an 'extra' dict compatible with JSONFormatter."""
    return {"extra": kwargs}


# ---------------------------------------------------------------------------
# Retry decorators
# ---------------------------------------------------------------------------

RETRY_POLICY: Callable[[Any], Any] = retry(
    retry=retry_if_exception_type(
        (httpx.HTTPStatusError, httpx.NetworkError, httpx.TimeoutException)
    ),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)


def get_retry_policy(attempts: int = 5) -> Callable[[Any], Any]:
    """Return a tenacity retry decorator tuned for HTTP errors.

    Retries on 429 / 5xx from ``httpx.HTTPStatusError`` as well as
    network and timeout errors, with exponential backoff.

    Args:
        attempts: Maximum retry attempts.

    Returns:
        A tenacity ``retry`` decorator.
    """
    return retry(
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, httpx.NetworkError, httpx.TimeoutException)
        ),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(attempts),
        reraise=True,
    )


# ---------------------------------------------------------------------------
# Anthropic client setup
# ---------------------------------------------------------------------------

def get_anthropic_client(api_key: str | None = None) -> Any:
    """Create an Anthropic client instance.

    Args:
        api_key: Anthropic API key. If ``None``, reads from
            ``ANTHROPIC_API_KEY`` environment variable.

    Returns:
        An ``anthropic.Anthropic`` client.

    Raises:
        ImportError: If ``anthropic`` package is not installed.
        ValueError: If no API key is available.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise ImportError("anthropic SDK is required. Install: pip install anthropic") from exc

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError(
            "Anthropic API key required. Set ANTHROPIC_API_KEY env var or pass api_key."
        )
    return anthropic.Anthropic(api_key=key)


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL file, skipping blank / malformed lines.

    Args:
        path: Path to ``.jsonl`` file.

    Returns:
        List of parsed JSON objects.
    """
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def hash_list(items: List[str]) -> str:
    """Return a stable SHA-256 hex digest of a sorted string list.

    Args:
        items: List of strings to hash.

    Returns:
        64-character hex digest.
    """
    payload = "|".join(sorted(items))
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# HTML stripping helper
# ---------------------------------------------------------------------------

def strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace.

    Args:
        html: Raw HTML string.

    Returns:
        Plain text with paragraph structure preserved.
    """
    text = RE_HTML_TAG.sub("", html)
    # Collapse multiple whitespace but keep paragraph breaks
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Clean iFixit guide text
# ---------------------------------------------------------------------------

def clean_ifixit_text(guide_json: Dict[str, Any]) -> str:
    """Extract clean plain text from an iFixit guide JSON.

    Preserves paragraph structure and includes title, steps, tools, parts.

    Args:
        guide_json: Raw iFixit guide as parsed JSON dict.

    Returns:
        Clean multi-line text suitable for LLM consumption.
    """
    parts: List[str] = []

    title = guide_json.get("title") or guide_json.get("display_title") or ""
    if title:
        parts.append(f"# {title}")

    summary = guide_json.get("summary") or guide_json.get("introduction") or ""
    if summary:
        parts.append(strip_html(summary))

    tools = guide_json.get("tools", [])
    if tools:
        parts.append("## Tools Required")
        for tool in tools:
            if isinstance(tool, dict):
                parts.append(f"- {tool.get('text', '')}")
            elif isinstance(tool, str):
                parts.append(f"- {tool}")

    parts_list = guide_json.get("parts", [])
    if parts_list:
        parts.append("## Parts")
        for part in parts_list:
            if isinstance(part, dict):
                parts.append(f"- {part.get('text', '')}")
            elif isinstance(part, str):
                parts.append(f"- {part}")

    steps = guide_json.get("steps", [])
    if steps:
        parts.append("## Steps")
        for idx, step in enumerate(steps, start=1):
            lines = [f"### Step {idx}"]
            step_text = step.get("text") or step.get("instructions") or ""
            if step_text:
                lines.append(strip_html(step_text))
            media = step.get("media", [])
            for m in media:
                caption = m.get("caption") or m.get("text", "")
                if caption:
                    lines.append(f"[image] {strip_html(caption)}")
            parts.append("\n".join(lines))

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

def load_prompt(prompt_name: str) -> str:
    """Load a prompt markdown file from the ``prompts/`` directory.

    Args:
        prompt_name: File name under ``prompts/`` (e.g.
            ``01-device-extractor.md``).

    Returns:
        Prompt text as a string.
    """
    prompts_dir = Path(__file__).resolve().parent / "prompts"
    path = prompts_dir / prompt_name
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Safe JSON parsing from LLM response
# ---------------------------------------------------------------------------

def safe_parse_json(text: str) -> Any:
    """Extract and parse JSON from an LLM response string.

    Handles markdown fences, trailing prose, and common LLM formatting.

    Args:
        text: Raw LLM response text.

    Returns:
        Parsed JSON object (dict, list, etc.).

    Raises:
        json.JSONDecodeError: If no valid JSON is found.
    """
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    fence_re = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
    matches = fence_re.findall(text)
    for candidate in matches:
        candidate = candidate.strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # Try to find the first [ or { and parse from there
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        try:
            start_idx = text.index(start_char)
            # Brute-force attempt: try parsing progressively shorter suffixes
            for end_idx in range(len(text), start_idx, -1):
                snippet = text[start_idx:end_idx]
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    continue
        except ValueError:
            continue

    raise json.JSONDecodeError("No valid JSON found in LLM response", text, 0)


# ---------------------------------------------------------------------------
# Async httpx client helper
# ---------------------------------------------------------------------------

async def get_async_client(timeout: float = 120.0) -> httpx.AsyncClient:
    """Create a pre-configured async ``httpx.AsyncClient``.

    Args:
        timeout: Request timeout in seconds.

    Returns:
        Configured async HTTP client.
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=10.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "load_config",
    "setup_logging",
    "log_extra",
    "get_anthropic_client",
    "get_retry_policy",
    "get_async_client",
    "estimate_tokens",
    "estimate_cost",
    "clean_ifixit_text",
    "strip_html",
    "load_prompt",
    "load_jsonl",
    "hash_list",
    "safe_parse_json",
    # Schema re-exports for convenience
    "Device",
    "ComponentInstance",
    "Project",
    "ProjectDonorLink",
    "SubstitutionChain",
    "KnowledgeBase",
    "KBMetadata",
]
