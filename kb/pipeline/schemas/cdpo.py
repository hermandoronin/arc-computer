"""CDPO — Component-Device-Project Ontology
Pydantic schemas for the ARK knowledge graph extraction pipeline.

Used by:
  - LLM extractors (kb-pipeline/extractors/) — validate model output
  - Graph builder (kb-pipeline/build_graph.py) — load into kuzu
  - Solver (server/crates/solver) — typed access via Rust port

Versioning: bump SCHEMA_VERSION on any breaking change.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

SCHEMA_VERSION = "0.1.0"


# ──────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────


class GoalCategory(str, Enum):
    energy = "energy"
    water = "water"
    food = "food"
    comms = "comms"
    security = "security"
    medical = "medical"
    manufacture = "manufacture"
    info = "info"
    community = "community"


class ComponentType(str, Enum):
    resistor = "resistor"
    capacitor = "capacitor"
    inductor = "inductor"
    diode = "diode"
    transistor = "transistor"
    mosfet = "mosfet"
    igbt = "igbt"
    optocoupler = "optocoupler"
    transformer = "transformer"
    motor_dc = "motor_dc"
    motor_stepper = "motor_stepper"
    motor_servo = "motor_servo"
    solenoid = "solenoid"
    relay = "relay"
    ic_logic = "ic_logic"
    ic_analog = "ic_analog"
    mcu = "mcu"
    fpga = "fpga"
    memory = "memory"
    sensor = "sensor"
    display = "display"
    speaker = "speaker"
    microphone = "microphone"
    antenna = "antenna"
    rf_module = "rf_module"
    psu = "psu"
    battery = "battery"
    fuse = "fuse"
    switch = "switch"
    connector = "connector"
    crystal = "crystal"
    led = "led"
    laser = "laser"
    heating_element = "heating_element"
    magnet = "magnet"
    optical = "optical"
    pcb_bare = "pcb_bare"
    mechanical = "mechanical"
    other = "other"


class ExtractionDifficulty(str, Enum):
    trivial = "trivial"     # 1-2 min, no tools
    easy = "easy"           # under 10 min, basic tools
    medium = "medium"       # 30-60 min, careful work
    hard = "hard"           # 2+ hours, specialized tools / risk
    destructive = "destructive"  # donor sacrificed entirely


class DamageRisk(str, Enum):
    none = "none"
    low = "low"           # might damage with bad luck
    medium = "medium"     # 1 in 5 chance of destroying part
    high = "high"         # likely partial damage, plan for spare


class SkillLevel(str, Enum):
    none = "none"          # no prior skill required
    basic = "basic"        # knows which end of soldering iron is hot
    intermediate = "intermediate"
    advanced = "advanced"
    expert = "expert"      # rare, e.g. SMD rework, RF tuning


class SafetyHazard(str, Enum):
    high_voltage = "high_voltage"        # > 50V AC or >120V DC
    mains_voltage = "mains_voltage"      # 110/220V AC
    capacitor_charge = "capacitor_charge"
    rf_radiation = "rf_radiation"
    laser = "laser"
    chemical = "chemical"
    asbestos = "asbestos"               # vintage heating elements
    mercury = "mercury"                  # old switches, CFL
    lead = "lead"                        # solder, CRT
    radioactive = "radioactive"          # vintage smoke detectors, medical
    sharp = "sharp"
    pinch_crush = "pinch_crush"
    burn_hot = "burn_hot"
    burn_cold = "burn_cold"             # cryo
    biological = "biological"


# ──────────────────────────────────────────────────────────────────
# Value types — units, ranges
# ──────────────────────────────────────────────────────────────────


class ParamValue(BaseModel):
    """Numeric param with unit, optional tolerance and range."""
    model_config = ConfigDict(extra="forbid")

    value: float | None = None
    min: float | None = None
    max: float | None = None
    nominal: float | None = None
    tolerance_pct: float | None = None
    unit: str  # SI base: V, A, F, H, Hz, ohm, s, m, kg, C, K, lm, W, etc.

    def is_consistent(self) -> bool:
        if self.min is not None and self.max is not None:
            return self.min <= self.max
        return True


class Range(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min: float
    max: float
    unit: str


# ──────────────────────────────────────────────────────────────────
# Core entities
# ──────────────────────────────────────────────────────────────────


class Provenance(BaseModel):
    """Where this fact came from. Every edge & property carries one."""
    model_config = ConfigDict(extra="forbid")

    source_id: str                      # 'ifixit_guide_12345', 'kicad_lib_A', etc.
    source_kind: Literal[
        "ifixit", "instructables", "hackaday", "youtube_transcript",
        "datasheet", "wikidata", "kicad", "survivor_library",
        "army_fm", "hesperian", "appropedia", "open_repair",
        "manual_curation", "llm_extracted", "user_contributed",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_by: str | None = None     # 'claude-4.7-batch-v1'
    extracted_at: datetime | None = None
    page_or_timestamp: str | None = None  # 'p.42' or '18:42'
    notes: str | None = None


class Component(BaseModel):
    """Canonical reusable component (e.g., 'TL431' regardless of manufacturer)."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^cmp:[a-z0-9_-]+$")  # 'cmp:tl431'
    name: str
    type: ComponentType
    aliases: list[str] = Field(default_factory=list)
    manufacturer_pns: list[str] = Field(default_factory=list)  # 'TL431ACDR', 'TL431IL'
    package_options: list[str] = Field(default_factory=list)   # ['TO-92', 'SOIC-8', 'SOT-23']
    parameters: dict[str, ParamValue] = Field(default_factory=dict)
    appearance_descriptor: str | None = None  # human description for vision matching
    visual_aliases: list[str] = Field(default_factory=list)
    datasheet_refs: list[str] = Field(default_factory=list)
    typical_uses: list[str] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)


