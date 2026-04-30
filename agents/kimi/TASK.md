# Kimi — Task assignment

> **Recipient** — Kimi K2 (subscription tier).
> **Working dir** — repository root.
> **Role** — master curator. Top-quality records that can't be produced via bulk batch.
> **Success metric** — 200–300 records of *exceptional* quality (Forrest Mims notebook level). Depth, not volume.

---

## 1. Out of scope

- Don't try to generate 80,000 records. DeepSeek handles bulk. Kimi handles what bulk can't deliver well.
- Don't extract from iFixit guides — that's the DeepSeek extractor's job. Kimi writes from scratch.
- Don't write production code (server, vision, packaging) — that's Claude's track.
- Don't review-gate with 5-record samples. Work in batches of 20–50; the user reviews afterwards.

## 2. In scope

### Tier 1 — Firmware-genome configurators (top-30 templates)

The killer feature: ARC auto-generates a working `Configuration.h` / `printer.cfg` / `device.yaml` for the user's specific hardware.

**Volume:** 30 firmware-generator templates × 1–2 hours each.

**Targets** (priority 1 marked):
1. `fwgen:marlin-2x` — `Configuration.h` + `Configuration_adv.h` + `platformio.ini` *(p1)*
2. `fwgen:klipper` — `printer.cfg` + `mcu.cfg` *(p1)*
3. `fwgen:openwrt` — wireless / network / dhcp *(p1)*
4. `fwgen:tasmota` — Web UI export JSON *(p1)*
5. `fwgen:esphome` — `device.yaml` *(p1)*
6. `fwgen:meshtastic` — `device.yaml` + `region.yaml` *(p1)*
7. `fwgen:betaflight` — CLI dump
8. `fwgen:inav` — CLI dump
9. `fwgen:ardupilot` — parameters file
10. `fwgen:px4` — params YAML
11. `fwgen:vesc` — `vesc_config.xml`
12. `fwgen:odrive` — `odrive_config.json`
13. `fwgen:wled` — `cfg.json`
14. `fwgen:retroarch` — `retroarch.cfg`
15. `fwgen:openipc` — `system.bin` config
16. `fwgen:grbl` — `config.h` (compile-time)
17. `fwgen:openevse` — `wifi.json`
18. `fwgen:diy-bms` — `user_config.h`
19. `fwgen:tasmota-irhvac` — IR codes config
20. `fwgen:tasmota-zigbee` — zigbee config
21. `fwgen:openplotter` (marine) — boat configs
22. `fwgen:reach-rs` (RTK GPS) — params
23. `fwgen:libreelec` — kodi config
24. `fwgen:dietpi` — automation script
25. `fwgen:armbian` — board tweaks
26. `fwgen:teensy-audio` — DSP config
27. `fwgen:platformio` — custom board config

**Each record contains:**
- JSON conforming to the `FirmwareConfigGenerator` schema
- Full Jinja2 template (200–500 lines of content)
- Full `user_input_schema` (JSON Schema)
- 2–3 testing examples (input → expected output hash)
- Cross-link to an existing `fwo:` record
- Provenance with upstream-repo git commit hash

**Output location:** `kb/output/firmware-genome/fwgen/fwgen_<id>.json`

### Tier 2 — Regional content packs (300 records)

Region-specific equipment, naming, and substitution chains for places where the global iFixit / Hackaday corpus is sparse — coastal hardware, regional manufacturer codes, local brand part numbers, climate-specific failure modes.

**Volume:** 300 records (100 devices + 100 projects + 100 components).

**Output location:** `kb/output/packs/<region>/<devices|projects|components>/`

### Tier 3 — Safety database (200 hazard profiles)

Five seed records exist (`b4-safety/`). Expand to 200 along the structure used in those seeds — real OSHA/NFPA/EU regulatory references, real fatality statistics, common misconceptions debunked.

**Volume:** 200 hazard profiles × ~30 min each.

**Output location:** `kb/output/extracted/safety/`

### Tier 4 — Demo scenarios (20 end-to-end examples)

Each scenario is a complete user-input → ARC-output pair, used for the launch demo and as solver evaluation harness.

```yaml
- id: scenario:irrigation-from-printers
  title: "10-zone irrigation from 3 broken HP printers"
  user_inventory: [...]
  user_goal: "Build 10-zone irrigation"
  expected_output:
    bom: [...] (with sourcing per donor)
    teardown_checklist: {donor: steps}
    schematic_ascii: <full schematic>
    firmware_code: <complete .ino>
    calibration: [steps]
    safety_warnings: [...]
```

**Output location:** `kb/output/extracted/demo-scenarios/`

## 3. Quality bar

Every record passes all of these gates:

- ✅ Schema validation against CDPO Pydantic models (`kb/pipeline/schemas/cdpo.py`)
- ✅ No generic placeholders ("remove screws", "internal", "consult professional", "see datasheet" → auto-reject)
- ✅ Numeric specs are concrete (not "high voltage" → "~2,100 V DC"; not "large capacitor" → "1.0–1.2 µF, 2.1 kV rated")
- ✅ Provenance with a real source citation
- ✅ Cross-references to existing entities resolve
- ✅ Minimum length per record type met
- ✅ Real engineering content — not a Wikipedia summary

## 4. Process

1. Read `kb/pipeline/schemas/cdpo.py` (data model — required)
2. Read `kb/STRATEGY.md` (output paths and storage strategy)
3. Start with **Tier 1 / Firmware Genome** — highest impact for the product
4. After each batch of 20–50 records, write progress to `agents/kimi/PROGRESS.jsonl` (one JSON line per batch with timestamp + count + categories)
5. If you hit a weekly subscription limit, save WIP under `kb/output-wip/` and exit gracefully
6. To resume after a pause, read `agents/kimi/PROGRESS.jsonl` to see where you stopped

## 5. Forbidden behaviours

- ❌ Don't write to `kb/output/extracted/devices/` or `extracted/projects/` — that's DeepSeek's territory
- ❌ Don't write production code (server, vision, validation scripts) — Claude's track
- ❌ Don't reorganise project folders — already finalised
- ❌ Don't modify the CDPO schema without coordination — it's used by all agents
- ❌ Don't go outside the in-scope topics in PRD §4 (power / water / food / comms / perimeter non-lethal / repair / tools / medical-reference / salvage)
- ✅ Hard limits in PRD §4 are strict: weapons, drug synthesis, unlicensed RF transmission, lockpicking, surveillance, anything illegal in the user's jurisdiction

## 6. Why this matters

Each curated record directly increases the value of the premium-content layer:

- Firmware-genome configurators → each one underpins a $49 content pack
- Regional packs → standalone $49 product, regional users willing to pay
- Safety database → legal protection + customer trust
- Demo scenarios → launch-day demo material

**Goal:** by the v0.1 launch, deliver ~300 records that the solver actively uses for the headline demo flow plus the premium-content groundwork.

## 7. Start

Begin Tier 1 with `fwgen:marlin-2x`. Produce the **full** template (~500 lines of Jinja2) covering both `Configuration.h` and `Configuration_adv.h`. Include three test examples with realistic `user_input` payloads.

Don't show samples before completing the full template. Generate full → save → move to `fwgen:klipper` → repeat.
