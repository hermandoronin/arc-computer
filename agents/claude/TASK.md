# Claude — Task assignment

> **Recipient** — Claude Code CLI (Sonnet 4.5 / Opus).
> **Working dir** — repository root.
> **Role** — production engineer. Critical-path code, validation pipelines, integration glue. No creative KB records — Kimi and DeepSeek own that.
> **Success metric** — working code that ships. Tests passing, deploy clean, runtime stable.

---

## 1. Out of scope

- ❌ No KB records (devices / projects / components) — that's DeepSeek and Kimi
- ❌ No content (regional packs, demo scenarios, safety profiles) — that's Kimi
- ❌ No greenfield design — already settled in `PRD.md`

## 2. In scope — five tracks

### Track 1 — Vision client implementation (CRITICAL, launch blocker)

**File:** `product/server/vision/client.py`

**Current state:** stub `raise NotImplementedError` in `_identify_replicate` and `_identify_openai`. Without a working vision endpoint there's no full product flow (photo → plan).

**To do:**

1. Implement `_identify_replicate()`:
   - Accepts `image_bytes: bytes`
   - Uploads to Replicate via the Predictions API (`POST /v1/predictions`)
   - Uses model `qwen2-vl-7b-instruct` (or `meta/llama-3.2-90b-vision-instruct` as fallback)
   - Polls until completion (30 s timeout, 2× retry)
   - Prompt: *"Identify electronic devices/appliances visible. Return JSON array `[{device_name, confidence_0_to_1, bbox_xywh_pct, raw_caption}]`. Be specific (e.g. 'HP DeskJet F2280 inkjet printer', not just 'printer')."*
   - Parse output, validate, return a `VisionResult`

2. Implement `_identify_openai()` as the fallback:
   - GPT-4o vision via `chat/completions` with `image_url` (data URI, base64)
   - Same prompt
   - Same `VisionResult` format

3. Update the `identify()` orchestrator:
   - Try Replicate first
   - On exception → try OpenAI fallback
   - Both fail → raise `VisionUnavailable`
   - `httpx` client, 30 s timeout, `tenacity` retry × 2 with exponential back-off

4. Tests in `product/server/vision/test_client.py`:
   - Mock `httpx` responses for both providers
   - Happy path
   - Fallback chain
   - Timeout handling
   - JSON parse-error handling

**Done criteria:**
- `pytest product/server/vision/` passes
- Manual: `curl -F "image=@test.jpg" localhost:8181/api/vision` returns valid JSON

### Track 2 — Server bug fixes

**File:** `product/server/api/routes.py`

- **Bug 1** — `SolverEngine()` is instantiated without `api_key`, always falls through to fallback. Fix: pass `api_key=settings.ANTHROPIC_API_KEY`.
- **Bug 2** — `len(kb.stats().get("devices", []))` but `stats()` returns `dict[str, int]`. Fix: `kb.stats().get("devices", 0) > 0`.
- **Bug 3** — `from main import get_kb_index, templates` is a circular-import risk. Fix: move both into `product/server/deps.py` and inject via FastAPI `Depends`.

### Track 3 — KB model unification (CDPO integration)

**Files:** `product/server/kb/models.py` + `product/server/kb/index.py`

**Issue:** `kb/index.py` declares a local `Project` model that doesn't match the canonical `Project` in `kb/pipeline/schemas/cdpo.py`. When the real KB loads, the mismatch breaks things.

**To do:**

1. Drop the local `Project` from `kb/index.py`
2. Import from CDPO: `from kb_pipeline.schemas.cdpo import Project, Device, ComponentInstance, ProjectDonorLink`
3. `KBIndex.load(path)` should:
   - Scan `kb/output/extracted/<category>/*.json`
   - Load each JSON via `pydantic.parse_file()` against the corresponding model
   - Build in-memory dicts: `devices_by_id`, `projects_by_id`, `components_by_id`
   - Build the lookup indices used by `find_donors`
4. `find_donors(device_type, components, top_k)` should match against the real CDPO structure (`Device.contains` + `Project.salvage_recommendations`)

**Done criteria:**
- `python3 -c "from kb.index import KBIndex; kb = KBIndex(); kb.load('kb/output/extracted')"` loads without errors
- `kb.stats()` returns correct counts
- `kb.find_donors('inkjet_printer', ['stepper_motor', 'solenoid'])` returns 5 projects with overlap > 0

### Track 4 — Validation + packaging pipeline

**Files:** `kb/pipeline/scripts/`

