# KIMI BRIEF — FIRMWARE GENOME PROJECT (FGP)

> **Адресат:** Kimi Computer Agent с computer use, git access, file ops, code execution.
>
> **Цель:** Построить полный structured граф **всех значимых open-source прошивок** + **на какое железо ставятся** + **что умеют** + **готовые configurator templates** для ARK solver.
>
> **Финальный deliverable:** ~80-150 firmware-records + ~300-500 configurator templates, упакованные в `/mnt/output/ark-firmware-genome-v0.1.tar.zst` и интегрированные с основной ARK KB.
>
> **Время:** 2-3 недели в подписке Kimi.
>
> **Зачем это критично:** превращает ARK из chat-обёртки в **программируемый генератор работающих прошивок** для любого hardware-сетапа из salvaged компонентов. Конкуренты (NOMAD, PrepperDisk) этого не делают и не сделают — слишком кропотливо.

---

# PART 0 — ПОЧЕМУ ЭТО КРИТИЧНО

ARK без firmware-genome:
> Юзер: "У меня ATmega2560 + 5 stepper'ов + 2 thermistor'а + hotend + bed + endstop'ы. Хочу 3D-принтер."  
> ARK: "Используй Marlin firmware. Скачай с github.com/MarlinFirmware/Marlin. Настрой Configuration.h."

Это уровень **Stack Overflow** — не уникально, не цепляет, юзер сам разбирается.

ARK с firmware-genome:
> Юзер: тот же запрос  
> ARK: "Detected setup matches BOARD_RAMPS_14_EFB. Generated Marlin 2.1.2 Configuration.h специфический под твой сетап. Пины stepper'ов: X=A0/A1/A2, Y=A6/A7/A8, ... Thermistor type 1 (100k NTC). PID auto-tune values: P=22.2, I=1.08, D=114. Flash через Arduino IDE 2.x: select Mega2560, programmer AVRISP mkII, upload. Сгенерированный .hex прилагается."  
> Output: Configuration.h + Configuration_adv.h + платформенные настройки + готовый .hex + flash инструкции в 5 шагов.

Это **уровень профессиональной интеграции** который копировать = месяцы работы. Это **наш moat**.

Каждая open-source firmware = **умножитель**. Marlin поддерживает 100+ материнских плат → 100 working printer paths. OpenWRT поддерживает 1500+ роутеров → 1500 router-builds. Klipper, Tasmota, ArduPilot, Betaflight, ESPHome — каждая такая.

50 firmware-проектов × 50 hardware targets каждый = **2500 working build-paths** из ничего, кроме структурированной информации которая уже есть в open source.

---

# PART 1 — SCOPE: ВСЕ КАТЕГОРИИ FIRMWARE

Покрыть надо ~80-150 проектов в этих доменах:

## 1.1 3D-принтеры / CNC

- **Marlin 2.x** (AVR + ARM, broad hardware) ⭐ priority
- **Klipper** (Pi + STM32 host) ⭐ priority
- **RepRapFirmware** (Duet boards)
- **Smoothieware** (LPC1768)
- **GRBL** (AVR, CNC) ⭐ priority
- **GRBL HAL** (ARM-port)
- **bCNC** (Python host)
- **Repetier** (legacy AVR)
- **MK4duo**
- **Sailfish** (старый Makerbot fork)
- **Prusa-Firmware** (Prusa-specific Marlin fork)
- **Voron firmware presets** (Klipper)
- **TeensyDuino CNC** (Teensy boards)
- **MachineKit** (RT-Linux)
- **LinuxCNC** (PC-host CNC)
- **OpenPnP** (pick-and-place machines)

## 1.2 Роутеры / networking / mesh

- **OpenWRT** ⭐ priority — MIPS, ARM, x86 broad
- **DD-WRT** (broader hardware via fork)
- **LEDE** (fork OpenWRT, мерджнулся)
- **Tomato** (legacy Broadcom)
- **pfSense** (x86)
- **OPNsense** (fork pfSense)
- **VyOS** (CLI-routing)
- **TurrisOS** (Turris Omnia + Mox)
- **OpenWisp** (multi-router management)
- **Meshtastic** ⭐ priority — ESP32 + LoRa (mesh comms критично для нашего use case)
- **B.A.T.M.A.N. Advanced** (mesh routing protocol)
- **batman-adv** + **OLSR** (mesh routing)
- **HamWAN / AREDN** (HAM mesh)

## 1.3 IoT / smart-home / sensors

- **Tasmota** ⭐ priority — ESP8266/ESP32 (broad smart-home replacement)
- **ESPHome** ⭐ priority — ESP8266/ESP32 (Home Assistant integration)
- **WLED** — ESP32 LED strip controller
- **ESP-Easy** (older ESP firmware)
- **Espurna**
- **Sonoff DIY firmware**
- **OpenMQTTGateway** (universal IoT bridge)
- **Home Assistant Core** (host, not MCU but critical for IoT projects)
- **Frigate** (NVR + AI)
- **Mosquitto** (MQTT broker, embedded-friendly)
- **OpenHAB** (smart-home OS)
- **NodeMCU** (Lua firmware, ESP)

## 1.4 Polety / RC / drones

