#!/usr/bin/env python3
"""ARK Final Assembler — Build the canonical knowledge-base artifact.

Loads every extracted device, project, donor link, and substitution chain,
deduplicates by ID (keeping the record with the highest
``extraction_confidence``), validates cross-references, and packages
everything into a versioned ``.tar.zst`` archive alongside a
``manifest.json``.

Features
--------
- **Deduplication**: when multiple records share the same ID, the one with
  the highest ``extraction_confidence`` wins.
- **Cross-reference validation**: warns about dangling project IDs, device
  IDs, or component canonical names in links, but never aborts.
- **Zstd compression**: fast, high-ratio compression for the final bundle.
- **Manifest generation**: JSON sidecar with counts, source list, and
  build timestamp.

Usage
-----
    python build_final.py --version 0.2 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import zstandard as zstd
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from common import (
    load_config,
    load_jsonl,
    log_extra,
    setup_logging,
    Device,
    Project,
    ProjectDonorLink,
    SubstitutionChain,
    KnowledgeBase,
    KBMetadata,
    ID_PREFIX_DEVICE,
    ID_PREFIX_PROJECT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXTRACTED_DEVICES = Path("/home/user/aisurvive/kb/output/extracted/devices")
EXTRACTED_PROJECTS = Path("/home/user/aisurvive/kb/output/extracted/projects")
LINKED_FILE = Path("/home/user/aisurvive/kb/output/linked/project-donors.jsonl")
SUBSTITUTIONS_FILE = Path("/home/user/aisurvive/kb/output/substitutions/substitutions.jsonl")
FINAL_DIR = Path("/home/user/aisurvive/kb/output/final")
CONSOLE = Console()

# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_devices() -> Tuple[Dict[str, Device], int]:
    """Load all extracted devices, deduplicated by ID.

    Returns:
        ``(id→Device mapping, number of duplicates dropped)``.
    """
    best: Dict[str, Device] = {}
    dupes = 0
    if not EXTRACTED_DEVICES.exists():
        return best, dupes
    for path in EXTRACTED_DEVICES.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            dev_data = data.get("device", data)
            dev = Device.model_validate(dev_data)
            existing = best.get(dev.id)
            if existing is None or dev.extraction_confidence > existing.extraction_confidence:
                if existing:
                    dupes += 1
                best[dev.id] = dev
        except (json.JSONDecodeError, ValidationError, KeyError):
            continue
    return best, dupes


def _load_projects() -> Tuple[Dict[str, Project], int]:
    """Load all extracted projects, deduplicated by ID.

    Returns:
        ``(id→Project mapping, number of duplicates dropped)``.
    """
    best: Dict[str, Project] = {}
    dupes = 0
    if not EXTRACTED_PROJECTS.exists():
        return best, dupes
    for path in EXTRACTED_PROJECTS.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            prj_data = data.get("project", data)
            prj = Project.model_validate(prj_data)
            existing = best.get(prj.id)
            if existing is None or prj.extraction_confidence > existing.extraction_confidence:
                if existing:
                    dupes += 1
                best[prj.id] = prj
        except (json.JSONDecodeError, ValidationError, KeyError):
            continue
    return best, dupes


def _load_links() -> List[ProjectDonorLink]:
    """Load all validated donor links from the JSONL file.

    Returns:
        List of ``ProjectDonorLink`` models.
    """
    links: List[ProjectDonorLink] = []
    if not LINKED_FILE.exists():
        return links
    for record in load_jsonl(LINKED_FILE):
        try:
            links.append(ProjectDonorLink.model_validate(record))
        except ValidationError:
            continue
    return links


def _load_substitutions() -> List[SubstitutionChain]:
    """Load all validated substitution chains from the JSONL file.

    Returns:
        List of ``SubstitutionChain`` models.
    """
    chains: List[SubstitutionChain] = []
    if not SUBSTITUTIONS_FILE.exists():
        return chains
    for record in load_jsonl(SUBSTITUTIONS_FILE):
        # Remove internal tracking fields before validation
        record.pop("_batch_hash", None)
        try:
            chains.append(SubstitutionChain.model_validate(record))
        except ValidationError:
            continue
    # Deduplicate by component name (keep first)
    seen: Set[str] = set()
    unique: List[SubstitutionChain] = []
    for chain in chains:
        if chain.component not in seen:
            seen.add(chain.component)
            unique.append(chain)
    return unique


# ---------------------------------------------------------------------------
# Cross-reference validation
# ---------------------------------------------------------------------------


def _validate_cross_references(
    devices: Dict[str, Device],
    projects: Dict[str, Project],
    links: List[ProjectDonorLink],
    logger: Any,
) -> Tuple[int, int, int]:
    """Validate that every referenced ID exists in the appropriate collection.

    Warns about:
    - ``project_id`` in links missing from ``projects``
    - ``donor_device_id`` in links missing from ``devices``
    - ``component_canonical`` referenced in links but absent from all devices

    Args:
        devices: Loaded devices.
        projects: Loaded projects.
        links: All donor links.
        logger: Logger for warnings.

    Returns:
        ``(missing_projects, missing_devices, missing_components)`` counts.
    """
    missing_projects = 0
    missing_devices = 0
    missing_components = 0

    # Collect all known component canonicals from devices
    known_components: Set[str] = set()
    for dev in devices.values():
        for comp in dev.components_inside:
            known_components.add(comp.component_canonical)

    for link in links:
        if link.project_id not in projects:
            logger.warning(
                "Dangling project_id in link",
                extra=log_extra(project_id=link.project_id, donor=link.donor_device_id),
            )
            missing_projects += 1

        if link.donor_device_id not in devices:
            logger.warning(
                "Dangling donor_device_id in link",
                extra=log_extra(donor_device_id=link.donor_device_id, project=link.project_id),
            )
            missing_devices += 1

        for sc in link.supplied_components:
            if sc.component_class not in known_components:
                # This is a soft warning — the component might come from a project BOM
                logger.warning(
                    "component_canonical not found in any device",
                    extra=log_extra(component=sc.component_class, link_project=link.project_id),
                )
                missing_components += 1

    return missing_projects, missing_devices, missing_components


# ---------------------------------------------------------------------------
# Packaging
# ---------------------------------------------------------------------------


def _build_archive(
    kb: KnowledgeBase,
    version: str,
    final_dir: Path,
    logger: Any,
    dry_run: bool = False,
) -> Path:
    """Package the knowledge base into a zstd-compressed tar archive.

    Writes:
    - ``ark-kb-v{version}.json`` (pretty-printed)
    - ``ark-kb-v{version}.tar.zst`` (compressed bundle)
    - ``manifest.json`` (sidecar metadata)

    Args:
        kb: Assembled knowledge base.
        version: Version string for the file name.
        final_dir: Output directory.
        logger: Logger.
        dry_run: If ``True``, skip writing files.

    Returns:
        Path to the compressed archive.
    """
    final_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"ark-kb-v{version}"
    json_path = final_dir / f"{base_name}.json"
    tar_path = final_dir / f"{base_name}.tar.zst"
    manifest_path = final_dir / "manifest.json"

    if dry_run:
        logger.info("[dry-run] Would write", extra=log_extra(
            json=str(json_path), tar=str(tar_path), manifest=str(manifest_path),
        ))
        return tar_path

    # Serialize pretty JSON
    kb_json = kb.model_dump_json(indent=2)
    json_path.write_text(kb_json, encoding="utf-8")

    # Build tar.zst
    cctx = zstd.ZstdCompressor(level=3, threads=os.cpu_count() or 1)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_json = Path(tmpdir) / f"{base_name}.json"
        tmp_json.write_text(kb_json, encoding="utf-8")
        with tarfile.open(tar_path, "w") as tar:
            tar.add(tmp_json, arcname=tmp_json.name)
        # Re-compress the tar with zstd for smaller size
        raw_tar = tar_path.read_bytes()
        tar_path.write_bytes(cctx.compress(raw_tar))

    # Manifest
    kb_dict = kb.model_dump()
    manifest: Dict[str, Any] = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources": kb.metadata.sources,
        "counts": {
            "devices": len(kb.devices),
            "projects": len(kb.projects),
            "components": sum(len(d.components_inside) for d in kb.devices),
            "links": len(kb.links),
            "substitutions": len(kb.substitutions),
        },
        "files": {
            "json": str(json_path),
            "tar_zst": str(tar_path),
        },
        "size_bytes": {
            "json": json_path.stat().st_size,
            "tar_zst": tar_path.stat().st_size,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.info("Archive built", extra=log_extra(
        tar=str(tar_path),
        json_size=json_path.stat().st_size,
        tar_size=tar_path.stat().st_size,
    ))
    return tar_path


# ---------------------------------------------------------------------------
# Stats printer
# ---------------------------------------------------------------------------


def _print_stats(
    devices: Dict[str, Device],
    projects: Dict[str, Project],
    links: List[ProjectDonorLink],
    substitutions: List[SubstitutionChain],
    dupes_dev: int,
    dupes_prj: int,
    missing_proj: int,
    missing_dev: int,
    missing_comp: int,
    archive_path: Path,
) -> None:
    """Print a rich summary table to the console."""
    total_components = sum(len(d.components_inside) for d in devices.values())
    table = Table(title="ARK Knowledge Base — Final Assembly")
    table.add_column("Entity", style="cyan")
    table.add_column("Count", justify="right", style="magenta")
    table.add_column("Notes", style="dim")
    table.add_row("Devices", str(len(devices)), f"{dupes_dev} dupes dropped")
    table.add_row("Components", str(total_components), "inside devices")
    table.add_row("Projects", str(len(projects)), f"{dupes_prj} dupes dropped")
    table.add_row("Donor Links", str(len(links)), "")
    table.add_row("Substitutions", str(len(substitutions)), "unique chains")
    table.add_row("Missing refs", f"P:{missing_proj} D:{missing_dev} C:{missing_comp}", "warnings only")
    table.add_row("Archive", str(archive_path.name), f"{archive_path.stat().st_size / 1024 / 1024:.1f} MB")
    CONSOLE.print(table)


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------


def main(argv: List[str] | None = None) -> int:
    """Entry point for the final assembler.

    Args:
        argv: CLI args.

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(description="ARK Final Assembler")
    parser.add_argument("--version", default="0.1", help="KB version tag")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    logger = setup_logging(
        level=config.get("logging", {}).get("level", "INFO"),
        log_dir=FINAL_DIR / "logs",
        script_name="build_final",
    )
    logger.info("Starting final assembly", extra=log_extra(version=args.version, dry_run=args.dry_run))

    # Load
    CONSOLE.print("[dim]Loading devices...[/dim]")
    devices_map, dupes_dev = _load_devices()
    CONSOLE.print(f"[dim]  → {len(devices_map)} devices (dropped {dupes_dev} dupes)[/dim]")

    CONSOLE.print("[dim]Loading projects...[/dim]")
    projects_map, dupes_prj = _load_projects()
    CONSOLE.print(f"[dim]  → {len(projects_map)} projects (dropped {dupes_prj} dupes)[/dim]")

    CONSOLE.print("[dim]Loading links...[/dim]")
    links = _load_links()
    CONSOLE.print(f"[dim]  → {len(links)} links[/dim]")

    CONSOLE.print("[dim]Loading substitutions...[/dim]")
    substitutions = _load_substitutions()
    CONSOLE.print(f"[dim]  → {len(substitutions)} substitution chains[/dim]")

    # Validate
    CONSOLE.print("[dim]Validating cross-references...[/dim]")
    missing_proj, missing_dev, missing_comp = _validate_cross_references(
        devices_map, projects_map, links, logger,
    )

    # Build KB
    sources = []
    if EXTRACTED_DEVICES.exists():
        sources.append("ifixit_teardowns")
    if EXTRACTED_PROJECTS.exists():
        sources.append("instructables_hackaday_projects")

    metadata = KBMetadata(
        version=args.version,
        created_at=datetime.now(timezone.utc),
        total_devices=len(devices_map),
        total_projects=len(projects_map),
        total_components=sum(len(d.components_inside) for d in devices_map.values()),
        total_links=len(links),
        sources=sources,
    )

    kb = KnowledgeBase(
        devices=list(devices_map.values()),
        projects=list(projects_map.values()),
        links=links,
        substitutions=substitutions,
        metadata=metadata,
    )

    # Package
    archive_path = _build_archive(kb, args.version, FINAL_DIR, logger, dry_run=args.dry_run)

    # Report
    _print_stats(
        devices_map, projects_map, links, substitutions,
        dupes_dev, dupes_prj, missing_proj, missing_dev, missing_comp,
        archive_path,
    )

    logger.info(
        "Final assembly complete",
        extra=log_extra(
            devices=len(devices_map),
            projects=len(projects_map),
            links=len(links),
            substitutions=len(substitutions),
            archive=str(archive_path),
        ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
