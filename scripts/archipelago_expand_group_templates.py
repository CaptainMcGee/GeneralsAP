#!/usr/bin/env python3
"""
Expand Archipelago.ini groups with explicit general-prefixed template names.

The group fallback (ap_unlock_next_group) iterates ThingFactory at runtime.
Templates like Slth_GLAInfantrySaboteur, Chem_GLAScudStorm exist in the game
but are not in our Data/INI - they come from retail Zero Hour (INIZH.big).
This script adds them explicitly to the INI so UnlockRegistry finds them.

When using --dump-file, only spawnable units/buildings are used (filters out
projectiles, crates, hulks, nature props, civilians, etc.).

Usage:
  python archipelago_expand_group_templates.py                    # synthesize from base names
  python archipelago_expand_group_templates.py --dump-file PATH  # use game dump (filtered to spawnable)
  python archipelago_expand_group_templates.py --in-place       # overwrite Archipelago.ini
  python archipelago_expand_group_templates.py --dump-file X --output-filtered-dump Y  # write filtered dump to Y

Output: Archipelago.ini with expanded templates (or build/archipelago/archipelago_expanded.ini)
"""

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_INI = REPO_ROOT / "Data" / "INI"
ARCHIPELAGO_INI = DATA_INI / "Archipelago.ini"

# Matches ArchipelagoState.cpp stripKnownGeneralPrefix + isAllowedGeneralPrefixForFaction
USA_PREFIXES = ("AirF_", "Lazr_", "SupW_")
CHINA_PREFIXES = ("Tank_", "Infa_", "Nuke_")
GLA_PREFIXES = ("Demo_", "Slth_", "Toxin_", "Chem_")
FACTION_PREFIXES = {"USA": USA_PREFIXES, "China": CHINA_PREFIXES, "GLA": GLA_PREFIXES}

KNOWN_PREFIX_LOWER = frozenset(
    "airf lazr supw tank infa nuke demo slth toxin chem".split()
)

