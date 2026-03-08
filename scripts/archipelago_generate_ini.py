#!/usr/bin/env python3
"""
Generate Archipelago.ini from Data/Archipelago config (groups.json, presets.json).

Expands base template names to explicit general-prefixed variants. Supports presets,
options overrides, and future Archipelago YAML option schema integration.

Usage:
  python archipelago_generate_ini.py [--preset NAME] [--output PATH] [--config-dir PATH]
  python archipelago_generate_ini.py --preset minimal
  python archipelago_generate_ini.py --options seed_options.yaml  # future: apply YAML options

Environment:
  ARCHIPELAGO_PRESET  - default preset if --preset not given
  ARCHIPELAGO_CONFIG_DIR - config directory (default: Data/Archipelago)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from archipelago_expand_group_templates import expand_template_with_general_variants
from archipelago_data_helpers import default_game_asset_path, ensure_no_denied_templates, load_non_spawnable_templates

DEFAULT_CONFIG_DIR = REPO_ROOT / "Data" / "Archipelago"
DEFAULT_OUTPUT = REPO_ROOT / "Data" / "INI" / "Archipelago.ini"
DEFAULT_VALIDATED_REFERENCE_INI = (
    REPO_ROOT
    / "Data"
    / "Archipelago"
    / "runtime_profiles"
    / "reference-clean"
    / "Data"
    / "INI"
    / "Archipelago.ini"
)
FACTION_BUILDING = default_game_asset_path(Path("Data") / "INI" / "Object" / "FactionBuilding.ini")

KNOWN_PREFIX_LOWER = frozenset(
    "airf lazr supw tank infa nuke demo slth toxin chem".split()
)

def strip_known_general_prefix(name: str) -> tuple[str, str | None]:
    """Return (base_name, prefix or None)."""
    pos = name.find("_")
    if pos == -1:
        return (name, None)
    prefix = name[:pos].lower()
    if prefix in KNOWN_PREFIX_LOWER:
        return (name[pos + 1 :], prefix)
    return (name, None)



def load_building_names(filepath: Path = FACTION_BUILDING) -> set[str]:
    """Extract Object and ObjectReskin names from FactionBuilding.ini."""
    names: set[str] = set()
    if not filepath.exists():
        print(
            f"Warning: {filepath} not found; by_display_name templates will be classified as units.",
            file=sys.stderr,
        )
        return names
    content = filepath.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"^Object\s+(\w+)\s*\n", content, re.MULTILINE):
        names.add(m.group(1))
    for m in re.finditer(r"^ObjectReskin\s+(\w+)\s+\w+\s*\n", content, re.MULTILINE):
        names.add(m.group(1))
    return names



def load_groups(config_dir: Path) -> dict:
    """Load groups.json."""
    path = config_dir / "groups.json"
    if not path.exists():
        raise FileNotFoundError(f"groups.json not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))



def load_presets(config_dir: Path) -> dict:
    """Load presets.json."""
    path = config_dir / "presets.json"
    if not path.exists():
        raise FileNotFoundError(f"presets.json not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))



def load_always_unlocked(config_dir: Path) -> dict:
    """Load always_unlocked.json. Returns {units: [...], buildings: [...]} or empty dict."""
    path = config_dir / "always_unlocked.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"units": data.get("units", []), "buildings": data.get("buildings", [])}



def load_display_names(config_dir: Path) -> dict[str, list[str]]:
    """Load display_names.json (display name -> template list). Returns {} if missing."""
    path = config_dir / "display_names.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if isinstance(v, list) and not k.startswith("_")}


def load_validated_group_names(ini_path: Path) -> set[str]:
    if not ini_path.exists():
        return set()

    content = ini_path.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"^UnlockGroup\s+(\S+)\s*$", content, re.MULTILINE))



def expand_templates(templates: list[str]) -> set[str]:
    """Expand base names to explicit general-prefixed variants."""
    result = set()
    for name in templates:
        if name.strip():
            result |= expand_template_with_general_variants(name)
    return result


def split_non_building_members(templates: list[str]) -> tuple[list[str], list[str], list[str]]:
    units: list[str] = []
    upgrades: list[str] = []
    commands: list[str] = []
    for name in templates:
        if not name or not name.strip():
            continue
        if name.startswith("Upgrade_"):
            upgrades.append(name)
        elif name.startswith("Command_"):
            commands.append(name)
        else:
            units.append(name)
    return (units, upgrades, commands)



def resolve_display_names(
    display_names: list[str],
    display_to_templates: dict[str, list[str]],
    building_names: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """
    Resolve display names (e.g. OBJECT:Ranger) to template lists.
    Returns (units, buildings). Uses FactionBuilding.ini Object names when
    building_names provided; otherwise falls back to heuristic.
    """
    if building_names is None:
        building_names = load_building_names()
    units, buildings = [], []
    for dn in display_names:
        templates = display_to_templates.get(dn, [])
        for t in templates:
            if t.startswith("Upgrade_") or t.startswith("Command_"):
                units.append(t)
            else:
                base, _ = strip_known_general_prefix(t)
                if base in building_names:
                    buildings.append(t)
                else:
                    units.append(t)
    return units, buildings



def resolve_group_templates(
    groups_def: dict,
    gname: str,
    display_to_templates: dict[str, list[str]],
    seen: set | None = None,
    building_names: set[str] | None = None,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Resolve a group's units and buildings.
    Supports: units, buildings, include, by_display_name (in-game names).
    Templates sharing a display name are always tied together.
    """
    seen = seen or set()
    if gname in seen:
        return [], []
    seen.add(gname)
    g = groups_def.get(gname, {})
    raw_units = list(g.get("units") or [])
    buildings = list(g.get("buildings") or [])
    upgrades = list(g.get("upgrades") or [])
    commands = list(g.get("commands") or [])
    units, inferred_upgrades, inferred_commands = split_non_building_members(raw_units)
    upgrades.extend(inferred_upgrades)
    commands.extend(inferred_commands)

    for dn in g.get("by_display_name", []) or []:
        dn_units, dn_buildings = resolve_display_names(
            [dn], display_to_templates, building_names
        )
        typed_units, typed_upgrades, typed_commands = split_non_building_members(dn_units)
        units.extend(typed_units)
        upgrades.extend(typed_upgrades)
        commands.extend(typed_commands)
        buildings.extend(dn_buildings)

    for inc in g.get("include", []) or []:
        inc_units, inc_buildings, inc_upgrades, inc_commands = resolve_group_templates(
            groups_def, inc, display_to_templates, seen, building_names
        )
        units.extend(inc_units)
        buildings.extend(inc_buildings)
        upgrades.extend(inc_upgrades)
        commands.extend(inc_commands)

    return units, buildings, upgrades, commands



