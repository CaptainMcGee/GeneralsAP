from __future__ import annotations

from BaseClasses import Region

from .Locations import GeneralsZHLocation, LOCATION_NAME_TO_ID


def create_regions(world) -> None:
    region = Region("Menu", world.player, world.multiworld)
    for name, location_id in LOCATION_NAME_TO_ID.items():
        region.locations.append(GeneralsZHLocation(world.player, name, location_id, region))
    world.multiworld.regions.append(region)
