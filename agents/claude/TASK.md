# CLAUDE — TASK ASSIGNMENT

> **Адресат:** Claude Code CLI (стандартный, через эту самую сессию ИЛИ через отдельный launcher с Sonnet 4.5/Opus). Working dir: `/home/user/aisurvive/`.
>
> **Роль:** production engineer. Critical-path code, validation pipelines, integration glue. Никаких творческих KB records — это Kimi и DeepSeek делают.
>
> **Единица успеха:** working code that ships. Tests passing, deploy ОК, runtime stable.

---

## 1. Что НЕ твоя задача

- ❌ Не генерируй KB records (devices/projects/components) — это DeepSeek и Kimi
- ❌ Не пиши content (Soviet pack, demo scenarios, safety profiles) — это Kimi
- ❌ Не делай from-scratch проектирование — продумано в PRD.md и mega-brief

## 2. Что твоя задача — пять treк'ов

### Track 1 — Vision client implementation (CRITICAL, blocker для launch)

**Файл:** `product/server/vision/client.py`

**Текущий статус:** stubs `raise NotImplementedError` в `_identify_replicate` и `_identify_openai`. Без рабочего vision endpoint — нет всего product flow (фотка → план).

**Что сделать:**

1. Имплементируй `_identify_replicate()`:
   - Принимает `image_bytes: bytes`
   - Загружает в Replicate через their Predictions API (`POST /v1/predictions`)
   - Использует модель `qwen2-vl-7b-instruct` (latest) или `meta/llama-3.2-90b-vision-instruct` если Qwen недоступен
   - Polls until completion (max 30 sec timeout, retry 2x)
   - Promtit: "Identify electronic devices/appliances visible. Return JSON array: [{device_name, confidence_0_to_1, bbox_xywh_pct, raw_caption}]. Be specific (e.g. 'HP DeskJet F2280 inkjet printer' not 'printer')."
   - Parse output, validate, return `VisionResult`

2. Имплементируй `_identify_openai()` как fallback:
   - GPT-5V / GPT-4o vision через `chat/completions` с `image_url` (data: URI base64)
   - Тот же prompt
   - Same VisionResult format

3. Update `identify()` orchestrator:
   - Try Replicate first
   - On exception → try OpenAI fallback
   - Both fail → raise `VisionUnavailable` (custom exception)
   - Add httpx client with 30s timeout, tenacity retry x2 with exponential backoff

4. Tests в `product/server/vision/test_client.py`:
   - Mock httpx responses for both providers
   - Test happy path
   - Test fallback chain
   - Test timeout handling
   - Test JSON parse error handling

**Done criteria:**
- `pytest product/server/vision/` passes
- Manual test: `curl -F "image=@test.jpg" localhost:8080/api/vision` returns valid JSON

### Track 2 — Server bug fixes

**Файл:** `product/server/api/routes.py`

**Bug 1 (line ~96):** `SolverEngine()` инстанцируется без api_key — всегда уходит в fallback. Fix:
```python
from solver.engine import SolverEngine
solver = SolverEngine(api_key=settings.ANTHROPIC_API_KEY)
```

**Bug 2 (line ~27):** `len(kb.stats().get("devices", []))` — но `stats()` возвращает `dict[str, int]`. Падает `TypeError`. Fix:
```python
"kb_loaded": kb is not None and kb.stats().get("devices", 0) > 0,
```

**Bug 3 (line ~14):** `from main import get_kb_index, templates` — circular import риск. Fix: создать `product/server/deps.py` с `templates` и `get_kb_index` через FastAPI Depends.

### Track 3 — KB models unification (CDPO integration)

**Файл:** `product/server/kb/models.py` + `product/server/kb/index.py`

**Проблема:** `kb/index.py` имеет свой локальный `Project` model который не совпадает с CDPO `Project` из `kb/pipeline/schemas/cdpo.py`. Когда подгрузим реальную KB — несовместимость.

**Что сделать:**

1. Удалить локальный `Project` в `kb/index.py`
2. Импортировать из CDPO: `from kb_pipeline.schemas.cdpo import Project, Device, ComponentInstance, ProjectDonorLink`
3. `KBIndex.load(path)` должен:
   - Сканировать `kb/output/extracted/<category>/*.json`
   - Загружать каждый JSON через `pydantic.parse_file()` соответствующей модели
   - Building in-memory dicts: devices_by_id, projects_by_id, components_by_id
   - Building lookup indices для быстрого find_donors

4. `find_donors(device_type, components, top_k)` should match по реальной CDPO структуре (`Device.contains` + `Project.salvage_recommendations`)

**Done criteria:**
- `python3 -c "from kb.index import KBIndex; kb = KBIndex(); kb.load('/home/user/aisurvive/kb/output/extracted')"` загружает без ошибок
- `kb.stats()` возвращает корректные counts
- `kb.find_donors('inkjet_printer', ['stepper_motor', 'solenoid'])` возвращает 5 проектов с overlap > 0

### Track 4 — Validation + packaging pipeline

