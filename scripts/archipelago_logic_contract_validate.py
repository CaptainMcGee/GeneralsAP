#!/usr/bin/env python3
"""Validate disabled future logic contract handoff files."""

from __future__ import annotations

import json
import sys
import types
import argparse
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OVERLAY_WORLDS = REPO / "vendor" / "archipelago" / "overlay" / "worlds"
DEFAULT_CONTRACT_DIR = REPO / "Data" / "Archipelago" / "logic_contracts"
REQUIREMENT_ALIAS_PATH = "requirement_aliases.json"
LOGIC_FOUNDRY_EXPORT_SCHEMA_PATH = "logic_foundry_export_schema.json"
LOGIC_FOUNDRY_EXPORT_FIXTURE_PATH = "fixtures/logic_foundry_export_fixture.json"


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


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


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


def require_unique(values: list[str], context: str) -> None:
    require(len(values) == len(set(values)), f"{context}: duplicate values")


def validate_faction_scope(scope: Any, context: str) -> None:
    require(isinstance(scope, dict), f"{context}: factionScope must be an object")
    mode = scope.get("mode")
    faction = scope.get("faction")
    general = scope.get("general")
    require(mode in ("global", "shared", "faction", "general"), f"{context}: bad factionScope mode {mode}")
    require(faction in (None, "usa", "china", "gla"), f"{context}: bad faction {faction}")
    require(general is None or isinstance(general, str), f"{context}: general must be null or string")
    if mode == "global":
        require(faction is None and general is None, f"{context}: global scope must not name faction/general")
    if mode == "shared":
        require(faction is None and general is None, f"{context}: shared scope must not name faction/general")
    if mode == "faction":
        require(faction is not None and general is None, f"{context}: faction scope must name only faction")
    if mode == "general":
        require(faction is not None and isinstance(general, str) and general, f"{context}: general scope must name faction and general")


def validate_requirement_aliases(alias_contract: dict[str, Any], allowed_requirements: tuple[str, ...]) -> None:
    require(alias_contract.get("status") == "planning_only_disabled", "requirement alias contract must stay disabled")
    require(alias_contract.get("scope") == "requirement_tag_handoff_aliases_only", "requirement alias scope drift")
    canonical = alias_contract.get("canonicalRequirementKeys")
    current = alias_contract.get("currentApRequirementKeys")
    aliases = alias_contract.get("canonicalToCurrentApAliases")
    require(isinstance(canonical, list) and canonical, "canonical requirement keys missing")
    require(isinstance(current, list) and current, "current AP requirement keys missing")
    require(isinstance(aliases, dict) and aliases, "requirement aliases missing")
    require_unique(canonical, "canonical requirement keys")
    require_unique(current, "current AP requirement keys")
    require(current == list(allowed_requirements), "current AP requirement keys drift")

    canonical_set = set(canonical)
    current_set = set(current)
    for source, target in aliases.items():
        require(source in canonical_set, f"alias source is not canonical: {source}")
        require(target in current_set, f"alias target is not a current AP requirement: {target}")

    for key in alias_contract.get("missionOnlyCanonicalKeys", []):
        require(key in canonical_set, f"mission-only key is not canonical: {key}")
        require(key not in aliases, f"mission-only key must not map to normal AP requirement: {key}")
    for key in alias_contract.get("reviewOnlyCanonicalKeys", []):
        require(key in canonical_set, f"review-only key is not canonical: {key}")
        require(key not in aliases, f"review-only key must not map to normal AP requirement: {key}")
    for key in alias_contract.get("economyKeys", []):
        require(key not in canonical_set, f"economy key must not be a combat/special requirement tag: {key}")


def normalize_requirement_key(alias_contract: dict[str, Any], key: str, context: str) -> str:
    aliases = alias_contract["canonicalToCurrentApAliases"]
    if key in aliases:
        return aliases[key]
    if key in alias_contract.get("missionOnlyCanonicalKeys", []):
        raise LogicContractValidationError(f"{context}: mission-only tag cannot be normalized as normal requirement: {key}")
    if key in alias_contract.get("reviewOnlyCanonicalKeys", []):
        raise LogicContractValidationError(f"{context}: review-only tag cannot be normalized as normal requirement: {key}")
    raise LogicContractValidationError(f"{context}: unknown requirement tag: {key}")


