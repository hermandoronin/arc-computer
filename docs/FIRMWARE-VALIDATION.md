# Firmware validation

The solver is allowed to surface a firmware template to a user only after
the template has been compiled (and, when possible, dry-run on a headless
emulator) by the pipeline scripts in `kb/pipeline/scripts/`. This document
lists the toolchains the validator dispatches to, install commands per
distro, and the procedure for adding a new MCU family.

## Pipeline overview

| Stage | Script | Output |
|---|---|---|
| Compile-check | `kb/pipeline/scripts/firmware_validator.py` | `kb/output/validation-reports/firmware.json` |
| Headless dry-run | `kb/pipeline/scripts/firmware_dry_run.py` | `kb/output/validation-reports/firmware-runtime.json` |

`firmware_dry_run.py` reads the compile report and only acts on records
flagged `compiled_ok`. Re-run the validator with `--keep-workdir` to
preserve binaries between the two stages.

## Required tools

| MCU family | Compiler | Headless runtime |
|---|---|---|
| AVR (atmega328p, atmega2560) | `avr-gcc` | `simavr` |
| Arduino sketches (.ino) | `arduino-cli` | `simavr` (after `arduino-cli compile`) |
| ESP32 / ESP8266 | `xtensa-esp32-elf-gcc` / `xtensa-lx106-elf-gcc` | _none — skipped on purpose_ |
| STM32 / RP2040 / generic ARM Cortex-M | `arm-none-eabi-gcc` | `qemu-system-arm` |

The validator reports `skipped: toolchain-missing` for any record whose
required compiler is absent — this is intentional. CI installs only the
toolchains we actively need; contributors install the rest only when they
work on those records.

### Arch Linux (pacman)

```bash
sudo pacman -S --needed avr-gcc avr-libc arduino-cli simavr \
                        arm-none-eabi-gcc arm-none-eabi-newlib \
                        qemu-system-arm
# ESP32 / ESP8266 toolchains are not in core repos:
yay -S xtensa-esp-elf-gcc xtensa-lx106-elf-gcc-bin
```

### Ubuntu / Debian (apt)

```bash
sudo apt-get update
sudo apt-get install -y \
    gcc-avr avr-libc simavr \
    gcc-arm-none-eabi libnewlib-arm-none-eabi \
    qemu-system-arm
# Arduino CLI:
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
sudo mv ./bin/arduino-cli /usr/local/bin/
arduino-cli core install arduino:avr esp32:esp32 esp8266:esp8266
```

The ESP toolchains on Debian come either from the
`xtensa-esp32-elf-clang` upstream tarball or the ESP-IDF installer; both
are out of scope for the OSS CI image.

## Adding a new MCU family

`firmware_validator.py` selects a toolchain from the module-level
`DISPATCH` table:

```python
# kb/pipeline/scripts/firmware_validator.py
DISPATCH: dict[str, tuple[str, str]] = {
    "AVR":     ("avr-gcc",            "avr"),
    "STM32":   ("arm-none-eabi-gcc",  "arm"),
    # ...
}
```

To add a new family — say RISC-V (`GD32V`) — do three things:

1. **Pick a CLI name** the validator can probe with `shutil.which`. For
   GD32V that would be `riscv32-unknown-elf-gcc`.
2. **Add a builder function** `_compile_riscv` modelled on `_compile_arm`,
   then register it under a new builder key in `_BUILDERS`.
3. **Wire the dispatch entry** mapping the chip family / canonical names
   that appear in `target_mcus` to the new `(cli_name, builder_key)` pair.

If the family also has a headless emulator, mirror the change in
`firmware_dry_run.py` (`_run_*` helper plus an `if "<key>" in toolchain`
branch). Otherwise leave it `skipped: no headless emulator`.

## Server side

The solver consumes `firmware.json` and `firmware-runtime.json` to attach
a small validation badge to the firmware block in the response payload:

```json
"firmware": {
  "id": "fwgen:grbl-build",
  "validated": {
    "compiled": true,
    "dry_run": "passed",
    "binary_size_bytes": 5400,
    "ram_estimate_bytes": 380
  }
}
```

A record without `compiled: true` must not be returned to the user.
