#!/usr/bin/env python3
"""Extract projects from Instructables/Hackaday using DeepSeek V4 Flash.

Phase A: 30 Instructables electronics projects
Phase B: 1000 Instructables + 300 Hackaday
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic
from anthropic import AsyncAnthropic

# Config
RAW_DIR = Path("/home/user/aisurvive/kb/output/raw/instructables")
OUT_DIR = Path("/home/user/aisurvive/kb/output/extracted-bulk/projects")
PROMPT_DIR = Path("/home/user/aisurvive/kb/pipeline/extractors/prompts")
FAILED_LOG = Path("/home/user/aisurvive/kb/output/extracted-bulk/validation-reports/projects-failures.jsonl")
BUDGET_FILE = Path("/home/user/aisurvive/agents/deepseek/budget_flash.json")
SCHEMAS_DIR = Path("/home/user/aisurvive/kb/pipeline/schemas")

CONCURRENCY = 30
MODEL = "deepseek-v4-flash"
MAX_TOKENS = 16384
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")

# Try env vars, then fall back to reading the multi-ai .env
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    env_file = Path("/home/user/.claude/mcp-servers/multi-ai/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DEEPSEEK_API_KEY="):
                API_KEY = line.split("=", 1)[1].strip().strip("\"'")
                break

if not API_KEY:
    print("FATAL: No API key. Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY")
    sys.exit(1)

sys.path.insert(0, str(SCHEMAS_DIR))
from cdpo import Project, BomEntry, Provenance
from pydantic import ValidationError

# Load prompts
ANTI_LAZY = (PROMPT_DIR / "00-anti-laziness-preamble.md").read_text(encoding="utf-8").strip()
PROJECT_PROMPT_RAW = (PROMPT_DIR / "02-project-extractor.md").read_text(encoding="utf-8").strip()


def build_prompt(project_text: str) -> str:
    combined = ANTI_LAZY + "\n\n" + PROJECT_PROMPT_RAW
    return combined.replace("{сюда полный текст проекта}", project_text)


def clean_instructables_text(data: dict) -> str:
    """Convert Instructables scraped JSON to readable text for the LLM."""
    parts = []

    title = data.get("title", "")
    if title:
        parts.append(f"# {title}")

    url = data.get("url", "")
    if url:
        parts.append(f"Source: {url}")

    author = data.get("author", "")
    if author:
        parts.append(f"Author: {author}")

    desc = data.get("description", "")
    if desc:
        parts.append(f"## Description\n{desc}")

    supplies = data.get("supplies", [])
    if supplies:
        parts.append("## Supplies / Materials / Parts")
        for s in supplies:
            if s:
                parts.append(f"- {s}")

    tools = data.get("tools", [])
    if tools:
        parts.append("## Tools")
        for t in tools:
            if t:
                parts.append(f"- {t}")

    steps = data.get("steps", [])
    if steps:
        parts.append("## Steps")
        for i, step in enumerate(steps, start=1):
            name = step.get("name", "")
            text = step.get("text", "")
            step_text = f"### Step {i}"
            if name:
                step_text += f": {name}"
            if text:
                step_text += f"\n{text}"
            parts.append(step_text)

    return "\n\n".join(parts)


def clean_hackaday_text(data: dict) -> str:
    """Convert Hackaday scraped JSON to readable text for the LLM."""
    parts = []

    title = data.get("title", "")
    if title:
        parts.append(f"# {title}")

    url = data.get("url", "")
    if url:
        parts.append(f"Source: {url}")

    author = data.get("author", "")
    if author:
        parts.append(f"Author: {author}")

    tags = data.get("tags", [])
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")

    summary = data.get("summary", "")
    if summary:
        parts.append(f"## Summary\n{summary}")

    description = data.get("description", "")
    if description:
        parts.append(f"## Description\n{description}")

    details = data.get("details", "")
    if details:
        parts.append(f"## Details\n{details}")

    components = data.get("components", [])
    if components:
        parts.append("## Components / Parts")
        for c in components:
            if c:
                parts.append(f"- {c}")

    instructions = data.get("instructions", [])
    if instructions:
        parts.append("## Instructions")
        for i, instr in enumerate(instructions, start=1):
            if instr:
                parts.append(f"### Step {i}\n{instr}")

    logs = data.get("logs", [])
    if logs:
        parts.append("## Project Logs")
        for log in logs:
            log_title = log.get("title", "")
            log_body = log.get("body", "")
            if log_title and log_body:
                parts.append(f"### {log_title}\n{log_body}")
            elif log_body:
                parts.append(log_body)

    return "\n\n".join(parts)


def detect_source_type(path: Path) -> str:
    """Detect if a JSON file is from Instructables or Hackaday."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "slug" in data or "steps" in data:
            return "instructables"
        if "project_id" in data or "tags" in data:
            return "hackaday"
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        pass
    # Fallback: check directory name
    parent = path.parent.name
    if "hackaday" in parent:
        return "hackaday"
    return "instructables"


