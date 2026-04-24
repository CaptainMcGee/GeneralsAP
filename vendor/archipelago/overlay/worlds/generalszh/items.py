from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from .constants import GAME_NAME

if TYPE_CHECKING:
    from .world import GeneralsZHWorld

ITEM_ID_BASE = 270100000

ITEM_NAME_TO_ID: dict[str, int] = {
    "Shared Rocket Infantry": ITEM_ID_BASE + 1,
    "Shared Tanks": ITEM_ID_BASE + 2,
    "Shared Machine Gun Vehicles": ITEM_ID_BASE + 3,
    "Shared Artillery": ITEM_ID_BASE + 4,
    "Upgrade Radar": ITEM_ID_BASE + 5,
    "Progressive Starting Money": ITEM_ID_BASE + 6,
    "Progressive Production": ITEM_ID_BASE + 7,
    "Supply Cache": ITEM_ID_BASE + 8,
}

DEFAULT_ITEM_CLASSIFICATIONS: dict[str, ItemClassification] = {
    "Shared Rocket Infantry": ItemClassification.progression,
    "Shared Tanks": ItemClassification.progression,
    "Shared Machine Gun Vehicles": ItemClassification.progression,
    "Shared Artillery": ItemClassification.progression,
    "Upgrade Radar": ItemClassification.progression,
    "Progressive Starting Money": ItemClassification.progression,
    "Progressive Production": ItemClassification.progression,
    "Supply Cache": ItemClassification.filler,
}

SKELETON_ITEM_POOL: tuple[str, ...] = (
    "Shared Rocket Infantry",
    "Shared Tanks",
    "Shared Machine Gun Vehicles",
    "Shared Artillery",
    "Upgrade Radar",
    "Progressive Starting Money",
    "Progressive Production",
    "Supply Cache",
)


class GeneralsZHItem(Item):
    game = GAME_NAME


def create_item(world: GeneralsZHWorld, name: str) -> GeneralsZHItem:
    return GeneralsZHItem(
        name,
        DEFAULT_ITEM_CLASSIFICATIONS[name],
        ITEM_NAME_TO_ID[name],
        world.player,
    )


def create_all_items(world: GeneralsZHWorld) -> None:
    from .locations import enabled_location_count_for_preset
    from .options import unlock_preset_name

    preset = unlock_preset_name(world.options.unlock_preset)
    pool = item_pool_for_location_count(enabled_location_count_for_preset(preset))
    world.multiworld.itempool += [world.create_item(name) for name in pool]


def item_pool_for_location_count(location_count: int) -> list[str]:
    pool = list(SKELETON_ITEM_POOL)
    if len(pool) > location_count:
        return pool[:location_count]
    pool.extend(["Supply Cache"] * (location_count - len(pool)))
    return pool


def get_filler_item_name(_: GeneralsZHWorld) -> str:
    return "Supply Cache"
