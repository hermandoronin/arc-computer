"""CDPO Firmware Genome extensions — OpenSourceFirmware + FirmwareConfigGenerator schemas."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


# ──────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────


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
    large = "large"
    medium = "medium"
    small = "small"
    obscure = "obscure"


# ──────────────────────────────────────────────────────────────────
# Supporting models
# ──────────────────────────────────────────────────────────────────


class FirmwareToolchainItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    min_version: str | None = None
    install_url: str | None = None
    install_command: str | None = None


class FirmwareFlashMethod(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    target_chip_families: list[str] = Field(default_factory=list)
    tool: str
    bootloader: str | None = None
    connection: str
    command_example: str | None = None
    steps: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)


class FirmwareBoardExample(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    full_name: str
    common_donor_devices: list[str] = Field(default_factory=list)


class FirmwareMCUTarget(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chip_canonical: str
    chip_family: str
    flash_size_kb: int | None = None
    ram_kb: int | None = None
    eeprom_kb: int | None = None
    cpu_speed_mhz: int | None = None
    board_examples: list[FirmwareBoardExample] = Field(default_factory=list)
    flash_method: FirmwareFlashMethod | None = None


class FirmwareRequiredPeripheral(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str
    quantity: str
    canonical_components: list[str] = Field(default_factory=list)
    interface: str


class FirmwareConfigSetting(BaseModel):
    model_config = ConfigDict(extra="ignore")
    key: str
    type: str
    values_enum: list[str] | None = None
    derived_from: str | None = None
    default: str | None = None


class FirmwareConfigFile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    path: str
    purpose: str
    auto_generatable: bool
    placeholder_count: int | None = None
    key_settings: list[FirmwareConfigSetting] = Field(default_factory=list)


class FirmwareAlternative(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    when_to_choose: str


class FirmwareUseDevice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    typical_setup: str


class ProvenanceFW(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source: str
    research_date: str
    research_method: str


# ──────────────────────────────────────────────────────────────────
# Main entities
# ──────────────────────────────────────────────────────────────────


class OpenSourceFirmware(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(pattern=r"^fwo:[a-z0-9_-]+$")
    name: str
    category: FirmwareCategory
    upstream_url: str
    upstream_mirror_urls: list[str] = Field(default_factory=list)
    license: str
    license_compatibility: str
    languages: list[str] = Field(default_factory=list)
    build_system: str
    toolchain_required: list[FirmwareToolchainItem] = Field(default_factory=list)

    source_size_kb_compressed: int | None = None
    last_release_version: str | None = None
    last_release_date: str | None = None
    maintenance_status: FirmwareMaintenanceStatus
    contributors_count: int | None = None
    github_stars: int | None = None
    documentation_quality: DocumentationQuality
    community_size: CommunitySize

    target_mcus: list[FirmwareMCUTarget] = Field(default_factory=list)
    primary_functions: list[str] = Field(default_factory=list)
    advanced_functions: list[str] = Field(default_factory=list)
    required_peripherals: list[FirmwareRequiredPeripheral] = Field(default_factory=list)
    config_files: list[FirmwareConfigFile] = Field(default_factory=list)
    flash_methods: list[FirmwareFlashMethod] = Field(default_factory=list)

    arksolver_can_configure: bool = False
    arksolver_template_id: str | None = None

    alternative_firmwares: list[FirmwareAlternative] = Field(default_factory=list)
    common_use_devices: list[FirmwareUseDevice] = Field(default_factory=list)
    enables_projects: list[str] = Field(default_factory=list)
    fork_relationships: dict[str, list[str]] = Field(default_factory=dict)
    documentation_links: list[str] = Field(default_factory=list)
    provenance: list[ProvenanceFW] = Field(default_factory=list)


class FirmwareConfigTemplate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    target_path: str
    template_content: str


class FirmwarePlaceholderFunction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["function", "lookup", "constant", "computed"]
    description: str
    examples: list[dict] = Field(default_factory=list)
    implementation_hint: str | None = None


class FirmwareValidationRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rule: str
    error_message: str


class FirmwareConfigGeneratorTest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    test_id: str
    user_input_example: dict = Field(default_factory=dict)
    expected_output_hash: str | None = None
    expected_compilation: str | None = None


class FirmwareConfigGenerator(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(pattern=r"^fwgen:[a-z0-9_-]+$")
    target_firmware: str
    description: str
    schema_version: str

    user_input_schema: dict = Field(default_factory=dict)
    config_template: list[FirmwareConfigTemplate] = Field(default_factory=list)
    placeholder_mappings: dict[str, FirmwarePlaceholderFunction] = Field(default_factory=dict)
    validation_rules: list[FirmwareValidationRule] = Field(default_factory=list)
    post_processing: list[str] = Field(default_factory=list)
    testing: list[FirmwareConfigGeneratorTest] = Field(default_factory=list)
    provenance: list[ProvenanceFW] = Field(default_factory=list)
