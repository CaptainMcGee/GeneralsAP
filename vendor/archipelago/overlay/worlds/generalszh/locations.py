from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import ItemClassification, Location

from . import items
from .constants import (
    cluster_location_name,
    cluster_unit_location_id,
    GAME_NAME,
    MAIN_MAP_KEYS,
    MAP_SLOTS,
    mission_location_name,
    mission_victory_location_id,
)
from .testing_catalog import all_testing_clusters, selected_testing_clusters

if TYPE_CHECKING:
    from .world import GeneralsZHWorld

MISSION_LOCATION_NAME_TO_ID: dict[str, int] = {
    mission_location_name(map_key): mission_victory_location_id(map_key)
    for map_key in MAIN_MAP_KEYS
}

CLUSTER_LOCATION_NAME_TO_ID: dict[str, int] = {
    cluster_location_name(map_key, int(cluster["clusterIndex"]), int(unit["unitIndex"])): cluster_unit_location_id(
        map_key,
        int(cluster["clusterIndex"]),
        int(unit["unitIndex"]),
    )
    for map_key, clusters in all_testing_clusters().items()
    for cluster in clusters
    for unit in cluster["units"]
}

LOCATION_NAME_TO_ID: dict[str, int] = {
    **MISSION_LOCATION_NAME_TO_ID,
    **CLUSTER_LOCATION_NAME_TO_ID,
}


class GeneralsZHLocation(Location):
    game = GAME_NAME


def create_mission_locations(world: GeneralsZHWorld) -> None:
    for map_key in MAP_SLOTS:
        region = world.get_region(region_name_for_map(map_key))
        name = mission_location_name(map_key)
        if map_key == "boss":
            location = GeneralsZHLocation(world.player, name, None, region)
            location.place_locked_item(
                items.GeneralsZHItem("Victory", ItemClassification.progression, None, world.player)
            )
            region.locations.append(location)
        else:
            region.add_locations({name: MISSION_LOCATION_NAME_TO_ID[name]}, GeneralsZHLocation)


def create_cluster_locations(world: GeneralsZHWorld) -> None:
    from .options import unlock_preset_name

    preset = unlock_preset_name(world.options.unlock_preset)
    for map_key, clusters in selected_testing_clusters(preset).items():
        region = world.get_region(region_name_for_map(map_key))
        for cluster in clusters:
            for unit in cluster["units"]:
                name = cluster_location_name(map_key, int(cluster["clusterIndex"]), int(unit["unitIndex"]))
                region.add_locations({name: LOCATION_NAME_TO_ID[name]}, GeneralsZHLocation)


def create_mission_events(world: GeneralsZHWorld) -> None:
    # Main challenge medals are shuffled AP items. Boss mission victory owns the locked final Victory item.
    return None


def region_name_for_map(map_key: str) -> str:
    return f"GeneralsZH {map_key}"


def enabled_location_count_for_preset(unlock_preset: str) -> int:
    cluster_units = sum(
        len(cluster["units"])
        for clusters in selected_testing_clusters(unlock_preset).values()
        for cluster in clusters
    )
    fillable_mission_locations = len(MAP_SLOTS) - 1  # Boss mission victory has a locked Victory item.
    return fillable_mission_locations + cluster_units


def selected_cluster_location_names(unlock_preset: str) -> list[str]:
    names: list[str] = []
    for map_key, clusters in selected_testing_clusters(unlock_preset).items():
        for cluster in clusters:
            for unit in cluster["units"]:
                names.append(cluster_location_name(map_key, int(cluster["clusterIndex"]), int(unit["unitIndex"])))
    return names