class ComponentInstance(BaseModel):
    """A component AS FOUND inside a specific Device."""
    model_config = ConfigDict(extra="forbid")

    instance_id: str = Field(pattern=r"^inst:[a-z0-9_-]+$")
    component_id: str
    device_id: str
    quantity: int = 1
    location_in_device: str | None = None
    extraction_difficulty: ExtractionDifficulty
    extraction_steps: list[str] = Field(default_factory=list)
    damage_risk: DamageRisk
    salvage_quality: Literal["pristine", "good", "usable", "scrap"] = "good"
    typical_failure_after_years: int | None = None
    notes: str | None = None
    provenance: list[Provenance] = Field(default_factory=list)


class Device(BaseModel):
    """A specific consumer/industrial device (donor candidate)."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^dev:[a-z0-9_-]+$")  # 'dev:hp-deskjet-f2280'
    name: str
    manufacturer: str | None = None
    model: str | None = None
    year_introduced: int | None = None
    year_eol: int | None = None
    category: str  # free-text but normalized: 'inkjet_printer', 'microwave_oven', etc.
    aliases: list[str] = Field(default_factory=list)
    popularity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    teardown_difficulty: ExtractionDifficulty
    tools_required: list[str] = Field(default_factory=list)
    safety_hazards: list[SafetyHazard] = Field(default_factory=list)
    contains: list[str] = Field(default_factory=list)  # ComponentInstance IDs
    teardown_steps: list[str] = Field(default_factory=list)
    images_refs: list[str] = Field(default_factory=list)  # cold-zone refs only, not data
    provenance: list[Provenance] = Field(default_factory=list)


class FirmwareTemplate(BaseModel):
    """Code template that solver can fill in for a project."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^fw:[a-z0-9_-]+$")
    name: str
    target_mcus: list[str] = Field(default_factory=list)  # ['atmega328p', 'esp32', 'stm32f103']
    language: Literal["c", "cpp", "rust", "python_micro", "arduino"] = "arduino"
    code: str  # full template, with {{placeholder}} markers
    placeholders: dict[str, str] = Field(default_factory=dict)  # name -> description
    pin_requirements: dict[str, str] = Field(default_factory=dict)  # logical -> capability spec
    libraries: list[str] = Field(default_factory=list)
    flash_method: list[str] = Field(default_factory=list)


class Project(BaseModel):
    """A recipe: how to assemble {Goal-relevant thing} from components."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^prj:[a-z0-9_-]+$")
    name: str
    summary: str
    goals: list[GoalCategory]
    difficulty: SkillLevel
    estimated_hours: float | None = None
    required_skills: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    required_components: list["BomEntry"] = Field(default_factory=list)
    optional_components: list["BomEntry"] = Field(default_factory=list)
    consumables: list[str] = Field(default_factory=list)
    safety_hazards: list[SafetyHazard] = Field(default_factory=list)
    assembly_steps: list[str] = Field(default_factory=list)
    schematic_svg: str | None = None
    schematic_ascii: str | None = None
    firmware_template_id: str | None = None
    calibration_steps: list[str] = Field(default_factory=list)
    maintenance: list[str] = Field(default_factory=list)
    troubleshooting: list["TroubleshootEntry"] = Field(default_factory=list)
    builds_tools: list[str] = Field(default_factory=list)  # if building this project produces tool X
    produces_goals: list[GoalCategory] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)


class BomEntry(BaseModel):
    """One line in a project's bill of materials."""
    model_config = ConfigDict(extra="forbid")

    component_id: str
    quantity: int
    notes: str | None = None
    substitutes: list[str] = Field(default_factory=list)  # other component_ids


class TroubleshootEntry(BaseModel):
    """Decision-tree node for 'I built it but it doesn't work'."""
    model_config = ConfigDict(extra="forbid")

    symptom: str
    likely_causes: list[str]
    diagnostic_steps: list[str]
    fix: str


class Substitution(BaseModel):
    """Edge: how to replace component A with B (or with discrete combination)."""
    model_config = ConfigDict(extra="forbid")

    from_component: str
    to_components: list[str]  # one or many (discrete substitution)
    confidence: float = Field(ge=0.0, le=1.0)
    conditions: list[str] = Field(default_factory=list)
    constraints_check: str | None = None  # algorithm hint for solver
    provenance: list[Provenance] = Field(default_factory=list)


