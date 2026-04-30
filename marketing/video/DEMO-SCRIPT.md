# Demo Video Script — 60s Hero + 90s Extended

> The single most important asset in the whole launch. Everything hinges on this 60 seconds. Shoot in one day, edit in one day. Budget: $500-1500 total (DOP day rate + props).

## Visual style guide

- **Lighting**: dim warm key + cool fill (workshop / garage at dusk feel)
- **Color grade**: matte, slightly desaturated, deep blacks. Reference: Blade Runner 2049 garage scenes / Fallout New Vegas color palette
- **Sound**: hum of single fluorescent + distant generator + occasional drip. Music starts at :15, builds to :45, drops at :55.
- **Pacing**: 1.5-2 second cuts in first 15 sec (hook), then 3-4 sec cuts (showcase), back to 1 sec (CTA)
- **Aspect**: 9:16 vertical primary (TikTok/Reels/X), 16:9 secondary (YouTube/landing)

---

## 60-SECOND HERO — shot list

```
[00:00–00:03] HOOK
  CU on hands holding a brick of melted electronics, ash, broken plastic
  V/O whisper: "When the internet dies..."
  CUT to slate: "When the internet dies."
  
[00:03–00:08] PROBLEM
  Wide: cluttered workshop, late dusk, flickering fluorescent
  Hands placing 4-5 broken devices on a workbench: HP printer, microwave, dead laptop, monitor, ATX PSU
  V/O: "...everyone with a question becomes a person without an answer."
  
[00:08–00:14] PRODUCT REVEAL
  Macro: ARK device on the bench, e-ink screen comes alive, copper-mesh on case glints
  Hand types on attached keyboard:
  > "I have 10 broken HP printers, a microwave, an old monitor.
  >  Build me a 10-zone irrigation system."
  
[00:14–00:25] THE MAGIC HAPPENS
  Quick cuts (1 sec each):
    - "Generating reverse BOM..." progress bar on e-ink
    - List populates: "Solenoid × 10 (printers), 12V PSU (ATX), MCU (router)..."
    - Schematic draws itself stroke by stroke (svg animation)
    - Firmware code scrolls in green-on-black terminal style
    - "Plan generated. 14 steps. 6 hours. ⚠ HV warning on ATX teardown."
  
[00:25–00:40] BUILD MONTAGE
  Hands actually doing it:
    - Screwdriver in printer (PH1 unscrew)
    - Soldering iron meeting joint, smoke curl
    - Magnifying glass on schematic on phone
    - Plugging in valves
    - Soil sensor pushed into pot
  V/O calmer, deeper: "The knowledge isn't gone. It's just not in the cloud anymore."
  
[00:40–00:50] PAYOFF
  Wide: same garden, three weeks later, daylight
  Drip emitters pulse, water beads on tomato leaves
  Pull back: ARK on stump, e-ink shows "Zone 3 — 72%, watering 18s"
  Solar panel folded next to it, swallow lands on antenna
  
[00:50–00:58] CTA
  Black screen
  Type appears: "ARK"
  Below: "When the internet dies, this remembers."
  Below: "ark.computer · Kickstarter in 3 weeks"
  
[00:58–01:00] LOGO STING
  Triangular △ ARK mark, single warm pulse, cut to black
```

### V/O script verbatim (under 60 words for 60 seconds)

> "When the internet dies — *(beat)* — everyone with a question becomes a person without an answer.
>
> I built a computer that remembers when nothing else can.
>
> Show it what you have. It tells you what you can build.
>
> The knowledge isn't gone. It's just not in the cloud anymore.
>
> *(beat)*
>
> ARK. When the internet dies, this remembers."

### V/O direction notes
- Voice: low, dry, faintly tired. Not hype. Not announcer. Think Werner Herzog meets a midnight ham radio op.
- Mic: SM7B or Sennheiser MKH 416 close. No reverb. Slight warmth, no compression artefacts.
- Russian-accented English is fine — adds founder authenticity. Don't fake American.