- **Betaflight** ⭐ priority — STM32F4/F7/H7 (FPV racing)
- **iNav** ⭐ priority — STM32 (long-range / autonomous)
- **EmuFlight**
- **Cleanflight** (legacy)
- **Baseflight** (legacy)
- **ArduPilot** ⭐ priority — ARM Pixhawk (autonomous, full-feature)
- **PX4** ⭐ priority — same target hardware
- **OpenTX / EdgeTX** (transmitter firmware)
- **CRSF / ELRS** (ExpressLRS for radio link)
- **DJI Naza-M** clones (legacy)

## 1.5 Радио / SDR / связь

- **Meshtastic** (см. выше)
- **OpenWSN** (mesh networks)
- **WSPR / FT8 firmwares** (HF digital modes)
- **T41 SDR transceiver firmware** (KiCad+software combo)
- **uBitx HF transceiver** (Arduino-based)
- **TJ-Sound HF SDR**
- **ChirpStack LoRaWAN gateway**
- **OpenLCD** (HamShield)
- **Gqrx** (host SDR app, не firmware но critical для radio projects)
- **DSDPlus** (digital decoder)
- **OpenSDR**
- **Codec2 firmwares** (low-bitrate digital voice)
- **FreeDV firmwares**
- **APRS firmwares** (Tracker, iGate, Digipeater)

## 1.6 Motor controllers / EV / e-bike

- **VESC** ⭐ priority — STM32F4 (BLDC controller)
- **ODrive** — STM32F4 (high-perf BLDC)
- **SmoothieBoard motor firmware**
- **MTPaint** (BMS)
- **DiyBMS** (lithium BMS)
- **Bafang BBSHD firmware** (e-bike motor)
- **TSDZ2 OSF** (open-source firmware for Tongsheng e-bike motor)

## 1.7 Locks / access / security

- **Flipper Zero firmwares** (Unleashed, RogueMaster, Xtreme)
- **Pwnagotchi** (security audit tool)
- **HackRF firmwares**
- **YubiKey clones / U2F-Zero** (HMAC OTP)
- **Iron Banker** (BLE lockpicking)

## 1.8 Test & measurement

- **Sigrok firmwares** (logic analyzers — fx2lafw, etc)
- **HantekDSO firmwares**
- **DSLogic firmware**
- **BusPirate firmware**
- **Saleae Logic Probe firmwares** (DIY clones)
- **OWON firmwares** (oscilloscopes hacked)

## 1.9 Cameras / video / imaging

- **CHDK** (Canon hack — broad camera coverage)
- **Magic Lantern** (Canon DSLR)
- **OpenIPC** ⭐ priority — IP cameras (HiSilicon Hi3516, Hi3518, Sigmastar SoCs)
- **MJPG-streamer** (Linux USB camera streaming)
- **ZoneMinder** (host NVR)
- **Frigate** (см. IoT)

## 1.10 Audio / DSP

- **Daisy seed** firmware projects (~50+ open synths)
- **Mod Devices firmwares**
- **Teensy Audio Library** projects
- **Pure Data embedded** (PDExt, libpd)
- **SuperCollider embedded**
- **Faust embedded**
- **Mozzi** (Arduino audio synth)

## 1.11 Game consoles / retro

- **libretro / RetroArch** ⭐ priority — multi-platform emulation
- **recalbox**
- **Lakka**
- **MiSTer FPGA** (FPGA cores for old hardware)
- **batocera**
- **EmuELEC**

## 1.12 Power / monitoring / energy

- **Solar charger firmwares** (multiple — Maximizer, Heliogen, OpenMPP)
- **DiyBMS** (см. motor controllers)
- **OpenInverter** (EV inverters)
- **OpenEVSE** (EV charging stations)
- **SmartEVSE**
- **VictronConnect alternatives** (open-source реверс)

## 1.13 Aerospace / experimental

- **KiwiSDR** (HF receiver)
- **FlightAware Dump1090** (ADS-B receiver)
- **OpenAvionics** projects

## 1.14 Embedded Linux distributions (мини)

- **Buildroot** (custom embedded Linux)
- **Yocto** (industrial)
- **DietPi** (Pi optimized)
- **Armbian** (single-board ARM)
- **postmarketOS** (phones)

## 1.15 Special category — OS-as-firmware для серверных платформ

- **CoreBoot** (BIOS replacement)
- **LinuxBIOS / Libreboot**
- **u-boot** (universal boot loader)
- **edk2** (UEFI reference)

---

# PART 2 — ИССЛЕДОВАНИЕ КАЖДОЙ ПРОШИВКИ

Для каждого firmware-проекта в Section 1 — выполни следующий research workflow:

## 2.1 Computer-agent шаги

```bash
# Шаг 1: Clone repo (depth=1 для скорости + размера)
mkdir -p /mnt/staging/firmware/<fwo_id>
cd /mnt/staging/firmware/<fwo_id>
git clone --depth 1 <upstream_url> source
cd source

# Шаг 2: Прочитай ключевые файлы
cat README.md README.rst README.org 2>/dev/null
ls docs/ 2>/dev/null && cat docs/*.md 2>/dev/null
cat LICENSE COPYING 2>/dev/null
find . -name "platformio.ini" -exec cat {} \;
find . -name "Makefile" | head -5
find . -name "CMakeLists.txt" | head -5
find . -name "*.json" -path "*board*" | head -10
find . -name "Configuration.h" | head -5
ls --recursive --max-depth=2 boards/ 2>/dev/null
ls --recursive --max-depth=2 src/ 2>/dev/null

# Шаг 3: Если есть docs sub-directory, инвестируй время в чтение
if [ -d docs ]; then
    find docs -name "*.md" -exec head -100 {} \;
fi

# Шаг 4: Определи toolchain
grep -E "platform = |framework = " platformio.ini 2>/dev/null
grep -E "TOOLCHAIN|toolchain|gcc-" Makefile 2>/dev/null

# Шаг 5: Определи поддерживаемые boards/MCU
# Marlin: ls Marlin/src/pins/
# Klipper: ls config/
# OpenWRT: ls target/linux/
# Tasmota: cat tasmota_compileversion.h
# Каждая прошивка имеет свой паттерн — research per project
```

