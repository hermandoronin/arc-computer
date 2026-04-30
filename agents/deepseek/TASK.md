# DeepSeek — Task assignment

> **Recipient** — DeepSeek V4 Pro via the Anthropic-compatible endpoint (`api.deepseek.com/anthropic`), launched through `~/.local/bin/deepseek-cli`.
> **Working dir** — repository root.
> **Alternate model** — `deepseek-v4-flash` (cheapest tier, $0.14/M input).
> **Role** — bulk worker. Take existing sources (iFixit guides, Instructables HTML, Hackaday API JSON), grind through them via batch API, output 2,000–5,000 structured CDPO records.
> **Success metric** — volume + acceptable quality. Glory in throughput.

---

## 1. Out of scope

- No from-scratch creative work (regional packs, demo scenarios, deep safety profiles) — that's Kimi's track.
- No production code (server, vision, packaging) — that's Claude's track.
- No structural reorganisation.
- No modifying the CDPO schema without coordination.

## 2. In scope

### 2.1 Source ingestion (one-time, before extraction)

```bash
mkdir -p kb/output/raw/{ifixit,instructables,hackaday}

# iFixit — top 1,500 guides via API (or scrape rate-limited if no key)
python3 kb/pipeline/scripts/download_ifixit.py --limit 1500

# Instructables — categories: electronics, workshop, homestead — top 1,000
python3 kb/pipeline/scripts/download_instructables.py --limit 1000

# Hackaday.io — popular projects, top 500
python3 kb/pipeline/scripts/download_hackaday.py --limit 500
```

If a script needs fixing — fix it. They live in `kb/pipeline/scripts/`.

### 2.2 Extraction pipeline — full volume

After ingestion, run through the four prompts in `kb/pipeline/extractors/prompts/`:
- `01-device-extractor.md` — applied to iFixit JSON + YouTube SRT
- `02-project-extractor.md` — applied to Instructables HTML + Hackaday JSON
- `03-linker.md` — after waves 1+2 are complete
- `04-substitution.md` — applied to the top-2,000 components

**Important:** before running an extractor, prepend the anti-laziness preamble (`kb/pipeline/extractors/prompts/00-anti-laziness-preamble.md`) to every prompt. This blocks lazy output like "remove screws", "internal", "consult professional".

**Volume targets:**

| Output | Target |
|---|---|
| Devices | 1,500 records |
| Projects | 1,000 records |
| Components (canonical) | 2,000 records |
| Substitution chains | 500 |
| Project-donor links | ~3,000 (cross product) |

**Total: ~7,000–8,000 raw records** → after de-dup, ~5,000.

**Output location:** `kb/output/extracted/<category>/<id>.json`

### 2.3 Cost management

DeepSeek V4 Pro pricing (native endpoint, with prompt caching enabled):
- Input: ~$0.27/M (uncached) · ~$0.027/M (cached, 10× cheaper)
- Output: ~$1.10/M

Estimated cost per record:
- iFixit guide: ~6k input + 3k output ≈ $0.01
- Instructables: ~4k input + 3k output ≈ $0.008
- Substitution: ~1k input + 3k output ≈ $0.005

**Real expected cost:** ~$25–32 for the full ~5,000-record extraction.

**Hard cap:** $30. Soft warn at $20. **Auto-switch to `v4-flash` at $25** (5× cheaper).

Track cost in `agents/deepseek/budget.json`:
```json
{"spent": 0.0, "calls": 0, "cap": 30.0}
```

Update after each batch. If `spent > cap` → STOP, log, alert.

### 2.4 Validation

After extraction:

1. **Schema** — every JSON validates against the CDPO Pydantic model in `kb/pipeline/schemas/cdpo.py`.
2. **Anti-laziness regex** — auto-reject records matching forbidden patterns.
3. **Cross-references** — every `component_id` / `device_id` / `project_id` reference resolves.
4. **De-duplication** — fuzzy match by name (Levenshtein) → keep one canonical, merge provenance.

Failed records → `kb/output/validation-reports/deepseek-failures.jsonl`, then re-prompt with tighter rules. Max two retries per record. Drop after that.

### 2.5 Daisy-chain to the linker