def build_ini_groups(
    groups_def: dict,
    preset: dict,
    display_to_templates: dict[str, list[str]],
    building_names: set[str] | None = None,
    denylist: set[str] | None = None,
    validated_group_names: set[str] | None = None,
) -> list[dict]:
    """
    Build list of group dicts for INI output.
    Supports units, buildings, include, by_display_name (in-game names).
    """
    if building_names is None:
        building_names = load_building_names()
    denylist = denylist or set()
    group_order = preset.get("group_order", list(groups_def.keys()))
    result = []
    for gname in group_order:
        if gname not in groups_def:
            print(f"Warning: preset references group '{gname}' not in groups.json", file=sys.stderr)
            continue
        if validated_group_names and gname not in validated_group_names:
            continue
        g = groups_def[gname]
        units, buildings, upgrades, commands = resolve_group_templates(
            groups_def, gname, display_to_templates, building_names=building_names
        )
        ensure_no_denied_templates(units + buildings + upgrades + commands, denylist, f"UnlockGroup {gname}")
        units = expand_templates(units)
        buildings = expand_templates(buildings)
        upgrades = expand_templates(upgrades)
        commands = expand_templates(commands)
        ensure_no_denied_templates(units | buildings | upgrades | commands, denylist, f"UnlockGroup {gname} expanded")

        result.append({
            "name": gname,
            "faction": g.get("faction", "Shared"),
            "display_name": g.get("display_name", ""),
            "item_pool": bool(g.get("item_pool", True)),
            "expanded_units": sorted(units),
            "expanded_buildings": sorted(buildings),
            "expanded_upgrades": sorted(upgrades),
            "expanded_commands": sorted(commands),
        })

    return result