def validate_logic_foundry_export_schema(schema: dict[str, Any], alias_contract: dict[str, Any]) -> None:
    require(schema.get("status") == "planning_only_disabled", "Logic Foundry export schema must stay disabled")
    require(schema.get("scope") == "logic_foundry_export_contract_only", "Logic Foundry export schema scope drift")
    require(schema.get("tagPolicy") == "canonical_tags_with_temporary_current_ap_aliases", "Logic Foundry tag policy drift")
    require(schema.get("supportPolicy") == "conditional_and_support_only_sources_are_review_context_only_for_alpha", "support policy drift")
    require(schema.get("missionPolicy") == "mission special requirements are authored separately from cluster requirements", "mission policy drift")
    require("playerItems" in schema.get("requiredTopLevelSections", []), "playerItems export section missing")
    require("clusters" in schema.get("requiredTopLevelSections", []), "clusters export section missing")
    require(schema.get("formalClusterStrengths") == ["primary", "secondary"], "formal cluster strengths drift")
    require(schema.get("nonFormalClusterStrengths") == ["conditional", "support_only"], "non-formal cluster strengths drift")
    require(set(alias_contract["canonicalRequirementKeys"]) >= set(alias_contract["canonicalToCurrentApAliases"]), "alias sources missing from canonical keys")


def validate_foundry_player_item(
    item: dict[str, Any],
    schema: dict[str, Any],
    alias_contract: dict[str, Any],
    facility_ids: set[str],
) -> tuple[int, int]:
    item_id = item.get("id")
    require(isinstance(item_id, str) and item_id, "player item missing id")
    kind = item.get("kind")
    require(kind in schema["allowedItemKinds"], f"{item_id}: bad item kind {kind}")
    validate_faction_scope(item.get("factionScope"), f"{item_id}.factionScope")
    required_facilities = item.get("requiredFacilityIds", [])
    require(isinstance(required_facilities, list), f"{item_id}: requiredFacilityIds must be a list")
    for facility_id in required_facilities:
        require(facility_id in facility_ids, f"{item_id}: unknown required facility {facility_id}")

    satisfies = item.get("satisfiesWeaknesses", [])
    require(isinstance(satisfies, list), f"{item_id}: satisfiesWeaknesses must be a list")
    if kind in ("economy", "buff"):
        require(not satisfies, f"{item_id}: economy/buff item must not satisfy normal requirements")

    formal_count = 0
    non_formal_count = 0
    for entry in satisfies:
        tag_id = entry.get("tagId")
        strength = entry.get("strength")
        require(tag_id in alias_contract["canonicalRequirementKeys"], f"{item_id}: bad canonical tag {tag_id}")
        require(strength in schema["allowedSatisfactionStrengths"], f"{item_id}: bad satisfaction strength {strength}")
        entry_facilities = entry.get("requiredFacilityIds", [])
        require(isinstance(entry_facilities, list), f"{item_id}.{tag_id}: requiredFacilityIds must be a list")
        for facility_id in entry_facilities:
            require(facility_id in facility_ids, f"{item_id}.{tag_id}: unknown required facility {facility_id}")

        if strength in schema["formalClusterStrengths"]:
            formal_count += 1
            normalize_requirement_key(alias_contract, tag_id, f"{item_id}.{tag_id}")
            require(kind in ("unit", "upgrade"), f"{item_id}.{tag_id}: formal source must be a unit or upgrade")
            if kind == "unit":
                require(entry_facilities, f"{item_id}.{tag_id}: formal unit source must list production facilities")
        else:
            non_formal_count += 1

        if tag_id in alias_contract.get("missionOnlyCanonicalKeys", []):
            require(strength == "conditional", f"{item_id}.{tag_id}: mission-only tag must be conditional")
        if tag_id in alias_contract.get("reviewOnlyCanonicalKeys", []):
            require(strength == "support_only", f"{item_id}.{tag_id}: review-only tag must be support_only")
    return formal_count, non_formal_count


