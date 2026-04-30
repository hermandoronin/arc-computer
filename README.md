<div align="center">

# `ARC.computer`

### Offline AI engineer. Turns scrap electronics into working tools.

**No internet. No cloud. No subscription.**

[Quickstart](#quickstart) ·
[Architecture](#architecture) ·
[Roadmap](#roadmap) ·
[Русский](README.ru.md)

<br>

[![License: Apache 2.0](https://img.shields.io/badge/Code-Apache%202.0-blue.svg)](LICENSE)
[![License: CC BY 4.0](https://img.shields.io/badge/KB-CC--BY--4.0-green.svg)](LICENSE-KB)
[![License: MIT](https://img.shields.io/badge/Adapters-MIT-orange.svg)](LICENSE-ADAPTERS)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()
[![GitHub stars](https://img.shields.io/github/stars/ORTODOX1/arc-computer?style=flat&color=yellow)](https://github.com/ORTODOX1/arc-computer/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/ORTODOX1/arc-computer)](https://github.com/ORTODOX1/arc-computer/issues)

</div>

---

## The problem

Every "AI for hardware" tool tells you what to **buy**. ChatGPT will hallucinate
parts. Wikipedia is offline-capable but doesn't reason. Your old electrical
engineering books don't fit in a backpack.

Nothing tells you what you can **build** from what you **already have**.

## How it works

```
                ┌──────────────────────────┐
                │  "I have 3 broken HP     │
                │   printers, a microwave, │
                │   an ATX PSU. I want a   │
                │   10-zone irrigation."   │
                └────────────┬─────────────┘
                             │
                             ▼
                ┌──────────────────────────┐
                │     ARC reverse-BOM      │
                │   ┌────────────────────┐ │
                │   │  78,869 records    │ │
                │   │  KB (offline)      │ │
                │   └────────────────────┘ │
                └────────────┬─────────────┘
                             │
                             ▼
                ┌──────────────────────────┐
                │ Working plan:            │
                │ • BOM with sources       │
                │ • Teardown checklist     │
                │ • Schematic (ASCII)      │
                │ • Firmware (.ino)        │
                │ • Calibration steps      │
                │ • Safety warnings        │
                └──────────────────────────┘
```

## Three modes

1. **Reverse-BOM** — *"I have X, want Y"* → solver picks components from your
   scrap pile and returns a complete build plan.
2. **Forward-BOM** — *"I want Y"* → solver returns the BOM and tells you which
   household devices typically contain those parts.
3. **Discovery** — *"I have X"* → solver returns 5 buildable projects sourced
   from the inventory you described.

## Compared to

| | ChatGPT | Kiwix / NOMAD offline | **ARC** |
|---|:---:|:---:|:---:|
| Offline-first | ❌ | ✓ | ✓ |
| Reverse-BOM (junk → project) | hallucinates | ❌ | ✓ |
| Inventory matching | ❌ | ❌ | ✓ |
| Constrained generation (no fake parts) | ❌ | ❌ | ✓ |
| Configurable firmware genome | ❌ | ❌ | ✓ |
| Substitution graph (no part X → use Y) | ❌ | ❌ | ✓ |
| Vision inventory (photo → list) | partial | ❌ | ✓ |

## Knowledge base

Structured offline knowledge graph, ~78k records, ~50 MB compressed.

| Collection | Records |
|---|---:|
| Components (canonical) | 55,414 |
| Substitutions (chains) | 10,000 |
| Devices (teardown patterns) | 5,000+ |
| Materials (DIY recipes) | 1,242 |
| Tools (with build-from-scrap paths) | 716 |
| Safety profiles | 500 |
| Phenomena (physics for solver) | 301 |
| Skills (with prerequisites) | 203 |
| Goals (top-level objectives) | 50 |
| Regional profiles (mains / radio bands / etc.) | 50 |
| Firmware genome (configurable templates) | 40 |
| Projects (recipes) | 1,225+ |
| **Total** | **~78,869** |

The KB is **distributed via GitHub Releases**, not git — see [Quickstart](#quickstart).

## Quickstart

```bash
git clone https://github.com/ORTODOX1/arc-computer.git
cd arc-computer

# 1. Bootstrap the dev server
bash scripts/local_dev.sh

# 2. Pull the KB tarball (~50 MB)
curl -fsSL https://github.com/ORTODOX1/arc-computer/releases/latest/download/arc-kb.tar.zst -o /tmp/kb.tar.zst
mkdir -p kb/output
tar --use-compress-program=zstd -xf /tmp/kb.tar.zst -C kb/output/

# 3. Verify
curl http://127.0.0.1:8181/health
curl http://127.0.0.1:8181/kb/stats | jq

# 4. Open the UI
xdg-open http://127.0.0.1:8181/
```

## Stack

- **Backend** — FastAPI · Pydantic v2 · httpx async
- **Frontend** — htmx · Jinja2 · minimal JS
- **AI runtime** — DeepSeek V4 Pro (Anthropic-compatible endpoint) · OpenAI · Anthropic
- **Vision** — Replicate Qwen2-VL-7B (primary) + OpenAI GPT vision (fallback)
- **KB** — in-memory CDPO Pydantic models · JSON-on-disk · Qdrant deferred to v2
- **Validation** — schema · cross-reference · anti-laziness regex · firmware compile via `simavr` / `avr-gcc` / `arm-none-eabi-gcc`
- **Deploy** — Docker → Fly.io

## Architecture

```
arc-computer/
├── README.md                    you are here
│
├── product/
│   └── server/                  FastAPI runtime
│       ├── main.py
│       ├── api/routes.py        / · /app · /solve · /health · /kb/stats
│       ├── vision/client.py     Replicate + OpenAI fallback
│       ├── solver/engine.py     Anthropic-compatible client + RAG
│       ├── kb/                  CDPO loaders + indices
│       ├── templates/           Jinja2 (landing + solver UI)
│       └── tests/               pytest
│
├── kb/
│   ├── STRATEGY.md              two-zone storage plan
│   ├── pipeline/
│   │   ├── schemas/cdpo.py      canonical Pydantic data model
│   │   ├── extractors/          LLM extraction adapters + prompts
│   │   └── scripts/             scrapers, validators, packagers
│   └── output/                  generated KB (gitignored, distributed via Releases)
│
├── docs/                        deployment + firmware validation guides
└── scripts/                     bootstrap + dev + deploy helpers
```

## Documentation

| Document | What |
|---|---|
| [`kb/STRATEGY.md`](kb/STRATEGY.md) | KB storage tiering (hot zone on device, cold on dev disk) |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Fly.io setup, deploy script, rollback |
| [`docs/FIRMWARE-VALIDATION.md`](docs/FIRMWARE-VALIDATION.md) | `simavr` / `qemu` / `avr-gcc` setup |

## Roadmap

- [x] **v0.1 alpha** — server scaffold, KB validation pipeline, OSS artefacts
- [ ] **v0.1 launch** — Fly.io deploy, public release
- [ ] **v0.2** — premium content packs (Marine, HAM, Homestead, 3D-printer salvage)
- [ ] **v0.3** — Raspberry Pi 5 hardware kit with pre-loaded KB, mesh federation, vision inventory v2
- [ ] **v1.0** — multi-language KB, mesh between devices

## Audience

ARC is built for people who already build things themselves:

- 🏡 Off-grid homesteaders (US / EU / AU / CA rural)
- ⛵ Sailors and liveaboards
- 🛠️ Remote-region engineers and repair shops
- 📰 Field NGO staff, journalists, expedition crews
- 🌱 Self-reliance / homestead communities
- 🔌 Maker hobbyists and hardware tinkerers

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Highlights:

- **Code style** — `ruff` (Python 3.13+)
- **Tests required** for new features
- **KB entries** follow [`kb/pipeline/schemas/cdpo.py`](kb/pipeline/schemas/cdpo.py) (Component-Device-Project Ontology)
- **Conventional Commits**

Issue templates: [bug](.github/ISSUE_TEMPLATE/bug.md) · [feature](.github/ISSUE_TEMPLATE/feature.md) · [knowledge-base entry](.github/ISSUE_TEMPLATE/kb-entry.md)

Community standards: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) (Contributor Covenant 2.1) · Security disclosures: [`SECURITY.md`](SECURITY.md)

## License

| Scope | License | File |
|---|---|---|
| Code (server, solver, validators) | Apache-2.0 | [`LICENSE`](LICENSE) |
| Knowledge-base content | CC-BY-4.0 | [`LICENSE-KB`](LICENSE-KB) |
| Adapters and scrapers | MIT | [`LICENSE-ADAPTERS`](LICENSE-ADAPTERS) |

Per-record provenance metadata in the KB JSON files indicates upstream sources
(iFixit content under CC-BY-NC-SA, manufacturer datasheets, etc.) — respect
the upstream licence when redistributing.

## Stay in touch

- **Issues** — open one on [GitHub](https://github.com/ORTODOX1/arc-computer/issues)
- **Discussions** — [GitHub Discussions](https://github.com/ORTODOX1/arc-computer/discussions)

## Star history

[![Star History Chart](https://api.star-history.com/svg?repos=ORTODOX1/arc-computer&type=Date)](https://star-history.com/#ORTODOX1/arc-computer&Date)

---

<div align="center">

**Built for people who build, fix, and grow things — anywhere, anytime.**

[Get involved](CONTRIBUTING.md) · [Report a security issue](SECURITY.md)

</div>
