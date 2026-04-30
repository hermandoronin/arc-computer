# ARC — Kickstarter Pitch

> **The offline AI computer that helps you build, fix, and grow things — anywhere, anytime.**

---

## ABOVE THE FOLD (first 5 seconds)

**Headline:** ARK — an offline AI that turns broken electronics into working tools.

**Hero video:** 60-second cut (see `marketing/video/demo-script.md`).

**One-liner:** Knowledge that works anywhere — without depending on someone else's server.

**CTA buttons:** `Back this project` · `Watch demo` · `How it works`

---

## THE STORY (above-the-fold long form)

### What if Wikipedia, Stack Overflow, and the entire history of engineering went unreachable tomorrow?

For a lot of people, that's not a hypothetical. That's a regular Tuesday on a remote farm, on a sailboat 800 nautical miles offshore, in a region with intermittent internet, or simply when a major service has an outage.

In 2021, AWS went down and 30% of the web went with it. In 2024, CrowdStrike took out hospitals, airports, and emergency services in a single afternoon. Texas froze. Spain blacked out. Submarine cables get cut. Cloudflare reroutes the world several times a year. And every year more of human knowledge — schematics, troubleshooting guides, repair manuals, medical references — sits behind a single API call that depends on a server farm 3,000 miles away.

**ARC is the answer to a simple question:** what tool would you want when you can't depend on someone else's server?

You'd want a small, rugged, solar-charged computer that knows how to fix things. How to grow things. How to build things. From the broken machines you already have, with the tools you already own.

That's ARC.

---

## WHAT IT ACTUALLY DOES

You type (or speak):

> *"I have a broken washing machine, an old microwave, and a dead laptop. Help me build a 10-zone irrigation system for my garden."*

ARK gives you back:

✅ A complete bill of materials — pulled from those exact devices
✅ Step-by-step teardown instructions for each donor
✅ A wiring schematic
✅ Working firmware (Arduino-ready, pre-compiled)
✅ Calibration procedure
✅ Maintenance schedule

**No internet. No cloud. No subscription.** Everything happens on the device, on the lithium battery in your hand.

---

## THE THREE THINGS THAT MAKE IT IMPOSSIBLE TO COPY

### 1. Reverse Bill of Materials engine

Every other "AI hardware tool" goes *forward*: you describe a project, it tells you what to buy from Mouser. ARK goes *backward*: you describe what you have, it tells you what you can build. Nobody else does this. We've checked.

### 2. The CODEX — 50 000 entries of curated, structured engineering knowledge

Not Wikipedia. Not a chatbot trying to remember things. A purpose-built knowledge graph: 5 000 devices teardowned and indexed, 50 000 components with full datasheets, 5 000 verified projects, plus the entire Hesperian medical library, the complete US Army field manuals, decades of *Survivor Library* engineering books, and the Soviet *Radio* magazine archive — all distilled into something an AI can reason about.

### 3. Constrained generation, not hallucination

Your offline AI assistant on the average laptop will happily tell you to "use a 7805 regulator" — even if you don't have one. ARK *can't* do that. It can only suggest components from devices you actually have on the shelf. If something's missing, it tells you which donor to break, or how to substitute from discrete parts.

---

## SPECS

| | |
|---|---|
| Platform | Raspberry Pi 5 8GB / NVMe 1TB |
| Display | Waveshare 7.5" e-ink (sunlight-readable, 0.4W idle) |
| Power | LiFePO4 12V/30Ah + 50W folding solar + MPPT |
| Comms | LoRa mesh (Meshtastic-compatible) + GPS + optional SDR |
| Case | Pelican 1450 with copper-mesh Faraday lining |
| AI model | Qwen 2.5 14B Q4 (local) + Qwen 2.5 VL 7B (vision) |
| Storage | 1 TB NVMe — 25 GB compressed KB + 975 GB user space |
| Battery life | 18-24h active, weeks idle |
| OS | Hardened Arch ARM, A/B partitions, no telemetry, no network calls |

---

## TIERS

### 🔧 ARK-1 "Operator" — $1499 (early bird, limited 100)
Full kit, assembled, tested. Ships with starter CODEX (50 000 entries).
**Then $1799 retail.**

### 📦 ARK-1 DIY Kit — $899 (limited 200)
All components, instructions, pre-flashed SD card. You assemble it. You learn it inside out.

### 🌱 Just the CODEX — $149 (digital, unlimited)
The knowledge base + open-source software for your own SBC. 1 TB image.

### 🛡️ ARK-1 Pro "Operator+" — $2299 (limited 50)
Same as Operator + 100W solar + extended battery + Iridium-ready slot + lifetime KB updates.

### 👥 ARK-1 Squad (5 units mesh-pre-paired) — $6499
For homesteading families, prepper communities, off-grid expeditions. Five units pre-configured for federation.

---

## TIMELINE

| | |
|---|---|
| Now (D+0) | Working prototype, this Kickstarter |
| Funded | Component bulk orders, contract assembly partner |
| +3 months | Closed beta — first 50 backers receive units |
| +6 months | Mass shipping begins (Operator + DIY kit) |
| +9 months | Pro tier ships, squad bundle ships |
| +12 months | KB v2 with vision inventory + mesh federation |