def parse_response(text: str) -> dict | None:
    parsed = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass
    if parsed is None:
        fence = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
        for match in fence.findall(text):
            try:
                parsed = json.loads(match.strip())
                break
            except json.JSONDecodeError:
                continue
    if parsed is None:
        for start_c, end_c in [("[", "]"), ("{", "}")]:
            try:
                si = text.index(start_c)
                for ei in range(len(text), si, -1):
                    try:
                        parsed = json.loads(text[si:ei])
                        break
                    except json.JSONDecodeError:
                        continue
                if parsed is not None:
                    break
            except ValueError:
                continue
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}
    if not isinstance(parsed, dict):
        return None
    return parsed


GOAL_VALUES = {"energy", "water", "food", "comms", "security", "medical", "manufacture", "info"}
DIFFICULTY_VALUES = {"basic", "intermediate", "advanced"}
SAFETY_HAZARD_VALUES = {
    "high_voltage", "mains_voltage", "capacitor_charge", "rf_radiation",
    "laser", "chemical", "asbestos", "mercury", "lead", "radioactive",
    "sharp", "pinch_crush", "burn_hot", "burn_cold", "biological",
}
# Prompt uses non-standard names that must be mapped to CDPO enum values
SAFETY_HAZARD_ALIASES = {
    "lethal_capacitor_charge": "capacitor_charge",
    "mains_lethal": "mains_voltage",
    "lethal": "high_voltage",
}


def validate_output(parsed: dict, project_slug: str) -> dict | None:
    project_data = parsed.get("project", parsed)
    bom_logical = parsed.get("bom_logical", [])
    salvage_recs = parsed.get("salvage_recommendations", [])
    confidence = parsed.get("extraction_confidence", 0.5)

    # Anti-laziness check
    raw_str = json.dumps(parsed, ensure_ascii=False).lower()
    for pat in ["remove screws", "disconnect wires", '"internal"', '"various"',
                 "consult professional", "see datasheet", "depends on model"]:
        if pat in raw_str:
            return None

    # Build ID from slug
    prj_id = f"prj:{project_slug.lower()}"
    project_data["id"] = prj_id

    # Map goals to valid values
    if "goals" in project_data:
        valid_goals = []
        for g in project_data["goals"]:
            if g in GOAL_VALUES:
                valid_goals.append(g)
        project_data["goals"] = valid_goals or ["manufacture"]

    # Map difficulty
    if "difficulty" in project_data:
        diff = project_data["difficulty"]
        if diff not in DIFFICULTY_VALUES:
            project_data["difficulty"] = "intermediate"

    # Map safety_hazards (with alias resolution for prompt-specific names)
    if "safety_hazards" in project_data:
        valid_hazards = []
        for h in project_data["safety_hazards"]:
            if h in SAFETY_HAZARD_VALUES:
                valid_hazards.append(h)
            elif h in SAFETY_HAZARD_ALIASES:
                valid_hazards.append(SAFETY_HAZARD_ALIASES[h])
        project_data["safety_hazards"] = valid_hazards

    # Normalize troubleshooting entries: prompt uses 'likely_cause' (str),
    # CDPO requires 'likely_causes' (list[str]) + 'diagnostic_steps' (list[str])
    if "troubleshooting" in project_data:
        normalized = []
        for entry in project_data["troubleshooting"]:
            if not isinstance(entry, dict):
                continue
            # Map likely_cause → likely_causes
            if "likely_cause" in entry and "likely_causes" not in entry:
                entry["likely_causes"] = [entry.pop("likely_cause")]
            elif "likely_causes" not in entry:
                entry["likely_causes"] = []
            if "diagnostic_steps" not in entry:
                entry["diagnostic_steps"] = []
            normalized.append(entry)
        project_data["troubleshooting"] = normalized

    # Coerce estimated_hours from string to float
    if "estimated_hours" in project_data and isinstance(project_data["estimated_hours"], str):
        try:
            import re
            nums = re.findall(r"[\d.]+", project_data["estimated_hours"])
            if nums:
                project_data["estimated_hours"] = float(nums[0])
            else:
                project_data["estimated_hours"] = None
        except (ValueError, TypeError):
            project_data["estimated_hours"] = None

    # Convert bom_logical to required_components (BomEntry list)
    required_components = []
    for entry in bom_logical:
        if not isinstance(entry, dict):
            continue
        comp_class = entry.get("component_class", "")
        if not comp_class:
            continue
        cmp_id = f"cmp:{comp_class.lower().replace(' ', '_').replace('/', '_')}"
        qty = entry.get("quantity", 1)
        try:
            qty = int(qty)
        except (ValueError, TypeError):
            qty = 1
        if qty <= 0:
            qty = 1
        notes = entry.get("purpose_in_circuit", "")
        examples = entry.get("specific_examples", [])
        if examples and notes:
            notes = f"{notes} (e.g., {', '.join(examples[:3])})"
        elif examples:
            notes = f"Examples: {', '.join(examples[:3])}"
        substitutes = []
        sub_hint = entry.get("substitution_hints", "")
        if sub_hint:
            substitutes.append(sub_hint)
        try:
            required_components.append(
                BomEntry(component_id=cmp_id, quantity=qty, notes=notes or None, substitutes=substitutes).model_dump()
            )
        except (ValidationError, TypeError, ValueError):
            pass

    project_data["required_components"] = required_components

    # Validate against CDPO Project
    try:
        validated_project = Project.model_validate(project_data)
    except ValidationError:
        return None

    result = validated_project.model_dump()

    # Attach extraction-specific fields
    result["bom_logical"] = bom_logical
    result["salvage_recommendations"] = salvage_recs
    result["extraction_confidence"] = confidence

    return result


