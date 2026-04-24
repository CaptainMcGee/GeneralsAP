from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from worlds.AutoWorld import World

from . import items, locations, options, regions, rules
from .constants import GAME_NAME
from .slot_data import build_testing_slot_data


class GeneralsZHWorld(World):
    """Archipelago skeleton for GeneralsAP alpha."""

    game = GAME_NAME
    options_dataclass = options.GeneralsZHOptions
    options: options.GeneralsZHOptions
    item_name_to_id = items.ITEM_NAME_TO_ID
    location_name_to_id = locations.LOCATION_NAME_TO_ID
    origin_region_name = regions.MENU_REGION

    def create_regions(self) -> None:
        regions.create_regions(self)
        locations.create_mission_locations(self)
        locations.create_cluster_locations(self)
        locations.create_mission_events(self)

    def create_items(self) -> None:
        items.create_all_items(self)

    def create_item(self, name: str) -> items.GeneralsZHItem:
        return items.create_item(self, name)

    def set_rules(self) -> None:
        rules.set_rules(self)

    def get_filler_item_name(self) -> str:
        return items.get_filler_item_name(self)

    def fill_slot_data(self) -> Mapping[str, Any]:
        seed_name = getattr(self.multiworld, "seed_name", "unknown-seed")
        slot_name = self.multiworld.get_player_name(self.player)
        preset = options.unlock_preset_name(self.options.unlock_preset)
        return build_testing_slot_data(
            seed_id=str(seed_name),
            slot_name=slot_name,
            session_nonce=f"{seed_name}:{self.player}",
            unlock_preset=preset,
        )