def validate_foundry_cluster(
    cluster: dict[str, Any],
    schema: dict[str, Any],
    alias_contract: dict[str, Any],
    map_slots: dict[str, int],
    enemy_ids: set[str],
) -> list[str]:
    cluster_id = cluster.get("id")
    require(isinstance(cluster_id, str) and cluster_id, "cluster missing id")
    require(cluster.get("mapKey") in map_slots, f"{cluster_id}: bad map key")
    tier = cluster.get("tier")
    gate = cluster.get("gate")
    require(tier in schema["allowedClusterTiers"], f"{cluster_id}: bad tier {tier}")
    require(gate in schema["allowedClusterGates"], f"{cluster_id}: bad gate {gate}")
    for enemy_id in cluster.get("enemyUnitIds", []):
        require(enemy_id in enemy_ids, f"{cluster_id}: unknown enemy spawnable {enemy_id}")

    policy = schema["clusterTierPolicy"][tier]
    require(gate in policy["allowedGates"], f"{cluster_id}: gate {gate} not allowed for {tier}")
    authored = cluster.get("authoredRequirements", {})
    requirements = authored.get("requiredWeaknessTagIds", [])
    require(isinstance(requirements, list), f"{cluster_id}: authored requirements must be a list")
    if "requiredAuthoredWeaknessCount" in policy:
        require(len(requirements) == policy["requiredAuthoredWeaknessCount"], f"{cluster_id}: wrong requirement count for {tier}")
    else:
        require(
            policy["requiredAuthoredWeaknessCountMin"] <= len(requirements) <= policy["requiredAuthoredWeaknessCountMax"],
            f"{cluster_id}: wrong requirement count for {tier}",
        )
    return [normalize_requirement_key(alias_contract, key, f"{cluster_id}.authoredRequirements") for key in requirements]


def validate_foundry_mission_special_requirement(
    record: dict[str, Any],
    alias_contract: dict[str, Any],
    map_slots: dict[str, int],
    floors: tuple[str, ...],
    item_ids: set[str],
) -> list[str]:
    record_id = record.get("id")
    require(isinstance(record_id, str) and record_id, "mission special requirement missing id")
    require(record.get("mapKey") in map_slots, f"{record_id}: bad map key")
    require(record.get("stage") in ("hold", "win"), f"{record_id}: bad stage")
    require(record.get("startingMoneyFloor") in floors, f"{record_id}: bad startingMoneyFloor")
    require(record.get("productionFloor") in floors, f"{record_id}: bad productionFloor")
    for item_id in record.get("requiredItemIds", []):
        require(item_id in item_ids, f"{record_id}: unknown required item {item_id}")
    return [
        normalize_requirement_key(alias_contract, key, f"{record_id}.requiredWeaknessTagIds")
        for key in record.get("requiredWeaknessTagIds", [])
    ]


