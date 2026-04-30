<div align="center">

# ARC.computer

### Компьютер судного дня. Offline AI который превращает мусор в работающие инструменты.

> *When the internet dies, this remembers.*

[![License: Apache 2.0](https://img.shields.io/badge/Code-Apache%202.0-blue.svg)](LICENSE)
[![License: CC-BY 4.0](https://img.shields.io/badge/KB-CC--BY--4.0-green.svg)](LICENSE-KB)
[![License: MIT](https://img.shields.io/badge/Adapters-MIT-orange.svg)](LICENSE-ADAPTERS)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

</div>

---

## Что это

ARC — **автономный AI-ассистент для off-grid / postapoc / sanctions-zone сценариев**. Юзер описывает что у него есть из электроники и что хочет собрать — система выдаёт **готовый план**: BOM из имеющихся доноров, схему, прошивку, шаги сборки, safety warnings.

Без интернета. Без облака. Без подписок.

```
                ┌─────────────────────────┐
                │  «У меня 3 принтера HP, │
                │   микроволновка, ATX    │
                │   PSU. Хочу автополив   │
                │   на 10 зон.»           │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │   ARC Reverse-BOM AI    │
                │   ┌──────────────────┐  │
                │   │ 78,869 records   │  │
                │   │ KB (offline)     │  │
                │   └──────────────────┘  │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │ Готовый план:           │
                │ • BOM с источниками     │
                │ • Teardown checklist    │
                │ • Schematic ASCII       │
                │ • Firmware (.ino)       │
                │ • Calibration steps     │
                │ • Safety warnings       │
                └─────────────────────────┘
```

## Чем отличается от ChatGPT / Wikipedia / NOMAD

| | ChatGPT | NOMAD / Kiwix offline | **ARC** |
|---|---|---|---|
| Offline | ❌ | ✓ | ✓ |
| Reverse-BOM (junk → project) | hallucinate | ❌ | ✓ |
| Inventory matching | ❌ | ❌ | ✓ |
| Constrained generation (no fake parts) | ❌ | ❌ | ✓ |
| Configurable firmware genome (auto-Configuration.h) | ❌ | ❌ | ✓ |
| Substitution graph (no part X → use Y) | ❌ | ❌ | ✓ |
| Vision inventory (фото полки → список) | partial | ❌ | ✓ |

## Возможности

### Три режима использования

1. **Reverse-BOM** — «у меня X, хочу Y» → solver подберёт компоненты из имеющегося хлама и план сборки
2. **Forward-BOM** — «хочу собрать Y» → solver выдаст BOM + где такие компоненты обычно найти в бытовой технике
3. **Discovery** — «у меня X» → solver покажет 5 проектов которые из этого собираются

### Структурированная knowledge base

| Категория | Записей |
|---|--:|
| **Components** (canonical) | 55,414 |
| **Substitutions** (chains) | 10,000 |
| **Devices** (teardown patterns) | 5,000+ |
| **Materials** (DIY recipes) | 1,242 |
| **Tools** (with build-from-junk paths) | 716 |
| **Safety** (hazard profiles) | 500 |
| **Phenomena** (physics for solver) | 301 |
| **Skills** (with prerequisites) | 203 |
| **Goals** (top-level survival) | 50 |
| **Regional profiles** (mains/radio/etc) | 50 |
| **Firmware genome** (configurable templates) | 40 |
| **Projects** (recipes) | 1,225+ |
| **Total** | **~78,869** |

### Stack

- **Backend:** FastAPI + Pydantic + httpx async
- **Frontend:** htmx + минимум JS
- **AI runtime:** DeepSeek V4 Pro (через Anthropic-compatible endpoint) или OpenAI/Anthropic
- **Vision:** Replicate Qwen2-VL-7B (primary) + OpenAI GPT vision (fallback)
- **KB:** in-memory CDPO Pydantic models, JSON-on-disk, Qdrant deferred to v2
- **Validation:** schema + cross-reference + anti-laziness regex + firmware compile via simavr/avr-gcc/arm-none-eabi
- **Deploy:** Docker → Fly.io

## Quickstart

```bash
git clone https://github.com/ORTODOX1/arc-computer.git
cd arc-computer

# Bootstrap server
bash scripts/local_dev.sh

# В другом терминале:
curl http://127.0.0.1:8181/health
curl http://127.0.0.1:8181/kb/stats | jq

# Открыть в браузере
xdg-open http://127.0.0.1:8181/
```

Knowledge base **не лежит в этом репо** — слишком большая (300 MB). Скачивается отдельно через GitHub Releases:

```bash
# Скачать последний KB-snapshot
curl -fsSL https://github.com/ORTODOX1/arc-computer/releases/latest/download/ark-kb.tar.zst -o /tmp/kb.tar.zst
mkdir -p kb/output
tar --use-compress-program=zstd -xf /tmp/kb.tar.zst -C kb/output/
```

## Архитектура

```
arc-computer/
├── PRD.md                  ← master product requirements
├── README.md
│
├── product/server/         ← FastAPI runtime
│   ├── main.py             ← app factory
│   ├── api/routes.py       ← /, /app, /solve, /health, /kb/stats
│   ├── vision/client.py    ← Replicate + OpenAI fallback
│   ├── solver/engine.py    ← Anthropic-compat client + RAG
│   ├── kb/                 ← CDPO loaders + indices
│   ├── templates/          ← Jinja2 (landing + solver UI)
│   └── tests/              ← pytest
│
├── kb/
│   ├── STRATEGY.md         ← two-zone storage plan
│   ├── pipeline/
│   │   ├── schemas/cdpo.py ← canonical Pydantic data model
│   │   ├── extractors/     ← LLM extraction adapters + 4 prompts
│   │   └── scripts/        ← scrapers, validators, packagers
│   └── output/             ← .gitignore'd (300 MB KB content via Releases)
│
├── product/landing/        ← marketing site (HTML)
├── product/hardware/       ← BOM, KiCad refs, STL refs
├── product/firmware-templates/
│
├── agents/                 ← per-AI agent assignments
│   ├── kimi/               ← curation tasks (Kimi K2 subscription)
│   ├── deepseek/           ← bulk extraction (DeepSeek V4)
│   └── claude/             ← production code (Claude Sonnet)
│
├── marketing/              ← Twitter thread, video script, pitch
├── brand/                  ← naming, palette, voice
└── docs/                   ← deployment, firmware validation guides
```

## Three-agent build strategy

ARC's KB and infrastructure были собраны за один день через **трёх AI-агентов параллельно**:

1. **Kimi K2** (subscription) — top-quality curation: 73,500+ records (phenomena, materials, tools, components, devices, substitutions, safety, firmware-genome)
2. **DeepSeek V4 Pro** (~$3 API) — bulk extraction из iFixit/Instructables/Hackaday: 2,340+ records
3. **Claude Sonnet 4.5** (subscription) — production code (8 tracks: server, vision client, KB integration, validation pipeline, OSS artifacts, firmware emulator, e2e tests, deploy automation)

См. [`agents/`](agents/) для конкретных задач каждого.

## Roadmap

- [x] **v0.1 alpha** — server scaffold, 78k records KB, validation pipeline, OSS artifacts
- [ ] **v0.1 launch** — domain registration, Fly.io deploy, viral launch (Twitter + HN)
- [ ] **v0.2** — SD-card $99 product, premium content packs (Soviet/Marine/HAM/Homestead)
- [ ] **v0.3** — Pi 5 hardware kit $499 with pre-loaded KB, mesh federation, vision inventory v2
- [ ] **v1.0** — multi-language KB, Tier 3 premium hardware, B2B licensing for NGOs

## Documentation

| Document | What |
|---|---|
| [`PRD.md`](PRD.md) | Master product requirements — read first |
| [`brand/BRAND.md`](brand/BRAND.md) | Naming, palette, founder narrative |
| [`kb/STRATEGY.md`](kb/STRATEGY.md) | Storage tiering (hot zone on device, cold on dev disk) |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Fly.io setup, deploy script, rollback |
| [`docs/FIRMWARE-VALIDATION.md`](docs/FIRMWARE-VALIDATION.md) | simavr/qemu/avr-gcc setup |
| [`agents/kimi/briefs/KIMI-MEGA-BRIEF.md`](agents/kimi/briefs/KIMI-MEGA-BRIEF.md) | Full KB scope spec (32 collections) |
| [`agents/kimi/briefs/KIMI-FIRMWARE-GENOME.md`](agents/kimi/briefs/KIMI-FIRMWARE-GENOME.md) | Firmware genome project brief |
| [`marketing/video/DEMO-SCRIPT.md`](marketing/video/DEMO-SCRIPT.md) | Viral launch video shot list |

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Key points:

- **Code style:** ruff (Python 3.13+)
- **Tests required** for new features
- **KB entries** follow [`kb/pipeline/schemas/cdpo.py`](kb/pipeline/schemas/cdpo.py) (Component-Device-Project Ontology)
- **Conventional Commits**

Issue templates: [bug](.github/ISSUE_TEMPLATE/bug.md) · [feature](.github/ISSUE_TEMPLATE/feature.md) · [knowledge-base entry](.github/ISSUE_TEMPLATE/kb-entry.md).

Community standards: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) (Contributor Covenant 2.1). Security disclosures: [`SECURITY.md`](SECURITY.md).

## License

| Scope | License | File |
|---|---|---|
| Code (server, solver, validators) | Apache-2.0 | [`LICENSE`](LICENSE) |
| Knowledge-base content | CC-BY-4.0 | [`LICENSE-KB`](LICENSE-KB) |
| Adapters and scrapers | MIT | [`LICENSE-ADAPTERS`](LICENSE-ADAPTERS) |

Per-record provenance metadata in KB JSONs may indicate upstream sources (iFixit content under CC-BY-NC-SA, manufacturer datasheets, etc) — respect upstream licenses when redistributing.

## Sponsors / Funding

- GitHub Sponsors: planned
- One-time funding: BTC / ETH (post-launch)

## Stay in touch

- Domain: `arc.computer` (registration in progress)
- Twitter: `@arccomputer` (registration in progress)
- Discord: planned post-launch
- Email: founder@arc.computer (placeholder)

---

<div align="center">

**Built for the Tuesday after the lights go out.**

[Read PRD](PRD.md) · [Get involved](CONTRIBUTING.md) · [Report security issue](SECURITY.md)

</div>
