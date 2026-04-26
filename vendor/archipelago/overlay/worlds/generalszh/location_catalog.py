from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from .constants import (
    MAP_SLOTS,
    captured_building_location_id,
    captured_building_location_name,
    captured_building_runtime_key,
    supply_pile_location_id,
    supply_pile_location_name,
    supply_pile_runtime_key,
)

CATALOG_VERSION = 1
CATALOG_STATUS = "catalog_only_disabled"


class LocationCatalogValidationError(ValueError):
    pass


def validate_location_catalog(catalog: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    _require(catalog.get("version") == CATALOG_VERSION, "invalid location catalog version")
    _require(catalog.get("status") == CATALOG_STATUS, "location catalog must stay disabled until runtime support exists")
    _require(catalog.get("familiesDefaultEnabled") is False, "future location families must default disabled")

    maps = catalog.get("maps")
    _require(isinstance(maps, Mapping), "catalog maps must be an object")
    _require(set(maps) == set(MAP_SLOTS), "catalog maps must match canonical map keys")

    seen_ids: set[int] = set()
    seen_keys: set[str] = set()

    for map_key in MAP_SLOTS:
        map_payload = maps[map_key]
        _require(isinstance(map_payload, Mapping), f"{map_key}: catalog map payload must be an object")
        captured = map_payload.get("capturedBuildings")
        supplies = map_payload.get("supplyPiles")
        _require(isinstance(captured, list), f"{map_key}: capturedBuildings must be a list")
        _require(isinstance(supplies, list), f"{map_key}: supplyPiles must be a list")
        _validate_captured_buildings(map_key, captured, seen_ids, seen_keys)
        _validate_supply_piles(map_key, supplies, seen_ids, seen_keys)

    if not seen_ids:
        warnings.append("location catalog contains no future checks yet; this is valid while families stay disabled")
    return warnings


def iter_catalog_location_records(catalog: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    validate_location_catalog(catalog)
    for map_key in MAP_SLOTS:
        map_payload = catalog["maps"][map_key]
        for entry in map_payload["capturedBuildings"]:
            building_index = _int_field(entry, "buildingIndex", f"{map_key}.capturedBuildings")
            yield {
                "family": "captured_building",
                "mapKey": map_key,
                "locationName": captured_building_location_name(map_key, building_index),
                "runtimeKey": captured_building_runtime_key(map_key, building_index),
                "apLocationId": captured_building_location_id(map_key, building_index),
                "label": entry["label"],
                "sourceIndex": building_index,
            }
        for pile in map_payload["supplyPiles"]:
            pile_index = _int_field(pile, "pileIndex", f"{map_key}.supplyPiles")
            for threshold in pile["thresholds"]:
                threshold_index = _int_field(threshold, "thresholdIndex", f"{map_key}.supplyPiles[{pile_index}]")
                yield {
                    "family": "supply_pile_threshold",
                    "mapKey": map_key,
                    "locationName": supply_pile_location_name(map_key, pile_index, threshold_index),
                    "runtimeKey": supply_pile_runtime_key(map_key, pile_index, threshold_index),
                    "apLocationId": supply_pile_location_id(map_key, pile_index, threshold_index),
                    "label": pile["label"],
                    "sourceIndex": pile_index,
                    "thresholdIndex": threshold_index,
                    "amountCollected": threshold.get("amountCollected"),
                    "fractionCollected": threshold.get("fractionCollected"),
                }


def catalog_location_counts(catalog: Mapping[str, Any]) -> dict[str, int]:
    counts = {
        "captured_building": 0,
        "supply_pile_threshold": 0,
        "total": 0,
    }
    for record in iter_catalog_location_records(catalog):
        counts[record["family"]] += 1
        counts["total"] += 1
    return counts


def _validate_captured_buildings(
    map_key: str,
    entries: list[Mapping[str, Any]],
    seen_ids: set[int],
    seen_keys: set[str],
) -> None:
    seen_indices: set[int] = set()
    for entry in entries:
        label = f"{map_key}.capturedBuildings"
        _require(isinstance(entry, Mapping), f"{label}: entry must be an object")
        building_index = _int_field(entry, "buildingIndex", label)
        _require(building_index not in seen_indices, f"{label}: duplicate buildingIndex {building_index}")
        seen_indices.add(building_index)
        _require_nonempty_string(entry, "label", label)
        _validate_optional_position(entry, label)

        runtime_key = captured_building_runtime_key(map_key, building_index)
        ap_location_id = captured_building_location_id(map_key, building_index)
        location_name = captured_building_location_name(map_key, building_index)
        _validate_optional_derived_fields(entry, label, runtime_key, ap_location_id, location_name)
        _track_unique(runtime_key, ap_location_id, seen_keys, seen_ids)


def _validate_supply_piles(
    map_key: str,
    entries: list[Mapping[str, Any]],
    seen_ids: set[int],
    seen_keys: set[str],
) -> None:
    seen_indices: set[int] = set()
    for pile in entries:
        label = f"{map_key}.supplyPiles"
        _require(isinstance(pile, Mapping), f"{label}: entry must be an object")
        pile_index = _int_field(pile, "pileIndex", label)
        _require(pile_index not in seen_indices, f"{label}: duplicate pileIndex {pile_index}")
        seen_indices.add(pile_index)
        _require_nonempty_string(pile, "label", label)
        _validate_optional_position(pile, label)

        starting_amount = pile.get("startingAmount")
        if starting_amount is not None:
            _require(isinstance(starting_amount, int) and starting_amount > 0, f"{label}: startingAmount must be positive integer")

        thresholds = pile.get("thresholds")
        _require(isinstance(thresholds, list) and thresholds, f"{label}: thresholds must be a non-empty list")
        seen_thresholds: set[int] = set()
        previous_amount = -1
        previous_fraction = -1.0
        for threshold in thresholds:
            threshold_label = f"{label}[{pile_index}].thresholds"
            _require(isinstance(threshold, Mapping), f"{threshold_label}: threshold must be an object")
            threshold_index = _int_field(threshold, "thresholdIndex", threshold_label)
            _require(threshold_index not in seen_thresholds, f"{threshold_label}: duplicate thresholdIndex {threshold_index}")
            seen_thresholds.add(threshold_index)

            amount = threshold.get("amountCollected")
            fraction = threshold.get("fractionCollected")
            _require(amount is not None or fraction is not None, f"{threshold_label}: threshold needs amountCollected or fractionCollected")
            if amount is not None:
                _require(isinstance(amount, int) and amount > 0, f"{threshold_label}: amountCollected must be positive integer")
                _require(amount > previous_amount, f"{threshold_label}: amountCollected must increase")
                previous_amount = amount
            if fraction is not None:
                _require(isinstance(fraction, int | float) and 0 < float(fraction) <= 1, f"{threshold_label}: fractionCollected must be 0..1")
                _require(float(fraction) > previous_fraction, f"{threshold_label}: fractionCollected must increase")
                previous_fraction = float(fraction)

            runtime_key = supply_pile_runtime_key(map_key, pile_index, threshold_index)
            ap_location_id = supply_pile_location_id(map_key, pile_index, threshold_index)
            location_name = supply_pile_location_name(map_key, pile_index, threshold_index)
            _validate_optional_derived_fields(threshold, threshold_label, runtime_key, ap_location_id, location_name)
            _track_unique(runtime_key, ap_location_id, seen_keys, seen_ids)


def _validate_optional_derived_fields(
    entry: Mapping[str, Any],
    label: str,
    runtime_key: str,
    ap_location_id: int,
    location_name: str,
) -> None:
    if "runtimeKey" in entry:
        _require(entry["runtimeKey"] == runtime_key, f"{label}: runtimeKey drift")
    if "apLocationId" in entry:
        _require(entry["apLocationId"] == ap_location_id, f"{label}: apLocationId drift")
    if "locationName" in entry:
        _require(entry["locationName"] == location_name, f"{label}: locationName drift")


def _validate_optional_position(entry: Mapping[str, Any], label: str) -> None:
    position = entry.get("position")
    if position is None:
        return
    _require(isinstance(position, Mapping), f"{label}: position must be an object")
    _require(isinstance(position.get("x"), int | float), f"{label}: position.x must be numeric")
    _require(isinstance(position.get("y"), int | float), f"{label}: position.y must be numeric")


def _int_field(entry: Mapping[str, Any], key: str, label: str) -> int:
    value = entry.get(key)
    _require(isinstance(value, int), f"{label}: {key} must be an integer")
    return int(value)


def _require_nonempty_string(entry: Mapping[str, Any], key: str, label: str) -> None:
    value = entry.get(key)
    _require(isinstance(value, str) and bool(value.strip()), f"{label}: {key} must be non-empty string")


def _track_unique(runtime_key: str, ap_location_id: int, seen_keys: set[str], seen_ids: set[int]) -> None:
    _require(runtime_key not in seen_keys, f"duplicate catalog runtime key: {runtime_key}")
    _require(ap_location_id not in seen_ids, f"duplicate catalog AP location ID: {ap_location_id}")
    seen_keys.add(runtime_key)
    seen_ids.add(ap_location_id)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LocationCatalogValidationError(message)
