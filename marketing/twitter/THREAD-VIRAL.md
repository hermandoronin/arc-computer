# Twitter / X — Viral launch thread

**Strategy:** drop on Tuesday 9am ET (highest tech-Twitter engagement). Pin demo video to thread. Reply to first 50 commenters within 2 hours.

**Target metrics:**
- Thread: 1M impressions, 50k engagements
- Landing CTR: ≥5%
- Email collect: 1500-3000 in 48h

---

## Thread (12 tweets, copy-paste ready)

---

**1/ HOOK** *(this is the only one that matters — make or break)*

> I built an AI computer that turns broken electronics into working tools.
>
> No internet. No cloud. Solar-powered.
>
> Watch it tell me how to build a 10-zone irrigation system out of old printers I had in my garage 👇
>
> [60-sec demo video]

---

**2/ THE PROBLEM**

> Every "AI for hardware" tool tells you what to BUY.
>
> ChatGPT will hallucinate parts that don't exist.
> Wikipedia is offline-capable but doesn't reason.
> Your old electrical engineering books don't fit in a backpack.
>
> Nothing tells you what you can BUILD from what you ALREADY HAVE.

---

**3/ WHAT IT IS**

> ARK is a portable, off-grid AI computer with a 50,000-entry knowledge graph of electronics teardowns, medical references, survival manuals, and verified DIY projects.
>
> You describe what you have. It tells you what to build, step by step.
>
> [Photo: device on workbench, e-ink screen lit]

---

**4/ HOW IT WORKS — REVERSE BOM**

> Traditional design: idea → bill of materials → buy parts.
>
> ARK: inventory → reverse BOM → which donor device contains the part you need → teardown plan → assembly → firmware → calibration.
>
> It's the inverse of every "AI hardware" tool. Nobody else does this.

---

**5/ DEMO — the real flow**

> Input: "I have 10 broken HP printers, a microwave, and an old laptop. Build me a 10-zone irrigation system."
>
> Output:
> • BOM with sources from your specific devices
> • Teardown checklist per donor
> • Wiring schematic
> • Pre-compiled firmware (Arduino-ready)
> • Soil-sensor calibration steps
>
> [Screenshot of solver output]

---

**6/ THE TRICK — constrained generation**

> AI hallucinations kill projects. ARK can't recommend a part that doesn't exist in its knowledge graph or your inventory.
>
> Every plan goes through a physics check: voltages, currents, package compatibility. If the math doesn't work, the plan doesn't ship.
>
> [diagram: solver pipeline]

---

**7/ THE HARDWARE**

> • Raspberry Pi 5 8GB + 1TB NVMe
> • 7.5" e-ink (sunlight-readable, 0.4W idle)
> • LiFePO4 30Ah + 50W solar = weeks of standby, 18-24h active
> • LoRa mesh + GPS + optional SDR
> • Pelican 1450 case, copper-mesh Faraday lining
>
> Spec'd for the worst Tuesday of your life.

---

**8/ THE KNOWLEDGE BASE**

> 50,000 entries. Not Wikipedia. Curated and structured:
>
> • 5,000 devices with full teardowns (iFixit + manual curation)
> • 50,000 components with datasheets
> • 5,000 verified DIY projects
> • Full Hesperian medical library
> • US Army field manuals (engineering, signal, medical)
> • Survivor Library, decades of Soviet *Radio* magazine
>
> All compressed to 25 GB.

---

**9/ WHO IT'S FOR**

> Realistically?
>
> ✅ Off-grid families
> ✅ Homesteaders
> ✅ Sailors & overlanders
> ✅ Field journalists, NGO staff, expedition crews
> ✅ Anyone who's had to fix something far from a hardware store
>
> Every-Tuesday utility for people who already build, fix, and grow things themselves.

---

**10/ WHAT IT WON'T DO**

> ARK has hard guardrails:
>
> ❌ No weapons
> ❌ No surveillance against people
> ❌ No medical diagnosis (reference only — points you to verified sources)
>
> If we can't bound a domain, we route to curated reference instead of generating.

---

**11/ OPEN-SOURCE COMMITMENT**

> Hardware design files: open after first ship (CERN-OHL)
> Firmware: MIT
> Solver runtime: Apache 2.0
> CODEX schema: CC0
>
> If we go under, your device keeps working. No DRM, no server check-ins, no expiring licenses.

---

**12/ HOW TO BACK**

> Kickstarter launches in 3 weeks. Early-bird tiers ($899 DIY kit / $1499 assembled) capped at 100 units each.
>
> Sign up at ark.computer to get 24h pre-launch access + a $50 backer credit.
>
> RT this thread = real help. We're solo-founder + AI copilot. No marketing budget. Just a workbench and a working prototype.
>
> [Landing link]

---

## Reply templates for common comments

| Comment type | Reply |
|---|---|
| «It's just ChatGPT in a box» | "Try asking ChatGPT 'I have these 10 broken devices, build me an irrigation system'. You'll get something plausible-looking that doesn't physically work. ARK has a constraint solver and a curated KB. The demo isn't faked — happy to do a livestream." |
| «How big is the model» | "Qwen 2.5 14B Q4 — 9 GB on disk, ~10 GB RAM in use, 5-10 tokens/sec on Pi 5. Vision model 5 GB additional." |
| «What's actually in the KB» | "Top-5000 curated devices, 50k canonical components from KiCad+Wikidata, 5k verified projects. Full sourcing list at ark.computer/sources." |
| «Pi 5 isn't fast enough» | "It's enough for 14B Q4 at 5-10 t/s. We benchmark on every batch. If we need to upgrade, RK3588 (Orange Pi 5+) is the qualified alternative — same software stack." |
| «Hallucinations» | "Constrained to KB whitelist + post-gen physics check. Hallucinated parts can't pass the solver. Detail thread soon." |
| «How is this not a scam» | "Working prototype demo'd in pinned tweet. Hardware fully open-source post-ship. Zero pre-orders before working firmware. Founder bio at arc.computer/about." |
| «$1500 too expensive» | "BOM is ~$650, manual assembly + curated KB + 2yr warranty. Compare: PrepperDisk $300-500 (no AI, no solver), commercial alternatives don't exist. Open-source DIY path = $899 kit (or $149 just-the-KB for your own SBC)." |

---

## Pre-launch outreach list

| Channel | Handle | Note |
|---|---|---|
| Hackaday | tip@hackaday.com + Brian Benchoff | Send demo video + repro instructions |
| Hackernews | self-submit Tuesday morning | Title: "Show HN: ARK — offline AI that turns broken electronics into tools" |
| Lex Fridman | DM after thread hits 100k | Long-form pitch |
| Marques Brownlee | low priority — too consumer |
| The Hated One | survival-tech YouTube |
| Reddit r/preppers | crosspost demo + thread |
| Reddit r/homestead | crosspost — angle: gardening automation |
| Reddit r/selfhosted | angle: offline AI |
| Reddit r/raspberry_pi | angle: cool Pi build |
| Reddit r/LocalLLaMA | angle: 14B on edge |
| Mastodon — fediverse hardware folk |
| BigClive | Reach for review unit (his audience = ours) |
| EEVblog forum | Post in chat, not as ad |

---

## Don't do

- ❌ Don't post on Monday (low engagement)
- ❌ Don't include all 12 tweets at once — drip if engagement stalls past tweet 3
- ❌ Don't engage trolls. Reply to genuine technical questions.
- ❌ Don't promise dates you'll miss — say "weeks" not "by Tuesday"
- ❌ Don't drop the demo video unless your landing page is live and email collect works
- ❌ Don't tag big accounts — looks desperate
