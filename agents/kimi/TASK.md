# KIMI — TASK ASSIGNMENT

> **Адресат:** Kimi K2 через подписку Allegretto на kimi.com. Запускается через рабочий стол `Kimi CLI`. Working dir: `/home/user/aisurvive/`.
>
> **Роль:** master curator. Top-quality records которые нельзя получить через bulk batch.
>
> **Единица успеха:** 200-300 записей **исключительного качества** уровня ARRL Handbook / Forrest Mims notebooks. Не объём — глубина.

---

## 1. Что НЕ твоя задача

Не пытайся сделать 80,000 records. У DeepSeek (через OpenRouter) другая task — bulk generation. Ты делаешь то что DeepSeek дешёвый не вытянет качественно.

Не извлекай данные из iFixit guides — это работа DeepSeek extractor. Ты пишешь from-scratch.

Не пиши production code (server, vision, packaging) — это Claude task.

Не делай review-gate с 5 records → ждать → 5 records. Ты можешь работать **порциями по 20-50 records**, потом пользователь ревьюит. Внутри одной такой порции — full output.

---

## 2. Что твоя задача

### Tier 1 — Firmware-genome configurators (топ-30 fwgen templates)

Это **killer feature** ARK — solver авто-генерирует working Configuration.h / printer.cfg / device.yaml под user's specific hardware.

Подробная спецификация в `agents/kimi/briefs/KIMI-FIRMWARE-GENOME.md` PART 3. Прочитай его полностью.

**Объём:** 30 fwgen templates × 1-2 hours each = 30-60 hours work.

**Список:**
1. fwgen:marlin-2x → Configuration.h + Configuration_adv.h + platformio.ini (priority 1)
2. fwgen:klipper → printer.cfg + mcu.cfg (priority 1)
3. fwgen:openwrt → /etc/config/wireless + network + dhcp (priority 1)
4. fwgen:tasmota → Web UI export JSON (priority 1)
5. fwgen:esphome → device.yaml (priority 1)
6. fwgen:meshtastic → device.yaml + region.yaml (priority 1)
7. fwgen:betaflight → CLI dump
8. fwgen:inav → CLI dump
9. fwgen:ardupilot → Parameters file
10. fwgen:px4 → params YAML
11. fwgen:vesc → vesc_config.xml
12. fwgen:odrive → odrive_config.json
13. fwgen:wled → cfg.json
14. fwgen:retroarch → retroarch.cfg
15. fwgen:openipc → system.bin config
16. fwgen:grbl → config.h (compile-time)
17. fwgen:openevse → wifi.json
18. fwgen:diy-bms → user_config.h
19. fwgen:tasmota-irhvac (sub-feature) → IR codes config
20. fwgen:tasmota-zigbee → zigbee config
21. fwgen:openplotter (marine) → boat configs
22. fwgen:reach-rs (RTK GPS) → params
23. fwgen:digitspider (security cam) → config
24. fwgen:libreelec → kodi config
25. fwgen:dietpi → automation script
26. fwgen:armbian → board-tweaks
27. fwgen:teensy-audio → DSP config
28. fwgen:vesc-firmware-bldc-tool → motor config
29. fwgen:openocd → debug config
30. fwgen:platformio → custom board config

**Каждая запись:**
- JSON по `FirmwareConfigGenerator` schema (см. KIMI-FIRMWARE-GENOME.md PART 4)
- Полный Jinja2 template (200-500 lines content)
- Полный `user_input_schema` (JSON Schema)
- 2-3 testing examples (input → expected output hash)
- Cross-link к существующему `fwo:` record
- Provenance с git commit hash upstream repo

**Where to write:** `kb/output/firmware-genome/fwgen/fwgen_<id>.json`

### Tier 2 — Soviet/PostSoviet pack (300 records — наш unique moat)

Никто из конкурентов не имеет structured KB по советской технике. **Это наш moat в RU/CIS market**.

**Объём:** 300 records (100 devices + 100 projects + 100 components)

**Девайсы (100):**
- Телевизоры: Рубин-714, Электрон-451Д, Юность-Ц404, Радуга-715
- Магнитофоны: Маяк-203, Электроника-302, Юпитер-203, Олимп-005, Ростов-101
- Радиоприёмники: ВЭФ-202 (готов в seed), Океан-209, Спидола-230, Альпинист-321, Селена B-216, Меридиан-235
- Осциллографы: С1-67, С1-94, С1-102, С1-65А
- Измерительная техника: Ц43, Ц4315, В7-26, В3-38, Ч3-66, Г4-102
- Станки и автоматика: МПК-1, СПУ-100, ЭВМ Электроника-60
- Бытовая: ЗИЛ-Москва (холодильники), Вязьма (стиральные), Чайка (швейные с электроникой)
- Связь: радиостанция Лен-В, военная Р-105

**Проекты (100) — restoration + modernization рецепты:**
- Замена УНЧ ламповых на полупроводниковые с сохранением звука
- Цифровая модернизация аналоговых стендов
- Восстановление магнитофонных лентопротяжек
- Conversion советских осциллографов в цифровые scope-as-DAQ
- Использование МПК-1 как современного PLC
- Самосборные ИБП на советских ферритовых сердечниках
- Восстановление ЭЛТ-мониторов после высыхания электролитов
- Перевод вентиляторных систем СССР на ШИМ-управление через ESP32