## 2.2 Структура record (CDPO extension)

Используй новую entity `OpenSourceFirmware`:

```yaml
id: fwo:marlin-2x
name: "Marlin 2.x"
category: "3d_printer_firmware"  # из enum FirmwareCategory
upstream_url: "https://github.com/MarlinFirmware/Marlin"
upstream_mirror_urls: ["https://gitlab.com/Marlin/Marlin"]  # backup
license: "GPL-3.0-only"
license_compatibility: "free for commercial salvage use"
languages: ["C++", "Arduino"]
build_system: "PlatformIO + Arduino IDE"
toolchain_required: 
  - name: "arduino-cli"
    min_version: "1.0.0"
    install: "https://arduino.github.io/arduino-cli/installation/"
  - name: "platformio-core"
    min_version: "6.0.0"
    install: "pip install platformio"

source_size_kb_compressed: 8500
last_release_version: "2.1.2.4"
last_release_date: "2024-08-15"
maintenance_status: "active"  # active | maintenance | abandoned
contributors_count: 870
github_stars: 16200
documentation_quality: "excellent"  # excellent | good | fair | poor
community_size: "large"

target_mcus:
  - chip_canonical: "ATmega2560"
    chip_family: "AVR"
    flash_size_kb: 256
    ram_kb: 8
    eeprom_kb: 4
    cpu_speed_mhz: 16
    board_examples: 
      - id: "RAMPS_14_EFB"
        full_name: "RepRap Arduino Mega Pololu Shield 1.4 (E0+Fan+Bed)"
        common_donor_devices: ["dev:reprap-arduino-mega-1.4", "dev:anet-a8-mainboard"]
      - id: "MKS_GEN_L_V1"
        full_name: "MKS Gen L v1.0"
        common_donor_devices: ["dev:tronxy-x5sa", "dev:cr10-mainboard"]
      - id: "ANET_V1_5"
        common_donor_devices: ["dev:anet-a8", "dev:anet-a6"]
    flash_method: 
      tool: "avrdude or Arduino IDE Sketch->Upload"
      bootloader: "STK500v2"
      connection: "USB-Serial via FTDI/CH340 chip"
      command_example: "avrdude -p m2560 -c wiring -P /dev/ttyUSB0 -b 115200 -U flash:w:firmware.hex:i"
    
  - chip_canonical: "STM32F103"
    chip_family: "ARM Cortex-M3"
    flash_size_kb: 128
    ram_kb: 20
    cpu_speed_mhz: 72
    board_examples: 
      - id: "BTT_SKR_MINI_E3_V1_2"
        common_donor_devices: ["dev:ender3-v2-mainboard", "dev:cr6-stock"]
    flash_method:
      tool: "STM32CubeProgrammer or DFU-util"
      bootloader: "DFU via USB OTG"
      connection: "USB-OTG cable"
      command_example: "dfu-util -d 0483:df11 -a 0 -s 0x08000000 -D firmware.bin"
  
  - chip_canonical: "STM32F407"
    chip_family: "ARM Cortex-M4"
    flash_size_kb: 1024
    ram_kb: 192
    board_examples: ["BTT_SKR_PRO_V1_2", "BTT_OCTOPUS_V1_1"]
    # ...
  
  # Покрыть ВСЕ supported boards — обычно 30-100 на firmware

primary_functions:
  - "G-code interpretation (RS274NGC subset)"
  - "Stepper motor control (constant accel + classic Bresenham)"
  - "Hotend PID temperature control (autotune via M303)"
  - "Bed PID temperature control"
  - "Probe-based Z-homing"
  - "Mesh bed leveling (UBL or bilinear)"
  - "Filament runout detection"
  - "Power loss recovery"
  - "LCD menu display (1602 + 12864 + TFT options)"
  - "SD card autonomous printing"
  - "USB serial host control"
  - "Network printing (via OctoPrint host or built-in WiFi for some boards)"

advanced_functions:
  - "Linear advance pressure compensation"
  - "Input shaping (M593, since 2.1.2)"
  - "Adaptive step smoothing"
  - "Junction deviation cornering"
  - "Probe gridded mesh interpolation"
  - "Multi-extruder switching (up to 5)"
  - "Coreless / mixing extruders"
  - "Belt printer mode"
  - "Polar / Delta / Cartesian / SCARA kinematics"

required_peripherals:
  - role: "stepper_drivers"
    quantity: "5 (X, Y, Z, E0, E1 typical)"
    canonical_components: ["A4988", "DRV8825", "TMC2208", "TMC2209", "TMC2226", "TMC5160"]
    interface: "STEP/DIR/EN + UART/SPI for TMC variants"
  - role: "thermistors"
    quantity: "2-3 (hotend, bed, optional chamber)"
    canonical_components: ["NTC_100k_3950", "PT100", "PT1000"]
    interface: "ADC input"
  - role: "heater_outputs"
    quantity: "2 (hotend MOSFET + bed MOSFET)"
    canonical_components: ["IRLB8743", "IRLB3034", "IRFZ44N"]
    interface: "PWM controlled gate"
  - role: "endstops"
    quantity: "3-6 (X, Y, Z min/max)"
    canonical_components: ["Mechanical microswitch", "Optical_endstop_KY-010"]
    interface: "Digital input with pull-up"
  - role: "sd_card"
    quantity: "1"
    interface: "SPI"
  - role: "lcd_interface"
    quantity: "1"
    canonical_components: ["1602_LCD_HD44780", "12864_GLCD_ST7920", "TFT_3.5_FSMC"]

config_files:
  - path: "Marlin/Configuration.h"
    purpose: "Hardware-specific user configuration"
    auto_generatable: true
    placeholder_count: ~150
    key_settings:
      - key: "MOTHERBOARD"
        type: "enum"
        values_enum: "all BOARD_* names from boards.h"
        derived_from: "user.target_board_id"
      - key: "DEFAULT_AXIS_STEPS_PER_UNIT"
        type: "float[5]"
        derived_from: "user.steppers_steps_per_mm OR computed from leadscrew/belt config"
      - key: "TEMP_SENSOR_0"
        type: "int"
        values_enum: [1,5,11,13,20,...]  # thermistor table indices
        derived_from: "user.hotend_thermistor_type"
      - key: "EXTRUDERS"
        type: "int"
        derived_from: "user.extruder_count"
      # ... ~150 more
  - path: "Marlin/Configuration_adv.h"
    purpose: "Advanced features tuning"
    auto_generatable: true
    placeholder_count: ~80
  - path: "platformio.ini"
    purpose: "Build environment selection"
    auto_generatable: true

flash_methods:
  - name: "Arduino IDE Upload"
    target_chip_families: ["AVR"]
    steps:
      - "Install Arduino IDE 2.x"
      - "Open Marlin/Marlin.ino"
      - "Tools → Board → Arduino Mega or Mega 2560"
      - "Tools → Port → /dev/ttyUSB0 (Linux) or COM3 (Windows)"
      - "Sketch → Upload"
    failure_modes:
      - "avrdude: stk500_recv(): programmer is not responding → wrong board / port"
      - "Compilation errors → Configuration.h syntax error, check brackets"
  - name: "PlatformIO Build + DFU Upload"
    target_chip_families: ["ARM"]
    steps:
      - "Install PlatformIO Core"
      - "cd Marlin && pio run -e <env-name>"
      - "Output: .pio/build/<env>/firmware.bin"
      - "Boot board into DFU mode (hold BOOT button while pressing RESET)"
      - "dfu-util -a 0 -s 0x08000000:leave -D firmware.bin"
  - name: "SD Card Bootloader (no host required)"
    target_chip_families: ["ARM (some)"]
    steps:
      - "Build .bin via PlatformIO"
      - "Rename to specific name (firmware.bin or fwlatest.bin per board)"
      - "Copy to root of SD card"
      - "Insert SD into board, power on, wait 30 seconds"
      - "Board auto-flashes from SD, blinks status LED"

arksolver_can_configure: true
arksolver_template_id: "fwgen:marlin-2x-config-generator"

alternative_firmwares:
  - id: "fwo:klipper"
    when_to_choose: "If you have a Raspberry Pi available + STM32 board. Klipper offloads motion planning to Pi."
  - id: "fwo:repetier"
    when_to_choose: "Legacy AVR-only setups, minimal feature requirement."
  - id: "fwo:rrf"
    when_to_choose: "If using Duet/RRF-compatible board specifically."

common_use_devices:
  - id: "dev:ender3-v2"
    typical_setup: "stock SKR Mini E3 v1.2, Marlin 2.x with BLTouch enabled"
  - id: "dev:anet-a8-original"
    typical_setup: "Anet 1.5 board, Marlin Anet config preset"
  - id: "dev:reprap-mega-ramps"
    typical_setup: "Mega 2560 + RAMPS 1.4, Marlin RAMPS config preset"

enables_projects:
  - id: "prj:3d-printer-from-scratch"
  - id: "prj:cnc-conversion-of-ramps"
  - id: "prj:laser-engraver-marlin-port"

fork_relationships:
  - parent_of: 
      - "fwo:prusa-firmware (Prusa-specific Marlin fork)"
      - "fwo:bigtreetech-marlin (BTT-specific fork with extras)"
  - fork_of:
      - "fwo:repetier-original (1990s)"

documentation_links:
  - "https://marlinfw.org/docs/configuration/configuration.html"
  - "https://marlinfw.org/docs/basics/install_arduino.html"
  - "https://github.com/MarlinFirmware/Configurations"

provenance:
  source: "github.com/MarlinFirmware/Marlin@<latest_commit_hash>"
  research_date: "2026-04-29"
  research_method: "git_clone + README + config files + community wiki"
```

