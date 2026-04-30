# DEEPSEEK — TASK ASSIGNMENT

> **Адресат:** DeepSeek V4 Pro через OpenRouter, запускается через `~/Desktop/DeepSeek CLI.desktop` (это Claude Code wrapper в режиме DeepSeek). Working dir: `/home/user/aisurvive/`.
>
> **Альтернативный mode:** `deepseek-flash` (deepseek-v4-flash, $0.14/M input — для самой дешёвой bulk).
>
> **Роль:** bulk worker. Берёшь существующие источники (iFixit guides, Instructables HTML, Hackaday API JSON), молотишь через batch API, выдаёшь 2,000-5,000 structured CDPO records.
>
> **Единица успеха:** объём + acceptable quality. Glory in throughput.

---

## 1. Что НЕ твоя задача

- Не делай from-scratch creativity (Soviet pack, demo scenarios, safety profiles deep) — это Kimi.
- Не пиши production code (server, vision, packaging) — это Claude.
- Не реорганизовывай структуру.
- Не модифицируй CDPO schema без согласования.

## 2. Что твоя задача

### 2.1 Source ingestion (один раз перед extraction)

```bash
cd /home/user/aisurvive
mkdir -p kb/output/raw/{ifixit,instructables,hackaday}

# iFixit — top-1500 guides via API
# (Если есть IFIXIT_KEY — используй; иначе scrape rate-limited)
python3 kb/pipeline/scripts/download_ifixit.py --limit 1500

# Instructables — categories: electronics + workshop + homestead, top-1000
python3 kb/pipeline/scripts/download_instructables.py --limit 1000

# Hackaday.io — popular projects, top-500
python3 kb/pipeline/scripts/download_hackaday.py --limit 500
```

Если scripts требуют доработки — fix them (your job too). Они в `kb/pipeline/scripts/`.

### 2.2 Extraction pipeline — full volume

После ingestion — прогонишь через 4 промпта в `kb/pipeline/extractors/prompts/`:
- `01-device-extractor.md` → applies to iFixit JSONs + YouTube SRT
- `02-project-extractor.md` → applies to Instructables HTML + Hackaday JSON
- `03-linker.md` → after Wave 1+2 done
- `04-substitution.md` → applied to top-2000 components

**ВАЖНО:** перед запуском extractor — добавь anti-laziness preamble в каждый prompt (см. `agents/kimi/briefs/KIMI-EXECUTE-NOW.md` Part 3.1 для текста). Это блокирует ленивый output типа "remove screws", "internal", "consult professional".

**Цель volumes:**

| Output | Target |
|---|---|
| Devices | 1,500 records |
| Projects | 1,000 records |
| Components | 2,000 records (canonical) |
| Substitutions | 500 chains |
| Project-donor links | ~3,000 (cross-product) |

**Total: ~7,000-8,000 raw records** → после dedupe ~5,000.

**Where to write:** `kb/output/extracted/<category>/<id>.json`.

### 2.3 Cost management

DeepSeek V4 Pro pricing (OpenRouter): ~$0.27/M input + $1.10/M output (примерные, проверь в pricing-cache).

Estimate per record extraction:
- iFixit guide: ~6k input + 3k output = ~$0.01 per record
- Instructables: ~4k input + 3k output = ~$0.008
- Substitution: ~1k input + 3k output = ~$0.005

**Real expected cost: ~$25-32** для full extraction 5,000+ records через DeepSeek V4 Pro promo (до 5 мая 2026).

**Hard cap: $30**. Soft warn при $20. **Auto-switch на v4-flash при $25** (5x дешевле). После 5 мая promo кончится — цены × 4, тогда нужно $100+.

Track cost через простой `~/aisurvive/agents/deepseek/budget.json`:
```json
{"spent": 0.0, "calls": 0, "cap": 200.0}
```

Update после каждого batch. Если spent > cap → STOP, log, alert.

### 2.4 Validation

После extraction:

1. **Schema** — все JSON проходят `pydantic.validate()` через CDPO models из `kb/pipeline/schemas/cdpo.py`.
2. **Anti-laziness regex** — auto-reject any record matching forbidden patterns (см. KIMI-MEGA-BRIEF Section 8.1).
3. **Cross-reference** — все `component_id` / `device_id` / `project_id` references resolve.
4. **Duplicate detection** — fuzzy match by name (Levenshtein) → keep one canonical, merge provenance.

Failed records → log в `kb/output/validation-reports/deepseek-failures.jsonl` + re-prompt с tighter rules. Max 2 retry attempts per record. Drop after that.

### 2.5 Daisy-chain to Linker

