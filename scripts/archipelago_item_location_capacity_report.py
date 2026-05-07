#!/usr/bin/env python3
"""Report current AP item/location capacity without enabling future checks."""

from __future__ import annotations

import argparse
import json
import math
import sys
import types
from collections import Counter
from enum import IntFlag
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OVERLAY_WORLDS = REPO / "vendor" / "archipelago" / "overlay" / "worlds"
DEFAULT_CATALOG = REPO / "Data" / "Archipelago" / "location_families" / "catalog.json"
DEFAULT_LOCATION_TARGETS = REPO / "Data" / "Archipelago" / "location_families" / "capacity_targets.json"
DEFAULT_TARGET_ITEM_COUNTS = (15, 100, 300, 600)
PLANNING_MODES = ("min", "target", "max")


def install_lightweight_archipelago_stubs() -> None:
    if "BaseClasses" not in sys.modules:
        baseclasses = types.ModuleType("BaseClasses")

        class ItemClassification(IntFlag):
            filler = 0
            progression = 1
            useful = 2
            trap = 4

        class Item:
            game = ""

            def __init__(self, name, classification, code, player):
                self.name = name
                self.classification = classification
                self.code = code
                self.player = player

        class Location:
            game = ""

            def __init__(self, player, name, address=None, parent=None):
                self.player = player
                self.name = name
                self.address = address
                self.parent_region = parent

        baseclasses.ItemClassification = ItemClassification
        baseclasses.Item = Item
        baseclasses.Location = Location
        sys.modules["BaseClasses"] = baseclasses

    if str(OVERLAY_WORLDS) not in sys.path:
        sys.path.insert(0, str(OVERLAY_WORLDS))
    worlds_pkg = sys.modules.setdefault("worlds", types.ModuleType("worlds"))
    worlds_pkg.__path__ = [str(OVERLAY_WORLDS)]  # type: ignore[attr-defined]
    generals_pkg = sys.modules.setdefault("worlds.generalszh", types.ModuleType("worlds.generalszh"))
    generals_pkg.__path__ = [str(OVERLAY_WORLDS / "generalszh")]  # type: ignore[attr-defined]


def load_world_helpers():
    install_lightweight_archipelago_stubs()
    from worlds.generalszh import constants, content_framework, items, location_catalog, locations, slot_data  # type: ignore[import-not-found]

    return constants, content_framework, items, location_catalog, locations, slot_data


def classification_name(items_module: Any, item_name: str) -> str:
    value = items_module.DEFAULT_ITEM_CLASSIFICATIONS[item_name]
    if value == items_module.ItemClassification.progression:
        return "progression"
    if value == items_module.ItemClassification.useful:
        return "useful"
    if value == items_module.ItemClassification.trap:
        return "trap"
    return "filler"


def required_locations_for_target(
    item_count: int,
    buffer_percent: int = 25,
    min_spare_locations: int = 25,
) -> int:
    if item_count <= 0:
        raise ValueError(f"item_count must be positive, got {item_count!r}")
    if buffer_percent < 0:
        raise ValueError(f"buffer_percent must be non-negative, got {buffer_percent!r}")
    if min_spare_locations < 0:
        raise ValueError(f"min_spare_locations must be non-negative, got {min_spare_locations!r}")
    spare = max(math.ceil(item_count * buffer_percent / 100), min_spare_locations)
    return item_count + spare


