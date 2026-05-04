#!/usr/bin/env python3
"""Validate disabled future logic contract handoff files."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OVERLAY_WORLDS = REPO / "vendor" / "archipelago" / "overlay" / "worlds"
DEFAULT_CONTRACT_DIR = REPO / "Data" / "Archipelago" / "logic_contracts"


class LogicContractValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LogicContractValidationError(message)


def load_generalszh_symbols() -> tuple[dict[str, int], tuple[str, ...], tuple[str, ...]]:
    if str(OVERLAY_WORLDS) not in sys.path:
        sys.path.insert(0, str(OVERLAY_WORLDS))
    worlds_pkg = types.ModuleType("worlds")
    worlds_pkg.__path__ = [str(OVERLAY_WORLDS)]  # type: ignore[attr-defined]
    sys.modules.setdefault("worlds", worlds_pkg)
    generals_pkg = types.ModuleType("worlds.generalszh")
    generals_pkg.__path__ = [str(OVERLAY_WORLDS / "generalszh")]  # type: ignore[attr-defined]
    sys.modules.setdefault("worlds.generalszh", generals_pkg)

    from worlds.generalszh.constants import MAP_SLOTS  # type: ignore[import-not-found]
    from worlds.generalszh.slot_data import FLOORS  # type: ignore[import-not-found]
    from worlds.generalszh.testing_catalog import ALLOWED_WEAKNESSES  # type: ignore[import-not-found]

    return MAP_SLOTS, ALLOWED_WEAKNESSES, FLOORS


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_capability_schema(schema: dict[str, Any], allowed_requirements: tuple[str, ...]) -> None:
    require(schema.get("status") == "planning_only_disabled", "capability schema must stay disabled")
    require(schema.get("scope") == "capability_source_contract_only", "capability schema scope drift")
    require(schema.get("allowedRequirementKeys") == list(allowed_requirements), "capability requirement keys drift")
    require(schema.get("formalSatisfactionPolicy") == "single_green_source_with_required_production_items", "formal source policy drift")
    require(schema.get("softSupportPolicy") == "yellow_notes_only_do_not_combine_into_green", "yellow source policy drift")
    require(schema.get("productionRequirementPolicy") == "unit_item_and_listed_production_facility_items_required", "production prerequisite policy drift")
    require(schema.get("itemSpecificityPolicy") == "individual_items_satisfy_requirements_not_whole_tag_unlocks", "item specificity policy drift")
    require("unit" in schema.get("allowedSourceTypes", []), "unit source type missing")
    require("general_power" in schema.get("allowedSourceTypes", []), "general power source type missing")
    require(schema.get("forbiddenNormalItems") == ["Boss General Medal", "Victory"], "forbidden normal item list drift")


def validate_mission_gate_schema(
    schema: dict[str, Any],
    map_slots: dict[str, int],
    allowed_requirements: tuple[str, ...],
    floors: tuple[str, ...],
) -> None:
    require(schema.get("status") == "planning_only_disabled", "mission gate schema must stay disabled")
    require(schema.get("scope") == "mission_gate_contract_only", "mission gate schema scope drift")
    require(schema.get("statusModel") == "hold_win_v1", "mission gate statusModel drift")
    require(schema.get("allowedMapKeys") == list(map_slots), "mission gate map keys drift")
    require(schema.get("allowedRequirementKeys") == list(allowed_requirements), "mission gate requirement keys drift")
    require(schema.get("allowedFloors") == list(floors), "mission gate floor list drift")
    require(schema.get("allowedStages") == ["hold", "win"], "mission gate stages drift")
    require("all_seven_shuffled_medals" in schema.get("bossPolicy", ""), "boss medal gate policy missing")


def validate_capability_source_record(record: dict[str, Any], capability_schema: dict[str, Any], map_slots: dict[str, int]) -> None:
    for field in capability_schema["requiredRecordFields"]:
        require(field in record, f"capability source missing field: {field}")
    require(record["sourceType"] in capability_schema["allowedSourceTypes"], f"bad sourceType: {record['sourceType']}")
    require(isinstance(record["requiresProductionItems"], list), f"{record['sourceKey']}: requiresProductionItems must be a list")
    require(record["itemName"] not in capability_schema["forbiddenNormalItems"], f"{record['sourceKey']}: forbidden normal item")
    satisfies = record.get("satisfies", [])
    require(isinstance(satisfies, list), f"{record['sourceKey']}: satisfies must be a list")
    has_green = False
    for entry in satisfies:
        require(entry.get("requirementKey") in capability_schema["allowedRequirementKeys"], f"{record['sourceKey']}: bad requirement")
        require(entry.get("strength") in capability_schema["allowedStrengths"], f"{record['sourceKey']}: bad strength")
        require(entry.get("appliesTo") in capability_schema["allowedAppliesTo"], f"{record['sourceKey']}: bad appliesTo")
        has_green = has_green or entry.get("strength") == "green"
    if record["sourceType"] == "unit" and has_green:
        require(record["requiresProductionItems"], f"{record['sourceKey']}: green unit source must list production prerequisite items")

    for special in record.get("specialMissionUses", []):
        require(special.get("mapKey") in map_slots, f"{record['sourceKey']}: bad special mission map")
        require(special.get("stage") in ("hold", "win"), f"{record['sourceKey']}: bad special mission stage")


def validate_gate_stage(stage: dict[str, Any], schema: dict[str, Any], context: str) -> None:
    requirements = stage.get("requirements")
    require(isinstance(requirements, list), f"{context}: requirements must be a list")
    for requirement in requirements:
        require(requirement in schema["allowedRequirementKeys"], f"{context}: bad requirement {requirement}")
    require(stage.get("startingMoneyFloor") in schema["allowedFloors"], f"{context}: bad startingMoneyFloor")
    require(stage.get("productionFloor") in schema["allowedFloors"], f"{context}: bad productionFloor")
    for item in stage.get("specialItems", []):
        require(isinstance(item.get("itemName"), str) and item["itemName"], f"{context}: special item missing name")
        require(item["itemName"] not in ("Boss General Medal", "Victory"), f"{context}: forbidden special item")


def validate_mission_gate_record(record: dict[str, Any], schema: dict[str, Any]) -> None:
    for field in schema["requiredRecordFields"]:
        require(field in record, f"mission gate missing field: {field}")
    require(record["mapKey"] in schema["allowedMapKeys"], f"bad mission gate mapKey: {record['mapKey']}")
    require(record["statusModel"] == schema["statusModel"], f"{record['mapKey']}: statusModel drift")
    validate_gate_stage(record["hold"], schema, f"{record['mapKey']}.hold")
    validate_gate_stage(record["win"], schema, f"{record['mapKey']}.win")


def validate_contract_dir(contract_dir: Path = DEFAULT_CONTRACT_DIR) -> dict[str, int]:
    map_slots, allowed_requirements, floors = load_generalszh_symbols()
    capability_schema = load_json(contract_dir / "capability_sources_schema.json")
    mission_gate_schema = load_json(contract_dir / "mission_gate_schema.json")
    fixture = load_json(contract_dir / "fixtures" / "example_logic_contracts.json")

    validate_capability_schema(capability_schema, allowed_requirements)
    validate_mission_gate_schema(mission_gate_schema, map_slots, allowed_requirements, floors)

    require(fixture.get("status") == "planning_only_disabled", "fixture must stay disabled")
    require(fixture.get("scope") == "fixture_only_not_generation_input", "fixture scope drift")
    for record in fixture.get("capabilitySources", []):
        validate_capability_source_record(record, capability_schema, map_slots)
    for record in fixture.get("missionGates", []):
        validate_mission_gate_record(record, mission_gate_schema)

    return {
        "capabilitySourceCount": len(fixture.get("capabilitySources", [])),
        "missionGateCount": len(fixture.get("missionGates", [])),
        "mapCount": len(map_slots),
        "requirementKeyCount": len(allowed_requirements),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    contract_dir = Path(argv[0]) if argv else DEFAULT_CONTRACT_DIR
    if not contract_dir.is_absolute():
        contract_dir = REPO / contract_dir
    summary = validate_contract_dir(contract_dir)
    print(f"Contract directory: {contract_dir.relative_to(REPO)}")
    print(f"Capability sources fixture rows: {summary['capabilitySourceCount']}")
    print(f"Mission gate fixture rows: {summary['missionGateCount']}")
    print(f"Map keys: {summary['mapCount']}")
    print(f"Requirement keys: {summary['requirementKeyCount']}")
    print("OK: logic contracts validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
