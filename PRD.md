# ARC.computer — Product Requirements Document

> **Master document.** Everything else (briefs, plans, tasks) derives from here.
> Last updated: 2026-04-29.

---

## 0. TL;DR

ARC — **offline AI computer with reverse-BOM solver** for makers, off-grid homesteaders, sailors, remote-region engineers, and self-reliant communities.

User snaps a photo of broken electronics on their shelf → ARC identifies devices → tells them which projects they can build from these donors → outputs working BOM, schematic, firmware, calibration steps. **No internet. Offline forever.**

**Open source core + commercial monetization layer** (SD-cards $99, hardware kit $499, premium content packs $49 each).

Distinguished from competitors (Project NOMAD, PrepperDisk, PrepStick) by:
1. **Reverse BOM solver** — junk → project, not project → buy
2. **Vision Inventory** — photo → list of buildable projects
3. **Configurable firmware genome** — auto-generates working Configuration.h/printer.cfg from user's specific MCU + components
4. **Substitution graph** — what to do when the exact component is unavailable
5. **Daisy-chain build planner** — if you need a tool you don't have, build it first

Nobody copies this in a weekend.

---

## 1. Vision

ARC is the tool a person reaches for when the nearest hardware store is 200 km away, when shipping takes a month, or when the cloud service they used to depend on just disappeared.

It's the tool an off-grid homesteader uses on a Tuesday to fix their well pump, the tool a sailor uses 800 nautical miles offshore to repair the AIS, the tool a remote-region engineer uses to keep refrigeration running for medication when the supply chain is broken.

The product is useful every Tuesday for anyone living in conditions where you can't depend on someone else's server. That's the broader reality our customers actually live in.

---

## 2. Three reality-checks (where we got smarter over time)

### 2.1 Project NOMAD changed the market in March 2026

Project NOMAD released as free, open-source, comprehensive offline AI server (Wikipedia + Ollama + Kolibri + Qdrant + RAG). 2,294 GitHub stars in one day, #1 trending. **Free knowledge-box-with-AI is solved.** Charging $1500 for ours-but-prettier is dead.

**Implication:** ARC competes by **doing what NOMAD does NOT** — reverse BOM solver, configurable firmware genome, vision inventory, substitution graph. NOMAD = static knowledge + chat. ARC = dynamic builder.

### 2.2 80,000 records in v0.1 was overscoping

Original mega-brief targeted 80k structured records. After 7 Kimi build iterations, total delivered: ~30 records. Kimi (and any single agent on subscription) can't bulk-produce 80k records — they hit review-gate patterns and compute limits.

**Implication:** v0.1 ships with **2,000-5,000 records of high quality**, not 80k of mediocre quality. NOMAD launched with effectively 0 structured records and went viral on potential. We can ship at 2k.

### 2.3 Single-agent strategy was wrong

Three different agent types do different things well:

| Agent | Cost | Strength | Best for |
|---|---|---|---|
| **Kimi (subscription)** | $0 marginal | Top-quality curation, agentic computer use, 200k+ context | 100-300 critical-path records (firmware-genome configurators, Soviet pack, deep safety) |
| **DeepSeek V4 Pro (via OpenRouter)** | $0.27/M output | Cheap reasoning, batch-friendly, 1M context | Bulk generation 2000-5000 records (devices, components, projects, substitutions) |
| **Claude Sonnet/Opus (via OpenRouter or direct)** | $3-15/M output | Production code, validation, integration | Server fixes, vision client, packaging scripts |

**Implication:** triplet strategy. Each agent has a `agents/<name>/TASK.md`. Each runs in parallel on its strength.

---

## 3. Customers

Seven personas, decreasing volume order:

1. **Off-grid homesteader (US/EU rural)** — 5M households globally; solar+well; far from town; fix-it-yourself culture
2. **Sailor / liveaboard** — ~400k vessels worldwide with house systems
3. **Remote-region maker** — engineers in regions with limited supply chains, intermittent connectivity, salvage-first culture
4. **Field NGO / journalist / aid worker** — expedition crews, climate-disaster response, humanitarian work
5. **Self-reliance / homestead community** — well-trained rural audience, $11B self-reliance industry
6. **Maker hobbyist** — high disposable income, contributes back to community
7. **Community organizer** — coordinating 10-100 people in shared infrastructure (eco-villages, co-housing, intentional communities)

