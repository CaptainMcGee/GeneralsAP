#!/usr/bin/env python3
"""
Audit Archipelago unlock groups against all spawnable units/buildings.

Excludes denylisted non-spawnable templates so the audit reflects the actual playable
Archipelago pool. Fails if denylisted templates survive into Data/INI/Archipelago.ini.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from archipelago_data_helpers import default_game_asset_path, is_denied_template, load_non_spawnable_templates

DATA_INI = REPO_ROOT / "Data" / "INI"
FACTION_UNIT = default_game_asset_path(Path("Data") / "INI" / "Object" / "FactionUnit.ini")
FACTION_BUILDING = default_game_asset_path(Path("Data") / "INI" / "Object" / "FactionBuilding.ini")
ARCHIPELAGO_INI = DATA_INI / "Archipelago.ini"
OUTPUT_REPORT = REPO_ROOT / "build" / "archipelago" / "archipelago_audit_report.md"
OUTPUT_LEFTOVERS = REPO_ROOT / "build" / "archipelago" / "archipelago_leftovers.txt"

EXCLUDE_PREFIXES = ("GC_", "CINE_", "Boss_")
VALID_SIDES = frozenset(("America", "China", "GLA"))
EXCLUDE_KINDOF_UNIT = frozenset(
    x.upper() for x in ("PARACHUTE", "PROJECTILE", "HULK", "MINE", "UNATTACKABLE")
)
EXCLUDE_NAME_CONTAINS = (
    "BogusTarget",
    "CinematicVersion",
    "Debris",
    "Rubble",
    "DeadHull",
    "Blades",
)
KNOWN_PREFIX_LOWER = frozenset("airf lazr supw tank infa nuke demo slth toxin chem".split())
FACTION_PREFIXES = {
    "USA": ("AirF_", "Lazr_", "SupW_"),
    "China": ("Tank_", "Infa_", "Nuke_"),
    "GLA": ("Demo_", "Slth_", "Toxin_", "Chem_"),
}
LEGACY_TO_CANONICAL = {
    "AmericaPathfinder": "AmericaInfantryPathfinder",
    "AmericaColonelBurton": "AmericaInfantryColonelBurton",
    "AmericaHumvee": "AmericaVehicleHumvee",
    "AmericaTOWMissileHumvee": "AmericaVehicleHumvee",
    "AmericaCrusaderTank": "AmericaTankCrusader",
    "AmericaLaserTank": "AmericaTankCrusader",
    "AmericaPaladinTank": "AmericaTankPaladin",
    "AmericaTomahawk": "AmericaVehicleTomahawk",
    "AmericaAmbulance": "AmericaVehicleMedic",
    "AmericaSentryDroneRobot": "AmericaVehicleBattleDrone",
    "AmericaComanche": "AmericaVehicleComanche",
    "AmericaJetAuroraAlpha": "AmericaJetAurora",
    "ChinaHacker": "ChinaInfantryHacker",
    "ChinaSuperHacker": "ChinaInfantryHacker",
    "ChinaBlackLotus": "ChinaInfantryBlackLotus",
    "ChinaBattlemaster": "ChinaTankBattleMaster",
    "ChinaEmperorBattlemaster": "ChinaTankBattleMaster",
    "ChinaDragonTank": "ChinaTankDragon",
    "ChinaGatlingTank": "ChinaTankGattling",
    "ChinaInfernoCannon": "ChinaVehicleInfernoCannon",
    "ChinaOverlord": "ChinaTankOverlord",
    "ChinaEmperorOverlord": "ChinaTankOverlord",
    "ChinaTroopCrawler": "ChinaVehicleTroopCrawler",
    "ChinaNukeCannon": "ChinaVehicleNukeLauncher",
    "GLARebel": "GLAInfantryRebel",
    "GLAToxinRebel": "GLAInfantryRebel",
    "GLATerrorist": "GLAInfantryTerrorist",
    "GLAHijacker": "GLAInfantryHijacker",
    "GLASaboteur": "GLAInfantryHijacker",
    "GLAJarmenKell": "GLAInfantryJarmenKell",
    "GLAAngryMob": "GLAInfantryAngryMobNexus",
    "GLATechnical": "GLAVehicleTechnical",
    "GLAScorpionTank": "GLATankScorpion",
    "GLAMarauderTank": "GLATankMarauder",
    "GLAQuadCannon": "GLAVehicleQuadCannon",
    "GLARocketBuggy": "GLAVehicleRocketBuggy",
    "GLAToxinTractor": "GLAVehicleToxinTruck",
    "GLABombTruck": "GLAVehicleBombTruck",
    "GLAScudLauncher": "GLAVehicleScudLauncher",
    "GLABattleBus": "GLAVehicleTechnical",
}


def resolve_to_canonical(name: str) -> str:
    return LEGACY_TO_CANONICAL.get(name, name) if name else name



def strip_known_general_prefix(name: str) -> tuple[str, str | None]:
    pos = name.find("_")
    if pos < 0:
        return (name, None)
    prefix = name[:pos].lower()
    if prefix in KNOWN_PREFIX_LOWER:
        return (name[pos + 1 :], prefix)
    return (name, None)



def detect_faction_from_core_name(core_name: str) -> str | None:
    lower = core_name.lower()
    if lower.startswith("america"):
        return "USA"
    if lower.startswith("china"):
        return "China"
    if lower.startswith("gla"):
        return "GLA"
    return None



def expand_template_with_general_variants(name: str) -> set[str]:
    canonical = resolve_to_canonical(name) if name else name
    if not canonical:
        return set()
    core_name, existing_prefix = strip_known_general_prefix(canonical)
    if existing_prefix is not None:
        return {canonical}
    faction = detect_faction_from_core_name(core_name)
    if not faction or faction not in FACTION_PREFIXES:
        return {canonical}
    result = {canonical}
    for prefix in FACTION_PREFIXES[faction]:
        result.add(prefix + core_name)
    return result



def parse_ini_objects(filepath: Path) -> list[dict[str, str]]:
    objects: list[dict[str, str]] = []
    content = filepath.read_text(encoding="utf-8", errors="replace")
    parent_attrs: dict[str, dict[str, str]] = {}

    block_pattern = re.compile(r"^Object\s+(\w+)\s*\n(.*?)^End\s*$", re.MULTILINE | re.DOTALL)
    for match in block_pattern.finditer(content):
        name = match.group(1).strip()
        body = match.group(2)
        kindof = ""
        buildable = ""
        side = ""
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if line.startswith("KindOf"):
                kindof = re.sub(r"KindOf\s*=\s*", "", line, flags=re.I).strip()
            elif line.startswith("Buildable"):
                buildable = re.sub(r"Buildable\s*=\s*", "", line, flags=re.I).strip()
            elif line.startswith("Side"):
                side = re.sub(r"Side\s*=\s*", "", line, flags=re.I).strip().split()[0] if line else ""
        obj = {
            "name": name,
            "kindof": kindof.upper() if kindof else "",
            "buildable": buildable,
            "side": side,
        }
        objects.append(obj)
        parent_attrs[name] = obj

    reskin_pattern = re.compile(r"^ObjectReskin\s+(\w+)\s+(\w+)\s*\n(.*?)^End\s*$", re.MULTILINE | re.DOTALL)
    for match in reskin_pattern.finditer(content):
        child_name = match.group(1).strip()
        parent_name = match.group(2).strip()
        parent = parent_attrs.get(parent_name, {})
        objects.append(
            {
                "name": child_name,
                "kindof": parent.get("kindof", ""),
                "buildable": parent.get("buildable", ""),
                "side": parent.get("side", ""),
            }
        )

    return objects



def is_spawnable_unit(obj: dict[str, str]) -> bool:
    name = obj["name"]
    if any(name.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return False
    if obj["buildable"] and obj["buildable"].upper().startswith("NO"):
        return False
    if not obj["side"] or obj["side"] not in VALID_SIDES:
        return False
    kindof_tokens = set(obj["kindof"].split()) if obj["kindof"] else set()
    if kindof_tokens & EXCLUDE_KINDOF_UNIT:
        return False
    for marker in EXCLUDE_NAME_CONTAINS:
        if marker.lower() in name.lower():
            return False
    return True



def is_spawnable_building(obj: dict[str, str]) -> bool:
    name = obj["name"]
    if any(name.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return False
    if obj["buildable"] and obj["buildable"].upper().startswith("NO"):
        return False
    if not obj["side"] or obj["side"] not in VALID_SIDES:
        return False
    if "STRUCTURE" not in (obj["kindof"] or "").upper():
        return False
    if "Hole" in name or "Debris" in name or "Rubble" in name:
        return False
    return True



def parse_archipelago_groups(filepath: Path) -> dict[str, dict[str, list[str] | str]]:
    groups: dict[str, dict[str, list[str] | str]] = {}
    content = filepath.read_text(encoding="utf-8", errors="replace")
    block_pattern = re.compile(r"^UnlockGroup\s+(\w+)\s*\n(.*?)^End\s*$", re.MULTILINE | re.DOTALL)
    for match in block_pattern.finditer(content):
        group_name = match.group(1)
        body = match.group(2)
        units: list[str] = []
        buildings: list[str] = []
        upgrades: list[str] = []
        commands: list[str] = []
        faction = ""
        item_pool = "Yes"
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if line.startswith("Units"):
                value = re.sub(r"Units\s*=\s*", "", line, flags=re.I).strip().split(";", 1)[0].strip()
                units = [item for item in re.split(r"[\s,]+", value) if item]
            elif line.startswith("Buildings"):
                value = re.sub(r"Buildings\s*=\s*", "", line, flags=re.I).strip().split(";", 1)[0].strip()
                buildings = [item for item in re.split(r"[\s,]+", value) if item]
            elif line.startswith("Upgrades"):
                value = re.sub(r"Upgrades\s*=\s*", "", line, flags=re.I).strip().split(";", 1)[0].strip()
                upgrades = [item for item in re.split(r"[\s,]+", value) if item]
            elif line.startswith("Commands"):
                value = re.sub(r"Commands\s*=\s*", "", line, flags=re.I).strip().split(";", 1)[0].strip()
                commands = [item for item in re.split(r"[\s,]+", value) if item]
            elif line.startswith("Faction"):
                faction = re.sub(r"Faction\s*=\s*", "", line, flags=re.I).strip()
            elif line.startswith("ItemPool"):
                item_pool = re.sub(r"ItemPool\s*=\s*", "", line, flags=re.I).strip()
        groups[group_name] = {"units": units, "buildings": buildings, "upgrades": upgrades, "commands": commands, "faction": faction, "item_pool": item_pool}
    return groups



def faction_of(name: str) -> str:
    core, _ = strip_known_general_prefix(name)
    if core.lower().startswith("america"):
        return "USA"
    if core.lower().startswith("china"):
        return "China"
    if core.lower().startswith("gla"):
        return "GLA"
    return "Shared"



def build_spawnable_pool(base_names: set[str], denied: set[str], kind: str) -> tuple[set[str], dict[str, str]]:
    expanded_pool: set[str] = set()
    name_to_type: dict[str, str] = {}
    for name in sorted(base_names):
        for expanded in expand_template_with_general_variants(name):
            if is_denied_template(expanded, denied):
                continue
            expanded_pool.add(expanded)
            name_to_type[expanded] = kind
    return expanded_pool, name_to_type



def main() -> int:
    denied = load_non_spawnable_templates()

    print("Parsing FactionUnit.ini...")
    unit_objs = parse_ini_objects(FACTION_UNIT)
    base_units = {
        obj["name"] for obj in unit_objs if is_spawnable_unit(obj) and not is_denied_template(obj["name"], denied)
    }

    print("Parsing FactionBuilding.ini...")
    building_objs = parse_ini_objects(FACTION_BUILDING)
    base_buildings = {
        obj["name"] for obj in building_objs if is_spawnable_building(obj) and not is_denied_template(obj["name"], denied)
    }

    spawnable_units, name_to_type = build_spawnable_pool(base_units, denied, "unit")
    spawnable_buildings, building_type_map = build_spawnable_pool(base_buildings, denied, "building")
    name_to_type.update(building_type_map)
    all_spawnable = spawnable_units | spawnable_buildings

    print("Parsing Archipelago.ini...")
    groups = parse_archipelago_groups(ARCHIPELAGO_INI)

    assigned: set[str] = set()
    denylisted_in_groups: set[str] = set()
    for group_name, group in groups.items():
        for template in list(group["units"]) + list(group["buildings"]) + list(group["upgrades"]) + list(group["commands"]):
            if is_denied_template(template, denied):
                denylisted_in_groups.add(template)
            for expanded in expand_template_with_general_variants(template):
                if is_denied_template(expanded, denied):
                    denylisted_in_groups.add(expanded)
                    continue
                assigned.add(expanded)

    leftovers = sorted(all_spawnable - assigned)
    leftover_units = [name for name in leftovers if name_to_type.get(name) == "unit"]
    leftover_buildings = [name for name in leftovers if name_to_type.get(name) == "building"]

    lines: list[str] = []
    lines.append("# Archipelago Unlock Groups Audit Report\n")
    lines.append("Generated by `archipelago_audit_groups.py`.\n")
    lines.append(f"- **Base spawnable (from INI, after denylist):** {len(base_units)} units, {len(base_buildings)} buildings")
    lines.append(f"- **Total spawnable (including general variants, after denylist):** {len(spawnable_units)} units, {len(spawnable_buildings)} buildings")
    lines.append(f"- **Assigned to groups:** {len(assigned & all_spawnable)}")
    lines.append(f"- **Leftovers (unassigned):** {len(leftovers)}")
    lines.append(f"- **Denylisted templates excluded from audit:** {len(denied)}\n")

    if denylisted_in_groups:
        lines.append("## Errors\n")
        lines.append("The following denylisted templates still appear in `Data/INI/Archipelago.ini` and must be removed from generation inputs:\n")
        for template in sorted(denylisted_in_groups):
            lines.append(f"- `{template}`")
        lines.append("")

    lines.append("---\n## Current Groups (from Archipelago.ini)\n")
    for group_name, group in sorted(groups.items()):
        lines.append(f"### {group_name} (Faction: {group['faction']}, ItemPool: {group['item_pool']})")
        if group["units"]:
            lines.append("- **Units:** " + ", ".join(group["units"]))
        if group["buildings"]:
            lines.append("- **Buildings:** " + ", ".join(group["buildings"]))
        if group["upgrades"]:
            lines.append("- **Upgrades:** " + ", ".join(group["upgrades"]))
        if group["commands"]:
            lines.append("- **Commands:** " + ", ".join(group["commands"]))
        lines.append("")

    lines.append("---\n## Leftovers (not in any group)\n")
    lines.append("Copy these into `groups.json` if they should become Archipelago unlockables.\n")

    for faction in ("USA", "China", "GLA", "Shared"):
        faction_units = [name for name in leftover_units if faction_of(name) == faction]
        faction_buildings = [name for name in leftover_buildings if faction_of(name) == faction]
        if not faction_units and not faction_buildings:
            continue
        lines.append(f"### {faction}")
        if faction_units:
            lines.append("**Units:**")
            for unit in faction_units:
                lines.append(f"- {unit}")
        if faction_buildings:
            lines.append("**Buildings:**")
            for building in faction_buildings:
                lines.append(f"- {building}")
        lines.append("")

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT_REPORT}")

    leftover_lines = ["# Leftover templates for manual assignment\n"]
    leftover_lines.extend(leftover_units)
    leftover_lines.append("")
    leftover_lines.extend(leftover_buildings)
    OUTPUT_LEFTOVERS.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_LEFTOVERS.write_text("\n".join(leftover_lines), encoding="utf-8")
    print(f"Wrote {OUTPUT_LEFTOVERS}")

    if denylisted_in_groups:
        print("ERROR: Denylisted templates remain in Data/INI/Archipelago.ini", file=sys.stderr)
        for template in sorted(denylisted_in_groups):
            print(f"  - {template}", file=sys.stderr)
        return 1

    print("OK: Audit completed with denylist applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