def validate_logic_foundry_export_fixture(
    fixture: dict[str, Any],
    schema: dict[str, Any],
    alias_contract: dict[str, Any],
    map_slots: dict[str, int],
    floors: tuple[str, ...],
    *,
    allowed_statuses: tuple[str, ...] = ("planning_only_disabled",),
    allowed_scopes: tuple[str, ...] = ("logic_foundry_fixture_only_not_generation_input",),
) -> dict[str, Any]:
    require(fixture.get("status") in allowed_statuses, "Logic Foundry export status drift")
    require(fixture.get("scope") in allowed_scopes, "Logic Foundry export scope drift")
    require(fixture.get("schemaName") == schema.get("schemaName"), "Logic Foundry fixture schema drift")
    for section in schema["requiredTopLevelSections"]:
        require(section in fixture, f"Logic Foundry fixture missing section: {section}")

    tag_ids = [record["id"] for record in fixture["requirementTags"]]
    require_unique(tag_ids, "Logic Foundry requirement tags")
    require(tag_ids == alias_contract["canonicalRequirementKeys"], "Logic Foundry canonical tag list drift")

    facility_ids = {record["id"] for record in fixture["productionFacilities"]}
    require(len(facility_ids) == len(fixture["productionFacilities"]), "duplicate production facility ids")
    for facility in fixture["productionFacilities"]:
        for parent_id in facility.get("parentFacilityIds", []):
            require(parent_id in facility_ids, f"{facility['id']}: unknown parent facility {parent_id}")

    item_ids = {record["id"] for record in fixture["playerItems"]}
    require(len(item_ids) == len(fixture["playerItems"]), "duplicate player item ids")
    formal_source_count = 0
    non_formal_source_count = 0
    for item in fixture["playerItems"]:
        formal, non_formal = validate_foundry_player_item(item, schema, alias_contract, facility_ids)
        formal_source_count += formal
        non_formal_source_count += non_formal

    enemy_ids = {record["id"] for record in fixture["enemySpawnables"]}
    require(len(enemy_ids) == len(fixture["enemySpawnables"]), "duplicate enemy spawnable ids")
    for enemy in fixture["enemySpawnables"]:
        for entry in enemy.get("defaultWeaknessProfile", []):
            require(entry.get("tagId") in alias_contract["canonicalRequirementKeys"], f"{enemy['id']}: bad default tag")

    normalized_cluster_requirements: dict[str, list[str]] = {}
    for cluster in fixture["clusters"]:
        normalized_cluster_requirements[cluster["id"]] = validate_foundry_cluster(
            cluster,
            schema,
            alias_contract,
            map_slots,
            enemy_ids,
        )

    normalized_mission_requirements: dict[str, list[str]] = {}
    for record in fixture["missionSpecialRequirements"]:
        normalized_mission_requirements[record["id"]] = validate_foundry_mission_special_requirement(
            record,
            alias_contract,
            map_slots,
            floors,
            item_ids,
        )

    return {
        "requirementTagCount": len(tag_ids),
        "productionFacilityCount": len(facility_ids),
        "playerItemCount": len(item_ids),
        "formalSourceCount": formal_source_count,
        "nonFormalSourceCount": non_formal_source_count,
        "enemySpawnableCount": len(enemy_ids),
        "foundryClusterCount": len(fixture["clusters"]),
        "missionSpecialRequirementCount": len(fixture["missionSpecialRequirements"]),
        "normalizedClusterRequirements": normalized_cluster_requirements,
        "normalizedMissionRequirements": normalized_mission_requirements,
    }


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
    validate_faction_scope(record.get("factionScope"), f"{record['sourceKey']}.factionScope")
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
        validate_faction_scope(item.get("factionScope"), f"{context}.{item['itemName']}.factionScope")


def validate_mission_gate_record(record: dict[str, Any], schema: dict[str, Any], known_special_item_names: set[str] | None = None) -> None:
    for field in schema["requiredRecordFields"]:
        require(field in record, f"mission gate missing field: {field}")
    require(record["mapKey"] in schema["allowedMapKeys"], f"bad mission gate mapKey: {record['mapKey']}")
    require(record["statusModel"] == schema["statusModel"], f"{record['mapKey']}: statusModel drift")
    validate_gate_stage(record["hold"], schema, f"{record['mapKey']}.hold")
    validate_gate_stage(record["win"], schema, f"{record['mapKey']}.win")
    if known_special_item_names is not None:
        for stage_name in ("hold", "win"):
            for item in record[stage_name].get("specialItems", []):
                require(
                    item["itemName"] in known_special_item_names,
                    f"{record['mapKey']}.{stage_name}: unknown special item {item['itemName']}",
                )


