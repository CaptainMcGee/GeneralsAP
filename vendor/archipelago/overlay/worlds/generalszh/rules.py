from __future__ import annotations

from typing import TYPE_CHECKING

from worlds.generic.Rules import set_rule

from .constants import MISSION_EVENT_ITEM_NAMES
from .regions import MAIN_TO_BOSS_ENTRANCE

if TYPE_CHECKING:
    from .world import GeneralsZHWorld


def set_rules(world: GeneralsZHWorld) -> None:
    boss_entrance = world.get_entrance(MAIN_TO_BOSS_ENTRANCE)
    required_victories = tuple(MISSION_EVENT_ITEM_NAMES.values())
    set_rule(boss_entrance, lambda state: state.has_all(required_victories, world.player))

    world.multiworld.completion_condition[world.player] = lambda state: state.has("Victory", world.player)