Primary voice = practical resilience + maker ethos. We're building tools for people who already build things themselves.

---

## 4. Scope

Key points:

### In scope
- Power: solar, wind, micro-hydro, LiFePO4 batteries, MPPT, inverters
- Water: pumping, filtration, UV sterilization, distillation, rain capture, irrigation
- Food: greenhouse automation, hydroponics, food drying, fermentation, root cellars
- Comms: licensed amateur radio operations, LoRa mesh, satellite IoT, encrypted local messaging
- Perimeter: alarms, motion sensors, deterrent lighting (non-lethal)
- Repair: appliance teardown + rebuild, motor rewinding, MCU re-flashing, PCB rework
- Tools: building tools from junk (lathes from washing machines, kilns from microwave parts, welders from MOTs)
- Reference content: standard first-aid procedures, the *Where There Is No Doctor* canon, US Army field manuals, *Hesperian* health library
- Salvage: device teardown patterns, donor-graph for components, substitution chains

### Hard limits — off-table regardless of context
- Weapons, ammunition, explosives, suppressors
- Drug synthesis (controlled or recreational), opioid synthesis
- Targeted human poisons, bioweapons, chemical mass-casualty agents
- Nuclear material handling
- Surveillance against people without their consent
- Unlicensed RF transmission (pirate radio, ham operations without callsign)
- Lockpicking instructions, vehicle theft, social engineering
- Anything in violation of applicable local law

ARC is a reference and engineering assistant, not a substitute for a licensed professional (medical, electrical, legal, RF). Users are responsible for compliance with the laws of their jurisdiction.

---

## 5. Architecture

### 5.1 Build-time (one-time)

```
SOURCES                  EXTRACTION             KB
─────                    ──────────             ──
iFixit guides       ─┐
Instructables       ─┤
Hackaday            ─┤   ┌──────────────┐    ┌────────────┐
YouTube subs        ─┼──▶│ DeepSeek V4  │───▶│ extracted/ │
Survivor Library    ─┤   │ batch        │    │ devices/   │
Datasheets          ─┤   │ extractors   │    │ projects/  │
KiCad libs          ─┤   └──────────────┘    │ ...        │
Wikidata            ─┘                       └────────────┘
                                                   │
                         ┌──────────────┐          │
                         │ Kimi K2      │          │
                         │ subscription │──────────┤
                         │ (curation)   │          │
                         └──────────────┘          │
                                                   ▼
                                            ┌────────────┐
                                            │ validation │
                                            │ packaging  │
                                            └─────┬──────┘
                                                  │
                                            ┌─────▼──────┐
                                            │ ark-kb-    │
                                            │ v0.1.tar.  │
                                            │ zst (5GB)  │
                                            └────────────┘
```

### 5.2 Runtime (production server)

```
USER                       SERVER (Fly.io)            KB
────                       ────────────────           ──
Photo upload  ───────────▶ /api/solve
                              │
                              ▼
                           Vision endpoint  ─────▶ Replicate
                              │                    Qwen 2.5 VL
                              │
                           [device list]
                              │
                              ▼
                           KB lookup       ◀────── Loaded KB
                              │                    (Qdrant + Tantivy)
                              ▼
                           Solver
                              │
                              ▼
                           Claude Sonnet 4.5 ◀──── Anthropic
                              │
                              ▼
                           Plan rendered
                              │
                              ▼
USER  ◀───────── htmx HTML response (BOM, teardown, code, schematic)
```

### 5.3 Folder structure

```
arc-computer/
├── PRD.md                           this file
├── README.md                        public-facing
├── agents/
│   ├── kimi/TASK.md                 Kimi's assignment
│   ├── deepseek/TASK.md             DeepSeek's assignment
│   └── claude/TASK.md               Claude's assignment
├── kb/
│   ├── STRATEGY.md                  KB storage + tiering strategy
│   ├── pipeline/                    extractors, schemas
│   └── output/                      generated KB (gitignored, distributed via Releases)
├── product/
│   ├── server/                      FastAPI runtime
│   ├── landing/                     marketing site
│   ├── hardware/                    BOM, KiCad, STL
│   └── firmware-templates/
├── marketing/
│   ├── kickstarter/
│   ├── twitter/
│   └── video/
└── brand/
    └── BRAND.md
```