def write_archipelago_ini(
    groups: list[dict],
    settings: dict,
    outpath: Path,
    header_comment: str = "",
    always_unlocked: dict | None = None,
    runtime_schema: str = "legacy-safe",
) -> None:
    """Write Archipelago.ini. always_unlocked: {units: [...], buildings: [...]}."""
    lines = [
        "; Archipelago Randomizer Configuration for C&C Generals: Zero Hour",
        "; Generated from Data/Archipelago config. Edit groups.json, presets.json, always_unlocked.json.",
        "; Defines unlock groups for units/buildings and starting general defaults.",
        "; Cross-faction groups: same unit/building types unlock together.",
        "; Explicit general-prefixed names (Slth_, Chem_, AirF_, etc.) for group fallback.",
        "",
    ]
    if header_comment:
        lines.append(f"; {header_comment}")
        lines.append("")

    if always_unlocked and (always_unlocked.get("units") or always_unlocked.get("buildings")):
        lines.append("; Templates unlocked from the start (no Archipelago item required)")
        lines.append("AlwaysUnlocked")
        if always_unlocked.get("units"):
            units = expand_templates(always_unlocked["units"])
            lines.append("    Units = " + " ".join(sorted(units)))
        if always_unlocked.get("buildings"):
            buildings = expand_templates(always_unlocked["buildings"])
            lines.append("    Buildings = " + " ".join(sorted(buildings)))
        lines.append("End")
        lines.append("")

    lines.append("ArchipelagoSettings")
    for key, val in settings.items():
        lines.append(f"    {key} = {val}")
    lines.append("End")
    lines.append("")

    for g in groups:
        lines.append(f"UnlockGroup {g['name']}")
        lines.append(f"    Faction = {g['faction']}")
        if g.get("display_name"):
            lines.append(f'    DisplayName = "{g["display_name"]}"')
        runtime_units = list(g.get("expanded_units", []))
        runtime_buildings = list(g.get("expanded_buildings", []))
        runtime_upgrades = list(g.get("expanded_upgrades", []))
        runtime_commands = list(g.get("expanded_commands", []))
        if runtime_schema == "legacy-safe":
            runtime_units = sorted(set(runtime_units) | set(runtime_upgrades) | set(runtime_commands))
            runtime_upgrades = []
            runtime_commands = []
        else:
            lines.append(f"    ItemPool = {'Yes' if g.get('item_pool', True) else 'No'}")
        if runtime_units:
            lines.append("    Units = " + " ".join(runtime_units))
        if runtime_buildings:
            lines.append("    Buildings = " + " ".join(runtime_buildings))
        if runtime_upgrades:
            lines.append("    Upgrades = " + " ".join(runtime_upgrades))
        if runtime_commands:
            lines.append("    Commands = " + " ".join(runtime_commands))
        lines.append("End")
        lines.append("")

    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text("\n".join(lines), encoding="utf-8")



def apply_options_overrides(settings: dict, options: dict) -> dict:
    """
    Apply options overrides to settings.
    options can come from --options YAML (future) or env vars.
    """
    out = dict(settings)
    option_map = {
        "starting_generals_usa": "StartingGeneralUSA",
        "starting_generals_china": "StartingGeneralChina",
        "starting_generals_gla": "StartingGeneralGLA",
        "StartingGeneralUSA": "StartingGeneralUSA",
        "StartingGeneralChina": "StartingGeneralChina",
        "StartingGeneralGLA": "StartingGeneralGLA",
    }
    for opt_key, ini_key in option_map.items():
        if opt_key in options:
            out[ini_key] = str(options[opt_key])
    return out



