from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .constants import CAPTURED_BUILDING_BASE, CLUSTER_UNIT_BASE, MISSION_VICTORY_BASE, SUPPLY_PILE_BASE


@dataclass(frozen=True)
class EconomyItemEffect:
    item_name: str
    effect_key: str
    default_classification: str
    runtime_field: str | None
    notes: str
    min_step_percent: int | None = None
    max_step_percent: int | None = None
    total_cap_percent: int | None = None


@dataclass(frozen=True)
class LocationFamily:
    key: str
    id_base: int
    runtime_key_pattern: str
    default_enabled: bool
    repeat_model: str
    runtime_support: str
    notes: str


ECONOMY_ITEM_EFFECTS: Mapping[str, EconomyItemEffect] = {
    "Progressive Starting Money": EconomyItemEffect(
        item_name="Progressive Starting Money",
        effect_key="starting_cash_floor",
        default_classification="useful_until_mission_logic_uses_it",
        runtime_field="startingCashBonus",
        notes="Permanent starting-cash floor. May become progression for Hold/Win when mission logic consumes it.",
    ),
    "Progressive Production": EconomyItemEffect(
        item_name="Progressive Production",
        effect_key="production_speed_bonus",
        default_classification="useful_until_mission_logic_uses_it",
        runtime_field="productionMultiplier",
        min_step_percent=25,
        max_step_percent=100,
        total_cap_percent=300,
        notes="Configurable per-item production speed bonus. +300% total cap means 4x final production multiplier.",
    ),
    "Supply Cache": EconomyItemEffect(
        item_name="Supply Cache",
        effect_key="cash_drop_once",
        default_classification="filler",
        runtime_field=None,
        notes="One-time cash item. Apply immediately if in mission, otherwise queue for next mission start.",
    ),
}


LOCATION_FAMILIES: Mapping[str, LocationFamily] = {
    "mission_victory": LocationFamily(
        key="mission_victory",
        id_base=MISSION_VICTORY_BASE,
        runtime_key_pattern="mission.<map>.victory",
        default_enabled=True,
        repeat_model="one_location_per_map",
        runtime_support="implemented",
        notes="Main mission victory checks plus Boss locked Victory item.",
    ),
    "cluster_unit": LocationFamily(
        key="cluster_unit",
        id_base=CLUSTER_UNIT_BASE,
        runtime_key_pattern="cluster.<map>.cXX.uYY",
        default_enabled=True,
        repeat_model="one_location_per_spawned_unit",
        runtime_support="implemented_for_seeded_clusters",
        notes="Selected seeded cluster-unit checks. Future authored clusters should use same family.",
    ),
    "captured_building": LocationFamily(
        key="captured_building",
        id_base=CAPTURED_BUILDING_BASE,
        runtime_key_pattern="capture.<map>.bXXX",
        default_enabled=False,
        repeat_model="one_location_per_authored_capturable_building",
        runtime_support="planned",
        notes="Capture check when player captures authored neutral/building objective. Receiving captured-building items should pre-capture matching buildings at mission start.",
    ),
    "supply_pile_threshold": LocationFamily(
        key="supply_pile_threshold",
        id_base=SUPPLY_PILE_BASE,
        runtime_key_pattern="supply.<map>.pXX.tYY",
        default_enabled=False,
        repeat_model="multiple_threshold_locations_per_pile_until_depleted",
        runtime_support="planned",
        notes="AP locations are one-shot, so repeatable supply piles become several threshold checks that persist after mission restart.",
    ),
}


def production_bonus_copy_count(step_percent: int, total_cap_percent: int = 300) -> int:
    if not 25 <= step_percent <= 100:
        raise ValueError(f"production bonus step must be 25..100, got {step_percent!r}")
    if total_cap_percent <= 0:
        raise ValueError(f"production bonus cap must be positive, got {total_cap_percent!r}")
    return (total_cap_percent + step_percent - 1) // step_percent


def production_multiplier_for_copies(copies: int, step_percent: int, total_cap_percent: int = 300) -> float:
    if copies < 0:
        raise ValueError(f"copies must be non-negative, got {copies!r}")
    applied_percent = min(copies * step_percent, total_cap_percent)
    return 1.0 + (applied_percent / 100.0)