---

## 6. Roadmap

### v0.1 — viral launch (D+0 → D+45)

Goal: ship working demo on `ark.computer` + viral video + public open-source GitHub repo.

**Deliverables:**
- 2,000-5,000 KB records (validated)
- Working solver web-app at `ark-solver.fly.dev`
- 35-second viral video
- Landing with email collect
- Twitter thread launch
- HN "Show HN" submission
- Reddit cross-posts
- Hackaday tip

**Cost:** ~$2,500-4,000 (KB extraction $400-1200 + video $700-1200 + hosting + domain + misc)

**Success metric:** 5,000+ GitHub stars, 1,000+ email signups, 1+ tier-1 media coverage in 14 days.

### v0.2 — first revenue (D+45 → D+90)

Goal: monetize attention.

- SD-card pre-loaded "ARC Starter" $99 → 100-200 sold
- Premium content packs $49 each (Sailor, HAM, Soviet, Homestead, 3D-printer)
- GitHub Sponsors / Patreon recurring

**Target revenue:** $10-30k cumulative.

### v0.3 — depth (D+90 → D+180)

- Hardware kit $499 (only if 100+ pre-orders confirmed)
- Hosted Vision API tier $5-15/mo for users running their own KB
- B2B outreach to NGOs / expedition outfitters
- KB grows to 10k-20k records via crowd contributions + targeted batch fills

**Target revenue:** $50-150k cumulative year-1.

### v1.0 (year 2+)

- Premium hardware tier $1,500 (only if v0.3 confirms demand)
- Multi-language KB (RU, DE, IT, ES, PL, FR)
- Mesh federation between devices
- Custom fine-tuned models per vertical

---

## 7. Unit economics (v0.2 monetization)

### SD-card "ARC Starter" $99

| Line | $ |
|---|---|
| 64GB Sandisk Extreme USB | 9 |
| Cardboard packaging + sticker | 2 |
| Shipping (avg) | 5 |
| Lemon Squeezy 5% (Merchant of Record) | 5 |
| Cost of goods | **21** |
| Margin | **78** |
| Sales target year-1 | 500 units |
| Revenue year-1 | $49,500 |
| Profit year-1 | $39,000 |

### Hardware kit $499 (post-validation)

| Line | $ |
|---|---|
| Pi 5 8GB + NVMe 1TB | 150 |
| E-ink 7.5" Waveshare | 80 |
| LiFePO4 12V/10Ah | 60 |
| USBasp + components kit | 30 |
| Pre-loaded SD with full KB | (already have) |
| Pelican-style ABS case | 40 |
| Assembly + QA | 30 |
| Shipping | 25 |
| Lemon Squeezy 5% | 25 |
| Cost of goods | **440** |
| Margin | **59** |
| Year-1 target | 50 units (limited release) |
| Revenue | $24,950 |
| Profit | $2,950 |

Hardware is low-margin until volume. Real revenue = SD-cards + content packs + recurring vision API + sponsors.

---

## 8. Hard constraints

1. **Open core.** Solver runtime + KB schema + adapters open source (Apache 2.0 / MIT / CC0). Premium content packs, hosted vision API, hardware kit are commercial.
2. **No telemetry.** Device runs without internet, without phoning home. Ever.
3. **Provenance.** Every fact in KB carries source attribution. Every record auditable.
4. **Constrained generation.** Solver picks from KB whitelist, doesn't hallucinate parts.
5. **In-scope topics covered honestly.** Practical engineering content with appropriate safety warnings, not corporate-speak deflection. See Section 4.
6. **Hard limits respected** under any context.
7. **Reproducible builds.** Anyone can rebuild ARC from open source + paid content packs.
8. **Legal compliance.** Content respects applicable laws (RF licensing, controlled substances, weapons). We are a reference tool, not a workaround.

---

## 9. Three-agent strategy — who does what

### Kimi (subscription, ~$0 marginal)
**Role:** master curator. Top-quality records nobody else can replicate quickly.

**Volume:** 100-300 records.