def validate_contract_dir(contract_dir: Path = DEFAULT_CONTRACT_DIR) -> dict[str, int]:
    map_slots, allowed_requirements, floors = load_generalszh_symbols()
    capability_schema = load_json(contract_dir / "capability_sources_schema.json")
    mission_gate_schema = load_json(contract_dir / "mission_gate_schema.json")
    requirement_aliases = load_json(contract_dir / REQUIREMENT_ALIAS_PATH)
    logic_foundry_export_schema = load_json(contract_dir / LOGIC_FOUNDRY_EXPORT_SCHEMA_PATH)
    fixture = load_json(contract_dir / "fixtures" / "example_logic_contracts.json")
    logic_foundry_fixture = load_json(contract_dir / LOGIC_FOUNDRY_EXPORT_FIXTURE_PATH)

    validate_capability_schema(capability_schema, allowed_requirements)
    validate_mission_gate_schema(mission_gate_schema, map_slots, allowed_requirements, floors)
    validate_requirement_aliases(requirement_aliases, allowed_requirements)
    validate_logic_foundry_export_schema(logic_foundry_export_schema, requirement_aliases)

    require(fixture.get("status") == "planning_only_disabled", "fixture must stay disabled")
    require(fixture.get("scope") == "fixture_only_not_generation_input", "fixture scope drift")
    capability_records = fixture.get("capabilitySources", [])
    mission_gate_records = fixture.get("missionGates", [])
    for record in capability_records:
        validate_capability_source_record(record, capability_schema, map_slots)
    for record in mission_gate_records:
        validate_mission_gate_record(record, mission_gate_schema)
    require_unique([record["sourceKey"] for record in capability_records], "capability source keys")
    require_unique([record["itemName"] for record in capability_records], "capability source item names")
    require_unique([record["mapKey"] for record in mission_gate_records], "mission gate map keys")
    known_special_item_names = {record["itemName"] for record in capability_records}
    for record in mission_gate_records:
        validate_mission_gate_record(record, mission_gate_schema, known_special_item_names)
    foundry_summary = validate_logic_foundry_export_fixture(
        logic_foundry_fixture,
        logic_foundry_export_schema,
        requirement_aliases,
        map_slots,
        floors,
    )

    return {
        "capabilitySourceCount": len(fixture.get("capabilitySources", [])),
        "missionGateCount": len(fixture.get("missionGates", [])),
        "mapCount": len(map_slots),
        "requirementKeyCount": len(allowed_requirements),
        "canonicalRequirementKeyCount": foundry_summary["requirementTagCount"],
        "foundryPlayerItemCount": foundry_summary["playerItemCount"],
        "foundryClusterCount": foundry_summary["foundryClusterCount"],
        "foundryMissionSpecialRequirementCount": foundry_summary["missionSpecialRequirementCount"],
    }


def validate_foundry_output_file(contract_dir: Path, output_path: Path) -> dict[str, Any]:
    map_slots, allowed_requirements, floors = load_generalszh_symbols()
    requirement_aliases = load_json(contract_dir / REQUIREMENT_ALIAS_PATH)
    logic_foundry_export_schema = load_json(contract_dir / LOGIC_FOUNDRY_EXPORT_SCHEMA_PATH)
    validate_requirement_aliases(requirement_aliases, allowed_requirements)
    validate_logic_foundry_export_schema(logic_foundry_export_schema, requirement_aliases)
    output = load_json(output_path)
    return validate_logic_foundry_export_fixture(
        output,
        logic_foundry_export_schema,
        requirement_aliases,
        map_slots,
        floors,
        allowed_statuses=("planning_only_disabled", "dry_run_only"),
        allowed_scopes=("logic_foundry_fixture_only_not_generation_input", "logic_foundry_dry_run_only"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract_dir", nargs="?", default=str(DEFAULT_CONTRACT_DIR))
    parser.add_argument(
        "--foundry-output",
        help="Optional Logic Foundry export JSON to validate in dry-run mode without writing generated AP data.",
    )
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    contract_dir = Path(args.contract_dir)
    if not contract_dir.is_absolute():
        contract_dir = REPO / contract_dir
    summary = validate_contract_dir(contract_dir)
    print(f"Contract directory: {contract_dir.relative_to(REPO)}")
    print(f"Capability sources fixture rows: {summary['capabilitySourceCount']}")
    print(f"Mission gate fixture rows: {summary['missionGateCount']}")
    print(f"Map keys: {summary['mapCount']}")
    print(f"Requirement keys: {summary['requirementKeyCount']}")
    print(f"Canonical requirement keys: {summary['canonicalRequirementKeyCount']}")
    print(f"Logic Foundry fixture player items: {summary['foundryPlayerItemCount']}")
    print(f"Logic Foundry fixture clusters: {summary['foundryClusterCount']}")
    print(f"Logic Foundry fixture mission specials: {summary['foundryMissionSpecialRequirementCount']}")
    if args.foundry_output:
        output_path = Path(args.foundry_output)
        if not output_path.is_absolute():
            output_path = REPO / output_path
        foundry_summary = validate_foundry_output_file(contract_dir, output_path)
        print(f"Dry-run Logic Foundry output: {display_path(output_path)}")
        print(f"Dry-run player items: {foundry_summary['playerItemCount']}")
        print(f"Dry-run clusters: {foundry_summary['foundryClusterCount']}")
        print(f"Dry-run mission specials: {foundry_summary['missionSpecialRequirementCount']}")
    print("OK: logic contracts validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
