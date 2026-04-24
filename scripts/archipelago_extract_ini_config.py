#!/usr/bin/env python3
"""
Extract Archipelago.ini to Data/Archipelago config format (groups.json, presets.json).

Collapses explicit general-prefixed template names to base names for easy editing.
Run once to migrate from existing Archipelago.ini, or re-run after manual INI edits.

Usage:
  python archipelago_extract_ini_config.py [--output-dir PATH]
"""

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIPELAGO_INI = REPO_ROOT / "Data" / "INI" / "Archipelago.ini"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "Data" / "Archipelago"

# Import expansion logic from archipelago_expand_group_templates
import sys
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from archipelago_expand_group_templates import (
    parse_archipelago_ini,
    strip_known_general_prefix,
    resolve_to_canonical,
    KNOWN_PREFIX_LOWER,
)


def collapse_to_base_names(templates: list[str]) -> list[str]:
    """
    Collapse explicit template names to base names (one per unique core).
    Templates with general prefix (AirF_, Chem_, etc.) -> core name.
    Others (Upgrade_*, etc.) -> keep as-is.
    """
    seen = set()
    result = []
    for name in templates:
        if not name.strip():
            continue
        core_name, prefix = strip_known_general_prefix(name)
        canonical = resolve_to_canonical(core_name)
        if prefix is not None:
            # Had a general prefix - use core as base
            key = canonical
        else:
            # No prefix (Upgrade_*, etc.) - use full name
            key = name
        if key not in seen:
            seen.add(key)
            result.append(key)
    return sorted(result)


def extract_groups(ini_path: Path) -> dict:
    """Parse INI and return groups dict for groups.json."""
    groups = parse_archipelago_ini(ini_path)
    out = {}
    for g in groups:
        units = collapse_to_base_names(g.get("units") or [])
        buildings = collapse_to_base_names(g.get("buildings") or [])
        upgrades = collapse_to_base_names(g.get("upgrades") or [])
        commands = collapse_to_base_names(g.get("commands") or [])
        out[g["name"]] = {
            "display_name": g.get("display_name", ""),
            "faction": g.get("faction", "Shared"),
            "item_pool": bool(g.get("item_pool", True)),
            "units": units,
            "buildings": buildings,
            "upgrades": upgrades,
            "commands": commands,
        }
    return out


def extract_settings(ini_path: Path) -> dict:
    """Extract ArchipelagoSettings block from INI."""
    content = ini_path.read_text(encoding="utf-8", errors="replace")
    settings = {}
    if "ArchipelagoSettings" in content:
        idx = content.find("ArchipelagoSettings")
        end = content.find("End", idx)
        block = content[idx:end]
        for line in block.split("\n"):
            if "=" in line and not line.strip().startswith(";"):
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                if key and key != "ArchipelagoSettings":
                    settings[key] = val
    return settings


def main():
    ap = argparse.ArgumentParser(description="Extract Archipelago.ini to config format")
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                    help="Output directory for groups.json and presets.json")
    ap.add_argument("--ini", type=Path, default=ARCHIPELAGO_INI,
                    help="Path to Archipelago.ini")
    args = ap.parse_args()

    out_dir = args.output_dir if args.output_dir.is_absolute() else REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    groups = extract_groups(args.ini)
    settings = extract_settings(args.ini)

    group_order = list(groups.keys())

    groups_path = out_dir / "groups.json"
    groups_path.write_text(json.dumps(groups, indent=2, sort_keys=False), encoding="utf-8")
    print(f"Wrote {groups_path} ({len(groups)} groups)")

    presets = {
        "default": {
            "description": "Standard Archipelago groups (extracted from current INI)",
            "group_order": group_order,
            "settings": settings,
        },
        "minimal": {
            "description": "Fewer, larger groups for faster unlocks",
            "group_order": [
                "Upgrade_CaptureBuilding", "Upgrade_Radar", "Upgrade_Weapons", "Upgrade_Infantry",
                "Upgrade_Vehicles", "Upgrade_Aircraft", "Shared_Drones", "Shared_Barracks",
                "Shared_CommandCenters", "Shared_SupplyCenters", "Shared_BaseDefenses",
                "Upgrade_Mines", "Shared_AirFields", "Shared_StrategyBuildings",
                "Shared_AltMoneyBuildings", "Shared_Superweapons", "Shared_WarFactoriesArmsDealers",
                "Shared_MiscBuildings", "Shared_RifleInfantry", "Shared_RocketInfantry",
                "Shared_InfantryVehicles", "Shared_Tanks", "Shared_MachineGunVehicles",
                "Shared_Artillery", "Shared_PlaneTypeAircraft", "Shared_MiscVehicles",
                "Shared_MiscInfantry", "Shared_ComanchesHelixes", "Shared_MiscUnits",
            ],
            "settings": settings,
        },
        "chaos": {
            "description": "Maximum granularity - smallest possible groups",
            "group_order": group_order,
            "settings": settings,
        },
    }

    presets_path = out_dir / "presets.json"
    with open(presets_path, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2, sort_keys=False)
    print(f"Wrote {presets_path} ({len(presets)} presets)")


if __name__ == "__main__":
    main()