Это **один** record. Сделай похожий для каждого из 80-150 firmware-проектов.

## 2.3 Что прочитать в каждом repo

```
1. README.md / README.rst — overview + supported hardware
2. docs/ folder — detailed documentation
3. boards/ или platformio.ini — список target hardware
4. config/ folder — example configurations
5. Configuration.h / configuration.yaml — параметры
6. examples/ folder — sample projects
7. Makefile / CMakeLists.txt — build system
8. .github/workflows/ — CI/CD setup, hint к toolchain'у
9. Issues / Discussions trends — common pitfalls
```

## 2.4 Минимальная глубина для каждого record

- Минимум **5 supported MCU/board targets** (если firmware поддерживает больше — 5 наиболее популярных + примечание "and N others")
- Минимум **10 functions** в `primary_functions` + 5 в `advanced_functions`
- Минимум **3 config files** described
- Минимум **2 flash methods**
- **Все** required_peripherals enumerated
- Минимум **3 alternative firmwares** с когда-выбирать
- Минимум **2 common_use_devices** связаны с ARK device DB
- **Cross-link** к существующим Project records

---

# PART 3 — CONFIGURATOR TEMPLATES (KILLER FEATURE)

Per firmware с `arksolver_can_configure: true` — генерируй **configurator template** который ARK solver использует чтобы автоматом написать config под user inputs.

