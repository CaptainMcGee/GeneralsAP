"""Logic Foundry import helpers for the Generals: Zero Hour AP world.

This module is intentionally free of Archipelago imports so it can be tested from
the GeneralsAP repo before the overlay is materialized into an AP checkout.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_SOURCE_PATH = REPO_ROOT / "Data" / "Archipelago" / "logic_foundry_ap_world_import.json"

YamlMode = str
StateHas = Callable[[str, int], bool]
MissionGateRule = Callable[[Any, str, "Route"], bool]
AbstractGroupRule = Callable[[Iterable[str]], bool]


@dataclass(frozen=True)
class Route:
    """One concrete army/general route being evaluated by AP logic."""

    faction: str
    general: str | None
    yaml_mode: YamlMode = "general_specific"
    abstract_group_can_field: AbstractGroupRule | None = None


def load_logic_foundry_source(path: Path | None = None) -> dict[str, Any]:
    """Load committed Logic Foundry source JSON."""

    source_path = path or DEFAULT_SOURCE_PATH
    with source_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_logic_foundry_source(source: Mapping[str, Any]) -> None:
    """Fail fast when AP world input is not the tested Foundry contract."""

    if source.get("kind") != "generalsap_logic_foundry_ap_world_import":
        raise ValueError("Logic Foundry source kind mismatch.")
    if source.get("validationSummary", {}).get("blocker") != 0:
        raise ValueError("Logic Foundry source has blocker validation issues.")
    semantics = source.get("importSemantics", {})
    if semantics.get("sourceOfTruth") != "clusters[].authoredRequirements.requiredWeaknessTagIds":
        raise ValueError("Logic Foundry source must use authored cluster requirements.")
    if "CollectionState" not in semantics.get("routePolicy", ""):
        raise ValueError("Logic Foundry source routePolicy must mention CollectionState.")
    if "allRequiredItemIds" not in semantics.get("productionPolicy", ""):
        raise ValueError("Logic Foundry source productionPolicy must mention allRequiredItemIds.")


def unit_rules_by_id(source: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {rule["unitId"]: rule for rule in source.get("unitBuildRules", [])}


def player_groups(source: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return list(source.get("playerUnitGroups", []))


def cluster_rules(source: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return list(source.get("clusterAccessRules", []))


def unit_matches_route(unit_rule: Mapping[str, Any], route: Route) -> bool:
    """Check route legality without checking AP item ownership."""

    if route.yaml_mode in {"general_specific", "faction_shared"}:
        if unit_rule.get("faction") != route.faction:
            return False
        unit_general = unit_rule.get("general")
        return unit_general is None or unit_general == route.general

    if route.yaml_mode == "abstract_shared":
        if route.abstract_group_can_field is None:
            return False
        return route.abstract_group_can_field(unit_rule.get("sourceUnlockGroupIds", []))

    return False


def unit_buildable(
    state_has: StateHas,
    player: int,
    unit_rule: Mapping[str, Any],
    route: Route,
) -> bool:
    """A unit counts only when route can field it and every AP item is owned."""

    return (
        unit_matches_route(unit_rule, route)
        and all(state_has(item_id, player) for item_id in unit_rule.get("allRequiredItemIds", []))
    )


def weakness_covered(
    state_has: StateHas,
    player: int,
    source: Mapping[str, Any],
    weakness_id: str,
    route: Route,
) -> bool:
    """Return True when a concrete player unit group covers one authored weakness."""

    units = unit_rules_by_id(source)
    for group in player_groups(source):
        if weakness_id not in group.get("coveredWeaknessTagIds", []):
            continue
        for unit_id in group.get("unitIds", []):
            unit_rule = units.get(unit_id)
            if unit_rule and unit_buildable(state_has, player, unit_rule, route):
                return True
    return False


def cluster_local_access(
    state_has: StateHas,
    player: int,
    source: Mapping[str, Any],
    cluster_rule: Mapping[str, Any],
    route: Route,
) -> bool:
    """Cluster-local rule: every authored weakness must be covered."""

    return all(
        weakness_covered(state_has, player, source, weakness_id, route)
        for weakness_id in cluster_rule.get("authoredWeaknessTagIds", [])
    )


def cluster_access(
    state: Any,
    state_has: StateHas,
    player: int,
    source: Mapping[str, Any],
    cluster_rule: Mapping[str, Any],
    route: Route,
    mission_hold: MissionGateRule | None = None,
    mission_win: MissionGateRule | None = None,
    special_mission_rule: MissionGateRule | None = None,
) -> bool:
    """Final cluster access. Mission Hold/Win stays separate from weakness coverage."""

    if not cluster_local_access(state_has, player, source, cluster_rule, route):
        return False

    gate = cluster_rule.get("gate")
    mission_id = cluster_rule.get("missionId", "")
    if gate == "none":
        return True
    if gate == "mission_hold":
        return bool(mission_hold and mission_hold(state, mission_id, route))
    if gate in {"mission_win", "mission_defeat"}:
        return bool(mission_win and mission_win(state, mission_id, route))
    return bool(special_mission_rule and special_mission_rule(state, mission_id, route))


def all_required_item_names(source: Mapping[str, Any]) -> list[str]:
    """All AP item names needed by imported unit rules plus medals and Victory."""

    names: set[str] = {"Victory"}
    for mission in source.get("missions", []):
        medal = mission.get("victoryMedalItemName")
        if medal:
            names.add(medal)
    for rule in source.get("unitBuildRules", []):
        names.update(rule.get("allRequiredItemIds", []))
    return sorted(names)


def item_name_to_id(source: Mapping[str, Any]) -> dict[str, int | None]:
    """Stable item table for alpha grouped source.

    Medal item IDs come from the Foundry/AP contract. Other items are assigned a
    deterministic range above the reserved medal offset. Victory is an event item.
    """

    base = int(source.get("apCompatibility", {}).get("itemIdBase", 270100000))
    medal_names = source.get("apCompatibility", {}).get("victoryMedalItemNames", {})
    medal_id_by_name = {
        mission["victoryMedalItemName"]: mission["victoryMedalItemId"]
        for mission in source.get("missions", [])
        if mission.get("victoryMedalItemName") and mission.get("victoryMedalItemId")
    }

    table: dict[str, int | None] = {"Victory": None}
    for name in sorted(medal_names.values()):
        table[name] = medal_id_by_name[name]

    next_id = base + 1000
    for name in all_required_item_names(source):
        if name in table:
            continue
        table[name] = next_id
        next_id += 1
    return table


def mission_location_name(mission: Mapping[str, Any]) -> str:
    return f"Mission: {mission['displayName']} Victory"


def cluster_unit_location_name(cluster_rule: Mapping[str, Any], unit_index: int) -> str:
    return f"Cluster: {cluster_rule['label']} Unit {unit_index + 1}"


def location_name_to_id(source: Mapping[str, Any]) -> dict[str, int]:
    """Stable mission and per-cluster-unit location table."""

    table: dict[str, int] = {}
    for mission in source.get("missions", []):
        table[mission_location_name(mission)] = int(mission["missionVictoryLocationId"])

    cluster_base = int(source.get("apCompatibility", {}).get("clusterUnitBase", 270010000))
    map_slots = source.get("apCompatibility", {}).get("mapSlots", {})
    per_mission_cluster_index: dict[str, int] = {}
    for cluster_rule in cluster_rules(source):
        mission_id = cluster_rule["missionId"]
        cluster_index = per_mission_cluster_index.get(mission_id, 0)
        per_mission_cluster_index[mission_id] = cluster_index + 1
        map_slot = int(map_slots[mission_id])
        for unit_index, _enemy_unit in enumerate(cluster_rule.get("enemyUnits", [])):
            location_id = cluster_base + (map_slot * 10000) + (cluster_index * 100) + unit_index
            table[cluster_unit_location_name(cluster_rule, unit_index)] = location_id
    return table


def boss_access(state_has: StateHas, player: int, source: Mapping[str, Any]) -> bool:
    """China Boss unlock: all seven shuffled General Medal items."""

    return all(state_has(item_name, player) for item_name in source.get("worldGoal", {}).get("requiredMedalItemNames", []))


def completion_condition(state_has: StateHas, player: int, source: Mapping[str, Any]) -> bool:
    return state_has(source.get("worldGoal", {}).get("finalVictoryEventName", "Victory"), player)