**Файлы:** `kb/pipeline/scripts/`

Создай (или дополни) скрипты для финального packaging KB:

1. `validate_schema.py` — Pydantic validate всех файлов в `kb/output/extracted/`. Output: `validation-reports/schema.json` со списком errors. Pass rate target ≥95%.

2. `validate_xref.py` — все references резолвятся? Output: `validation-reports/xref.json`.

3. `validate_antilaziness.py` — regex check на forbidden phrases (см. KIMI-MEGA-BRIEF Section 8.1). Output: `validation-reports/antilaziness.json`.

4. `validate_coverage.py` — sравнивает counts по категориям с targets из PRD. Output: `validation-reports/coverage.json`.

5. `build_index.py` — создаёт `kb/output/INDEX.json` со всеми records, sha256 hashes, total stats.

6. `package.sh` — упаковывает финальную KB:
   ```bash
   #!/bin/bash
   cd /home/user/aisurvive
   tar --create extracted/ packs/ firmware-genome/ INDEX.json | \
       zstd -19 --long=27 --threads=0 -o /home/user/aisurvive/kb/output/ark-kb-v0.1.tar.zst
   sha256sum kb/output/ark-kb-v0.1.tar.zst > kb/output/ark-kb-v0.1.sha256
   ```

7. `report.py` — генерирует `kb/output/REPORT.md` с прогресс-барами по категориям, validation rates, total cost spent.

**Done criteria:**
- All 7 scripts run without errors
- Final tar.zst создан
- REPORT.md заполнен реальными данными

### Track 5 — Open source release artifacts

**Папка:** `/home/user/aisurvive/oss/` (или интегрировать в репо).

Создай:

1. `LICENSE` (Apache 2.0 для solver/code)
2. `LICENSE-KB` (CC-BY 4.0 для KB content)
3. `LICENSE-ADAPTERS` (MIT для scrapers)
4. `CONTRIBUTING.md` — как контрибьютить KB entries, code, tests
5. `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1)
6. `SECURITY.md` (security@ark.computer, responsible disclosure)
7. `CHANGELOG.md` (v0.1.0 entry)
8. `.github/workflows/ci.yml` — ruff + pytest на PR
9. `.github/ISSUE_TEMPLATE/{bug.md,feature.md,kb-entry.md}`
10. `.github/PULL_REQUEST_TEMPLATE.md`
11. Update root `README.md` — public-facing, с Quickstart, architecture diagram (Mermaid), how to contribute, license summary

---

## 3. Process

1. Read `PRD.md`. Это master document.
2. Read `agents/claude/TASK.md` (этот файл).
3. Read existing code в `product/server/` чтобы понять текущее состояние.
4. Read `kb/pipeline/schemas/cdpo.py` — это data model.
5. Track 1 first (vision) — это самый высокий приоритет blocker.
6. После каждого track — pytest проверка.
7. После всех 5 tracks — manual smoke test:
   ```
   uvicorn product.server.main:app --reload
   curl localhost:8080/healthz                 # → 200
   curl -F "image=@test.jpg" localhost:8080/api/vision  # → JSON device list
   curl -X POST localhost:8080/api/solve \
       -F "image=@test.jpg" \
       -F "user_input=Build me an irrigation controller" \
       -F "mode=daily"                          # → JSON Plan
   ```

## 4. Forbidden behaviors

- ❌ Не пиши KB records — это DeepSeek/Kimi
- ❌ Не делай Twitter posts / video scripts / brand assets — это marketing track
- ❌ Не модифицируй CDPO schema без явного запроса — она **canonical** для всех агентов
- ❌ Не запускай Anthropic batch с KB extraction (ты не должен тратить наш budget на bulk — это территория DeepSeek)
- ❌ Не реорганизовывай папки — структура уже задана в PRD Section 5.3

## 5. Done criteria — на уровне whole task

```
[ ] vision/client.py имплементирован (Replicate + OpenAI fallback) ✓ tests pass
[ ] routes.py баги исправлены ✓ smoke test pass
[ ] kb/index.py использует CDPO models ✓ load real KB without errors
[ ] 7 validation/packaging scripts созданы ✓ run end-to-end
[ ] OSS release artifacts готовы ✓ ready to flip репо public
[ ] Server deploy на Fly.io работает (`fly deploy` без ошибок)
[ ] Manual smoke test проходит (vision → solve → plan rendered HTML)
```

## 6. Что ты получаешь

**Эта работа разблокирует launch.** Без vision client ARK не работает. Без validation pipeline KB нельзя поставить в production. Без OSS artifacts репо нельзя открыть.

**Срок:** 1-2 недели (5-7 дней focused work).

**Cost:** ~$50 на Claude API для тестирования (если работаешь не через Claude Code OAuth).

## 7. Start

Begin with Track 1 (Vision client). Read existing stub в `product/server/vision/client.py`. Read Replicate API docs (qwen2-vl-7b-instruct endpoint). Imp полный реальный код. Run tests. If pass — commit. Move to Track 2.

Поехали.