## 3.1 Структура `FirmwareConfigGenerator` (новая entity в CDPO)

```yaml
id: fwgen:marlin-2x-config-generator
target_firmware: fwo:marlin-2x
description: "Generates fully-configured Marlin 2.x Configuration.h + Configuration_adv.h based on user hardware specification."
schema_version: "0.1"

user_input_schema:
  type: object
  required: ["motherboard", "extruder_count", "hotend_thermistor", "bed_thermistor", "stepper_drivers", "kinematics", "axis_max_mm", "axis_steps_per_mm"]
  properties:
    motherboard:
      type: string
      description: "Board ID from BOARDS list. Run ARK solver with photo of mainboard to auto-detect."
      enum: ["BOARD_RAMPS_14_EFB", "BOARD_BTT_SKR_MINI_E3_V1_2", "BOARD_MKS_GEN_L_V1", ...]
    extruder_count:
      type: integer
      minimum: 1
      maximum: 5
    hotend_thermistor:
      type: object
      properties:
        type: 
          type: string
          enum: ["NTC_100k_3950", "PT100", "PT1000", "thermocouple_K"]
        beta_value:
          type: integer
          default: 3950
    # ... full schema for all 150+ Configuration.h settings
    kinematics:
      type: string
      enum: ["cartesian", "delta", "corexy", "coreyx", "scara", "polar", "belt"]
    axis_steps_per_mm:
      type: array
      items: { type: number }
      minItems: 4  # X, Y, Z, E0
      maxItems: 8

config_template:
  - target_path: "Marlin/Configuration.h"
    template_content: |
      // Auto-generated by ARK Firmware Generator
      // Generated for: {{user_input.motherboard}} with {{user_input.extruder_count}} extruders
      // Generated date: {{generation_date}}
      
      #ifndef CONFIGURATION_H
      #define CONFIGURATION_H
      
      #define CONFIGURATION_H_VERSION 02010202
      
      #define MOTHERBOARD {{motherboard_to_marlin_id(user_input.motherboard)}}
      
      #define EXTRUDERS {{user_input.extruder_count}}
      #define DEFAULT_NOMINAL_FILAMENT_DIA {{user_input.filament_diameter | default(1.75)}}
      
      // Thermistor settings
      #define TEMP_SENSOR_0 {{thermistor_to_marlin_index(user_input.hotend_thermistor.type)}}
      #define TEMP_SENSOR_BED {{thermistor_to_marlin_index(user_input.bed_thermistor.type)}}
      
      // Axis settings
      #define DEFAULT_AXIS_STEPS_PER_UNIT { {{user_input.axis_steps_per_mm | join(", ")}} }
      #define DEFAULT_MAX_FEEDRATE { {{user_input.axis_max_feedrates | default([300, 300, 5, 25]) | join(", ")}} }
      
      // Kinematics
      {% if user_input.kinematics == "delta" %}
      #define DELTA
      #define DELTA_DIAGONAL_ROD {{user_input.delta_diagonal_rod_mm}}
      #define DELTA_PRINTABLE_RADIUS {{user_input.delta_radius_mm}}
      {% elif user_input.kinematics == "corexy" %}
      #define COREXY
      {% endif %}
      
      // ... 200+ more settings using Jinja2 conditional templating
      
      #endif

  - target_path: "Marlin/Configuration_adv.h"
    template_content: |
      // ... ~80 settings

placeholder_mappings:
  motherboard_to_marlin_id: 
    type: function
    description: "Map ARK canonical board ID to Marlin BOARD_* enum"
    examples:
      - input: "BOARD_RAMPS_14_EFB"
        output: "BOARD_RAMPS_14_EFB"
      - input: "BOARD_BTT_SKR_MINI_E3_V1_2"
        output: "BOARD_BTT_SKR_MINI_E3_V1_2"
  thermistor_to_marlin_index:
    type: function
    description: "Map thermistor type to Marlin thermistor table index"
    examples:
      - input: "NTC_100k_3950"
        output: 1
      - input: "PT100_pt100_amplifier"
        output: 20
      - input: "PT1000"
        output: 1047

validation_rules:
  - rule: "extruder_count > 0 AND extruder_count <= 5"
    error_message: "Marlin supports 1-5 extruders only"
  - rule: "axis_steps_per_mm.length >= 4"
    error_message: "Need at least 4 axis_steps values: X, Y, Z, E0"
  - rule: "if kinematics == 'delta' then delta_diagonal_rod_mm is required"
    error_message: "Delta kinematics requires delta_diagonal_rod_mm parameter"

post_processing:
  - "Run pio run -e <env_for_motherboard> to compile"
  - "Output binary at .pio/build/<env>/firmware.bin"
  - "Calculate SHA256 of generated firmware for user verification"

testing:
  - test_id: "ramps_basic_config"
    user_input_example: 
      motherboard: "BOARD_RAMPS_14_EFB"
      extruder_count: 1
      hotend_thermistor: {type: "NTC_100k_3950"}
      bed_thermistor: {type: "NTC_100k_3950"}
      kinematics: "cartesian"
      axis_steps_per_mm: [80, 80, 400, 100]
    expected_output_hash: "<sha256 of expected Configuration.h>"
    expected_compilation: "successful with avr-gcc 7.3"
```