---

## RISKS — what could go wrong

We're shipping consumer hardware. We've read every Kickstarter post-mortem and we've assumed the worst.

### Component supply
Pi 5 has been in supply shortage twice since 2024. If it happens again, we have qualified Orange Pi 5 Plus (RK3588) as drop-in alternative — same software stack, similar performance, priced equivalent.

### Hallucinations
Yes, AI models hallucinate. Our solver runs **physical constraint checking** on every plan it generates — currents, voltages, package compatibility. If the math doesn't work, the plan doesn't ship. If we can't constrain a domain (e.g., medical), we mark it as **reference only** and route the user to the curated source.

### Delivery delays
Most Kickstarter hardware delivers 6-18 months late. We've baked this into our timeline and we've capped the first batch at 350 units total. We will not over-promise volume we can't deliver.

### Legal / regulatory
The KB contains material derived from CC, public-domain, and grey-area sources. We're consulting EU and US right-to-repair counsel. The product is sold as a knowledge **reference tool** — not a substitute for licensed professionals (medical, electrical, legal).

### What if I disappear / the company dies
The CODEX format is open. The runtime is open-source. If we go under, **everything you bought keeps working** — no server check-ins, no DRM, no expiring licenses. That's the whole point.

---

## WHO'S BUILDING THIS

[Founder bio — to be filled]

A team of 1. Augmented by Claude/GPT for boilerplate and research. *(Real founder bio — verifiable hardware + software background — to be filled in before public launch.)* Why one person? Because focus beats team-size, and because every dollar we don't spend on payroll is a dollar that goes into the product you receive.

---

## OPEN-SOURCE COMMITMENTS

- **Hardware design files** (KiCad, STL) — released under CERN-OHL after first shipping batch
- **Firmware** — MIT
- **Solver runtime** — Apache 2.0
- **CODEX schema** — CC0 (so others can build compatible KBs)
- **CODEX content** — mixed (some CC, some sourced — we publish provenance for every record)

We're not building a walled garden. We're building the seed of an ecosystem.

---

## FAQ (top 12)

**Q: Is this just an offline ChatGPT?**
A: No. ChatGPT is a general-purpose conversation. ARK is a specialized solver with a curated knowledge graph, constrained generation, and the ability to source components from your physical inventory. Try asking ChatGPT "I have these 10 broken devices, build me an irrigation system" — you'll get something plausible-looking that doesn't actually work. ARK gives you something that does.

**Q: How big is the AI model? Will it fit on this hardware?**
A: 14 billion parameters, 4-bit quantized — about 9 GB. Runs at 5-10 tokens/sec on Pi 5. Small enough to be portable, big enough to be smart.

**Q: Can I update the knowledge base?**
A: Yes. Three ways: (1) USB/SD card from us, monthly KB deltas; (2) Wi-Fi when you have it, optional pull; (3) mesh network from another ARK that's been updated.

**Q: What if I'm not technical?**
A: ARK has three "user modes" — Beginner explains every step like you've never held a soldering iron. Tinkerer assumes basic competence. Engineer is terse and assumes you know your Ohms.

**Q: Languages?**
A: Ships in English. v2 adds Russian, German, Spanish, Italian, French — running through the local model, no cloud.

**Q: Is this just for "doomers"?**
A: No. Most of our customers will probably be homesteaders, off-grid families, journalists, NGO staff, expedition crews, sailors, and anyone who's ever had to fix something far from a hardware store. Every-Tuesday utility for people who already build, fix, and grow things themselves.

**Q: Can ARK help me build weapons?**
A: No. Our CODEX is curated to exclude weapons and surveillance-against-people content. We have a hard line.

**Q: What about medical advice?**
A: ARK includes Hesperian's Where There Is No Doctor, WHO field guides, and US Army medical FMs as **reference**. It will tell you the same things those manuals tell you. It won't pretend to be a doctor.

**Q: What's the warranty?**
A: 2 years parts and labor. If a component fails, we'll send a replacement.

**Q: What happens if I drop it?**
A: Pelican 1450 case is rated IP67 — drop it, soak it, freeze it. Internals are shock-mounted. The screen is e-ink (no backlight to break). It's designed to survive a journey, not a single calm afternoon.

**Q: Can I see the source?**
A: Software repos open at funding goal. Hardware files open after first ship. Sign up at ark.computer for early access.

**Q: Why backing instead of waiting for retail?**
A: Lower price (early bird saves $300+). First batch numbered serial. Lifetime KB updates included for backers (retail is annual sub for major updates after year 2).

---

## STRETCH GOALS

| Goal | Unlocked |
|---|---|
| $50k | Funded — production starts |
| $100k | Add 5 000 more devices to teardown KB |
| $200k | Russian + German localization at launch |
| $300k | Vision inventory (point camera at shelf, ARK identifies devices) |
| $500k | Mesh federation v1 (cross-device KB sync) |
| $750k | Open-source the production tooling so anyone can manufacture compatible units |
| $1M | Permanent grant fund for community KB contributions |

---

## THE PITCH IN ONE SENTENCE

**Knowledge dies in the cloud. ARK keeps it in your hand.**

---

*[Reward graphics, FAQ video, team photos, demo loop — to be added during pre-launch]*
