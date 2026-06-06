from __future__ import annotations

from BaseClasses import Item, ItemClassification

from .logic_foundry_import import item_name_to_id, load_logic_foundry_source, validate_logic_foundry_source


SOURCE = load_logic_foundry_source()
validate_logic_foundry_source(SOURCE)
ITEM_NAME_TO_ID = item_name_to_id(SOURCE)
NEXT_SCAFFOLD_ITEM_ID = max(item_id for item_id in ITEM_NAME_TO_ID.values() if item_id is not None) + 1
ITEM_NAME_TO_ID["Victory"] = NEXT_SCAFFOLD_ITEM_ID
FILLER_ITEM_NAME = "Supply Drop"
ITEM_NAME_TO_ID[FILLER_ITEM_NAME] = NEXT_SCAFFOLD_ITEM_ID + 1


class GeneralsZHItem(Item):
    game = "Command & Conquer: Generals - Zero Hour"


def item_classification(name: str) -> ItemClassification:
    if name == FILLER_ITEM_NAME:
        return ItemClassification.filler
    if name == "Victory":
        return ItemClassification.progression
    if name.endswith(" Medal"):
        return ItemClassification.progression
    return ItemClassification.progression


def create_item(world, name: str) -> GeneralsZHItem:
    return GeneralsZHItem(name, item_classification(name), ITEM_NAME_TO_ID[name], world.player)