## 3.2 Configurator templates для топ-20 firmware-проектов

Топ-priority configurators (каждый ~500 строк template):
1. fwgen:marlin-2x → Configuration.h + Configuration_adv.h + platformio.ini
2. fwgen:klipper → printer.cfg + mcu.cfg
3. fwgen:openwrt → /etc/config/wireless + /etc/config/network + /etc/config/dhcp
4. fwgen:tasmota → Web UI export JSON
5. fwgen:esphome → device.yaml
6. fwgen:meshtastic → device.yaml + region.yaml
7. fwgen:betaflight → CLI dump
8. fwgen:inav → CLI dump
9. fwgen:ardupilot → Parameters file
10. fwgen:px4 → params YAML
11. fwgen:vesc → vesc_config.xml
12. fwgen:odrive → odrive_config.json
13. fwgen:wled → cfg.json
14. fwgen:retroarch → retroarch.cfg
15. fwgen:openipc → system.bin
16. fwgen:grbl → config.h (compile-time)
17. fwgen:openwsn → openvisualizer config
18. fwgen:diy-bms → user_config.h
19. fwgen:openevse → wifi.json
20. fwgen:flipper-zero → applications.fam

Для остальных firmware (Tier B-C) — basic template без advanced placeholder logic.

---

# PART 4 — CDPO SCHEMA EXTENSIONS

Добавь в `kb-pipeline/schemas/cdpo.py`:

```python
class FirmwareCategory(str, Enum):
    printer_3d = "3d_printer_firmware"
    cnc = "cnc_firmware"
    router_networking = "router_networking_firmware"
    iot_smarthome = "iot_smarthome_firmware"
    rc_drone = "rc_drone_firmware"
    radio_sdr = "radio_sdr_firmware"
    motor_controller = "motor_controller_firmware"
    security_lock = "security_lock_firmware"
    test_measurement = "test_measurement_firmware"
    camera_video = "camera_video_firmware"
    audio_dsp = "audio_dsp_firmware"
    game_retro = "game_retro_firmware"
    power_energy = "power_energy_firmware"
    aerospace = "aerospace_firmware"
    embedded_linux = "embedded_linux_distro"
    bios_bootloader = "bios_bootloader_firmware"
    other = "other"

class FirmwareMaintenanceStatus(str, Enum):
    active = "active"
    maintenance = "maintenance"
    abandoned = "abandoned"
    archived = "archived"

class DocumentationQuality(str, Enum):
    excellent = "excellent"
    good = "good"
    fair = "fair"
    poor = "poor"
    none = "none"

class CommunitySize(str, Enum):
    large = "large"      # 5000+ stars / contributors
    medium = "medium"    # 500-5000
    small = "small"      # <500
    obscure = "obscure"  # niche

class FirmwareToolchainItem(BaseModel):
    name: str
    min_version: str | None = None
    install_url: str | None = None
    install_command: str | None = None

class FirmwareMCUTarget(BaseModel):
    chip_canonical: str
    chip_family: str
    flash_size_kb: int | None = None
    ram_kb: int | None = None
    eeprom_kb: int | None = None
    cpu_speed_mhz: int | None = None
    board_examples: list[FirmwareBoardExample]
    flash_method: FirmwareFlashMethod

class FirmwareBoardExample(BaseModel):
    id: str
    full_name: str
    common_donor_devices: list[str] = []  # device ids в ARK KB

class FirmwareFlashMethod(BaseModel):
    name: str
    target_chip_families: list[str]
    tool: str
    bootloader: str | None = None
    connection: str
    command_example: str | None = None
    steps: list[str] = []
    failure_modes: list[str] = []

class FirmwareRequiredPeripheral(BaseModel):
    role: str  # "stepper_driver", "thermistor", etc
    quantity: str  # "5 (X,Y,Z,E0,E1)"
    canonical_components: list[str]
    interface: str

class FirmwareConfigFile(BaseModel):
    path: str
    purpose: str
    auto_generatable: bool
    placeholder_count: int | None = None
    key_settings: list[FirmwareConfigSetting] = []

class FirmwareConfigSetting(BaseModel):
    key: str
    type: str  # "enum", "int", "float", "string", "bool", "array"
    values_enum: list[str] | None = None
    derived_from: str | None = None  # "user.<field>" or "computed:..."
    default: str | None = None

class FirmwareAlternative(BaseModel):
    id: str  # fwo:<other-firmware>
    when_to_choose: str

class FirmwareUseDevice(BaseModel):
    id: str  # device id в ARK KB
    typical_setup: str

class OpenSourceFirmware(BaseModel):
    """Knowledge graph entry for an open-source firmware project."""
    
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(pattern=r"^fwo:[a-z0-9_-]+$")
    name: str
    category: FirmwareCategory
    upstream_url: str
    upstream_mirror_urls: list[str] = []
    license: str
    license_compatibility: str
    languages: list[str]
    build_system: str
    toolchain_required: list[FirmwareToolchainItem]
    
    source_size_kb_compressed: int | None = None
    last_release_version: str | None = None
    last_release_date: str | None = None
    maintenance_status: FirmwareMaintenanceStatus
    contributors_count: int | None = None
    github_stars: int | None = None
    documentation_quality: DocumentationQuality
    community_size: CommunitySize
    
    target_mcus: list[FirmwareMCUTarget]
    primary_functions: list[str]
    advanced_functions: list[str] = []
    required_peripherals: list[FirmwareRequiredPeripheral]
    config_files: list[FirmwareConfigFile]
    flash_methods: list[FirmwareFlashMethod]
    
    arksolver_can_configure: bool
    arksolver_template_id: str | None = None
    
    alternative_firmwares: list[FirmwareAlternative] = []
    common_use_devices: list[FirmwareUseDevice] = []
    enables_projects: list[str] = []  # project ids
    fork_relationships: dict[str, list[str]] = {}  # {parent_of: [...], fork_of: [...]}
    
    documentation_links: list[str] = []
    provenance: list[Provenance]


class FirmwareConfigGenerator(BaseModel):
    """Programmatic configurator for an OpenSourceFirmware."""
    
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(pattern=r"^fwgen:[a-z0-9_-]+$")
    target_firmware: str  # fwo: id
    description: str
    schema_version: str
    
    user_input_schema: dict  # JSON Schema describing user inputs
    
    config_template: list[FirmwareConfigTemplate]
    placeholder_mappings: dict[str, FirmwarePlaceholderFunction]
    validation_rules: list[FirmwareValidationRule]
    post_processing: list[str]
    testing: list[FirmwareConfigGeneratorTest]
    provenance: list[Provenance]


class FirmwareConfigTemplate(BaseModel):
    target_path: str
    template_content: str  # Jinja2 template
    
class FirmwarePlaceholderFunction(BaseModel):
    type: Literal["function", "lookup", "constant", "computed"]
    description: str
    examples: list[dict] = []
    implementation_hint: str | None = None
    
class FirmwareValidationRule(BaseModel):
    rule: str
    error_message: str

class FirmwareConfigGeneratorTest(BaseModel):
    test_id: str
    user_input_example: dict
    expected_output_hash: str | None = None
    expected_compilation: str | None = None
```

