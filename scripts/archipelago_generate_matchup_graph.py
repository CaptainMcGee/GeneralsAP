#!/usr/bin/env python3
"""
Generate a directed weighted unit matchup graph for Archipelago generation.

Graph nodes are spawnable units (units that can be built from a building command),
restricted to units that appear in current named unlock groups.

Weights are 0..10 and are derived from:
1) archetype vs archetype baseline matrix, and
2) explicit unit-vs-unit override rows.

Output:
- Data/Archipelago/generated_unit_matchup_graph.json
- Data/Archipelago/generated_unit_matchup_graph.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from archipelago_data_helpers import default_game_asset_path, ensure_no_denied_templates, load_name_overrides, load_non_spawnable_templates

DEFAULT_CONFIG_DIR = REPO_ROOT / "Data" / "Archipelago"
DEFAULT_GROUPS = DEFAULT_CONFIG_DIR / "groups.json"
DEFAULT_DISPLAY_NAMES = DEFAULT_CONFIG_DIR / "display_names.json"
DEFAULT_INGAME_NAMES = DEFAULT_CONFIG_DIR / "ingame_names.json"
DEFAULT_TEMPLATE_NAMES = DEFAULT_CONFIG_DIR / "template_ingame_names.json"
DEFAULT_NAME_OVERRIDES = DEFAULT_CONFIG_DIR / "name_overrides.json"
DEFAULT_ARCHETYPE_CONFIG = DEFAULT_CONFIG_DIR / "unit_matchup_archetypes.json"
DEFAULT_ARCHETYPE_MATRIX = DEFAULT_CONFIG_DIR / "unit_matchup_archetype_weights.csv"
DEFAULT_OVERRIDES = DEFAULT_CONFIG_DIR / "unit_matchup_overrides.csv"
DEFAULT_OUT_JSON = DEFAULT_CONFIG_DIR / "generated_unit_matchup_graph.json"
DEFAULT_OUT_CSV = DEFAULT_CONFIG_DIR / "generated_unit_matchup_graph.csv"
DEFAULT_OUT_READABLE = DEFAULT_CONFIG_DIR / "generated_unit_matchup_graph_readable.txt"

COMMAND_SET = default_game_asset_path(Path("Data") / "INI" / "CommandSet.ini")
COMMAND_BUTTON = default_game_asset_path(Path("Data") / "INI" / "CommandButton.ini")
FACTION_UNIT = default_game_asset_path(Path("Data") / "INI" / "Object" / "FactionUnit.ini")
FACTION_BUILDING = default_game_asset_path(Path("Data") / "INI" / "Object" / "FactionBuilding.ini")

KNOWN_PREFIX_TO_GENERAL = {
    "AirF": "Air Force",
    "Lazr": "Laser",
    "SupW": "Superweapon",
    "Tank": "Tank",
    "Infa": "Infantry",
    "Nuke": "Nuke",
    "Demo": "Demolition",
    "Slth": "Stealth",
    "Toxin": "Toxin",
    "Chem": "Toxin",
}
KNOWN_PREFIX_LOWER = frozenset(x.lower() for x in KNOWN_PREFIX_TO_GENERAL.keys())

EXCLUDE_PREFIXES = ("GC_", "CINE_", "Boss_")
VALID_SIDES = frozenset(("America", "China", "GLA"))


@dataclass(frozen=True)
class EdgeOverride:
    weight: int
    source: str
    rationale: str


@dataclass(frozen=True)
class UnitTemplateDef:
    kind: str
    parent: str | None
    body: str
    side: str
    buildable: str
    kindof: str


def strip_comment(line: str) -> str:
    pos = line.find(";")
    if pos >= 0:
        return line[:pos]
    return line


def strip_known_general_prefix(name: str) -> tuple[str, str | None]:
    pos = name.find("_")
    if pos < 0:
        return (name, None)
    prefix = name[:pos]
    if prefix.lower() in KNOWN_PREFIX_LOWER:
        return (name[pos + 1 :], prefix)
    return (name, None)


def expand_template_with_general_variants(name: str) -> set[str]:
    """Mirror expansion logic used by the Archipelago group generator."""
    base, prefix = strip_known_general_prefix(name)
    if prefix is not None:
        # already prefixed variant
        return {name}
    lower = base.lower()
    variants = {base}
    if lower.startswith("america"):
        variants.update({f"{p}_{base}" for p in ("AirF", "Lazr", "SupW")})
    elif lower.startswith("china"):
        variants.update({f"{p}_{base}" for p in ("Tank", "Infa", "Nuke")})
    elif lower.startswith("gla"):
        variants.update({f"{p}_{base}" for p in ("Demo", "Slth", "Toxin", "Chem")})
    return variants


def extract_basic_attrs(body: str, inherited: dict[str, str] | None = None) -> tuple[str, str, str]:
    side = inherited.get("side", "") if inherited else ""
    buildable = inherited.get("buildable", "") if inherited else ""
    kindof = inherited.get("kindof", "") if inherited else ""

    for raw in body.splitlines():
        line = strip_comment(raw).strip()
        if not line:
            continue
        if line.startswith("Side"):
            side = re.sub(r"^Side\s*=\s*", "", line, flags=re.I).strip().split()[0]
        elif line.startswith("Buildable"):
            buildable = re.sub(r"^Buildable\s*=\s*", "", line, flags=re.I).strip()
        elif line.startswith("KindOf"):
            kindof = re.sub(r"^KindOf\s*=\s*", "", line, flags=re.I).strip().upper()
    return side, buildable, kindof


def parse_unit_templates(path: Path) -> dict[str, UnitTemplateDef]:
    """
    Extract top-level Object/ObjectReskin templates with inheritance and attrs.

    Uses a top-level parser (header at column 0, object End at column 0) to
    avoid stopping on nested module `End` lines.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    defs: dict[str, UnitTemplateDef] = {}
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        stripped = raw.strip()
        is_top_level = raw == raw.lstrip()

        if is_top_level and stripped.startswith("ObjectReskin "):
            parts = stripped.split()
            if len(parts) >= 3:
                child = parts[1].strip()
                parent = parts[2].strip()
                i += 1
                body_lines: list[str] = []
                while i < n:
                    end_line = lines[i]
                    if end_line == end_line.lstrip() and end_line.strip() == "End":
                        break
                    body_lines.append(end_line)
                    i += 1
                body = "\n".join(body_lines)
                parent_def = defs.get(parent)
                inherited = (
                    {"side": parent_def.side, "buildable": parent_def.buildable, "kindof": parent_def.kindof}
                    if parent_def
                    else {"side": "", "buildable": "", "kindof": ""}
                )
                side, buildable, kindof = extract_basic_attrs(body, inherited)
                defs[child] = UnitTemplateDef(
                    kind="reskin",
                    parent=parent,
                    body=body,
                    side=side,
                    buildable=buildable,
                    kindof=kindof,
                )
            i += 1
            continue

        if is_top_level and stripped.startswith("Object "):
            parts = stripped.split()
            if len(parts) >= 2:
                name = parts[1].strip()
                i += 1
                body_lines = []
                while i < n:
                    end_line = lines[i]
                    if end_line == end_line.lstrip() and end_line.strip() == "End":
                        break
                    body_lines.append(end_line)
                    i += 1
                body = "\n".join(body_lines)
                side, buildable, kindof = extract_basic_attrs(body)
                defs[name] = UnitTemplateDef(
                    kind="object",
                    parent=None,
                    body=body,
                    side=side,
                    buildable=buildable,
                    kindof=kindof,
                )
            i += 1
            continue

        i += 1

    return defs