def load_location_capacity_targets(path: Path = DEFAULT_LOCATION_TARGETS) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def planned_location_target_counts(
    targets: dict[str, Any],
    map_keys: list[str],
) -> dict[str, Any]:
    if targets.get("version") != 1:
        raise ValueError("location capacity targets version must be 1")
    if targets.get("status") != "planning_only_disabled":
        raise ValueError("location capacity targets must stay planning_only_disabled")
    thresholds_per_pile = targets.get("thresholdsPerSupplyPile")
    if not isinstance(thresholds_per_pile, dict):
        raise ValueError("thresholdsPerSupplyPile must be object")
    maps = targets.get("maps")
    if not isinstance(maps, dict):
        raise ValueError("location capacity target maps must be object")
    if set(maps) != set(map_keys):
        raise ValueError("location capacity target maps must match canonical map keys")

    counts: dict[str, Any] = {}
    for mode in PLANNING_MODES:
        threshold_count = thresholds_per_pile.get(mode)
        if not isinstance(threshold_count, int) or threshold_count <= 0:
            raise ValueError(f"{mode}: thresholdsPerSupplyPile must be positive integer")
        captured_total = 0
        supply_pile_total = 0
        per_map: dict[str, Any] = {}
        for map_key in map_keys:
            mode_payload = maps[map_key].get(mode)
            if not isinstance(mode_payload, dict):
                raise ValueError(f"{map_key}: missing {mode} location capacity target")
            captured = mode_payload.get("capturedBuildings")
            supply_piles = mode_payload.get("supplyPiles")
            if not isinstance(captured, int) or captured < 0:
                raise ValueError(f"{map_key}.{mode}: capturedBuildings must be non-negative integer")
            if not isinstance(supply_piles, int) or supply_piles < 0:
                raise ValueError(f"{map_key}.{mode}: supplyPiles must be non-negative integer")
            captured_total += captured
            supply_pile_total += supply_piles
            per_map[map_key] = {
                "captured_buildings": captured,
                "supply_piles": supply_piles,
                "supply_thresholds": supply_piles * threshold_count,
                "total_future_checks": captured + (supply_piles * threshold_count),
            }
        supply_threshold_total = supply_pile_total * threshold_count
        counts[mode] = {
            "thresholds_per_supply_pile": threshold_count,
            "captured_buildings": captured_total,
            "supply_piles": supply_pile_total,
            "supply_thresholds": supply_threshold_total,
            "total_future_checks": captured_total + supply_threshold_total,
            "per_map": per_map,
        }
    return counts


