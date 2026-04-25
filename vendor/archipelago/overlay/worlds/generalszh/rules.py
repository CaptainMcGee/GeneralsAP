from __future__ import annotations

from typing import TYPE_CHECKING

from worlds.generic.Rules import set_rule

from .constants import VICTORY_MEDAL_ITEM_NAMES, cluster_location_name
from .testing_catalog import WEAKNESS_TO_ITEMS, selected_testing_clusters
from .regions import MAIN_TO_BOSS_ENTRANCE

if TYPE_CHECKING:
    from .world import GeneralsZHWorld


def set_rules(world: GeneralsZHWorld) -> None:
    boss_entrance = world.get_entrance(MAIN_TO_BOSS_ENTRANCE)
    required_medals = tuple(VICTORY_MEDAL_ITEM_NAMES.values())
    set_rule(boss_entrance, lambda state: state.has_all(required_medals, world.player))
    set_cluster_rules(world)

    # Future Boss Win logic should gate the Victory event; medals only unlock boss-map access.
    world.multiworld.completion_condition[world.player] = lambda state: state.has("Victory", world.player)


def set_cluster_rules(world: GeneralsZHWorld) -> None:
    from .options import unlock_preset_name

    preset = unlock_preset_name(world.options.unlock_preset)
    for map_key, clusters in selected_testing_clusters(preset).items():
        for cluster in clusters:
            required_weaknesses = tuple(cluster["requiredWeaknesses"])
            for unit in cluster["units"]:
                name = cluster_location_name(map_key, int(cluster["clusterIndex"]), int(unit["unitIndex"]))
                location = world.get_location(name)
                set_rule(location, _cluster_access_rule(required_weaknesses, world.player))


def _cluster_access_rule(required_weaknesses: tuple[str, ...], player: int):
    def rule(state) -> bool:
        for weakness in required_weaknesses:
            candidate_items = WEAKNESS_TO_ITEMS[weakness]
            if not any(state.has(item, player) for item in candidate_items):
                return False
        return True

    return rule