**Компоненты (100) — советские → западные эквиваленты:**
- Транзисторы: КТ315, КТ3107, КТ502, КТ503, КТ602, КТ805, КТ818, КТ819 (есть seed для KT315)
- Микросхемы: К140УД6 (LM741), К140УД7, К155ЛА3 (7400), К155ЛА4, К561ИЕ8 (CD4017), К561ЛА7 (CD4011)
- Лампы: 6П3С (6L6), 6Н2П (12AX7), 6Ж1П (6CB6), 6Н3П (12AX7-substitute), 6П14П (EL84 — done), Г807, ГУ-50
- Диоды: Д9 (1N34A), Д18, Д814, Д226, КД105, КД201
- Конденсаторы: К50-3, К50-6, К50-16, КМ-5, КМ-6, бумажные МБМ
- Стабилитроны: Д814А-Д, КС147

**Где писать:** `kb/output/packs/pack-soviet/<devices|projects|components>/`

**Источники:** Старые «Радио» 1960-2000, «Радиолюбитель», «Моделист-конструктор», справочники «Транзисторы для бытовой аппаратуры», «Микросхемы серии К155», vrtp.ru forum threads.

### Tier 3 — Safety database deep (200 hazard profiles)

Уже есть 5 в seed (`b4-safety/`). Расширь до 200 по mega-brief Section 11 Tier A структуре.

**Объём:** 200 hazard profiles × ~30 min each = 100 hours.

Каждый профиль уровня `haz:hv-capacitor-microwave.json` — с реальными OSHA/NFPA/EU/RU regulatory references, real fatality stats, common misconceptions debunked.

**Где писать:** `kb/output/extracted/safety/`

### Tier 4 — Killer demo scenarios (20 end-to-end examples)

Это для виральности. Каждый scenario — полный flow юзер-input → ARK output:

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

**Список 20 сценариев** см. в KIMI-MEGA-BRIEF.md или предложи свои на основе ARK use cases (3D-printer from broken Voron parts, wind generator from microwave magnets, IV from aquarium tubing, etc).

**Где писать:** `kb/output/extracted/demo-scenarios/`

---

## 3. Quality bar

Каждая запись должна пройти все следующие gates:

✅ Schema validation через CDPO Pydantic (см. `kb/pipeline/schemas/cdpo.py`)
✅ Никаких generic placeholders ("remove screws", "internal", "consult professional", "see datasheet" — auto-reject)
✅ Numeric specs реальные (не "high voltage" → "~2100V DC", не "large capacitor" → "1.0-1.2µF, 2.1kV rated")
✅ Provenance с реальным source citation
✅ Cross-references к существующим ARK entities резолвятся
✅ Минимальная длина soблюдена per type (см. mega-brief Section 8.2)
✅ Real engineering — не Wikipedia summary

---

## 4. Process

1. Прочитай `agents/kimi/briefs/KIMI-MEGA-BRIEF.md` end-to-end (если ещё не читал).
2. Прочитай `agents/kimi/briefs/KIMI-FIRMWARE-GENOME.md` end-to-end.
3. Прочитай `kb/pipeline/schemas/cdpo.py` (data model — обязательно).
4. Read `kb/STRATEGY.md` (output paths + storage strategy).
5. Начни с **Tier 1 / Firmware Genome** — это самое импактфул для product.
6. После каждых 20-50 records — пиши progress в `agents/kimi/PROGRESS.jsonl` (one line JSON per batch с timestamp + count + categories).
7. Если упираешься в weekly subscription limit — сохрани WIP в `kb/output-wip/` и выйди gracefully.
8. Когда хочешь продолжить после паузы — `cat agents/kimi/PROGRESS.jsonl` чтобы понять где остановился.

---

## 5. Что НЕ работать (forbidden)

- ❌ Не работай в `kb/output/extracted/devices/` или `extracted/projects/` — это территория DeepSeek для bulk extraction
- ❌ Не пиши production code (server, vision, validation scripts) — это Claude task
- ❌ Не реорганизовывай папки проекта — это уже сделано
- ❌ Не модифицируй CDPO schema без согласования — она используется всеми агентами
- ❌ Не выходи за in-scope topics из PRD §4: power/water/food/comms/perimeter/repair/tools/medical-reference/salvage. Engineering content with safety warnings, not corporate-speak deflection.
- ✅ Hard limits из PRD §4 соблюдай: weapons / drug-synthesis / unlicensed-RF / lockpicking / surveillance / anything illegal in user jurisdiction

---

## 6. Что ты получаешь

**Каждая записанная запись прямо повышает revenue потенциал ARK.**

- Firmware-genome configurators → каждый = $49 premium content pack value
- Soviet pack → $49 standalone product, ~1000 RU/CIS users готовы платить
- Safety DB → legal protection + customer trust
- Demo scenarios → виральный материал для Twitter/HN

**Цель Kimi:** к моменту launch (D+30) выдать ~300 records которые solver использует для killer-demo flow + premium content pack groundwork.

---

## 7. Start

Begin Tier 1 с fwgen:marlin-2x. Сделай **полный** template (~500 lines Jinja2) с обоими Configuration.h и Configuration_adv.h. Включи 3 test examples с реальными user_inputs.

Не показывай мне sample прежде full template. Generate full. Save. Move to fwgen:klipper. Repeat.

Поехали.
