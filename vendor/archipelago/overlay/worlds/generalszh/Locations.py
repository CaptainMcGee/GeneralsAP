from __future__ import annotations

from BaseClasses import Location

from .logic_foundry_import import (
    load_logic_foundry_source,
    location_name_to_id,
    validate_logic_foundry_source,
)


SOURCE = load_logic_foundry_source()
validate_logic_foundry_source(SOURCE)
LOCATION_NAME_TO_ID = location_name_to_id(SOURCE)


class GeneralsZHLocation(Location):
    game = "Command & Conquer: Generals - Zero Hour"