def parse_command_sets(path: Path) -> set[str]:
    content = path.read_text(encoding="utf-8", errors="replace")
    used_buttons: set[str] = set()
    set_pat = re.compile(r"^CommandSet\s+\w+\s*\n(.*?)^End\s*$", re.MULTILINE | re.DOTALL)
    for m in set_pat.finditer(content):
        body = m.group(1)
        for raw in body.splitlines():
            line = strip_comment(raw).strip()
            if not line:
                continue
            hit = re.search(r"=\s*(Command_[A-Za-z0-9_]+)\s*$", line)
            if hit:
                used_buttons.add(hit.group(1))
    return used_buttons


def parse_command_buttons(path: Path) -> dict[str, dict[str, str]]:
    content = path.read_text(encoding="utf-8", errors="replace")
    buttons: dict[str, dict[str, str]] = {}
    btn_pat = re.compile(r"^CommandButton\s+(\w+)\s*\n(.*?)^End\s*$", re.MULTILINE | re.DOTALL)
    for m in btn_pat.finditer(content):
        name = m.group(1).strip()
        body = m.group(2)
        cmd = ""
        obj = ""
        for raw in body.splitlines():
            line = strip_comment(raw).strip()
            if not line:
                continue
            if line.startswith("Command"):
                cmd = re.sub(r"^Command\s*=\s*", "", line, flags=re.I).strip()
            elif line.startswith("Object"):
                obj = re.sub(r"^Object\s*=\s*", "", line, flags=re.I).strip()
        buttons[name] = {"command": cmd, "object": obj}
    return buttons


def collect_spawnable_units(unit_defs: dict[str, UnitTemplateDef]) -> set[str]:
    used_buttons = parse_command_sets(COMMAND_SET)
    button_defs = parse_command_buttons(COMMAND_BUTTON)

    constructed_objects: set[str] = set()
    for btn in used_buttons:
        b = button_defs.get(btn)
        if not b:
            continue
        if b["command"] not in {"UNIT_BUILD", "DOZER_CONSTRUCT"}:
            continue
        if b["object"]:
            constructed_objects.add(b["object"])

    spawnable_units: set[str] = set()
    for name in constructed_objects:
        if any(name.startswith(p) for p in EXCLUDE_PREFIXES):
            continue
        tdef = unit_defs.get(name)
        if not tdef:
            continue
        if tdef.buildable.upper().startswith("NO"):
            continue
        if tdef.side not in VALID_SIDES:
            continue
        spawnable_units.add(name)
    return spawnable_units


def is_playable_template(template: str, unit_defs: dict[str, UnitTemplateDef]) -> bool:
    tdef = unit_defs.get(template)
    if not tdef:
        return False
    if any(template.startswith(p) for p in EXCLUDE_PREFIXES):
        return False
    if tdef.buildable.upper().startswith("NO"):
        return False
    return tdef.side in VALID_SIDES


def extract_gameplay_lines(body: str) -> list[str]:
    """
    Build a lightweight gameplay signature:
    - keep DESIGN/ENGINEERING-like lines
    - drop ART/AUDIO-focused lines
    """
    section = ""
    gameplay_lines: list[str] = []
    ignore_keys = {
        "SelectPortrait",
        "ButtonImage",
        "UpgradeCameo1",
        "UpgradeCameo2",
        "UpgradeCameo3",
        "UpgradeCameo4",
        "UpgradeCameo5",
        "DisplayName",
        "EditorSorting",
    }
    for raw in body.splitlines():
        stripped = raw.strip()
        if stripped.startswith(";"):
            upper = stripped.upper()
            if "ART PARAMETERS" in upper:
                section = "ART"
            elif "AUDIO PARAMETERS" in upper:
                section = "AUDIO"
            elif "DESIGN PARAMETERS" in upper or "***DESIGN" in upper:
                section = "DESIGN"
            elif "ENGINEERING PARAMETERS" in upper:
                section = "ENGINEERING"
            continue

        line = strip_comment(raw).strip()
        if not line:
            continue
        if section in {"ART", "AUDIO"}:
            continue
        key = line.split("=", 1)[0].strip().split()[0]
        if key in ignore_keys:
            continue
        if key in {"Draw", "ClientUpdate", "Animation"}:
            continue
        gameplay_lines.append(re.sub(r"\s+", " ", line))
    return gameplay_lines