Create or extend the scripts that finalise the KB:

1. `validate_schema.py` — Pydantic validation on every file in `kb/output/extracted/`. Output: `validation-reports/schema.json`. Pass-rate target ≥ 95 %.
2. `validate_xref.py` — confirm every reference resolves. Output: `validation-reports/xref.json`.
3. `validate_antilaziness.py` — regex check on forbidden phrases. Output: `validation-reports/antilaziness.json`.
4. `validate_coverage.py` — compare counts per category against PRD targets. Output: `validation-reports/coverage.json`.
5. `build_index.py` — emit `kb/output/INDEX.json` listing every record with sha256 hash and total stats.
6. `package.sh` — package the final KB tarball:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   cd "$(dirname "$0")/../../.."
   tar --create extracted/ packs/ firmware-genome/ INDEX.json | \
       zstd -19 --long=27 --threads=0 -o kb/output/arc-kb-v0.1.tar.zst
   sha256sum kb/output/arc-kb-v0.1.tar.zst > kb/output/arc-kb-v0.1.sha256
   ```
7. `report.py` — generate `kb/output/REPORT.md` with progress bars by category, validation rates, and total cost spent.

**Done criteria:** all seven scripts run without errors, the final `tar.zst` is built, `REPORT.md` is filled with real data.

### Track 5 — Open-source release artefacts

In the repository root, create (or polish):

1. `LICENSE` — Apache 2.0 (solver / code)
2. `LICENSE-KB` — CC-BY-4.0 (KB content)
3. `LICENSE-ADAPTERS` — MIT (scrapers / adapters)
4. `CONTRIBUTING.md` — how to contribute KB entries, code, tests
5. `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1
6. `SECURITY.md` — `security@arc.computer`, responsible disclosure
7. `CHANGELOG.md` — v0.1.0 entry
8. `.github/workflows/ci.yml` — `ruff` + `pytest` on PR
9. `.github/ISSUE_TEMPLATE/{bug.md,feature.md,kb-entry.md}`
10. `.github/PULL_REQUEST_TEMPLATE.md`
11. Update root `README.md` — public-facing, with Quickstart, architecture diagram, contribution guide, license summary

## 3. Process

1. Read `PRD.md` (master document)
2. Read `agents/claude/TASK.md` (this file)
3. Read existing code under `product/server/` to understand current state
4. Read `kb/pipeline/schemas/cdpo.py` (the data model)
5. Track 1 first (vision) — highest priority blocker
6. After each track, run `pytest`
7. After all five tracks, run a manual smoke test:
   ```bash
   uvicorn product.server.main:app --reload
   curl localhost:8181/health
   curl -F "image=@test.jpg" localhost:8181/api/vision
   curl -X POST localhost:8181/solve \
       -F "image=@test.jpg" \
       -F "user_input=Build me an irrigation controller" \
       -F "mode=daily"
   ```

## 4. Forbidden behaviours

- ❌ No KB records — that's DeepSeek / Kimi
- ❌ No Twitter posts / video scripts / brand assets — that's the marketing track
- ❌ No CDPO schema modifications without explicit request — it's canonical for all agents
- ❌ No bulk KB extraction via Anthropic — don't burn budget on bulk; that's DeepSeek's territory
- ❌ No folder reorganisation — structure is fixed in PRD §5.3

## 5. Done criteria — whole task

```
[ ] vision/client.py implemented (Replicate + OpenAI fallback) ✓ tests pass
[ ] routes.py bugs fixed ✓ smoke test passes
[ ] kb/index.py uses CDPO models ✓ loads real KB without errors
[ ] 7 validation/packaging scripts created ✓ run end-to-end
[ ] OSS release artefacts ready ✓ ready to flip the repo public
[ ] Server deploy on Fly.io works (`fly deploy` clean)
[ ] Manual smoke test passes (vision → solve → plan rendered HTML)
```

## 6. Why this matters

This work unblocks launch. Without the vision client, ARC doesn't run. Without the validation pipeline, the KB can't ship. Without OSS artefacts, the repo can't go public.

**Timeline:** 1–2 weeks (5–7 days of focused work).

**Cost:** ~$50 of Claude API spend for testing (or $0 if you're already on a Claude Code subscription).

## 7. Start

Begin with Track 1 (Vision client). Read the existing stub at `product/server/vision/client.py`. Read the Replicate API docs (`qwen2-vl-7b-instruct` endpoint). Implement the full real code. Run tests. If they pass, commit. Move to Track 2.
