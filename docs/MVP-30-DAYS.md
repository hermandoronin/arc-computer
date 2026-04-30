# ARC — MVP in 30 days

Goal: by D+30 we have a working prototype, a launch video, a landing page with email capture, and a ready pitch deck. **Public launch — D+45**, after audience warm-up.

## Principles

1. **Worse is better.** A rough working demo at D+30 beats a perfect product at D+180.
2. **Demo-first development.** A feature exists only if it can be shown in a 30-second video.
3. **Steal infrastructure.** llama.cpp, htmx, Qdrant, Pi 5 — no reinvention.
4. **Lean storage on device, fat storage in dev.** External disk for extraction; on-device storage stays compact.
5. **One viral use-case demo.** "Printer → automated irrigation". Every resource concentrated on this scenario.

---

## Week 1 — Foundation (D+0 → D+7)

### Goal: KB extraction pipeline + base hardware

| Day | Task |
|---|---|
| D+0 | Buy hardware (Pi 5 8GB, NVMe 1TB, Waveshare 7.5" V2 e-ink, LiFePO4, Pelican-style case) |
| D+0–1 | Run `bootstrap-kb.sh` on the external disk — pull starter KB (~150–200 GB external) |
| D+2 | Install Ollama / llama.cpp + Qwen 2.5 14B Q4 on the dev box, run 30 demo prompts manually |
| D+3–4 | Build the LLM extraction pipeline (Python + Claude / DeepSeek batch API) |
| D+5–7 | Run extraction over the top-50 devices (microwaves, printers, monitors, ATX PSUs, routers) → first structured records |

**Verifiable output, W1:** 50 devices with extracted teardowns in Qdrant + working local chat with Qwen 14B.

### W1 budget

- Hardware: ~$400–500
- Claude API extraction: ~$200–300 (50 devices × several guides each)
- Time: ~40 hours

---

## Week 2 — Solver + Reverse-BOM (D+8 → D+14)

### Goal: first working reverse-BOM solver on a single use case

| Day | Task |
|---|---|
| D+8–9 | Stand up Rust-axum stub + htmx UI (no styling yet) |
| D+10–11 | Write solver v0.1 — simple LLM-driven (one prompt with large RAG context, no symbolic check yet) |
| D+12–13 | Run on the "HP DeskJet + microwave → automated irrigation" scenario. Iterate on prompts until quality is acceptable |
| D+14 | Generate a firmware template for ATmega/ESP32 irrigation → wire into solver output |

**Verifiable output, W2:** input "I have X scrap, want automated irrigation" → output BOM, teardown checklist, schematic description, ready-to-flash Arduino `.ino` file.

---

## Week 3 — Hardware integration + DEMO (D+15 → D+21)

### Goal: device in case, launch video shot

| Day | Task |
|---|---|
| D+15 | Assemble Pi 5 + e-ink + power into Pelican-style case |
| D+16 | NixOS image / DietPi with pre-loaded stack, kiosk-mode browser → htmx UI |
| D+17 | Wi-Fi AP mode — device acts as access point, user connects from phone |
| D+18 | Push compact KB onto NVMe (~10–20 GB after compression from W1 extracts) |
| D+19–21 | **SHOOT THE LAUNCH VIDEO** — actually disassemble a printer per AI plan, build the irrigation, show the bed growing a week later |

**Verifiable output, W3:** field-ready device in case + 60–90 s launch video, ready to publish.

### Demo script — see `marketing/video/DEMO-SCRIPT.md`

---

## Week 4 — Marketing prep (D+22 → D+30)

### Goal: landing, email capture, pitch, launch readiness

| Day | Task |
|---|---|
| D+22–23 | Landing site `arc.computer` (HTML + htmx, no React landfill), email capture via Beehiiv / Buttondown |
| D+24 | Twitter thread, prepared answers to typical questions, FAQ |
| D+25–26 | Kickstarter pitch (copy + video cut from W3) — but **not** published yet |
| D+27 | Pre-launch — seed survival-tech bloggers (10 review-unit requests) |
| D+28–29 | Soft launch on Hacker News, `r/preppers`, `r/homestead`, `r/selfhosted`, Hackaday tip line |
| D+30 | **Twitter teaser + landing live.** Goal: 1,000 emails in a week |

**Verifiable output, W4:** live landing, email list growing, pitch ready for Kickstarter.

---

## D+31 → D+45 — Soak time

15 days during which we:
- Catch feedback on Twitter, iterate messaging
- Polish the demo
- Shoot a second demo video (alternate scenario — e.g. "charge phones from a car alternator")
- Grow email list to 3–5 k

## D+45 — Kickstarter launch

Goal: **$50–150 k** in 30 days. Tier 2 (Operator) — 50–100 backers at $1,500–2,000.

---

## Team

| Role | Who |
|---|---|
| Hardware / firmware | Founder |
| Software backend | Founder + AI copilot (Claude Code) |
| Knowledge curation | Founder + LLM extraction pipeline |
| Marketing / Twitter | Founder (founder voice outweighs any agency) |
| Video | Hire a DOP at $500–1,000 for the W3 shoot day |

**Solo + AI-augmented. No employees pre-Kickstarter.**

---

## Total budget D+0 → D+45

| Item | Amount |
|---|---|
| Hardware (1 prototype) | $500 |
| Claude / GPT API extraction | $1,500–3,000 |
| Camera / DOP for demo video | $500–1,000 |
| Domain + landing hosting | $50 |
| Newsletter tool (Beehiiv free until 2.5 k) | $0 |
| Kickstarter video edit | $300–500 |
| Misc (props, packaging, Pelican case) | $200 |
| **Total** | **~$3–5 k** |

---

## What we don't do in the first 30 days

- ❌ NixOS magic (Arch ARM is enough; NixOS post-Kickstarter)
- ❌ Mesh federation (post-Kickstarter)
- ❌ Vision inventory (post-Kickstarter — but **mention as "coming v2" in pitch**)
- ❌ Tier 1 / Tier 3 hardware (Tier 2 as hero product only)
- ❌ Multi-language (EN-only until Kickstarter)
- ❌ All nine goal categories (only three: energy, water, irrigation as the flagship)
- ❌ Symbolic constraint solver (LLM-only first, symbolic — v2)
- ❌ Codegen for every platform (ESP32 + ATmega328P only in v1)

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucinates during the demo | Scenario tightly rehearsed, prompt hard-coded |
| Video doesn't go viral | Backup B-roll scenario ("ATX → phone charger") shot in parallel |
| No one buys | Soak period gives signal; zero emails in a week → pivot before launch |
| Kickstarter recommends 6-month delivery | Closed beta for first 50 backers in 4 months, mass shipping at 9 months |
| Pi 5 / Jetson prices spike | +20 % cushion baked into Kickstarter retail; verify a week before launch |
| Solo founder bottleneck | AI copilot writes 70 % of the boilerplate; founder focuses on critical path |

---

## Decisions to confirm before D+0

- [ ] Prototype tier: **Tier 2 (Pi 5 8GB)** ✅ (scale to Jetson post-Kickstarter)
- [ ] Video length: **60 s primary + 90 s extended cut**
- [ ] Legal entity for Kickstarter: Estonia OÜ via e-Residency (apply D+1, typically 2–4 weeks)
- [ ] Banking: Wise + Stripe Atlas for US-payment backup
- [ ] Domain: verify `arc.computer` / `arccomputer.io`