---

# PART 5 — VOLUME / TIME / SCOPE

## 5.1 Целевые объёмы

- **80-150 fwo records** (по категории purposeful coverage)
- **~30 fwgen configurator templates** (топ-priority firmware с advanced template)
- **~70 fwgen basic templates** (остальные firmware с simple substitution)
- **All cross-links** к existing ARK devices, components, projects
- **Schema extensions** в cdpo.py merged

## 5.2 Wave распределение

```
Wave 1 (parallel sub-agents):
├── agent_3dprinter_cnc      → 16 records (Marlin/Klipper/RRF/Smoothie/GRBL/...)
├── agent_router_networking  → 13 records (OpenWRT/DD-WRT/pfSense/...)
├── agent_iot_smarthome      → 12 records (Tasmota/ESPHome/WLED/...)
├── agent_rc_drone           → 10 records (Betaflight/iNav/ArduPilot/PX4/...)
├── agent_radio_sdr          → 12 records (Meshtastic/T41/uBitx/...)
├── agent_motor_controllers  → 7 records (VESC/ODrive/DiyBMS/...)
├── agent_test_measurement   → 6 records (sigrok/Hantek/...)
└── agent_other              → ~25 records (locks/cameras/audio/games/power/aerospace/etc)

Wave 2 (after Wave 1 done):
├── agent_configurator_top20 → 20 fwgen templates with full Jinja2 logic
└── agent_configurator_basic → ~70 fwgen simple templates

Wave 3:
├── agent_xref_validator     → cross-link integrity check
├── agent_schema_validator   → CDPO Pydantic validation
└── agent_packager           → tar.zst + SHA + manifest
```

## 5.3 Время в Kimi подписке

- Per fwo record (research + write): 30-60 минут
- Per fwgen template advanced: 1-2 часа
- Per fwgen template basic: 15-30 минут
- Validation + packaging: 2-4 часа

Итого: **~80 часов compute** в Kimi подписке. Распределяется на 1-3 недели реальные.

## 5.4 Качественные критерии

- ≥80% fwo records имеют ≥5 supported MCU targets
- ≥80% fwo records имеют ≥10 primary_functions enumerated
- ≥80% fwo records имеют cross-links к existing ARK devices/projects
- 100% top-20 firmware имеют working fwgen configurator template
- 100% fwgen templates имеют ≥1 testing example
- 100% fwo records имеют license + maintenance_status
- Schema validation pass rate 100% (Pydantic strict)

---

# PART 6 — INTEGRATION С ARK

## 6.1 Solver enhancement

После integration ARK solver получает новый flow:

