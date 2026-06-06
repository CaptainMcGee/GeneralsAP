from __future__ import annotations

from dataclasses import dataclass

from Options import Choice, OptionGroup, PerGameCommonOptions


class StartingArmy(Choice):
    """Base army shown in the YAML. General choice controls the concrete unit route."""

    display_name = "Army"
    option_usa = 0
    option_china = 1
    option_gla = 2
    default = option_usa


class StartGeneral(Choice):
    """General whose units can count for route logic."""

    display_name = "General"
    option_usa = 0
    option_air_force = 1
    option_laser = 2
    option_superweapon = 3
    option_china = 4
    option_tank = 5
    option_nuke = 6
    option_infantry = 7
    option_gla = 8
    option_stealth = 9
    option_toxin = 10
    option_demolition = 11
    default = option_air_force


class ItemMode(Choice):
    """How AP item names are grouped while fielding still respects the active general."""

    display_name = "Item Mode"
    option_general_specific = 0
    option_faction_shared = 1
    option_abstract_shared = 2
    default = option_general_specific


@dataclass
class GeneralsZHOptions(PerGameCommonOptions):
    starting_army: StartingArmy
    start_general: StartGeneral
    item_mode: ItemMode


option_groups = [
    OptionGroup("Route", [StartingArmy, StartGeneral, ItemMode]),
]
