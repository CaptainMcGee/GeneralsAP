from __future__ import annotations

from worlds.generic.Rules import set_rule

from .Locations import LOCATION_NAME_TO_ID
from .logic_foundry_import import (
    Route,
    boss_access,
    cluster_access,
    cluster_rules,
    cluster_unit_location_name,
    completion_condition,
    load_logic_foundry_source,
    mission_location_name,
)


GENERAL_ROUTES = {
    "usa": ("USA", None),
    "air_force": ("USA", "Air Force"),
    "laser": ("USA", "Laser"),
    "superweapon": ("USA", "Superweapon"),
    "china": ("China", None),
    "tank": ("China", "Tank"),
    "nuke": ("China", "Nuke"),
    "infantry": ("China", "Infantry"),
    "gla": ("GLA", None),
    "stealth": ("GLA", "Stealth"),
    "toxin": ("GLA", "Toxin"),
    "demolition": ("GLA", "Demolition"),
}

ARMY_ROUTES = {
    "usa": "USA",
    "china": "China",
    "gla": "GLA",
}


def _state_has(state, item_name: str, player: int) -> bool:
    return state.has(item_name, player)


def route_for_world(world) -> Route:
    general_key = world.options.start_general.current_key
    faction, general = GENERAL_ROUTES[general_key]
    if general is None:
        faction = ARMY_ROUTES[world.options.starting_army.current_key]
    return Route(faction=faction, general=general, yaml_mode=world.options.item_mode.current_key)


def set_rules(world) -> None:
    source = load_logic_foundry_source()
    route = route_for_world(world)

    def mission_hold_rule(state, mission_id: str, route: Route) -> bool:
        # Mission Hold logic is intentionally separate and not authored yet.
        # Keep alpha scaffold generation runnable until that table exists.
        return True

    def mission_win_rule(state, mission_id: str, route: Route) -> bool:
        # Temporary scaffold: mission medals are the current AP proof of a defeated mission.
        for mission in source.get("missions", []):
            if mission.get("id") == mission_id and mission.get("victoryMedalItemName"):
                return state.has(mission["victoryMedalItemName"], world.player)
        return False

    for mission in source.get("missions", []):
        location_name = mission_location_name(mission)
        if location_name not in LOCATION_NAME_TO_ID:
            continue
        location = world.multiworld.get_location(location_name, world.player)
        if mission.get("isBoss"):
            set_rule(location, lambda state, src=source: boss_access(lambda item, player: _state_has(state, item, player), world.player, src))

    for cluster_rule in cluster_rules(source):
        for unit_index, _enemy_unit in enumerate(cluster_rule.get("enemyUnits", [])):
            location_name = cluster_unit_location_name(cluster_rule, unit_index)
            if location_name not in LOCATION_NAME_TO_ID:
                continue
            location = world.multiworld.get_location(location_name, world.player)
            set_rule(
                location,
                lambda state, rule=cluster_rule, src=source: cluster_access(
                    state,
                    lambda item, player: _state_has(state, item, player),
                    world.player,
                    src,
                    rule,
                    route,
                    mission_hold=mission_hold_rule,
                    mission_win=mission_win_rule,
                ),
            )

    world.multiworld.completion_condition[world.player] = (
        lambda state, src=source: completion_condition(lambda item, player: _state_has(state, item, player), world.player, src)
    )