def main():
    ap = argparse.ArgumentParser(
        description="Generate Archipelago.ini from Data/Archipelago config",
        epilog="Set ARCHIPELAGO_PRESET for default preset. Set ARCHIPELAGO_CONFIG_DIR for config path.",
    )
    ap.add_argument("--preset", "-p", default=os.environ.get("ARCHIPELAGO_PRESET", "default"),
                    help="Preset name (default: default or ARCHIPELAGO_PRESET)")
    ap.add_argument("--output", "-o", type=Path,
                    help="Output path (default: Data/INI/Archipelago.ini)")
    ap.add_argument("--config-dir", "-c", type=Path,
                    default=None,
                    help="Config directory with groups.json and presets.json (default: Data/Archipelago)")
    ap.add_argument("--list-presets", action="store_true",
                    help="List available presets and exit")
    ap.add_argument("--options", type=Path,
                    help="Path to options YAML (future: for seed generation options)")
    ap.add_argument(
        "--runtime-schema",
        choices=("legacy-safe", "current"),
        default="legacy-safe",
        help="Runtime schema to emit. legacy-safe omits new INI fields and filters to validated groups.",
    )
    ap.add_argument(
        "--validated-reference-ini",
        type=Path,
        default=DEFAULT_VALIDATED_REFERENCE_INI,
        help="Reference Archipelago.ini used to define the validated legacy-safe group set.",
    )
    args = ap.parse_args()

    env_config = os.environ.get("ARCHIPELAGO_CONFIG_DIR", "").strip()
    config_dir = args.config_dir or (Path(env_config) if env_config else None) or DEFAULT_CONFIG_DIR
    if not config_dir.is_absolute():
        config_dir = REPO_ROOT / config_dir
    output_path = args.output or DEFAULT_OUTPUT
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    validated_reference_ini = args.validated_reference_ini
    if not validated_reference_ini.is_absolute():
        validated_reference_ini = REPO_ROOT / validated_reference_ini

    try:
        groups_def = load_groups(config_dir)
        presets = load_presets(config_dir)
        always_unlocked = load_always_unlocked(config_dir)
        display_to_templates = load_display_names(config_dir)
        denylist = load_non_spawnable_templates(config_dir / "non_spawnable_templates.json")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.list_presets:
        print("Available presets:")
        for name, p in presets.items():
            desc = p.get("description", "")
            print(f"  {name}: {desc}")
        sys.exit(0)

    preset_name = args.preset
    if preset_name not in presets:
        print(f"Error: preset '{preset_name}' not found. Available: {list(presets.keys())}", file=sys.stderr)
        sys.exit(1)

    preset = presets[preset_name]
    settings = dict(preset.get("settings", {}))
    if not settings:
        settings = {"StartingGeneralUSA": "RANDOM", "StartingGeneralChina": "RANDOM", "StartingGeneralGLA": "RANDOM"}

    if args.options and args.options.exists():
        try:
            import yaml
            opts = yaml.safe_load(args.options.read_text(encoding="utf-8")) or {}
            settings = apply_options_overrides(settings, opts)
        except ImportError:
            pass

    ensure_no_denied_templates(always_unlocked.get("units", []), denylist, "AlwaysUnlocked units")
    ensure_no_denied_templates(always_unlocked.get("buildings", []), denylist, "AlwaysUnlocked buildings")
    validated_group_names = set()
    if args.runtime_schema == "legacy-safe":
        validated_group_names = load_validated_group_names(validated_reference_ini)
        if not validated_group_names:
            print(
                f"Error: legacy-safe runtime schema requires a validated reference INI with UnlockGroup entries: {validated_reference_ini}",
                file=sys.stderr,
            )
            sys.exit(1)
    groups = build_ini_groups(
        groups_def,
        preset,
        display_to_templates,
        denylist=denylist,
        validated_group_names=validated_group_names if args.runtime_schema == "legacy-safe" else None,
    )
    always_unlocked_expanded = expand_templates(always_unlocked.get("units", [])) | expand_templates(always_unlocked.get("buildings", []))
    fully_auto_groups = []
    for group in groups:
        if not group.get("item_pool", True):
            continue
        members = set(group.get("expanded_units", [])) | set(group.get("expanded_buildings", [])) | set(group.get("expanded_upgrades", [])) | set(group.get("expanded_commands", []))
        if members and members.issubset(always_unlocked_expanded):
            fully_auto_groups.append(group["name"])
    if fully_auto_groups:
        print(
            "Error: item_pool groups fully satisfied by AlwaysUnlocked content: "
            + ", ".join(sorted(fully_auto_groups)),
            file=sys.stderr,
        )
        sys.exit(1)
    header = f"Preset: {preset_name}"
    if preset.get("description"):
        header += f" - {preset['description']}"
    write_archipelago_ini(
        groups, settings, output_path,
        header_comment=header,
        always_unlocked=always_unlocked if always_unlocked else None,
        runtime_schema=args.runtime_schema,
    )

    print(f"Generated {output_path} (preset: {preset_name}, schema: {args.runtime_schema}, {len(groups)} groups)")


if __name__ == "__main__":
    main()