def build_capacity_report(
    target_item_counts: list[int] | None = None,
    buffer_percent: int = 25,
    min_spare_locations: int = 25,
    catalog_path: Path = DEFAULT_CATALOG,
    location_targets_path: Path = DEFAULT_LOCATION_TARGETS,
) -> dict[str, Any]:
    constants, content_framework, items, location_catalog, locations, slot_data = load_world_helpers()
    target_item_counts = target_item_counts or list(DEFAULT_TARGET_ITEM_COUNTS)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_warnings = location_catalog.validate_location_catalog(catalog)
    catalog_counts = location_catalog.catalog_location_counts(catalog)
    location_targets = load_location_capacity_targets(location_targets_path)
    location_target_counts = planned_location_target_counts(location_targets, list(constants.MAP_SLOTS))

    presets: dict[str, Any] = {}
    fixed_pool_size = len(items.SKELETON_ITEM_POOL)
    fixed_item_class_counts = Counter(
        classification_name(items, item_name)
        for item_name in items.SKELETON_ITEM_POOL
    )

    for preset in ("minimal", "default"):
        enabled_locations = locations.enabled_location_count_for_preset(preset)
        cluster_units = len(locations.selected_cluster_location_names(preset))
        fillable_missions = enabled_locations - cluster_units
        pool = items.item_pool_for_location_count(enabled_locations)
        item_counts = Counter(pool)
        class_counts = Counter(classification_name(items, item_name) for item_name in pool)
        seeded_payload = slot_data.build_testing_slot_data(
            seed_id=f"capacity-{preset}",
            slot_name="Capacity Report",
            session_nonce=f"capacity-{preset}:1",
            unlock_preset=preset,
        )
        presets[preset] = {
            "enabled_locations": enabled_locations,
            "fillable_mission_locations": fillable_missions,
            "selected_cluster_unit_locations": cluster_units,
            "item_pool_size": len(pool),
            "unique_item_types_in_pool": len(item_counts),
            "fixed_skeleton_pool_size": fixed_pool_size,
            "extra_supply_cache_copies": max(0, len(pool) - fixed_pool_size),
            "item_class_counts": dict(sorted(class_counts.items())),
            "selected_future_locations": slot_data.selected_future_location_count(seeded_payload),
        }

    capture_capacity = len(constants.MAP_SLOTS) * (constants.CAPTURED_BUILDING_STRIDE - 1)
    supply_capacity = len(constants.MAP_SLOTS) * 49 * 9
    future_capacity = {
        "captured_building_id_lanes": capture_capacity,
        "supply_pile_threshold_id_lanes": supply_capacity,
        "total_disabled_future_id_lanes": capture_capacity + supply_capacity,
        "authored_catalog_counts": catalog_counts,
        "catalog_warnings": catalog_warnings,
        "production_guard_active": all(
            presets[preset]["selected_future_locations"] == 0
            for preset in presets
        ),
    }

    active_planned_names = {
        entry.item_name
        for entry in content_framework.PLANNED_ITEM_COPY_ENTRIES
        if entry.active_item
    }
    fixed_core_items = [
        item_name
        for item_name in items.SKELETON_ITEM_POOL
        if item_name not in active_planned_names
    ]
    planned_modes: dict[str, Any] = {}
    for mode in PLANNING_MODES:
        copy_counts = content_framework.planned_item_copy_counts(mode)
        planned_total_items = len(fixed_core_items) + sum(copy_counts.values())
        required = required_locations_for_target(planned_total_items, buffer_percent, min_spare_locations)
        planned_modes[mode] = {
            "fixed_core_items": len(fixed_core_items),
            "planned_copy_counts": copy_counts,
            "planned_total_items": planned_total_items,
            "required_locations_with_buffer": required,
            "default_shortfall": max(0, required - presets["default"]["enabled_locations"]),
            "minimal_shortfall": max(0, required - presets["minimal"]["enabled_locations"]),
        }

    projected_location_modes: dict[str, Any] = {}
    for mode in PLANNING_MODES:
        planned_locations = location_target_counts[mode]
        planned_items = planned_modes[mode]
        projected_default = presets["default"]["enabled_locations"] + planned_locations["total_future_checks"]
        projected_minimal = presets["minimal"]["enabled_locations"] + planned_locations["total_future_checks"]
        projected_location_modes[mode] = {
            "planned_future_checks": planned_locations["total_future_checks"],
            "projected_default_locations": projected_default,
            "projected_minimal_locations": projected_minimal,
            "required_locations_with_buffer": planned_items["required_locations_with_buffer"],
            "projected_default_shortfall": max(0, planned_items["required_locations_with_buffer"] - projected_default),
            "projected_minimal_shortfall": max(0, planned_items["required_locations_with_buffer"] - projected_minimal),
        }

    scenarios: dict[str, Any] = {}
    for item_count in target_item_counts:
        required = required_locations_for_target(item_count, buffer_percent, min_spare_locations)
        scenarios[str(item_count)] = {
            "target_item_count": item_count,
            "required_locations_with_buffer": required,
            "buffer_percent": buffer_percent,
            "min_spare_locations": min_spare_locations,
            "default_shortfall": max(0, required - presets["default"]["enabled_locations"]),
            "minimal_shortfall": max(0, required - presets["minimal"]["enabled_locations"]),
        }

    return {
        "summary": {
            "scope": "accounting_only_no_new_locations_enabled",
            "fixed_skeleton_pool_size": fixed_pool_size,
            "fixed_item_class_counts": dict(sorted(fixed_item_class_counts.items())),
        },
        "presets": presets,
        "future_location_capacity": future_capacity,
        "planned_item_pool": {
            "status": "planning_only_not_active_generation",
            "fixed_core_items": fixed_core_items,
            "entries": [
                {
                    "item_name": entry.item_name,
                    "category": entry.category,
                    "classification": entry.classification,
                    "active_item": entry.active_item,
                    "min_copies": entry.min_copies,
                    "target_copies": entry.target_copies,
                    "max_copies": entry.max_copies,
                    "notes": entry.notes,
                }
                for entry in content_framework.PLANNED_ITEM_COPY_ENTRIES
            ],
            "modes": planned_modes,
        },
        "planned_location_targets": {
            "status": "planning_only_not_active_generation",
            "counts": location_target_counts,
            "projected_modes": projected_location_modes,
        },
        "target_scenarios": scenarios,
    }


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# GeneralsZH AP Item/Location Capacity Report",
        "",
        "Scope: accounting only. No future location family is enabled by this report.",
        "",
        "## Current enabled presets",
        "",
        "| Preset | Enabled locations | Mission checks | Cluster-unit checks | Item pool | Unique item types | Extra Supply Cache copies | Future checks selected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for preset, data in report["presets"].items():
        lines.append(
            "| {preset} | {enabled_locations} | {fillable_mission_locations} | {selected_cluster_unit_locations} | "
            "{item_pool_size} | {unique_item_types_in_pool} | {extra_supply_cache_copies} | {selected_future_locations} |".format(
                preset=preset,
                **data,
            )
        )

    future = report["future_location_capacity"]
    lines.extend(
        [
            "",
            "## Disabled future location lanes",
            "",
            f"- Captured-building ID lanes: {future['captured_building_id_lanes']}",
            f"- Supply-pile-threshold ID lanes: {future['supply_pile_threshold_id_lanes']}",
            f"- Total reserved future lanes: {future['total_disabled_future_id_lanes']}",
            f"- Authored active future checks today: {future['authored_catalog_counts']['total']}",
            f"- Production guard active: {future['production_guard_active']}",
        ]
    )
    for warning in future["catalog_warnings"]:
        lines.append(f"- Catalog warning: {warning}")

    lines.extend(
        [
            "",
            "## Planned item-copy pressure",
            "",
            "Status: planning only. Counts below do not change active AP item generation.",
            "",
            "| Mode | Planned items | Required locations with buffer | Default shortfall | Minimal shortfall | Starting Money | Production | Supply Cache | Future filler | Future traps |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    planned = report["planned_item_pool"]
    for mode, data in planned["modes"].items():
        counts = data["planned_copy_counts"]
        lines.append(
            "| {mode} | {planned_total_items} | {required_locations_with_buffer} | {default_shortfall} | {minimal_shortfall} | "
            "{starting_money} | {production} | {supply_cache} | {future_filler} | {future_traps} |".format(
                mode=mode,
                planned_total_items=data["planned_total_items"],
                required_locations_with_buffer=data["required_locations_with_buffer"],
                default_shortfall=data["default_shortfall"],
                minimal_shortfall=data["minimal_shortfall"],
                starting_money=counts["Progressive Starting Money"],
                production=counts["Progressive Production"],
                supply_cache=counts["Supply Cache"],
                future_filler=counts["Future Filler Slot"],
                future_traps=counts["Future Trap Slot"],
            )
        )

    lines.extend(
        [
            "",
            "## Planned location-family targets",
            "",
            "Status: planning only. Counts below do not add catalog records or production locations.",
            "",
            "| Mode | Future checks | Captured buildings | Supply piles | Supply thresholds | Projected default locations | Required locations | Projected default shortfall |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    location_targets = report["planned_location_targets"]
    for mode, counts in location_targets["counts"].items():
        projected = location_targets["projected_modes"][mode]
        lines.append(
            "| {mode} | {future_checks} | {captured} | {supply_piles} | {supply_thresholds} | {projected_default} | {required} | {shortfall} |".format(
                mode=mode,
                future_checks=counts["total_future_checks"],
                captured=counts["captured_buildings"],
                supply_piles=counts["supply_piles"],
                supply_thresholds=counts["supply_thresholds"],
                projected_default=projected["projected_default_locations"],
                required=projected["required_locations_with_buffer"],
                shortfall=projected["projected_default_shortfall"],
            )
        )

    lines.extend(
        [
            "",
            "## Target item-count pressure",
            "",
            "| Target items | Required locations with buffer | Default shortfall | Minimal shortfall |",
            "|---:|---:|---:|---:|",
        ]
    )
    for scenario in report["target_scenarios"].values():
        lines.append(
            "| {target_item_count} | {required_locations_with_buffer} | {default_shortfall} | {minimal_shortfall} |".format(
                **scenario
            )
        )

    lines.extend(
        [
            "",
            "## Findings",
            "",
            f"- Current default preset has {report['presets']['default']['enabled_locations']} fillable locations.",
            f"- Current minimal preset has {report['presets']['minimal']['enabled_locations']} fillable locations.",
            f"- Planned target item pool is {report['planned_item_pool']['modes']['target']['planned_total_items']} items before per-general unit expansion.",
            f"- Planned target location families add {report['planned_location_targets']['counts']['target']['total_future_checks']} inactive future checks, enough for target economy/filler pressure once runtime support exists.",
            "- Current active presets can absorb some new items by replacing duplicate Supply Cache filler, but they are not enough for per-general unit granularity.",
            "- Reserved future ID lanes are large enough for authored capture/supply checks, but runtime completion/persistence must land before those checks become production locations.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_target_counts(raw: str) -> list[int]:
    counts = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not counts:
        raise argparse.ArgumentTypeError("at least one target item count is required")
    if any(count <= 0 for count in counts):
        raise argparse.ArgumentTypeError("target item counts must be positive")
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-item-counts",
        type=parse_target_counts,
        default=list(DEFAULT_TARGET_ITEM_COUNTS),
        help="Comma-separated future item-count scenarios. Default: 15,100,300,600.",
    )
    parser.add_argument("--buffer-percent", type=int, default=25)
    parser.add_argument("--min-spare-locations", type=int, default=25)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    report = build_capacity_report(
        target_item_counts=list(args.target_item_counts),
        buffer_percent=args.buffer_percent,
        min_spare_locations=args.min_spare_locations,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
