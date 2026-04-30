#!/usr/bin/env python3
"""Phase 2: Full extraction of all iFixit guides (local + external drive)."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import anthropic
from anthropic import AsyncAnthropic

# Config
RAW_DIRS = [
    Path("/home/user/aisurvive/kb/output/raw/ifixit"),
    Path("/run/media/user/External/ark/raw/ifixit"),
    Path("/run/media/user/External/ark/raw/ifixit/skip"),
]
OUT_DIR = Path("/home/user/aisurvive/kb/output/extracted-bulk/devices")
PROMPT_DIR = Path("/home/user/aisurvive/kb/pipeline/extractors/prompts")
FAILED_LOG = Path("/home/user/aisurvive/kb/output/extracted-bulk/validation-reports/deepseek-failures.jsonl")
BUDGET_FILE = Path("/home/user/aisurvive/agents/deepseek/budget.json")
SCHEMAS_DIR = Path("/home/user/aisurvive/kb/pipeline/schemas")

CONCURRENCY = 25  # bumped from 10 — sync->async fix gives real parallelism
MODEL = "deepseek-v4-pro"
MAX_TOKENS = 8192
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")

if not API_KEY:
    print("FATAL: No API key. Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY")
    sys.exit(1)

sys.path.insert(0, str(SCHEMAS_DIR))
from cdpo import Device, ComponentInstance, Provenance
from pydantic import ValidationError

# Load prompts
ANTI_LAZY = (PROMPT_DIR / "00-anti-laziness-preamble.md").read_text(encoding="utf-8").strip()
DEVICE_PROMPT_RAW = (PROMPT_DIR / "01-device-extractor.md").read_text(encoding="utf-8").strip()

def build_prompt(guide_text: str) -> str:
    combined = ANTI_LAZY + "\n\n" + DEVICE_PROMPT_RAW
    return combined.replace("{сюда вставляется raw text guide или transcript}", guide_text)

def clean_guide_text(guide_json: dict) -> str:
    import re
    parts = []
    title = guide_json.get("title") or guide_json.get("display_title") or ""
    if title:
        parts.append(f"# {title}")
    summary = guide_json.get("summary") or guide_json.get("introduction") or ""
    if summary:
        parts.append(re.sub(r"<[^>]+>", "", summary))
    tools = guide_json.get("tools", [])
    if tools:
        parts.append("## Tools Required")
        for t in tools:
            txt = t.get("text", "") if isinstance(t, dict) else str(t)
            if txt:
                parts.append(f"- {txt}")
    parts_list = guide_json.get("parts", [])
    if parts_list:
        parts.append("## Parts")
        for p in parts_list:
            if isinstance(p, dict):
                txt = p.get("text_raw") or p.get("text") or p.get("name", "")
            else:
                txt = str(p)
            if txt:
                parts.append(f"- {re.sub(r'<[^>]+>', '', txt)}")
    steps = guide_json.get("steps", [])
    if steps:
        parts.append("## Steps")
        for idx, step in enumerate(steps, start=1):
            s_parts = [f"### Step {idx}"]
            for line in step.get("lines", []):
                txt = line.get("text_raw") or line.get("text_rendered") or ""
                if txt:
                    s_parts.append(re.sub(r"<[^>]+>", "", txt))
            media = step.get("media")
            if isinstance(media, dict):
                for img in media.get("data", []):
                    cap = img.get("caption") or img.get("text", "")
                    if cap:
                        s_parts.append(f"[image] {re.sub(r'<[^>]+>', '', cap)}")
            parts.append("\n".join(s_parts))
    return "\n\n".join(parts)

def parse_response(text: str) -> dict | None:
    import re as _re
    parsed = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass
    if parsed is None:
        fence = _re.compile(r"```(?:json)?\s*(.*?)\s*```", _re.DOTALL)
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
    if parsed is None:
        return None
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}
    if not isinstance(parsed, dict):
        return None
    return parsed

VALID_COMP_TYPES = {
    "resistor","capacitor","inductor","diode","transistor","mosfet","igbt",
    "optocoupler","transformer","motor_dc","motor_stepper","motor_servo",
    "solenoid","relay","ic_logic","ic_analog","mcu","fpga","memory",
    "sensor","display","speaker","microphone","antenna","rf_module",
    "psu","battery","fuse","switch","connector","crystal","led","laser",
    "heating_element","magnet","optical","pcb_bare","mechanical","other"
}

# Fields that belong in ComponentInstance (from cdpo.py)
COMP_INSTANCE_FIELDS = {
    "instance_id", "component_id", "device_id", "quantity", "location_in_device",
    "extraction_difficulty", "extraction_steps", "damage_risk", "salvage_quality",
    "typical_failure_after_years", "notes", "provenance"
}

DIFFICULTY_VALUES = {"trivial", "easy", "medium", "hard", "destructive"}
DAMAGE_RISK_VALUES = {"none", "low", "medium", "high"}
SALVAGE_VALUES = {"pristine", "good", "usable", "scrap"}

def validate_output(parsed: dict, guide_id: str) -> dict | None:
    device_data = parsed.get("device", parsed)
    components_raw = parsed.get("components_inside", [])
    confidence = parsed.get("extraction_confidence", 0.5)

    # Anti-laziness check
    raw_str = json.dumps(parsed, ensure_ascii=False).lower()
    for pat in ["remove screws", "disconnect wires", '"internal"', '"various"',
                 "consult professional", "see datasheet", "depends on model"]:
        if pat in raw_str:
            return None

    # Validate device
    try:
        validated_device = Device.model_validate(device_data)
    except ValidationError:
        return None

    validated_components = []
    for comp in components_raw:
        if not isinstance(comp, dict):
            continue
        try:
            # Map component_canonical -> component_id
            if "component_id" not in comp and "component_canonical" in comp:
                name = comp["component_canonical"].lower().replace(" ", "_").replace("/", "_")
                comp["component_id"] = f"cmp:{name}"
            if "component_id" not in comp:
                name = guide_id.replace("-", "_")
                comp["component_id"] = f"cmp:{name}_comp_{len(validated_components)}"
            # Ensure device_id
            if "device_id" not in comp:
                comp["device_id"] = validated_device.id
            # Map type to valid enum
            comp_type = comp.get("type", "other")
            if comp_type not in VALID_COMP_TYPES:
                comp["type"] = "other"
            # Map difficulty
            diff = comp.get("extraction_difficulty", "medium")
            if diff not in DIFFICULTY_VALUES:
                comp["extraction_difficulty"] = "medium"
            # Map damage_risk
            risk = comp.get("damage_risk", "low")
            if risk not in DAMAGE_RISK_VALUES:
                comp["damage_risk"] = "low"
            # Map salvage_quality
            sq = comp.get("salvage_quality_typical", comp.get("salvage_quality", "good"))
            if sq not in SALVAGE_VALUES:
                comp["salvage_quality"] = "good"
            else:
                comp["salvage_quality"] = sq
            # Ensure quantity is int
            if "quantity" in comp:
                try:
                    comp["quantity"] = int(comp["quantity"])
                except (ValueError, TypeError):
                    comp["quantity"] = 1
            if comp.get("quantity", 0) <= 0:
                comp["quantity"] = 1
            # Strip non-schema fields
            clean_comp = {k: v for k, v in comp.items() if k in COMP_INSTANCE_FIELDS}
            validated_components.append(ComponentInstance.model_validate(clean_comp).model_dump())
        except (ValidationError, TypeError, ValueError):
            pass

    return {
        "device": validated_device.model_dump(),
        "components_inside": validated_components,
        "extraction_confidence": confidence,
    }

def update_budget(input_tokens: int, output_tokens: int, cache_read_tokens: int = 0):
    # Pricing: $0.435/M input, $0.87/M output (promo)
    cost = (input_tokens / 1_000_000) * 0.435 + (output_tokens / 1_000_000) * 0.87 + (cache_read_tokens / 1_000_000) * 0.0174
    budget = json.loads(BUDGET_FILE.read_text())
    budget["spent_usd"] = round(budget.get("spent_usd", 0) + cost, 6)
    budget["calls"] = budget.get("calls", 0) + 1
    if budget.get("started_at") is None:
        budget["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    BUDGET_FILE.write_text(json.dumps(budget, indent=2, ensure_ascii=False) + "\n")
    return cost, budget["spent_usd"]

async def extract_one(sem: asyncio.Semaphore, client: anthropic.Anthropic, guide_path: Path, counter: dict, total: int):
    guide_id = guide_path.stem
    device_id = f"dev:{guide_id}"
    out_path = OUT_DIR / f"{device_id}.json"

    if out_path.exists():
        counter["existing"] += 1
        return {"status": "skip_existing"}

    try:
        raw = json.loads(guide_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        counter["failed"] += 1
        return {"status": "error", "reason": "bad_json", "guide_id": guide_id}

    text = clean_guide_text(raw)
    if not text or len(text) < 50:
        counter["failed"] += 1
        return {"status": "error", "reason": "text_too_short", "guide_id": guide_id}

    prompt = build_prompt(text)

    async with sem:
        try:
            # Split prompt: anti-lazy + extractor schema → cacheable system; guide text → user message
            # cache_control marker → system prompt cached after first call (input cost 25× cheaper on cache hit)
            resp = await client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": ANTI_LAZY + "\n\n" + DEVICE_PROMPT_RAW.replace(
                            "{сюда вставляется raw text guide или transcript}",
                            "{guide_text}"
                        ),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": text}],
                thinking={"type": "disabled"},
            )
        except Exception as exc:
            counter["failed"] += 1
            return {"status": "error", "reason": f"api_error: {exc}", "guide_id": guide_id}

    raw_text = ""
    for block in resp.content:
        if hasattr(block, "text"):
            raw_text += block.text

    parsed = parse_response(raw_text)
    if parsed is None:
        counter["failed"] += 1
        FAILED_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FAILED_LOG, "a") as f:
            f.write(json.dumps({"guide_id": guide_id, "reason": "json_parse_failed", "raw_preview": raw_text[:200]}) + "\n")
        return {"status": "error", "reason": "json_parse_failed", "guide_id": guide_id}

    validated = validate_output(parsed, guide_id)
    if validated is None:
        counter["failed"] += 1
        FAILED_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FAILED_LOG, "a") as f:
            f.write(json.dumps({"guide_id": guide_id, "reason": "validation_or_lazy_reject"}) + "\n")
        return {"status": "error", "reason": "validation_or_lazy_reject", "guide_id": guide_id}

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

    print(f"  OK [{counter['success']}] {device_id} "
          f"({in_tok}+{out_tok} tok, ${cost:.4f}, total ${spent:.4f})  "
          f"components: {len(validated.get('components_inside', []))}")

    return {"status": "ok", "guide_id": guide_id, "device_id": device_id}


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_LOG.parent.mkdir(parents=True, exist_ok=True)

    # Collect from all sources, deduplicate by stem
    seen = set()
    guide_paths = []
    for raw_dir in RAW_DIRS:
        if not raw_dir.exists():
            print(f"WARNING: Directory not found: {raw_dir}")
            continue
        for gp in sorted(raw_dir.glob("*.json")):
            if gp.stem not in seen:
                seen.add(gp.stem)
                guide_paths.append(gp)

    if not guide_paths:
        print("No guide files found.")
        return

    print(f"Source directories:")
    for raw_dir in RAW_DIRS:
        count = len(list(raw_dir.glob("*.json"))) if raw_dir.exists() else 0
        print(f"  {raw_dir} ({count} files)")
    print(f"Total unique guides: {len(guide_paths)}")
    print(f"Output dir: {OUT_DIR} -> {OUT_DIR.resolve()}")
    print(f"Budget file: {BUDGET_FILE}")
    budget = json.loads(BUDGET_FILE.read_text())
    print(f"Budget before: ${budget['spent_usd']} / ${budget['cap_usd']}")
    print(f"Model: {MODEL} @ {BASE_URL}")
    print(f"Concurrency: {CONCURRENCY}")
    print(f"Anti-lazy preamble: {len(ANTI_LAZY)} chars")
    print()

    client = AsyncAnthropic(api_key=API_KEY, base_url=BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)

    counter = {"success": 0, "failed": 0, "existing": 0, "total_cost": 0.0,
               "total_input_tokens": 0, "total_output_tokens": 0}
    total = len(guide_paths)
    counter["existing_initial"] = sum(1 for gp in guide_paths if (OUT_DIR / f"dev:{gp.stem}.json").exists())

    start = time.time()

    tasks = [extract_one(sem, client, gp, counter, total) for gp in guide_paths]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            counter["failed"] += 1
            print(f"  ERROR: {r}")

    elapsed = time.time() - start
    rate = (counter["success"] + counter["failed"]) / (elapsed / 60) if elapsed > 0 else 0

    print()
    print("=" * 60)
    print(f"Phase 2 Complete!")
    print(f"  Total guides: {total}")
    print(f"  Success: {counter['success']}")
    print(f"  Failed: {counter['failed']}")
    print(f"  Already existing: {counter['existing']}")
    print(f"  Pass rate: {counter['success']/max(total-counter['existing'],1)*100:.1f}%")
    print(f"  Time: {elapsed/60:.1f} min ({rate:.1f} guides/min)")
    print(f"  Tokens: {counter['total_input_tokens']:,} in / {counter['total_output_tokens']:,} out")
    print(f"  Cost: ${counter['total_cost']:.4f}")
    budget = json.loads(BUDGET_FILE.read_text())
    print(f"  Total budget spent: ${budget['spent_usd']:.4f} / ${budget['cap_usd']}")

    if budget["spent_usd"] >= budget["cap_usd"]:
        print("  *** BUDGET CAP HIT ***")

if __name__ == "__main__":
    asyncio.run(main())