---

## 90-SECOND EXTENDED CUT (for landing page above-the-fold)

Same opening through 0:25, then expand "build" section to 30 sec with:

- B-roll of 3 different inputs producing 3 different outputs:
  - Input: "Charge phones from car alternator." Output: schematic + 5 components needed.
  - Input: "Filter water for 4 people for a week." Output: ceramic + UV stack.
  - Input: "AM radio receiver from RAM stick capacitors." Output: 12-step build.
- Show each working at the end (LED on phone, water dripping clear, voice through speaker)
- Closing CTA same as 60s

---

## B-ROLL shot list (capture day)

Bring back-up of 3x everything; you only have one day on set.

| # | Shot | Duration | Notes |
|---|---|---|---|
| 1 | Hands placing devices on bench (slow) | 4s | rehearsed, 3 takes |
| 2 | Macro keyboard typing | 3s | aim for keystroke sound |
| 3 | E-ink screen text appearing | 6s | screen recording then phys composite |
| 4 | Schematic draw animation | 4s | post — SVG stroke-on |
| 5 | Code scrolling in terminal | 3s | real Arduino IDE shot |
| 6 | Soldering iron + smoke curl | 2s | actual joint, with rosin smoke |
| 7 | Drip emitter + tomato | 3s | shoot ahead, 2 weeks before |
| 8 | Solar panel deploy | 4s | golden hour |
| 9 | ARK on stump w/ swallow | 3s | shoot multiple, hope one works |
| 10 | Logo sting | 2s | post-only |

---

## Music license

Three options:
1. **Original score** — $300-500 from Fiverr / Soundbetter for a custom 60s ambient cue. Best.
2. **Epidemic Sound subscription** ($15/mo) — search "patient", "ambient melancholy", "post-rock dawn"
3. **CC0 / public domain** — bensound.com, freemusicarchive — risks looking generic

Recommend (1). One cue, used in all derivatives.

---

## Distribution plan (D-day video drops)

| Channel | Format | Caption |
|---|---|---|
| X / Twitter | 60s MP4 vertical, 16:9 backup | Pinned to thread tweet 1 |
| Instagram Reels | 60s 9:16 | Cross-post, no link in caption (link in bio) |
| TikTok | 60s 9:16 | Drop 12h after Twitter to let momentum build |
| YouTube Shorts | 60s 9:16 | + full 90s as regular video |
| Hackaday tip | Email with 90s link | Subject: "Offline AI computer for reverse-engineering broken electronics" |
| Landing page hero | 90s 16:9 with subtitles ON | Auto-play muted, click for audio |
| Kickstarter video | 2-3 min cut combining demo + founder talk | Build during pre-launch period |

---

## Risk: what if the demo doesn't actually work?

Two layers of safety:

1. **Pre-rehearse the exact prompt** in the demo. Don't ad-lib. Solver outputs are deterministic given seed; lock the seed for the take.
2. **B-roll backup**: shoot a second, simpler scenario in case the irrigation one is too ambitious to credibly complete in 30 days. Backup = "charge phone from broken car alternator" (3 components, schematic in 1 page).

If solver outputs something nonsensical on the day of shoot — **don't fake it**. Reshoot prompt. We'd rather delay the launch a week than ship a video where techies can spot a fabricated demo. The whole brand is built on "this actually works."

---

## Don't

- ❌ Don't put a person's face in the first 5 seconds — drops retention
- ❌ Don't show the LLM thinking spinner for more than 2 sec
- ❌ Don't let any hallucination slip into the demo (cross-check every component name against KB before final cut)
- ❌ Don't use AI-generated voiceover. Real human voice = founder credibility.
- ❌ Don't use stock music people will recognize from a Squarespace ad
- ❌ Don't shoot at home unless your home looks intentional. Rent a workshop / film studio for $200/day.