After waves 1+2 (devices + projects extracted), run the linker (prompt #3):

For each project → take the top-200 devices by popularity score → batch-prompt → output `extracted/links/<project_id>.json`.

This builds the project ↔ donor-device graph edges — critical for the solver.

### 2.6 Substitution graph

Top-2,000 extracted components → batch-prompted through prompt #4 → output `extracted/substitutions/<component_id>.json`.

Each substitution chain has 2–5 alternatives (drop-in + near-drop-in + discrete-assembly minimum).

## 3. How to run

Open `~/.local/bin/deepseek-cli` (or the desktop launcher). It launches a `kitty` terminal in the repo root with DeepSeek V4 Pro selected.

In the chat:

```
Read PRD.md, agents/deepseek/TASK.md, kb/pipeline/schemas/cdpo.py,
kb/pipeline/extractors/prompts/01-device-extractor.md.

Then execute the extraction pipeline per agents/deepseek/TASK.md §2.

Use AsyncAnthropic with concurrency 25 and prompt-caching on the system prompt.
Track cost. Don't exceed $30 budget cap.
Output validated CDPO JSON files to kb/output/extracted/.
Don't ask for review. Generate full target volumes.
```

## 4. Quality vs volume trade-off

DeepSeek V4 Pro delivers acceptable quality at high throughput. Not top-tier on creative curation (Kimi's strength), but more than enough to extract from existing structured sources (iFixit / Instructables JSON).

If quality drops below 70 % validation pass-rate, switch to reasoning mode:

```bash
DEEPSEEK_MODEL=deepseek-v4-pro:reasoning ~/.local/bin/deepseek-cli
```

Reasoning mode is 3× slower but considerably higher quality.

## 5. Forbidden behaviours

- ❌ No generic placeholders ("remove screws" etc.) — auto-reject
- ❌ No going outside the in-scope topics in PRD §4 (power / water / food / comms / perimeter non-lethal / repair / tools / medical-reference / salvage)
- ❌ No 5-record review-gate samples — full volume only
- ❌ No exceeding the **$30** budget cap without explicit user approval (real expected ~$25–32)
- ❌ No writing to `kb/output/firmware-genome/` or `kb/output/packs/` — that's Kimi's territory

## 6. Forbidden topics (hard limits)

Per PRD §4 hard limits: weapons, ammunition, explosives, drug synthesis, opioid synthesis, targeted human poisons, bioweapons, chemical mass-casualty agents, nuclear material handling, surveillance against people without consent, unlicensed RF transmission, lockpicking instructions, vehicle theft, social engineering. **Skip silently if encountered.**

## 7. Output structure

```
kb/output/extracted-bulk/                     (large outputs — see kb/STRATEGY.md for storage tiering)
├── devices/dev_<id>.json                     iFixit-derived (1,500)
├── projects/prj_<id>.json                    Instructables/Hackaday-derived (1,000)
├── components/cmp_<id>.json                  canonical (2,000)
├── substitutions/sub_<id>.json               chains (500)
├── links/lnk_<project>_<device>.json         linker output (3,000)
└── validation-reports/                       success / failure logs

kb/output/raw/
├── ifixit/                                   iFixit JSON dumps
├── instructables/                            Instructables HTML
├── hackaday/                                 Hackaday API JSON
└── youtube/                                  YouTube SRT transcripts
```

**Don't write to `kb/output/extracted/`** — that's Kimi's curated territory. DeepSeek's bulk output goes to `kb/output/extracted-bulk/`.

## 8. Done criteria

```
[ ] Extraction script runs end-to-end without crash
[ ] kb/output/extracted-bulk/devices/         ≥ 1,500 valid records
[ ] kb/output/extracted-bulk/projects/        ≥ 1,000 valid records
[ ] kb/output/extracted-bulk/components/      ≥ 2,000 valid records
[ ] kb/output/extracted-bulk/substitutions/   ≥ 500 chains
[ ] kb/output/extracted-bulk/links/           ≥ 3,000 links
[ ] Schema validation pass rate              ≥ 85 %
[ ] Anti-laziness violations                 < 5 %
[ ] Broken cross-references                  < 10 %
[ ] Total budget spent                       < $30
[ ] kb/output/extracted-bulk/INDEX.json      built
```

When all ✓ — task complete. Report path to `INDEX.json`.

## 9. Why this matters

Without 5,000 extracted records, the solver doesn't work on realistic queries. This is the **infrastructure layer** of the product.

Kimi delivers the quality showcase. Claude delivers the code. **DeepSeek delivers the foundation that the other two stand on.** No foundation → no product.

Execute.

## 10. Storage paths

The internal disk has limited free space. Heavy data lives on the external disk via symlinks:

| Content | Project path (symlink) | Real path |
|---|---|---|
| Raw downloads (iFixit / Instructables / Hackaday / YouTube) | `kb/output/raw/<source>/` | external disk |
| Bulk extracted records (5,000+ JSONs) | `kb/output/extracted-bulk/` | external disk |
| Staging / WIP / temp | `kb/output-wip/` | external disk |
| Final tar.zst package | `kb/output/final/` | external disk |

**Don't write to** `kb/output/extracted/`, `kb/output/packs/`, `kb/output/firmware-genome/`, `kb/output/scripts/` — that's Kimi's territory on the internal disk.

**Disk-space sanity check before each large batch:**

```python
import shutil
free_gb = shutil.disk_usage("/run/media/user/External").free / 1e9
if free_gb < 10:
    raise RuntimeError(f"External disk only {free_gb:.1f} GB free — abort")
```