def update_budget(input_tokens: int, output_tokens: int, cache_read_tokens: int = 0):
    # Flash pricing: $0.14/M input, $0.28/M output, cache 10% of input
    cost = (input_tokens / 1_000_000) * 0.14 + (output_tokens / 1_000_000) * 0.28 + (cache_read_tokens / 1_000_000) * 0.014
    budget = json.loads(BUDGET_FILE.read_text())
    budget["spent_usd"] = round(budget.get("spent_usd", 0) + cost, 6)
    budget["calls"] = budget.get("calls", 0) + 1
    if budget.get("started_at") is None:
        budget["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    BUDGET_FILE.write_text(json.dumps(budget, indent=2, ensure_ascii=False) + "\n")
    return cost, budget["spent_usd"]


def check_budget():
    budget = json.loads(BUDGET_FILE.read_text())
    spent = budget.get("spent_usd", 0)
    cap = budget.get("cap_usd", 15.0)
    soft_warn = budget.get("soft_warning_at_usd", 10.0)
    if spent >= cap:
        print(f"  *** BUDGET CAP HIT: ${spent:.2f} >= ${cap} ***")
        return False
    if spent >= soft_warn:
        print(f"  *** SOFT WARN: ${spent:.2f} >= ${soft_warn} ***")
    return True


async def extract_one(sem: asyncio.Semaphore, client: anthropic.Anthropic, project_path: Path, counter: dict):
    slug = project_path.stem
    prj_id = f"prj:{slug.lower()}"
    out_path = OUT_DIR / f"{prj_id}.json"

    if out_path.exists():
        counter["existing"] += 1
        return {"status": "skip_existing"}

    try:
        raw = json.loads(project_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        counter["failed"] += 1
        return {"status": "error", "reason": "bad_json", "slug": slug}

    source_type = detect_source_type(project_path)
    cleaner = clean_hackaday_text if source_type == "hackaday" else clean_instructables_text
    text = cleaner(raw)
    if not text or len(text) < 50:
        counter["failed"] += 1
        return {"status": "error", "reason": "text_too_short", "slug": slug}

    prompt = build_prompt(text)

    async with sem:
        try:
            resp = await client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": ANTI_LAZY + "\n\n" + PROJECT_PROMPT_RAW.replace(
                            "{сюда полный текст проекта}",
                            "{project_text}"
                        ),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": text}],
                thinking={"type": "disabled"},
            )
        except Exception as exc:
            counter["failed"] += 1
            return {"status": "error", "reason": f"api_error: {exc}", "slug": slug}

    raw_text = ""
    for block in resp.content:
        if hasattr(block, "text"):
            raw_text += block.text

    parsed = parse_response(raw_text)
    if parsed is None:
        counter["failed"] += 1
        FAILED_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FAILED_LOG, "a") as f:
            f.write(json.dumps({"slug": slug, "reason": "json_parse_failed", "raw_preview": raw_text[:200]}) + "\n")
        return {"status": "error", "reason": "json_parse_failed", "slug": slug}

    validated = validate_output(parsed, slug)
    if validated is None:
        counter["failed"] += 1
        FAILED_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FAILED_LOG, "a") as f:
            f.write(json.dumps({"slug": slug, "reason": "validation_or_lazy_reject"}) + "\n")
        return {"status": "error", "reason": "validation_or_lazy_reject", "slug": slug}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(validated, indent=2, ensure_ascii=False), encoding="utf-8")

    in_tok = resp.usage.input_tokens if resp.usage else 0
    out_tok = resp.usage.output_tokens if resp.usage else 0
    cache_read = getattr(resp.usage, "cache_read_input_tokens", 0) or 0
    cost, spent = update_budget(in_tok, out_tok, cache_read)
    counter["success"] += 1
    counter["total_cost"] += cost
    counter["total_input_tokens"] += in_tok
    counter["total_output_tokens"] += out_tok

    print(f"  OK [{counter['success']}] {prj_id} "
          f"({in_tok}+{out_tok} tok, ${cost:.4f}, total ${spent:.4f})  "
          f"steps: {len(validated.get('assembly_steps', []))}, "
          f"bom: {len(validated.get('bom_logical', []))}")
    return {"status": "ok", "slug": slug, "project_id": prj_id}


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_LOG.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Create budget file if not exists
    if not BUDGET_FILE.exists():
        BUDGET_FILE.write_text(json.dumps({
            "spent_usd": 0.0, "calls": 0, "cap_usd": 15.0,
            "soft_warning_at_usd": 10.0, "hard_stop_at_usd": 14.0,
            "started_at": None,
        }, indent=2) + "\n")

    # If specific files passed as args, use those; else use all
    if len(sys.argv) > 1:
        project_paths = [RAW_DIR / f"{a}.json" if not a.endswith('.json') else RAW_DIR / a for a in sys.argv[1:]]
        project_paths = [p for p in project_paths if p.exists()]
    else:
        project_paths = sorted(RAW_DIR.glob("*.json"))
        # Exclude manifest
        project_paths = [p for p in project_paths if p.name != "manifest.json"]

    if not project_paths:
        print("No project files found.")
        return

    print(f"Instructables files: {len(project_paths)}")
    print(f"Output dir: {OUT_DIR} -> {OUT_DIR.resolve()}")
    print(f"Budget file: {BUDGET_FILE}")
    budget = json.loads(BUDGET_FILE.read_text())
    print(f"Budget before: ${budget['spent_usd']} / ${budget['cap_usd']}")
    print(f"Model: {MODEL} @ {BASE_URL}")
    print(f"Concurrency: {CONCURRENCY}")
    print(f"Anti-lazy preamble: {len(ANTI_LAZY)} chars")
    print()

    # Check external disk space
    out_mount = Path("/run/media/user/External")
    if out_mount.exists():
        free_gb = __import__('shutil').disk_usage(str(out_mount)).free / 1e9
        print(f"External disk: {free_gb:.1f} GB free")
        if free_gb < 5:
            print("FATAL: External disk < 5GB free")
            return
    print()

    client = AsyncAnthropic(api_key=API_KEY, base_url=BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)

    counter = {"success": 0, "failed": 0, "existing": 0, "total_cost": 0.0,
               "total_input_tokens": 0, "total_output_tokens": 0}
    total = len(project_paths)

    start = time.time()
    tasks = [extract_one(sem, client, pp, counter) for pp in project_paths]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            counter["failed"] += 1
            print(f"  ERROR: {r}")

    elapsed = time.time() - start
    processed = counter["success"] + counter["failed"]
    rate = processed / (elapsed / 60) if elapsed > 0 else 0
    pass_rate = counter["success"] / max(processed, 1) * 100

    print()
    print("=" * 60)
    print("Projects Extraction Complete!")
    print(f"  Total files: {total}")
    print(f"  Success: {counter['success']}")
    print(f"  Failed: {counter['failed']}")
    print(f"  Already existing: {counter['existing']}")
    print(f"  Pass rate: {pass_rate:.1f}%")
    print(f"  Time: {elapsed/60:.1f} min ({rate:.1f} projects/min)")
    print(f"  Tokens: {counter['total_input_tokens']:,} in / {counter['total_output_tokens']:,} out")
    print(f"  Cost: ${counter['total_cost']:.4f}")
    budget = json.loads(BUDGET_FILE.read_text())
    print(f"  Total budget spent: ${budget['spent_usd']:.4f} / ${budget['cap_usd']}")

    if budget["spent_usd"] >= budget["cap_usd"]:
        print("  *** BUDGET CAP HIT ***")


if __name__ == "__main__":
    asyncio.run(main())