**Focus:**
- Firmware-genome configurators (top-30 fwgen templates with full Jinja2 logic)
- Soviet pack devices/projects/components (unique moat — nobody else has it structured)
- Safety profiles deep (200 hazard records with regulatory cites)
- Killer demo scenarios (top-20 end-to-end "input photo → output plan" examples)

**Brief:** `agents/kimi/TASK.md`

### DeepSeek V4 Pro (OpenRouter, ~$50-150 total)
**Role:** bulk extraction + generation.

**Volume:** 2,000-5,000 records.

**Focus:**
- Devices extraction from iFixit guides (1,500 records)
- Projects extraction from Instructables/Hackaday (1,000 records)
- Components canonical from KiCad libs (2,000 records)
- Substitution chains (500 records)

**Brief:** `agents/deepseek/TASK.md`

### Claude (this session OR via OpenRouter, ~$50 total)
**Role:** production code + critical-path fixes.

**Focus:**
- Vision client implementation (real Replicate + OpenAI fallback, replace stubs)
- Server bugs (routes.py, kb/index.py CDPO unification)
- Validation pipeline scripts
- INDEX.json builder
- tar.zst packaging
- GitHub OSS release artifacts

**Brief:** `agents/claude/TASK.md`

---

## 10. Open questions before launch

- [ ] Domain registered (`arc.computer` / `arccomputer.io`)
- [ ] Twitter / X handle (`@arccomputer` or alternative)
- [x] GitHub repository public — `github.com/ORTODOX1/arc-computer`
- [ ] Legal entity for monetization (Estonia OÜ via e-Residency or similar)
- [ ] Payment processor — Lemon Squeezy / Stripe with Merchant of Record
- [ ] Trademark search ($300–1,500)
- [ ] Domain squatting protection — secure `.com / .io / .computer / .ai`
- [ ] Founder identity — LinkedIn, GitHub history, public references

Blockers for monetization, not for v0.1 product launch. Build product first; legal infrastructure runs in parallel.

---

## 11. Tooling — current state

| Tool | Status | Notes |
|---|---|---|
| Kimi K2 CLI | ✓ installed and logged in | KB curation |
| DeepSeek V4 Pro CLI | ✓ installed (`~/.local/bin/deepseek-cli`) | Anthropic-compatible endpoint at `api.deepseek.com/anthropic` |
| Claude Code | ✓ active | Production code authoring |
| Replicate / OpenAI vision | ❌ pending | Runtime vision endpoint for `/solve` photo upload |
| Domain `arc.computer` | ❌ pending | Pre-launch step 1 |
| Payment processor | ❌ pending | Pre-launch step 2 |
| Legal entity | ❌ pending | Background track, several weeks |

---

## 12. Reference docs (live)

| File | What |
|---|---|
| `agents/kimi/TASK.md` | Kimi's specific assignment |
| `agents/deepseek/TASK.md` | DeepSeek's specific assignment |
| `agents/claude/TASK.md` | Claude's specific assignment |
| `kb/STRATEGY.md` | Two-zone storage strategy |
| `kb/pipeline/schemas/cdpo.py` | CDPO Pydantic data model |
| `marketing/video/DEMO-SCRIPT.md` | Viral video shot list |
| `marketing/twitter/THREAD-VIRAL.md` | Twitter launch thread |
| `marketing/kickstarter/PITCH.md` | Kickstarter copy (probably won't use) |
| `product/hardware/bom/PROTOTYPE-BOM.md` | Hardware BOM |
| `brand/BRAND.md` | Naming, palette, voice |

---

## 13. The bet

ARC is a bet that:
- People will pay $99-499 for offline AI + curated salvage knowledge
- The "self-reliance / resilience" frame lands on real every-Tuesday utility for off-grid life and remote-region work
- Open core + commercial content/hardware is more sustainable than closed product or pure SaaS
- Solo founder + AI augmentation can ship to viral scale in 30-45 days

If those bets hold — D+90 revenue $20-50k, D+180 $50-150k, year-2 $150-400k. Lifestyle business, not VC-scale, but real.

If those bets fail — open source contribution to the maker community, learnings documented, time wasted is 30-45 days not 2 years.

Bet is asymmetric in our favor. Execute.
