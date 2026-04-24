from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import ItemClassification, Location

from . import items
from .constants import (
    GAME_NAME,
    MAIN_MAP_KEYS,
    MAP_SLOTS,
    MISSION_EVENT_ITEM_NAMES,
    mission_location_name,
    mission_victory_location_id,
)

if TYPE_CHECKING:
    from .world import GeneralsZHWorld

LOCATION_NAME_TO_ID: dict[str, int] = {
    mission_location_name(map_key): mission_victory_location_id(map_key)
    for map_key in MAP_SLOTS
}


class GeneralsZHLocation(Location):
    game = GAME_NAME


def create_mission_locations(world: GeneralsZHWorld) -> None:
    for map_key in MAP_SLOTS:
        region = world.get_region(region_name_for_map(map_key))
        region.add_locations(
            {mission_location_name(map_key): LOCATION_NAME_TO_ID[mission_location_name(map_key)]},
            GeneralsZHLocation,
        )


def create_mission_events(world: GeneralsZHWorld) -> None:
    for map_key in MAIN_MAP_KEYS:
        region = world.get_region(region_name_for_map(map_key))
        event_location = GeneralsZHLocation(
            world.player,
            f"Event - {MISSION_EVENT_ITEM_NAMES[map_key]}",
            None,
            region,
        )
        event_item = items.GeneralsZHItem(
            MISSION_EVENT_ITEM_NAMES[map_key],
            ItemClassification.progression,
            None,
            world.player,
        )
        event_location.place_locked_item(event_item)
        region.locations.append(event_location)

    boss_region = world.get_region(region_name_for_map("boss"))
    boss_region.add_event("Event - GeneralsAP Victory", "Victory", GeneralsZHLocation, items.GeneralsZHItem)


def region_name_for_map(map_key: str) -> str:
    return f"GeneralsZH {map_key}"