def template_gameplay_signature(
    template: str,
    unit_defs: dict[str, UnitTemplateDef],
    memo: dict[str, tuple[str, ...]],
    stack: set[str] | None = None,
) -> tuple[str, ...]:
    if template in memo:
        return memo[template]
    stack = stack or set()
    if template in stack:
        return tuple()
    stack.add(template)

    tdef = unit_defs.get(template)
    if not tdef:
        memo[template] = tuple()
        return memo[template]

    inherited: tuple[str, ...] = tuple()
    if tdef.parent:
        inherited = template_gameplay_signature(tdef.parent, unit_defs, memo, stack)
    own = tuple(extract_gameplay_lines(tdef.body))
    sig = inherited + own
    memo[template] = sig
    return sig


def has_variant_stat_difference(
    variant_template: str,
    base_template: str,
    unit_defs: dict[str, UnitTemplateDef],
    sig_memo: dict[str, tuple[str, ...]],
) -> bool:
    if variant_template == base_template:
        return False
    if variant_template not in unit_defs or base_template not in unit_defs:
        return False
    return template_gameplay_signature(variant_template, unit_defs, sig_memo) != template_gameplay_signature(
        base_template, unit_defs, sig_memo
    )


def load_groups(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_display_names(path: Path) -> dict[str, list[str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if isinstance(v, list)}


def clean_display_key(key: str) -> str:
    if ":" in key:
        return key.split(":", 1)[1]
    return key


def build_display_reverse(display: dict[str, list[str]]) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = {}
    for dkey, templates in display.items():
        for t in templates:
            reverse.setdefault(t, [])
            if dkey not in reverse[t]:
                reverse[t].append(dkey)
    return reverse


def _resolve_ingame_name(display_key: str, ingame_names: dict[str, str]) -> str:
    """Resolve a DisplayName key (e.g. OBJECT:Ranger) to the exact localized in-game string."""
    candidates = [display_key, clean_display_key(display_key)]
    for candidate in candidates:
        if candidate in ingame_names:
            return ingame_names[candidate]
    lowered = {candidate.lower() for candidate in candidates}
    for key, value in ingame_names.items():
        if key.lower() in lowered:
            return value
    raise KeyError(f"No localized in-game name found for display key {display_key!r}")


def _resolve_display_override(display_key: str, display_name_overrides: dict[str, str]) -> str | None:
    if not display_name_overrides:
        return None
    candidates = [display_key, clean_display_key(display_key)]
    for candidate in candidates:
        if candidate in display_name_overrides:
            return display_name_overrides[candidate]
    lowered = {candidate.lower() for candidate in candidates}
    for key, value in display_name_overrides.items():
        if key.lower() in lowered:
            return value
    return None


def pretty_template_name(
    template: str,
    template_names: dict[str, str],
    reverse_display: dict[str, list[str]],
    ingame_names: dict[str, str] | None = None,
    display_name_overrides: dict[str, str] | None = None,
    template_name_overrides: dict[str, str] | None = None,
) -> str:
    ingame = ingame_names or {}
    display_overrides = display_name_overrides or {}
    template_overrides = template_name_overrides or {}

    if template in template_overrides:
        return template_overrides[template]

    core, prefix = strip_known_general_prefix(template)
    base = template_names.get(template) or template_names.get(core)
    if not base and core in template_overrides:
        base = template_overrides[core]
    if not base:
        names = reverse_display.get(template) or reverse_display.get(core)
        if not names:
            raise KeyError(f"No localized player-facing name found for template {template!r}")
        display_key = names[0]
        base = _resolve_display_override(display_key, display_overrides) or _resolve_ingame_name(display_key, ingame)

    if prefix and prefix in KNOWN_PREFIX_TO_GENERAL:
        return f"{base} ({KNOWN_PREFIX_TO_GENERAL[prefix]})"
    return base


def debug_template_label(
    template: str,
    template_names: dict[str, str],
    reverse_display: dict[str, list[str]],
    ingame_names: dict[str, str] | None = None,
    display_name_overrides: dict[str, str] | None = None,
    template_name_overrides: dict[str, str] | None = None,
) -> str:
    return f"{pretty_template_name(template, template_names, reverse_display, ingame_names, display_name_overrides, template_name_overrides)} [{template}]"


def resolve_group_units(
    groups: dict,
    group_id: str,
    display: dict[str, list[str]],
    seen: set[str] | None = None,
) -> set[str]:
    seen = seen or set()
    if group_id in seen:
        return set()
    seen.add(group_id)
    group = groups.get(group_id, {})

    units: set[str] = set(group.get("units", []) or [])

    for dn in group.get("by_display_name", []) or []:
        for t in display.get(dn, []):
            units.add(t)

    for sub in group.get("include", []) or []:
        units |= resolve_group_units(groups, sub, display, seen)

    return units


def resolve_group_buildings(
    groups: dict,
    group_id: str,
    display: dict[str, list[str]],
    seen: set[str] | None = None,
) -> set[str]:
    seen = seen or set()
    if group_id in seen:
        return set()
    seen.add(group_id)
    group = groups.get(group_id, {})

    buildings: set[str] = set(group.get("buildings", []) or [])

    for dn in group.get("by_display_name", []) or []:
        for t in display.get(dn, []):
            # display map includes both units and buildings; defer strict filtering later.
            buildings.add(t)

    for sub in group.get("include", []) or []:
        buildings |= resolve_group_buildings(groups, sub, display, seen)

    return buildings


def load_archetype_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_archetype_matrix(path: Path) -> dict[tuple[str, str], int]:
    weights: dict[tuple[str, str], int] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(row for row in f if row.strip() and not row.lstrip().startswith("#"))
        for row in reader:
            a = row["attacker_archetype"].strip()
            d = row["defender_archetype"].strip()
            w = int(row["weight"].strip())
            weights[(a, d)] = max(0, min(10, w))
    return weights


def load_overrides(path: Path) -> dict[tuple[str, str], EdgeOverride]:
    overrides: dict[tuple[str, str], EdgeOverride] = {}
    if not path.exists():
        return overrides
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(row for row in f if row.strip() and not row.lstrip().startswith("#"))
        for row in reader:
            atk = row["attacker_template"].strip()
            dfn = row["defender_template"].strip()
            w = int(row["weight"].strip())
            src = row.get("source", "").strip()
            rat = row.get("rationale", "").strip()
            overrides[(atk, dfn)] = EdgeOverride(weight=max(0, min(10, w)), source=src, rationale=rat)
    return overrides


def compile_rule_regexes(cfg: dict) -> list[tuple[re.Pattern[str], str]]:
    compiled: list[tuple[re.Pattern[str], str]] = []
    for rule in cfg.get("pattern_rules", []):
        rx = re.compile(rule["regex"])
        compiled.append((rx, rule["archetype"]))
    return compiled


def classify_archetype(template: str, cfg: dict, rules: list[tuple[re.Pattern[str], str]]) -> str:
    explicit = cfg.get("explicit_template_archetypes", {})
    if template in explicit:
        return explicit[template]
    core, _ = strip_known_general_prefix(template)
    if core in explicit:
        return explicit[core]
    for rx, arch in rules:
        if rx.search(template) or rx.search(core):
            return arch
    return cfg.get("default_archetype", "support")


def compile_non_combat_regexes(cfg: dict) -> list[re.Pattern[str]]:
    return [re.compile(x) for x in cfg.get("non_combat_regexes", [])]


def compile_force_variant_regexes(cfg: dict) -> list[re.Pattern[str]]:
    return [re.compile(x) for x in cfg.get("force_include_variant_regexes", [])]


def compile_stealth_reliant_regexes(cfg: dict) -> list[re.Pattern[str]]:
    return [re.compile(x) for x in cfg.get("stealth_reliant_regexes", [])]


def is_forced_variant_include(template: str, cfg: dict, force_variant_regexes: list[re.Pattern[str]]) -> bool:
    explicit = set(cfg.get("force_include_variant_templates", []))
    core, _ = strip_known_general_prefix(template)
    if template in explicit:
        return True
    for rx in force_variant_regexes:
        if rx.search(template) or rx.search(core):
            return True
    return False


def is_non_combat_template(template: str, cfg: dict, non_combat_regexes: list[re.Pattern[str]]) -> bool:
    explicit = set(cfg.get("non_combat_templates", []))
    core, _ = strip_known_general_prefix(template)
    if template in explicit or core in explicit:
        return True
    for rx in non_combat_regexes:
        if rx.search(template) or rx.search(core):
            return True
    return False


def should_include_template_node(
    template: str,
    spawnable_base_units: set[str],
    unit_defs: dict[str, UnitTemplateDef],
    archetype_cfg: dict,
    non_combat_regexes: list[re.Pattern[str]],
    force_variant_regexes: list[re.Pattern[str]],
    sig_memo: dict[str, tuple[str, ...]],
) -> bool:
    if is_non_combat_template(template, archetype_cfg, non_combat_regexes):
        return False

    core, prefix = strip_known_general_prefix(template)
    if prefix is None:
        return template in spawnable_base_units and is_playable_template(template, unit_defs)

    # For prefixed general variants, only include when:
    # - the base unit is spawnable, and
    # - this variant actually differs in gameplay stats from the base template.
    if core not in spawnable_base_units:
        return False
    if not is_forced_variant_include(template, archetype_cfg, force_variant_regexes):
        if not is_playable_template(template, unit_defs):
            return False
    else:
        # forced variants may come from runtime content not present in local INIs.
        return True
    return has_variant_stat_difference(template, core, unit_defs, sig_memo)


def is_stealth_reliant_attacker(
    template: str, archetype: str, stealth_regexes: list[re.Pattern[str]]
) -> bool:
    if archetype == "infantry_elite":
        # Some elite infantry rely heavily on stealth utility.
        for rx in stealth_regexes:
            if rx.search(template):
                return True
    for rx in stealth_regexes:
        if rx.search(template):
            return True
    return False


def get_cluster_tier_veterancy_factor(cfg: dict, cluster_tier: str) -> float:
    """Veterancy factor for cluster tier: Easy=Rank1, Medium=Rank2, Hard=Rank3."""
    factors = cfg.get("balance_model", {}).get("cluster_tier_veterancy_factors", {})
    return float(factors.get(cluster_tier, factors.get("medium", 1.15)))


def apply_context_scaling(
    base_weight: int,
    attacker_template: str,
    attacker_archetype: str,
    enemy_hp_multiplier: float,
    enemy_dmg_multiplier: float,
    cfg: dict,
    stealth_regexes: list[re.Pattern[str]],
    defender_cluster_tier: str = "medium",
) -> int:
    model = cfg.get("balance_model", {})

    hp_weight = float(model.get("hp_weight", 0.55))
    dmg_weight = float(model.get("dmg_weight", 0.45))
    default_vet = float(model.get("enemy_max_veterancy_factor", 1.15))
    veterancy_factor = get_cluster_tier_veterancy_factor(cfg, defender_cluster_tier) if defender_cluster_tier else default_vet
    self_repair_factor = float(model.get("enemy_self_repair_factor", 1.08))
    suicide_penalty = float(model.get("suicide_attacker_penalty_factor", 0.82))
    stealth_penalty = float(model.get("stealth_attacker_penalty_factor", 0.85))
    enemy_detects_stealth = bool(model.get("enemy_detects_stealth", True))

    hp = max(0.01, enemy_hp_multiplier)
    dmg = max(0.01, enemy_dmg_multiplier)

    # Higher enemy HP/DMG, veterancy, and self-repair reduce attacker effectiveness.
    enemy_effective_power = (hp ** hp_weight) * (dmg ** dmg_weight) * veterancy_factor * self_repair_factor
    scaled = float(base_weight) / max(0.05, enemy_effective_power)

    if attacker_archetype == "suicide":
        scaled *= suicide_penalty

    if enemy_detects_stealth and is_stealth_reliant_attacker(attacker_template, attacker_archetype, stealth_regexes):
        scaled *= stealth_penalty

    return clamp_weight(round(scaled))


def clamp_weight(value: int) -> int:
    return max(0, min(10, int(value)))


def is_playable_structure_template(template: str, bld_defs: dict[str, UnitTemplateDef]) -> bool:
    tdef = bld_defs.get(template)
    if not tdef:
        return False
    if any(template.startswith(p) for p in EXCLUDE_PREFIXES):
        return False
    if tdef.buildable.upper().startswith("NO"):
        return False
    if tdef.side not in VALID_SIDES:
        return False
    return "STRUCTURE" in tdef.kindof.split()


def compile_defender_allowed_infantry_regexes(cfg: dict) -> list[re.Pattern[str]]:
    """Regexes for infantry/suicide units allowed as defenders (Pathfinder, MiniGunner, Angry Mob, Bomb Truck)."""
    patterns = cfg.get("defender_allowed_infantry_regexes", [])
    return [re.compile(x) for x in patterns]


def compile_defender_cluster_exclude_regexes(cfg: dict) -> list[re.Pattern[str]]:
    """Regexes for units never spawnable as defenders (Black Lotus, Troop Crawler, utility, etc.)."""
    patterns = cfg.get("defender_cluster_exclude_regexes", [])
    return [re.compile(x) for x in patterns]


def compile_cluster_tier_regexes(cfg: dict, key: str) -> list[re.Pattern[str]]:
    """Compile regexes for cluster tier assignment (easy, medium, hard)."""
    patterns = cfg.get(key, [])
    return [re.compile(x) for x in patterns]


def get_defender_cluster_tier(
    template: str,
    archetype: str,
    is_base_defense: bool,
    cfg: dict,
    easy_regexes: list[re.Pattern[str]],
    hard_regexes: list[re.Pattern[str]],
) -> str:
    """Return cluster_tier: easy, medium, or hard. Base defenses are medium only."""
    if is_base_defense:
        return "medium"
    core, _ = strip_known_general_prefix(template)
    hard_include = set(cfg.get("defender_cluster_tier_hard_include_templates", []))
    if template in hard_include or core in hard_include:
        return "hard"
    for rx in easy_regexes:
        if rx.search(template) or rx.search(core):
            return "easy"
    for rx in hard_regexes:
        if rx.search(template) or rx.search(core):
            return "hard"
    return "medium"


def is_allowed_infantry_defender(
    template: str, cfg: dict, infantry_regexes: list[re.Pattern[str]]
) -> bool:
    """True if template matches defender_allowed_infantry (Pathfinder, MiniGunner, Angry Mob, Bomb Truck)."""
    core, _ = strip_known_general_prefix(template)
    for rx in infantry_regexes:
        if rx.search(template) or rx.search(core):
            return True
    return False


def is_cluster_excluded_defender(
    template: str, cfg: dict, exclude_regexes: list[re.Pattern[str]]
) -> bool:
    """True if template should never be a defender (excluded from all clusters)."""
    core, _ = strip_known_general_prefix(template)
    hard_include = set(cfg.get("defender_cluster_tier_hard_include_templates", []))
    if template in hard_include or core in hard_include:
        return False
    explicit = set(cfg.get("defender_cluster_exclude_templates", []))
    if template in explicit or core in explicit:
        return True
    for rx in exclude_regexes:
        if rx.search(template) or rx.search(core):
            return True
    return False


def compile_base_defense_exclude_regexes(cfg: dict) -> list[re.Pattern[str]]:
    defaults = [r"NoSpawn$", r"WallHub$", r"Wall$", r"Moat$", r"Checkpoint$"]
    patterns = cfg.get("defender_base_defense_exclude_regexes", defaults)
    return [re.compile(x) for x in patterns]


def compile_base_defense_force_include_regexes(cfg: dict) -> list[re.Pattern[str]]:
    defaults = [r"StingerSite$", r"PatriotBattery$", r"GattlingCannon$", r"TunnelNetwork$", r"FireBase$", r"Bunker$"]
    patterns = cfg.get("defender_base_defense_force_include_regexes", defaults)
    return [re.compile(x) for x in patterns]


def is_combative_base_defense(
    template: str,
    bld_defs: dict[str, UnitTemplateDef],
    sig_memo: dict[str, tuple[str, ...]],
    exclude_regexes: list[re.Pattern[str]],
    force_include_regexes: list[re.Pattern[str]],
) -> bool:
    for rx in exclude_regexes:
        if rx.search(template):
            return False
    for rx in force_include_regexes:
        if rx.search(template):
            return True
    # Treat base defense as combative if it exposes explicit weapon config.
    sig = template_gameplay_signature(template, bld_defs, sig_memo)
    for line in sig:
        if line.startswith("WeaponSet") or line.startswith("Weapon "):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate Archipelago spawnable-unit matchup graph.")
    ap.add_argument("--config-dir", default=str(DEFAULT_CONFIG_DIR), help="Data/Archipelago directory.")
    ap.add_argument("--groups", default=str(DEFAULT_GROUPS), help="groups.json path.")
    ap.add_argument("--display-names", default=str(DEFAULT_DISPLAY_NAMES), help="display_names.json path.")
    ap.add_argument("--ingame-names", default=str(DEFAULT_INGAME_NAMES), help="ingame_names.json path.")
    ap.add_argument("--template-names", default=str(DEFAULT_TEMPLATE_NAMES), help="template_ingame_names.json path.")
    ap.add_argument("--name-overrides", default=str(DEFAULT_NAME_OVERRIDES), help="name_overrides.json path.")
    ap.add_argument("--archetypes", default=str(DEFAULT_ARCHETYPE_CONFIG), help="Archetype config JSON.")
    ap.add_argument("--matrix", default=str(DEFAULT_ARCHETYPE_MATRIX), help="Archetype matrix CSV.")
    ap.add_argument("--overrides", default=str(DEFAULT_OVERRIDES), help="Pair override CSV.")
    ap.add_argument("--out-json", default=str(DEFAULT_OUT_JSON), help="Output graph JSON path.")
    ap.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV), help="Output graph CSV path.")
    ap.add_argument("--out-readable", default=str(DEFAULT_OUT_READABLE), help="Output readable text path.")
    ap.add_argument(
        "--enemy-hp-multiplier",
        type=float,
        default=1.0,
        help="Spawned enemy HP multiplier used for context scaling (default: 1.0).",
    )
    ap.add_argument(
        "--enemy-dmg-multiplier",
        type=float,
        default=1.0,
        help="Spawned enemy damage multiplier used for context scaling (default: 1.0).",
    )
    args = ap.parse_args()

    groups_path = Path(args.groups)
    display_path = Path(args.display_names)
    ingame_path = Path(args.ingame_names)
    template_names_path = Path(args.template_names)
    name_overrides_path = Path(args.name_overrides)
    archetypes_path = Path(args.archetypes)
    matrix_path = Path(args.matrix)
    overrides_path = Path(args.overrides)
    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    out_readable = Path(args.out_readable)

    groups = load_groups(groups_path)
    display = load_display_names(display_path)
    reverse_display = build_display_reverse(display)
    if not ingame_path.exists():
        raise FileNotFoundError(
            f"{ingame_path} not found. Run scripts/archipelago_build_localized_name_map.py before generating the matchup graph."
        )
    raw = json.loads(ingame_path.read_text(encoding="utf-8"))
    ingame_names = {k: v for k, v in raw.items() if isinstance(v, str) and not k.startswith("_")}
    if not template_names_path.exists():
        raise FileNotFoundError(
            f"{template_names_path} not found. Run scripts/archipelago_build_template_name_map.py before generating the matchup graph."
        )
    raw_template_names = json.loads(template_names_path.read_text(encoding="utf-8"))
    template_names = {k: v for k, v in raw_template_names.items() if isinstance(v, str) and not k.startswith("_")}
    display_name_overrides, template_name_overrides = load_name_overrides(name_overrides_path)
    denylist = load_non_spawnable_templates()

    unit_defs = parse_unit_templates(FACTION_UNIT)
    building_defs = parse_unit_templates(FACTION_BUILDING)
    archetype_cfg = load_archetype_config(archetypes_path)
    rules = compile_rule_regexes(archetype_cfg)
    non_combat_regexes = compile_non_combat_regexes(archetype_cfg)
    force_variant_regexes = compile_force_variant_regexes(archetype_cfg)
    stealth_reliant_regexes = compile_stealth_reliant_regexes(archetype_cfg)
    base_defense_exclude_regexes = compile_base_defense_exclude_regexes(archetype_cfg)
    base_defense_force_include_regexes = compile_base_defense_force_include_regexes(archetype_cfg)
    defender_infantry_regexes = compile_defender_allowed_infantry_regexes(archetype_cfg)
    defender_cluster_exclude_regexes = compile_defender_cluster_exclude_regexes(archetype_cfg)
    cluster_tier_easy_regexes = compile_cluster_tier_regexes(
        archetype_cfg, "defender_cluster_tier_easy_regexes"
    )
    cluster_tier_hard_regexes = compile_cluster_tier_regexes(
        archetype_cfg, "defender_cluster_tier_hard_regexes"
    )
    matrix = load_archetype_matrix(matrix_path)
    overrides = load_overrides(overrides_path)
    sig_memo: dict[str, tuple[str, ...]] = {}
    bld_sig_memo: dict[str, tuple[str, ...]] = {}

    spawnable_units = collect_spawnable_units(unit_defs)
    attacker_allowed_archetypes = set(
        archetype_cfg.get(
            "attacker_allowed_archetypes",
            [
                "infantry_rifle",
                "infantry_rocket",
                "infantry_elite",
                "vehicle_light",
                "vehicle_anti_air",
                "tank_medium",
                "tank_heavy",
                "artillery",
                "air_helicopter",
                "air_plane",
                "suicide",
            ],
        )
    )
    defender_allowed_unit_archetypes = set(
        archetype_cfg.get(
            "defender_allowed_unit_archetypes",
            [
                "infantry_rifle",
                "infantry_rocket",
                "infantry_elite",
                "vehicle_light",
                "vehicle_anti_air",
                "tank_medium",
                "tank_heavy",
                "artillery",
                "air_helicopter",
                "suicide",
            ],
        )
    )
    defender_base_defense_group_ids = list(archetype_cfg.get("defender_base_defense_group_ids", ["Shared_BaseDefenses"]))

    # Build group->expanded spawnable combat units.
    group_to_units: dict[str, set[str]] = {}
    unit_candidates: set[str] = set()
    easy_non_combat_defenders: set[str] = set()
    easy_non_combat_to_groups: dict[str, list[str]] = {}
    for group_id in groups.keys():
        base_units = resolve_group_units(groups, group_id, display)
        ensure_no_denied_templates(base_units, denylist, f"group {group_id} units")
        expanded: set[str] = set()
        for u in base_units:
            expanded |= expand_template_with_general_variants(u)
        ensure_no_denied_templates(expanded, denylist, f"group {group_id} expanded units")
        filtered = {
            u
            for u in expanded
            if should_include_template_node(
                u,
                spawnable_units,
                unit_defs,
                archetype_cfg,
                non_combat_regexes,
                force_variant_regexes,
                sig_memo,
            )
        }
        if filtered:
            group_to_units[group_id] = filtered
            unit_candidates |= filtered
        for u in expanded:
            if u not in unit_candidates and is_non_combat_template(u, archetype_cfg, non_combat_regexes):
                if not is_playable_template(u, unit_defs):
                    continue
                core, _ = strip_known_general_prefix(u)
                if any(rx.search(u) or rx.search(core) for rx in cluster_tier_easy_regexes):
                    if not is_cluster_excluded_defender(u, archetype_cfg, defender_cluster_exclude_regexes):
                        easy_non_combat_defenders.add(u)
                        easy_non_combat_to_groups.setdefault(u, []).append(group_id)

    # Hard-only include templates (e.g. Battle Chinook): in exclude list but allowed as defenders for hard tier.
    hard_include_templates = set(archetype_cfg.get("defender_cluster_tier_hard_include_templates", []))
    ensure_no_denied_templates(hard_include_templates, denylist, "hard include defenders")
    hard_include_defenders = {t for t in hard_include_templates if t in unit_defs and is_playable_template(t, unit_defs)}

    # Defender-only base defense nodes from building groups.
    defender_base_defense_nodes: set[str] = set()
    base_def_group_map: dict[str, list[str]] = {}
    for gid in defender_base_defense_group_ids:
        base_buildings = resolve_group_buildings(groups, gid, display)
        ensure_no_denied_templates(base_buildings, denylist, f"group {gid} buildings")
        expanded: set[str] = set()
        for b in base_buildings:
            expanded |= expand_template_with_general_variants(b)
        ensure_no_denied_templates(expanded, denylist, f"group {gid} expanded buildings")
        for t in expanded:
            if not is_playable_structure_template(t, building_defs):
                continue
            if not is_combative_base_defense(
                t,
                building_defs,
                bld_sig_memo,
                base_defense_exclude_regexes,
                base_defense_force_include_regexes,
            ):
                continue
            defender_base_defense_nodes.add(t)
            base_def_group_map.setdefault(t, [])
            base_def_group_map[t].append(gid)

    all_node_templates = unit_candidates | defender_base_defense_nodes | easy_non_combat_defenders | hard_include_defenders
    ensure_no_denied_templates(all_node_templates, denylist, "matchup graph nodes")
    template_to_groups: dict[str, list[str]] = {t: [] for t in all_node_templates}
    for gid, units in group_to_units.items():
        for t in units:
            template_to_groups.setdefault(t, [])
            template_to_groups[t].append(gid)
    for t, gids in base_def_group_map.items():
        template_to_groups.setdefault(t, [])
        template_to_groups[t].extend(gids)
    for t, gids in easy_non_combat_to_groups.items():
        template_to_groups.setdefault(t, [])
        template_to_groups[t].extend(gids)
    for t in template_to_groups:
        template_to_groups[t] = sorted(set(template_to_groups[t]))

    forced_archetype: dict[str, str] = {t: "base_defense" for t in defender_base_defense_nodes}
    node_meta: dict[str, dict] = {}
    for t in sorted(all_node_templates):
        arch = forced_archetype.get(t, classify_archetype(t, archetype_cfg, rules))
        node_meta[t] = {
            "template": t,
            "name": pretty_template_name(t, template_names, reverse_display, ingame_names, display_name_overrides, template_name_overrides),
            "archetype": arch,
            "groups": template_to_groups.get(t, []),
        }

    attackers = sorted([t for t in unit_candidates if node_meta[t]["archetype"] in attacker_allowed_archetypes])

    # Defender list = spawnable list (Part 1). Infantry: only Pathfinder, MiniGunner, Angry Mob, Bomb Truck.
    # Non-infantry: defender_allowed_unit_archetypes minus cluster_exclude.
    infantry_archetypes = {"infantry_rifle", "infantry_rocket", "infantry_elite", "suicide"}
    defenders_units = []
    for t in unit_candidates:
        if is_cluster_excluded_defender(t, archetype_cfg, defender_cluster_exclude_regexes):
            continue
        arch = node_meta[t]["archetype"]
        if arch in infantry_archetypes:
            if is_allowed_infantry_defender(t, archetype_cfg, defender_infantry_regexes):
                defenders_units.append(t)
        elif arch in defender_allowed_unit_archetypes:
            defenders_units.append(t)
    defenders_units = sorted(set(defenders_units) | easy_non_combat_defenders | hard_include_defenders)
    defenders = sorted(set(defenders_units) | defender_base_defense_nodes)

    # Part 1: Assign cluster_tier to each defender (easy/medium/hard).
    easy_non_combat_weight_ratio = float(
        archetype_cfg.get("easy_cluster_non_combat_weight_ratio", 1.0 / 3.0)
    )
    for t in defenders:
        is_bd = t in defender_base_defense_nodes
        arch = node_meta[t]["archetype"]
        node_meta[t]["cluster_tier"] = get_defender_cluster_tier(
            t,
            arch,
            is_bd,
            archetype_cfg,
            cluster_tier_easy_regexes,
            cluster_tier_hard_regexes,
        )
        if node_meta[t]["cluster_tier"] == "easy":
            if is_non_combat_template(t, archetype_cfg, non_combat_regexes):
                node_meta[t]["easy_spawn_weight"] = easy_non_combat_weight_ratio
            else:
                node_meta[t]["easy_spawn_weight"] = 1.0

    default_weight = matrix.get(("default", "default"), 5)
    edges: list[dict] = []
    csv_rows: list[dict] = []
    readable_lines: list[str] = []

    for atk in attackers:
        atk_meta = node_meta[atk]
        for dfn in defenders:
            if atk == dfn:
                continue
            dfn_meta = node_meta[dfn]
            basis = "archetype_matrix"
            source = ""
            rationale = ""
            override = overrides.get((atk, dfn))
            if override:
                base_weight = override.weight
                basis = "override"
                source = override.source
                rationale = override.rationale
            else:
                base_weight = matrix.get((atk_meta["archetype"], dfn_meta["archetype"]), default_weight)

            weight = apply_context_scaling(
                base_weight=base_weight,
                attacker_template=atk,
                attacker_archetype=atk_meta["archetype"],
                enemy_hp_multiplier=args.enemy_hp_multiplier,
                enemy_dmg_multiplier=args.enemy_dmg_multiplier,
                cfg=archetype_cfg,
                stealth_regexes=stealth_reliant_regexes,
                defender_cluster_tier=dfn_meta.get("cluster_tier", "medium"),
            )

            edge = {
                "attacker_template": atk,
                "attacker_name": atk_meta["name"],
                "defender_template": dfn,
                "defender_name": dfn_meta["name"],
                "base_weight": clamp_weight(base_weight),
                "weight": clamp_weight(weight),
                "basis": basis,
                "source": source,
                "rationale": rationale,
            }
            edges.append(edge)
            csv_rows.append(
                {
                    **edge,
                    "attacker_archetype": atk_meta["archetype"],
                    "defender_archetype": dfn_meta["archetype"],
                    "defender_cluster_tier": dfn_meta.get("cluster_tier", ""),
                }
            )
            readable_lines.append(f"{debug_template_label(atk, template_names, reverse_display, ingame_names, display_name_overrides, template_name_overrides)} vs {debug_template_label(dfn, template_names, reverse_display, ingame_names, display_name_overrides, template_name_overrides)}: {edge['base_weight']}")

    graph = {
        "version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "node_count": len(all_node_templates),
        "attacker_node_count": len(attackers),
        "defender_node_count": len(defenders),
        "edge_count": len(edges),
        "notes": {
            "weight_scale": "0..10",
            "duel_assumption": "1v1 or small homogeneous group vs small homogeneous group",
            "direction_assumption": "attacker is player-owned unit; defender is spawned enemy unit",
            "enemy_context": {
                "hp_multiplier": args.enemy_hp_multiplier,
                "dmg_multiplier": args.enemy_dmg_multiplier,
                "veterancy_by_tier": "easy=Rank1, medium=Rank2, hard=Rank3 (baked into weight)",
                "self_repair_assumed": True,
                "enemy_detects_stealth": bool(archetype_cfg.get("balance_model", {}).get("enemy_detects_stealth", True)),
            },
            "weight_meaning": {
                "0": "attacker effectively cannot threaten defender in normal conditions",
                "10": "attacker can decisively and quickly eliminate defender with low risk",
            },
            "node_inclusion_policy": {
                "general_variants": "included as separate nodes only when gameplay signature differs from base template",
                "non_combat_units": "excluded",
            },
            "defender_filters": {
                "unit_archetypes": sorted(defender_allowed_unit_archetypes),
                "base_defense_groups": defender_base_defense_group_ids,
                "base_defenses_defender_only": True,
                "cluster_tier_policy": "easy/medium/hard; base_defenses=medium only; no base defenses in hard",
            },
        },
        "attackers": [node_meta[t] for t in attackers],
        "defenders": [node_meta[t] for t in defenders],
        "edges": edges,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(graph, indent=2, sort_keys=False), encoding="utf-8")
    out_readable.parent.mkdir(parents=True, exist_ok=True)

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        fields = [
            "attacker_template",
            "attacker_name",
            "attacker_archetype",
            "defender_template",
            "defender_name",
            "defender_archetype",
            "defender_cluster_tier",
            "base_weight",
            "weight",
            "basis",
            "source",
            "rationale",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(csv_rows)

    out_readable.write_text("\n".join(readable_lines) + ("\n" if readable_lines else ""), encoding="utf-8")

    print(
        f"Generated matchup graph: {len(attackers)} attackers, {len(defenders)} defenders, {len(edges)} directed edges\n"
        f"JSON: {out_json}\nCSV:  {out_csv}\nTXT:  {out_readable}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