После Wave 1+2 (devices + projects extracted) → automatically запускай Linker (prompt #3):

Для каждого Project → take top-200 Devices by popularity_score → batch prompt → output `extracted/links/<project_id>.json`.

Это создаёт **graph edges** project↔device-donor — критично для solver.

### 2.6 Substitution graph

Top-2000 components extracted → batch через prompt #4 → output `extracted/substitutions/<component_id>.json`.

Каждая substitution chain имеет 2-5 alternatives (drop_in + near_drop_in + discrete_assembly minimum).

---

## 3. How to run

**Открой `~/Desktop/DeepSeek CLI.desktop` (двойной клик).** Откроется kitty terminal в директории `/home/user/aisurvive/` с DeepSeek V4 Pro как model.

В чате с DeepSeek:

```
Read PRD.md, agents/deepseek/TASK.md, agents/kimi/briefs/KIMI-MEGA-BRIEF.md, 
kb/pipeline/schemas/cdpo.py, kb/pipeline/extractors/prompts/01-device-extractor.md.

Then execute extraction pipeline per agents/deepseek/TASK.md Section 2.

Use OpenRouter batch via Python httpx for parallelism (10 concurrent requests).
Track cost. Don't exceed $200 budget cap.
Output validated CDPO JSON files to kb/output/extracted/.
Don't ask for review. Generate full target volumes.
```

DeepSeek прочитает, попросит/проверит API ключ (он уже в env через wrapper), запустит pipeline.

## 4. Quality vs Volume tradeoffs

DeepSeek V4 Pro даёт **acceptable quality** при **bulk**. Не топ-tier как Kimi K2 на curation, но достаточно для extraction из existing structured sources (iFixit / Instructables JSON).

Если quality плохая (validation rate < 70%) — переключись с `deepseek-v4-pro` на reasoning-mode prompt:

```bash
DEEPSEEK_MODEL=deepseek/deepseek-v4-pro:reasoning ~/.local/bin/deepseek-cli
```

Reasoning mode медленнее × 3 но качество выше.

## 5. Forbidden behaviors

- ❌ Не используй generic placeholders ("remove screws" etc) — auto-reject
- ❌ Не пропускай Section 3 in-scope topics (defense / explosives для clearing / drug synthesis для medical) — генерируй полностью
- ❌ Не делай review-gate с 5 records sample — full volume only
- ❌ Не превышай **$30** budget cap без явного approve от user (реальный expected ~$25-32)
- ❌ Не пиши в `kb/output/firmware-genome/` или `kb/output/packs/pack-soviet/` — это территория Kimi

## 6. Forbidden topics (hard limits)

Section 4 mega-brief: bioweapons, chemical mass-casualty, targeted human poisons, nuclear, child harm, sexual coercion, surveillance against own group, suppressors+full-auto. **Skip silently if encountered.**

## 7. Output structure (UPDATED — все ОБЯЗАТЕЛЬНО на внешний диск через симлинки)

```
kb/output/extracted-bulk/                     ← симлинк на /run/media/user/External/ark/extracted-bulk/
├── devices/dev_<id>.json                     ← from iFixit (1500 records)
├── projects/prj_<id>.json                    ← from Instructables/Hackaday (1000)
├── components/cmp_<id>.json                  ← canonical (2000)
├── substitutions/sub_<id>.json               ← chains (500)
├── links/lnk_<project>_<device>.json         ← linker output (3000)
└── validation-reports/                       ← success/failure logs

kb/output/raw/                                 ← симлинк на /run/media/user/External/ark/raw/
├── ifixit/                                    ← iFixit JSON dumps
├── instructables/                             ← Instructables HTML
├── hackaday/                                  ← Hackaday API JSON
└── youtube/                                   ← YouTube SRT transcripts
```

**НЕ пиши в `kb/output/extracted/`** — это где Kimi работает на внутреннем диске. Твоя территория = `kb/output/extracted-bulk/`.

## 8. Done criteria

```
[ ] Extraction script runs end-to-end without crash
[ ] kb/output/extracted-bulk/devices/ has ≥1500 valid records
[ ] kb/output/extracted-bulk/projects/ has ≥1000 valid records  
[ ] kb/output/extracted-bulk/components/ has ≥2000 valid records
[ ] kb/output/extracted-bulk/substitutions/ has ≥500 chains
[ ] kb/output/extracted-bulk/links/ has ≥3000 links
[ ] Schema validation pass rate ≥85%
[ ] Anti-laziness violations < 5% of total
[ ] Cross-reference broken refs < 10%
[ ] Total budget spent < $30
[ ] kb/output/extracted-bulk/validation-reports/coverage.json shows breakdown
[ ] kb/output/extracted-bulk/INDEX.json built
[ ] Internal disk (/) usage didn't grow more than 100 MB during entire run
```

When all ✓ — task done. Report path to INDEX.json.

## 9. Why this matters

Без 5,000 extracted records solver не работает на realistic queries. Это **infrastructure для product**.

Kimi делает quality showcase. Claude делает code. **DeepSeek делает foundation который оба остальных используют.** No foundation → no product.

Execute.

---

## 10. STORAGE PATHS (UPDATED 2026-04-29)

**Внутренний диск (Arch /) имеет только 35GB свободно.** Тяжёлые данные ОБЯЗАТЕЛЬНО на внешний через симлинки:

| Что | Path в проекте (симлинк) | Реальный путь |
|---|---|---|
| Raw downloads (iFixit/Instructables/Hackaday/YouTube) | `kb/output/raw/<source>/` | `/run/media/user/External/ark/raw/<source>/` |
| Bulk extracted records (5000+ JSONs) | `kb/output/extracted-bulk/` | `/run/media/user/External/ark/extracted-bulk/` |
| Staging / WIP / temp files | `kb/output-wip/` | `/run/media/user/External/ark/staging/` |
| Final tar.zst package | `kb/output/final/` | `/run/media/user/External/ark/final/` |

**Не пиши** в `kb/output/extracted/`, `kb/output/packs/`, `kb/output/firmware-genome/`, `kb/output/scripts/` — это территория Kimi на внутреннем диске.

**Когда адаптируешь download_*.py скрипты:**
- Замени `RAW_DIR = Path("/mnt/staging/ark-kb/raw/...")` на `RAW_DIR = Path("/home/user/aisurvive/kb/output/raw/...")`
- Это идёт на внешний через симлинк автоматически

**Когда адаптируешь run_*_extractor.py:**
- Output dir = `/home/user/aisurvive/kb/output/extracted-bulk/` (тоже симлинк на внешний)

**Disk space sanity check** перед каждым крупным batch:
```python
import shutil
free_gb = shutil.disk_usage("/run/media/user/External").free / 1e9
if free_gb < 10:
    raise RuntimeError(f"External disk only {free_gb:.1f}GB free — abort")
```