class Tool(BaseModel):
    """A physical tool used in projects."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^tool:[a-z0-9_-]+$")
    name: str
    category: str
    alternatives: list[str] = Field(default_factory=list)
    can_be_built_by_projects: list[str] = Field(default_factory=list)  # for daisy-chain solver
    skill_to_use: SkillLevel = SkillLevel.basic


class Skill(BaseModel):
    id: str = Field(pattern=r"^skill:[a-z0-9_-]+$")
    name: str
    prerequisite_skills: list[str] = Field(default_factory=list)
    learning_resources: list[str] = Field(default_factory=list)


class Goal(BaseModel):
    id: str = Field(pattern=r"^goal:[a-z0-9_-]+$")
    category: GoalCategory
    description: str
    typical_subgoals: list[str] = Field(default_factory=list)
    related_projects: list[str] = Field(default_factory=list)


class Material(BaseModel):
    """Consumable material (solder, flux, water, fuel)."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^mat:[a-z0-9_-]+$")
    name: str
    substitutes: list[str] = Field(default_factory=list)
    can_be_made_from: list[str] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────
# Inventory — runtime state of one user
# ──────────────────────────────────────────────────────────────────


class InventoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["device", "component", "tool", "material"]
    ref_id: str
    quantity: int = 1
    condition: Literal["working", "broken", "unknown"] = "unknown"
    notes: str | None = None


class UserProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona: Literal["newbie", "tinkerer", "engineer", "group_leader"] = "tinkerer"
    skills: list[str] = Field(default_factory=list)
    region: str | None = None
    locale: str = "en"
    inventory: list[InventoryEntry] = Field(default_factory=list)
    completed_projects: list[str] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────
# Solver I/O (used by Rust solver via JSON)
# ──────────────────────────────────────────────────────────────────


class SolverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str  # natural-language
    user: UserProfile
    constraints: dict[str, str] = Field(default_factory=dict)
    output_layers: list[Literal["L0","L1","L2","L3","L4","L5","L6","L7","L8","L9"]] = ["L0","L1","L2","L4","L5"]


class SolverPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    schema_version: str = SCHEMA_VERSION
    brief: str  # L0
    bom: list["SolvedBomLine"]  # L1
    teardown_checklists: dict[str, list[str]] = Field(default_factory=dict)  # device_id -> steps
    schematic_ascii: str | None = None  # L3
    schematic_svg: str | None = None
    assembly_steps: list[str] = Field(default_factory=list)  # L4
    firmware_code: str | None = None  # L5
    calibration: list[str] = Field(default_factory=list)  # L6
    maintenance: list[str] = Field(default_factory=list)  # L7
    safety_warnings: list[str] = Field(default_factory=list)
    estimated_hours: float | None = None
    daisy_chain_subplans: list["SolverPlan"] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Provenance] = Field(default_factory=list)


class SolvedBomLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: str
    component_name: str
    quantity: int
    sourced_from: list["SourcingOption"]
    chosen_source_index: int = 0


class SourcingOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    donor_device_id: str | None = None  # if extracted from a device user has
    fallback: Literal["substitute", "make_from_discretes", "user_must_acquire"] = "substitute"
    extraction_difficulty: ExtractionDifficulty | None = None
    damage_risk: DamageRisk | None = None
    notes: str | None = None


# Resolve forward refs
Project.model_rebuild()
SolverPlan.model_rebuild()
SolvedBomLine.model_rebuild()


# ──────────────────────────────────────────────────────────────────
# Validators (light-weight CSP — full check is in Rust)
# ──────────────────────────────────────────────────────────────────


def validate_project_bom_consistency(p: Project, components: dict[str, Component]) -> list[str]:
    """Quick sanity checks on a project's BOM. Returns list of issues."""
    issues = []
    for entry in p.required_components:
        if entry.component_id not in components:
            issues.append(f"Unknown component: {entry.component_id}")
        if entry.quantity <= 0:
            issues.append(f"Non-positive quantity for {entry.component_id}")
    return issues


# ──────────────────────────────────────────────────────────────────
# Sample (for tests)
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tl431 = Component(
        id="cmp:tl431",
        name="TL431 Programmable Shunt Regulator",
        type=ComponentType.ic_analog,
        aliases=["TL431A", "TL431AC", "Programmable Zener"],
        manufacturer_pns=["TL431ACDR", "TL431AID", "TL431BIDBVR"],
        package_options=["TO-92", "SOIC-8", "SOT-23"],
        appearance_descriptor=(
            "Three-terminal device, often TO-92 with flat front face marked 'TL431'. "
            "In SMD form usually SOT-23-3 marked 'TLY' or similar 3-char code."
        ),
        visual_aliases=["Looks like BC547 transistor in TO-92 — distinguished by 'TL431' marking."],
        typical_uses=["voltage reference", "PSU feedback", "battery charge cutoff"],
    )
    print(tl431.model_dump_json(indent=2))