```
User input: "I have <hardware list>. I want <project goal>."

Solver pipeline:
1. Vision/inventory → recognized hardware components
2. KB lookup: which Projects can be built with these components?
3. For each candidate Project:
   a. Lookup which fwo (firmware) projects support it
   b. For each fwo: check if user's MCU is in target_mcus[]
   c. If yes AND fwo.arksolver_can_configure: 
      → fwgen template applies
      → user_input_schema validates user's reported hardware
      → generate configured Configuration.h / printer.cfg / device.yaml / etc
   d. Cross-reference required_peripherals with user's actual peripherals
4. Output:
   - Project plan (existing ARK behavior)
   - + Specific firmware recommendation (fwo)
   - + GENERATED working firmware config (fwgen output)
   - + Compilation command
   - + Flash instructions specific to user's setup
   - + Calibration steps
```

Это **тысячи** реальных rebuild paths из ничего, кроме curated knowledge graph.

## 6.2 Vision integration

Когда vision endpoint распознаёт "это материнка SKR Mini E3" — solver автоматом:
- Lookup what fwo support this board → Marlin, Klipper
- User chooses preference → solver generates appropriate config
- One image → full working firmware in <10 seconds

## 6.3 Updates / forks tracking

`fwo` записи имеют `last_release_date` и `maintenance_status`. Updater проверяет git remote раз в месяц:
- Если new release → update fwo record + re-test fwgen templates
- Если abandoned → mark, suggest alternative_firmwares
- Если new fork становится popular → research and add as separate fwo

---

# PART 7 — FORBIDDEN BEHAVIORS

Стандартные правила из KIMI-MEGA-BRIEF + специфические для FGP:

- ❌ Не указывай supported boards без верификации в самом repo. Если board упомянут только в community wiki — confidence ≤0.7.
- ❌ Не выдумывай config-file paths. Open repo и убедись что путь реальный.
- ❌ Не выдумывай flash commands. Test command syntax в реальном toolchain'е.
- ❌ Не пропускай старые но критичные firmwares (GRBL — выглядит legacy но это базис всего CNC).
- ❌ Не игнорируй forks. У Marlin важные forks: Prusa, BTT-Marlin. У OpenWRT: DD-WRT, LEDE.
- ❌ Не игнорируй closed-source competitors как baseline (Klipper vs Marlin есть конкуренция, нужно writing про них обоих).
- ❌ Не пиши Jinja2 placeholders в template без realistic implementation. Каждый placeholder должен быть рабочим.
- ❌ Не пропускай license info — это критично для commercial use story.

---

# PART 8 — DELIVERABLES

```
/mnt/output/firmware-genome/
├── INDEX.json                              # master index
├── schemas/                                # CDPO extensions
│   └── firmware.py                         # OpenSourceFirmware + FirmwareConfigGenerator + supporting models
├── fwo/                                    # 80-150 firmware records
│   ├── fwo_marlin-2x.json
│   ├── fwo_klipper.json
│   ├── fwo_openwrt.json
│   ├── ... (80-150 files)
├── fwgen/                                  # configurator templates
│   ├── fwgen_marlin-2x-config-generator.json
│   ├── fwgen_klipper-printer-cfg.json
│   ├── ... (90-100 files)
├── tests/                                  # configurator self-tests
│   ├── test_fwgen_marlin_ramps14.py        # generates config and tries pio compile
│   └── ... 
├── cross-references/                       # links к ARK KB
│   ├── fwo-to-devices.jsonl                # which fwo work with which ARK devices
│   ├── fwo-to-projects.jsonl               # which projects benefit from which fwo
│   └── fwo-to-components.jsonl             # required_peripherals → ARK component ids
├── README.md                               # how to use, integration guide
└── REPORT.md                               # generation stats
```

Финал: `/mnt/output/ark-firmware-genome-v0.1.tar.zst` (compressed).

Объём: 50-200 MB compressed, 200-500 MB extracted.

---

# PART 9 — START

Без preamble. Без "let me confirm". 

Шаг 1: создай рабочее пространство.
Шаг 2: clone first 5 highest-priority firmwares (Marlin, Klipper, OpenWRT, Tasmota, ESPHome).
Шаг 3: пиши их fwo records по template из PART 2.2.
Шаг 4: пиши fwgen configurator для Marlin (топ-приоритет).
Шаг 5: тест fwgen на одном realistic input → compile result via pio.
Шаг 6: повторяй для всех 80-150 firmwares.
Шаг 7: validation + cross-references + packaging.
Шаг 8: финальный tar.zst + REPORT.md.

---

# APPENDIX — KILLER SCENARIO для validation

После завершения — выполни этот end-to-end test:

```
Input: 
  user_inventory:
    - SKR Mini E3 v1.2 mainboard (STM32F103)
    - 4× NEMA17 stepper 200 steps/rev
    - 2× thermistor 100k NTC
    - 1× hotend MOSFET module
    - 1× bed MOSFET module 
    - 5× mechanical endstop
    - 12V 360W PSU
    - 12864 LCD
    - SD card slot
  user_goal: "3D printer using my Voron 2.4 frame"

Expected ARK solver output:
  recommended_firmware: fwo:klipper (better for Voron 2.4 vs Marlin)
  generated_config_files:
    - printer.cfg (Klipper printer config)
    - mcu.cfg (SKR Mini E3 v1.2 MCU pinout)
  compilation_steps: [...]
  flash_steps: [...]
  expected_print_quality: <validated_specs>
```

Если solver smooth-flow проходит — FGP integration успешна.

---

# END.

Execute. Build the firmware genome. Make every salvaged board into a working machine.
