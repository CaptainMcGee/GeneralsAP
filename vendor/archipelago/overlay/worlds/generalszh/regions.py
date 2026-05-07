from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Region

from .constants import MAIN_MAP_KEYS, MAP_SLOTS
from .locations import region_name_for_map

if TYPE_CHECKING:
    from .world import GeneralsZHWorld

MENU_REGION = "Menu"
MAIN_TO_BOSS_ENTRANCE = "GeneralsZH Main Victories to Boss"


def create_regions(world: GeneralsZHWorld) -> None:
    regions = [Region(MENU_REGION, world.player, world.multiworld)]
    regions.extend(
        Region(region_name_for_map(map_key), world.player, world.multiworld)
        for map_key in MAP_SLOTS
    )
    world.multiworld.regions += regions

    menu = world.get_region(MENU_REGION)
    for map_key in MAIN_MAP_KEYS:
        menu.connect(world.get_region(region_name_for_map(map_key)), f"GeneralsZH Menu to {map_key}")
    menu.connect(world.get_region(region_name_for_map("boss")), MAIN_TO_BOSS_ENTRANCE)
