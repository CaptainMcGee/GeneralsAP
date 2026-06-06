from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from worlds.AutoWorld import World

from . import Items, Locations, Options, Regions, Rules
from .logic_foundry_import import load_logic_foundry_source, mission_location_name


class GeneralsZHWorld(World):
    """Command & Conquer: Generals - Zero Hour alpha AP world scaffold."""

    game = "Command & Conquer: Generals - Zero Hour"
    options_dataclass = Options.GeneralsZHOptions
    options: Options.GeneralsZHOptions
    item_name_to_id = Items.ITEM_NAME_TO_ID
    location_name_to_id = Locations.LOCATION_NAME_TO_ID

    def create_regions(self) -> None:
        Regions.create_regions(self)

    def set_rules(self) -> None:
        Rules.set_rules(self)

    def create_item(self, name: str) -> Items.GeneralsZHItem:
        return Items.create_item(self, name)

    def create_items(self) -> None:
        source = load_logic_foundry_source()
        locked_location_count = 0
        for mission in source.get("missions", []):
            if not mission.get("isBoss"):
                continue
            boss_location = self.multiworld.get_location(mission_location_name(mission), self.player)
            boss_location.place_locked_item(self.create_item("Victory"))
            locked_location_count += 1

        # Scaffold rule: current authored source has fewer locations than all
        # possible grouped unit/building items. Precollect non-medal placeholders
        # so cluster rules remain testable without inventing extra locations.
        available_slots = len(self.location_name_to_id) - locked_location_count
        medal_names = sorted(
            mission["victoryMedalItemName"]
            for mission in source.get("missions", [])
            if mission.get("victoryMedalItemName")
        )
        other_names = sorted(name for name in self.item_name_to_id if name != "Victory" and name not in medal_names)
        for name in other_names:
            self.multiworld.push_precollected(self.create_item(name))

        filler_slots = max(0, available_slots - len(medal_names))
        item_pool_names = medal_names + [self.get_filler_item_name()] * filler_slots
        self.multiworld.itempool += [self.create_item(name) for name in item_pool_names]

    def get_filler_item_name(self) -> str:
        return Items.FILLER_ITEM_NAME

    def fill_slot_data(self) -> Mapping[str, Any]:
        source = load_logic_foundry_source()
        route = Rules.route_for_world(self)
        return {
            "logicModel": source["apCompatibility"]["logicModel"],
            "slotDataVersion": source["apCompatibility"]["slotDataVersion"],
            "sourceKind": source["kind"],
            "route": {
                "faction": route.faction,
                "general": route.general,
                "itemMode": route.yaml_mode,
            },
            "missions": source["missions"],
            "clusterAccessRules": source["clusterAccessRules"],
            "worldGoal": source["worldGoal"],
        }