# Legacy -> canonical from ArchipelagoState.cpp resolveLegacyTemplateName
# GLAInfantrySaboteur: Zero Hour uses Saboteur in general variant names (Slth_GLAInfantrySaboteur)
LEGACY_TO_CANONICAL = {
    "GLASaboteur": "GLAInfantryHijacker",
    "GLAInfantrySaboteur": "GLAInfantryHijacker",
    "GLAHijacker": "GLAInfantryHijacker",
    "GLARebel": "GLAInfantryRebel",
    "GLAToxinRebel": "GLAInfantryRebel",
    "GLATerrorist": "GLAInfantryTerrorist",
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

# Canonical -> alternate base names that appear in Zero Hour general variants
# e.g. Slth_GLAInfantrySaboteur exists in game; GLAInfantrySaboteur is alternate for GLAInfantryHijacker
CANONICAL_TO_LEGACY_BASE = {
    "GLAInfantryHijacker": ["GLAInfantrySaboteur"],
}


def resolve_to_canonical(name: str) -> str:
    return LEGACY_TO_CANONICAL.get(name, name) if name else name


def strip_known_general_prefix(name: str) -> tuple[str, str | None]:
    pos = name.find("_")
    if pos == -1:
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


def expand_template_with_general_variants(name: str, include_legacy_bases: bool = True) -> set[str]:
    """Expand base template to include all general-prefixed variants + legacy base names."""
    canonical = resolve_to_canonical(name) if name else name
    if not canonical:
        return set()
    core_name, _ = strip_known_general_prefix(canonical)
    faction = detect_faction_from_core_name(core_name)
    if not faction or faction not in FACTION_PREFIXES:
        return {canonical}

    result = {canonical}
    bases_to_expand = [core_name]
    if include_legacy_bases and canonical in CANONICAL_TO_LEGACY_BASE:
        bases_to_expand.extend(CANONICAL_TO_LEGACY_BASE[canonical])

    for base in bases_to_expand:
        result.add(base)
        for prefix in FACTION_PREFIXES[faction]:
            result.add(prefix + base)

    return result


def parse_archipelago_ini(filepath: Path) -> list[dict]:
    """Parse Archipelago.ini and return list of groups."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    groups = []
    current = None

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("UnlockGroup "):
            if current and current.get("templates"):
                groups.append(current)
            name = stripped[len("UnlockGroup ") :].strip()
            current = {
                "name": name,
                "faction": "",
                "display_name": "",
                "item_pool": True,
                "units": [],
                "buildings": [],
                "upgrades": [],
                "commands": [],
                "templates": [],
                "is_building_group": False,
            }
            continue
        if current is None:
            continue
        if stripped in ("End", "END", "end"):
            if current.get("templates"):
                groups.append(current)
            current = None
            continue
        if "=" in stripped:
            key, _, val = stripped.partition("=")
            key = key.strip()
            val = val.strip()
            if key == "Faction":
                current["faction"] = val
            elif key == "DisplayName":
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                current["display_name"] = val
            elif key == "Units":
                current["is_building_group"] = False
                tokens = [t.strip() for t in re.split(r"[\s,]+", val) if t.strip()]
                current["units"] = tokens
                current["templates"] = current.get("templates", []) + tokens
            elif key == "Upgrades":
                current["is_building_group"] = False
                tokens = [t.strip() for t in re.split(r"[\s,]+", val) if t.strip()]
                current["upgrades"] = tokens
                current["templates"] = current.get("templates", []) + tokens
            elif key == "Commands":
                current["is_building_group"] = False
                tokens = [t.strip() for t in re.split(r"[\s,]+", val) if t.strip()]
                current["commands"] = tokens
                current["templates"] = current.get("templates", []) + tokens
            elif key == "Buildings":
                current["is_building_group"] = True
                tokens = [t.strip() for t in re.split(r"[\s,]+", val) if t.strip()]
                current["buildings"] = tokens
                current["templates"] = current.get("templates", []) + tokens
            elif key == "ItemPool":
                current["item_pool"] = val.lower() not in ("no", "false", "0", "off")

    return groups


def build_group_to_templates(groups: list[dict]) -> dict[str, set[str]]:
    """Map group name -> set of base templates (canonical names)."""
    result = {}
    for g in groups:
        result[g["name"]] = set(g["templates"])
    return result


def build_spawnable_allowed_set(groups: list[dict]) -> set[str]:
    """
    Build set of allowed template names from current Archipelago.ini groups.
    Only includes templates that belong to our groups (spawnable through normal means).
    Used to filter dump to exclude projectiles, crates, hulks, nature, civilians, etc.
    """
    allowed = set()
    for g in groups:
        for t in g.get("templates", []):
            allowed |= expand_template_with_general_variants(t)
    return allowed


def expand_groups(groups: list[dict], dump_file: Path | None, output_filtered_dump: Path | None = None) -> list[dict]:
    """Expand each group with explicit general-prefixed names."""
    group_to_bases = build_group_to_templates(groups)
    dump_assignments = {}  # gname -> {name: is_building}

    if dump_file and dump_file.exists():
        allowed_spawnable = build_spawnable_allowed_set(groups)
        dump_templates = []
        for line in dump_file.read_text(encoding="utf-8", errors="replace").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                name, typ = parts[0].strip(), parts[1].strip().lower()
                if name in allowed_spawnable:
                    dump_templates.append((name, typ == "building"))
        if output_filtered_dump:
            lines = ["# Filtered dump - spawnable units/buildings only\n", "# name\tunit|building\n"]
            for name, is_bld in sorted(dump_templates, key=lambda x: (not x[1], x[0])):
                lines.append(f"{name}\t{'building' if is_bld else 'unit'}\n")
            out = output_filtered_dump if output_filtered_dump.is_absolute() else REPO_ROOT / output_filtered_dump
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("".join(lines), encoding="utf-8")
            print(f"Wrote filtered dump ({len(dump_templates)} templates) to {out}")
        # Assign each dump template to a group; track unit vs building
        canonical_to_group = {}
        for gname, bases in group_to_bases.items():
            for b in bases:
                canonical = resolve_to_canonical(b)
                canonical_to_group[canonical] = gname
        for gname in group_to_bases:
            dump_assignments[gname] = {"units": set(), "buildings": set()}
        for name, is_building in dump_templates:
            core, _ = strip_known_general_prefix(name)
            canonical = resolve_to_canonical(core)
            if canonical in canonical_to_group:
                gname = canonical_to_group[canonical]
                if is_building:
                    dump_assignments[gname]["buildings"].add(name)
                else:
                    dump_assignments[gname]["units"].add(name)

    for g in groups:
        gname = g["name"]
        orig_units = set(g.get("units") or [])
        orig_buildings = set(g.get("buildings") or [])

        if gname in dump_assignments and (dump_assignments[gname]["units"] or dump_assignments[gname]["buildings"]):
            # Merge dump with synthesis: dump may miss some templates (e.g. GLAInfantryRebel)
            dump_units = dump_assignments[gname]["units"]
            dump_buildings = dump_assignments[gname]["buildings"]
            units = set(dump_units)
            buildings = set(dump_buildings)
            for base in orig_units:
                units |= expand_template_with_general_variants(base)
            for base in orig_buildings:
                buildings |= expand_template_with_general_variants(base)
            g["expanded_units"] = sorted(units)
            g["expanded_buildings"] = sorted(buildings)
        else:
            # Synthesize: expand each base; type comes from which list it was in
            units = set()
            buildings = set()
            for base in orig_units:
                units |= expand_template_with_general_variants(base)
            for base in orig_buildings:
                buildings |= expand_template_with_general_variants(base)
            g["expanded_units"] = sorted(units)
            g["expanded_buildings"] = sorted(buildings)

    return groups


def write_archipelago_ini(groups: list[dict], outpath: Path):
    """Write expanded Archipelago.ini."""
    lines = []
    lines.append("; Archipelago Randomizer Configuration for C&C Generals: Zero Hour")
    lines.append("; Defines unlock groups for units/buildings and starting general defaults.")
    lines.append("; Cross-faction groups: same unit/building types unlock together.")
    lines.append("; Explicit general-prefixed names (Slth_, Chem_, AirF_, etc.) for group fallback.")
    lines.append("")

    # Read original header (ArchipelagoSettings block)
    orig = ARCHIPELAGO_INI.read_text(encoding="utf-8", errors="replace")
    if "ArchipelagoSettings" in orig:
        idx = orig.find("ArchipelagoSettings")
        end = orig.find("End", idx) + 3
        lines.append(orig[idx:end].strip())
        lines.append("")

    for g in groups:
        lines.append(f"UnlockGroup {g['name']}")
        lines.append(f"    Faction = {g['faction']}")
        if g.get("display_name"):
            lines.append(f'    DisplayName = "{g["display_name"]}"')
        lines.append(f"    ItemPool = {'Yes' if g.get('item_pool', True) else 'No'}")
        if g.get("expanded_units"):
            lines.append("    Units = " + " ".join(g["expanded_units"]))
        if g.get("expanded_buildings"):
            lines.append("    Buildings = " + " ".join(g["expanded_buildings"]))
        if g.get("upgrades"):
            lines.append("    Upgrades = " + " ".join(g["upgrades"]))
        if g.get("commands"):
            lines.append("    Commands = " + " ".join(g["commands"]))
        lines.append("End")
        lines.append("")

    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Expand Archipelago.ini with explicit general-prefixed template names")
    ap.add_argument("--dump-file", type=Path, help="Path to ArchipelagoThingFactoryTemplates.txt from game dump")
    ap.add_argument("--in-place", action="store_true", help="Overwrite Archipelago.ini (default: write build/archipelago/archipelago_expanded.ini)")
    ap.add_argument("--output-filtered-dump", type=Path, help="Write filtered (spawnable-only) dump to this path")
    args = ap.parse_args()

    dump_path = args.dump_file
    if dump_path and not dump_path.is_absolute():
        dump_path = REPO_ROOT / dump_path

    groups = parse_archipelago_ini(ARCHIPELAGO_INI)
    groups = expand_groups(groups, dump_path, args.output_filtered_dump)

    if args.in_place:
        outpath = ARCHIPELAGO_INI
    else:
        outpath = REPO_ROOT / "build" / "archipelago" / "archipelago_expanded.ini"

    write_archipelago_ini(groups, outpath)
    print(f"Wrote {outpath}")

    if not args.in_place:
        print("Run with --in-place to overwrite Archipelago.ini")


if __name__ == "__main__":
    main()
