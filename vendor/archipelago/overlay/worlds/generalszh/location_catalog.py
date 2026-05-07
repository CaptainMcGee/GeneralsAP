from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
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
AUTHORING_SCHEMA_VERSION = 1
AUTHORING_SCHEMA_STATUS = "planning_only_disabled"
RUNTIME_PERSISTENCE_CONTRACT_VERSION = 1
RUNTIME_PERSISTENCE_CONTRACT_STATUS = "planning_only_disabled"
ENABLE_CRITERIA_VERSION = 1
ENABLE_CRITERIA_STATUS = "planning_only_disabled"
REQUIRED_ENABLE_CRITERIA_IDS = (
    "author_catalog_approved_disabled",
    "runtime_object_identity",
    "runtime_completion_event",
    "runtime_replay_persistence",
    "bridge_translation_selected_only",
    "ap_generation_selection_option",
    "production_guard_removal_test",
    "manual_playtest_proof",
)
REQUIRED_AUTHORING_SCHEMA_SECTIONS = (
    "allowedAuthorStatuses",
    "allowedMissabilityRisks",
    "allowedPersistenceRequirements",
    "allowedSphereZeroRoles",
    "sharedRequiredFields",
    "sharedAuthoringRequiredFields",
    "visualRequiredFields",
    "families",
    "visualAuthoringMetadata",
)


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


def validate_location_authoring_schema(schema: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    _require(schema.get("version") == AUTHORING_SCHEMA_VERSION, "invalid location authoring schema version")
    _require(schema.get("status") == AUTHORING_SCHEMA_STATUS, "location authoring schema must stay planning-only")
    for section in REQUIRED_AUTHORING_SCHEMA_SECTIONS:
        _require(section in schema, f"location authoring schema missing {section}")

    author_statuses = schema["allowedAuthorStatuses"]
    missability_risks = schema["allowedMissabilityRisks"]
    persistence_requirements = schema["allowedPersistenceRequirements"]
    sphere_zero_roles = schema["allowedSphereZeroRoles"]
    _require_list_contains(author_statuses, "candidate", "allowedAuthorStatuses")
    _require_list_contains(author_statuses, "approved_disabled", "allowedAuthorStatuses")
    _require_list_contains(missability_risks, "high", "allowedMissabilityRisks")
    _require_list_contains(persistence_requirements, "mission_replay_persistent", "allowedPersistenceRequirements")
    _require_list_contains(sphere_zero_roles, "near_start_safe", "allowedSphereZeroRoles")

    shared_fields = set(_require_string_list(schema["sharedRequiredFields"], "sharedRequiredFields"))
    _require({"label", "position", "sphere", "authorStatus", "authoring"}.issubset(shared_fields), "sharedRequiredFields missing required authoring fields")
    authoring_fields = set(_require_string_list(schema["sharedAuthoringRequiredFields"], "sharedAuthoringRequiredFields"))
    _require({"candidateStatus", "sphereZeroRole", "missabilityRisk", "persistenceRequirement", "visual", "notes"}.issubset(authoring_fields), "sharedAuthoringRequiredFields missing required review fields")
    visual_fields = set(_require_string_list(schema["visualRequiredFields"], "visualRequiredFields"))
    _require({"icon", "mapMarker", "screenshotRef"}.issubset(visual_fields), "visualRequiredFields missing required visual fields")

    families = schema["families"]
    _require(isinstance(families, Mapping), "authoring schema families must be object")
    _require(set(families) == {"capturedBuildings", "supplyPiles"}, "authoring schema families must match future catalog families")
    _validate_authoring_family_schema(families["capturedBuildings"], "capturedBuildings", "buildingIndex", "runtime_capture_event")
    _validate_authoring_family_schema(families["supplyPiles"], "supplyPiles", "pileIndex", "runtime_supply_collection_tracker")
    supply_thresholds = families["supplyPiles"].get("thresholdRequiredFields")
    _require_list_contains(supply_thresholds, "thresholdIndex", "supplyPiles.thresholdRequiredFields")
    _require_list_contains(supply_thresholds, "amountCollected_or_fractionCollected", "supplyPiles.thresholdRequiredFields")

    checklist_lengths = [
        len(families[family].get("authoringChecklist", []))
        for family in ("capturedBuildings", "supplyPiles")
    ]
    if any(length < 5 for length in checklist_lengths):
        warnings.append("authoring checklists should keep at least five review prompts per family")
    return warnings


def validate_runtime_persistence_contract(
    contract: Mapping[str, Any],
    authoring_schema: Mapping[str, Any],
) -> list[str]:
    validate_location_authoring_schema(authoring_schema)

    warnings: list[str] = []
    _require(contract.get("version") == RUNTIME_PERSISTENCE_CONTRACT_VERSION, "invalid runtime persistence contract version")
    _require(contract.get("status") == RUNTIME_PERSISTENCE_CONTRACT_STATUS, "runtime persistence contract must stay planning-only")
    _require(contract.get("scope") == "runtime_persistence_contract_only", "runtime persistence contract scope drift")
    _require(contract.get("familiesDefaultEnabled") is False, "runtime persistence contract must not enable future families")

    shared = contract.get("shared")
    _require(isinstance(shared, Mapping), "runtime persistence contract shared section must be object")
    _require(shared.get("persistentStore") == "UserData/Save/ArchipelagoState.json", "persistentStore drift")
    _require(shared.get("outboundFile") == "UserData/Archipelago/Bridge-Outbound.json", "outboundFile drift")
    _require(shared.get("runtimeKeySource") == "verified Seed-Slot-Data.json only", "runtimeKeySource drift")
    _require(shared.get("outboundCompletionUnit") == "runtimeKey", "outboundCompletionUnit drift")
    _require(shared.get("bridgeTranslationRequired") is True, "bridgeTranslationRequired drift")
    _require(shared.get("duplicateCompletionPolicy") == "idempotent_noop", "duplicate completion policy must stay idempotent")
    _require(shared.get("missionRestartPolicy") == "preserve_family_state", "mission restart policy drift")
    _require(shared.get("profileResetPolicy") == "explicit_user_reset_only", "profile reset policy drift")
    _require(shared.get("wrongSeedPolicy") == "reject_without_import", "wrong seed policy drift")
    _require(shared.get("demoFallbackPolicy") == "future_location_families_unavailable_in_demo_fallback", "demo fallback policy drift")
    _require_list_contains(shared.get("seedBindingFields"), "seedId", "seedBindingFields")
    _require_list_contains(shared.get("seedBindingFields"), "slotName", "seedBindingFields")
    _require_list_contains(shared.get("seedBindingFields"), "slotDataHash", "seedBindingFields")
    _require_list_contains(shared.get("seedBindingFields"), "slotDataVersion", "seedBindingFields")
    _require(shared.get("sessionField") == "sessionNonce", "sessionField drift")
    _require_list_contains(shared.get("completedCheckCollections"), "completedChecks", "completedCheckCollections")
    _require_list_contains(shared.get("completedCheckCollections"), "completedLocations", "completedCheckCollections")

    families = contract.get("families")
    _require(isinstance(families, Mapping), "runtime persistence families must be object")
    _require(set(families) == {"capturedBuildings", "supplyPiles"}, "runtime persistence families must match future catalog families")
    schema_families = authoring_schema["families"]
    _validate_runtime_persistence_family(
        families["capturedBuildings"],
        schema_families["capturedBuildings"],
        family_key="capturedBuildings",
        slot_data_section="capturedBuildings",
        runtime_key_pattern="capture.<map>.bXXX",
        completion_owner="runtime_capture_event",
        runtime_state_collection="capturedBuildingState",
        state_key_pattern="capture.<map>.bXXX",
        required_field_sets={
            "requiredStateFields": [
                "runtimeKey",
                "mapKey",
                "buildingKey",
                "apLocationId",
                "completed",
                "firstCompletedSeedId",
                "firstCompletedSlotDataHash",
                "firstCompletedSessionNonce",
            ],
        },
    )
    _validate_runtime_persistence_family(
        families["supplyPiles"],
        schema_families["supplyPiles"],
        family_key="supplyPiles",
        slot_data_section="supplyPileThresholds",
        runtime_key_pattern="supply.<map>.pXX.tYY",
        completion_owner="runtime_supply_collection_tracker",
        runtime_state_collection="supplyPileState",
        state_key_pattern="supply.<map>.pXX",
        required_field_sets={
            "requiredPileStateFields": [
                "mapKey",
                "pileKey",
                "startingAmount",
                "persistentCollectedAmount",
                "completedThresholdKeys",
                "dry",
                "lastSeenSeedId",
                "lastSeenSlotDataHash",
            ],
            "requiredThresholdStateFields": [
                "runtimeKey",
                "thresholdKey",
                "apLocationId",
                "amountCollectedOrFractionCollected",
                "completed",
            ],
        },
    )
    return warnings


def validate_future_location_enable_criteria(
    criteria: Mapping[str, Any],
    runtime_contract: Mapping[str, Any],
) -> list[str]:
    warnings: list[str] = []
    _require(criteria.get("version") == ENABLE_CRITERIA_VERSION, "invalid future location enable-criteria version")
    _require(criteria.get("status") == ENABLE_CRITERIA_STATUS, "future location enable criteria must stay planning-only")
    _require(criteria.get("scope") == "future_location_family_enable_criteria", "future location enable-criteria scope drift")
    _require(criteria.get("familiesDefaultEnabled") is False, "future location enable criteria must not enable families")
    _require(criteria.get("productionGuardRequired") is True, "future location production guard must stay required")

    required = criteria.get("requiredCriteria")
    _require(isinstance(required, list), "requiredCriteria must be a list")
    criteria_by_id: dict[str, Mapping[str, Any]] = {}
    for entry in required:
        _require(isinstance(entry, Mapping), "requiredCriteria entries must be objects")
        criterion_id = entry.get("id")
        _require(isinstance(criterion_id, str) and criterion_id, "requiredCriteria entry missing id")
        _require(criterion_id not in criteria_by_id, f"duplicate enable criterion: {criterion_id}")
        _require(isinstance(entry.get("category"), str) and entry["category"], f"{criterion_id}: category required")
        _require(isinstance(entry.get("description"), str) and entry["description"], f"{criterion_id}: description required")
        _require(isinstance(entry.get("requiredProof"), str) and entry["requiredProof"], f"{criterion_id}: requiredProof required")
        criteria_by_id[criterion_id] = entry
    for criterion_id in REQUIRED_ENABLE_CRITERIA_IDS:
        _require(criterion_id in criteria_by_id, f"required enable criterion missing: {criterion_id}")

    _require(criteria_by_id["runtime_object_identity"]["category"] == "runtime", "runtime_object_identity category drift")
    _require(criteria_by_id["runtime_replay_persistence"]["category"] == "runtime", "runtime_replay_persistence category drift")
    _require(criteria_by_id["bridge_translation_selected_only"]["category"] == "bridge", "bridge_translation_selected_only category drift")
    _require(criteria_by_id["ap_generation_selection_option"]["category"] == "ap_world", "ap_generation_selection_option category drift")
    _require(criteria_by_id["manual_playtest_proof"]["category"] == "manual_playtest", "manual_playtest_proof category drift")

    families = criteria.get("families")
    _require(isinstance(families, Mapping), "future location enable families must be object")
    _require(set(families) == {"capturedBuildings", "supplyPiles"}, "future location enable families must match future catalog families")
    contract_families = runtime_contract["families"]
    _validate_enable_criteria_family(
        families["capturedBuildings"],
        contract_families["capturedBuildings"],
        family_key="capturedBuildings",
        slot_data_section="capturedBuildings",
        runtime_state_collection="capturedBuildingState",
        runtime_key_pattern="capture.<map>.bXXX",
        required_ids=set(REQUIRED_ENABLE_CRITERIA_IDS),
    )
    _validate_enable_criteria_family(
        families["supplyPiles"],
        contract_families["supplyPiles"],
        family_key="supplyPiles",
        slot_data_section="supplyPileThresholds",
        runtime_state_collection="supplyPileState",
        runtime_key_pattern="supply.<map>.pXX.tYY",
        required_ids=set(REQUIRED_ENABLE_CRITERIA_IDS),
    )
    return warnings


def validate_catalog_authoring_metadata(
    catalog: Mapping[str, Any],
    schema: Mapping[str, Any],
    require_authoring: bool = False,
) -> list[str]:
    validate_location_catalog(catalog)
    validate_location_authoring_schema(schema)

    warnings: list[str] = []
    maps = catalog["maps"]
    for map_key in MAP_SLOTS:
        map_payload = maps[map_key]
        for index, entry in enumerate(map_payload["capturedBuildings"]):
            _validate_candidate_authoring(
                entry,
                schema,
                family_key="capturedBuildings",
                label=f"{map_key}.capturedBuildings[{index}]",
                require_authoring=require_authoring,
            )
        for index, pile in enumerate(map_payload["supplyPiles"]):
            _validate_candidate_authoring(
                pile,
                schema,
                family_key="supplyPiles",
                label=f"{map_key}.supplyPiles[{index}]",
                require_authoring=require_authoring,
            )
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
                "template": entry.get("template"),
                "position": deepcopy(entry.get("position")),
                "sphere": entry.get("sphere"),
                "authorStatus": entry.get("authorStatus"),
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
                    "template": pile.get("template"),
                    "position": deepcopy(pile.get("position")),
                    "sphere": pile.get("sphere"),
                    "authorStatus": pile.get("authorStatus"),
                    "startingAmount": pile.get("startingAmount"),
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


def _validate_authoring_family_schema(
    family_schema: Any,
    family_key: str,
    index_field: str,
    completion_owner: str,
) -> None:
    _require(isinstance(family_schema, Mapping), f"{family_key}: schema must be object")
    required_fields = set(_require_string_list(family_schema.get("requiredFields"), f"{family_key}.requiredFields"))
    _require(index_field in required_fields, f"{family_key}: requiredFields missing {index_field}")
    _require("authoring" in required_fields, f"{family_key}: requiredFields missing authoring")
    _require(family_schema.get("completionOwner") == completion_owner, f"{family_key}: completionOwner drift")
    _require(family_schema.get("persistenceRequirement") == "mission_replay_persistent", f"{family_key}: persistenceRequirement drift")
    checklist = family_schema.get("authoringChecklist")
    _require(isinstance(checklist, list) and all(isinstance(item, str) and item.strip() for item in checklist), f"{family_key}: authoringChecklist must be non-empty strings")


def _validate_candidate_authoring(
    entry: Mapping[str, Any],
    schema: Mapping[str, Any],
    family_key: str,
    label: str,
    require_authoring: bool,
) -> None:
    authoring = entry.get("authoring")
    if authoring is None:
        _require(not require_authoring, f"{label}: missing authoring metadata")
        return
    _require(isinstance(authoring, Mapping), f"{label}: authoring must be object")

    _require_value_in(authoring.get("candidateStatus"), schema["allowedAuthorStatuses"], f"{label}.authoring.candidateStatus")
    _require_value_in(authoring.get("sphereZeroRole"), schema["allowedSphereZeroRoles"], f"{label}.authoring.sphereZeroRole")
    _require_value_in(authoring.get("missabilityRisk"), schema["allowedMissabilityRisks"], f"{label}.authoring.missabilityRisk")
    _require_value_in(authoring.get("persistenceRequirement"), schema["allowedPersistenceRequirements"], f"{label}.authoring.persistenceRequirement")
    _require(
        authoring["persistenceRequirement"] == schema["families"][family_key]["persistenceRequirement"],
        f"{label}.authoring.persistenceRequirement does not match family requirement",
    )
    if "authorStatus" in entry:
        _require(authoring["candidateStatus"] == entry["authorStatus"], f"{label}: authorStatus/candidateStatus mismatch")

    visual = authoring.get("visual")
    _require(isinstance(visual, Mapping), f"{label}.authoring.visual must be object")
    for field in schema["visualRequiredFields"]:
        value = visual.get(field)
        _require(isinstance(value, str) and bool(value.strip()), f"{label}.authoring.visual.{field} must be non-empty string")

    notes = authoring.get("notes")
    _require(isinstance(notes, list) and notes, f"{label}.authoring.notes must be non-empty list")
    _require(all(isinstance(note, str) and note.strip() for note in notes), f"{label}.authoring.notes must contain non-empty strings")


def _validate_runtime_persistence_family(
    family: Any,
    authoring_family: Mapping[str, Any],
    family_key: str,
    slot_data_section: str,
    runtime_key_pattern: str,
    completion_owner: str,
    runtime_state_collection: str,
    state_key_pattern: str,
    required_field_sets: Mapping[str, list[str]],
) -> None:
    _require(isinstance(family, Mapping), f"{family_key}: runtime persistence family must be object")
    _require(family.get("slotDataSection") == slot_data_section, f"{family_key}: slotDataSection drift")
    _require(family.get("runtimeKeyPattern") == runtime_key_pattern, f"{family_key}: runtimeKeyPattern drift")
    _require(family.get("completionOwner") == completion_owner, f"{family_key}: completionOwner drift")
    _require(family.get("completionOwner") == authoring_family.get("completionOwner"), f"{family_key}: completionOwner disagrees with authoring schema")
    _require(family.get("persistenceRequirement") == "mission_replay_persistent", f"{family_key}: persistenceRequirement drift")
    _require(family.get("persistenceRequirement") == authoring_family.get("persistenceRequirement"), f"{family_key}: persistenceRequirement disagrees with authoring schema")
    _require(family.get("runtimeStateCollection") == runtime_state_collection, f"{family_key}: runtimeStateCollection drift")
    _require(family.get("stateKeyPattern") == state_key_pattern, f"{family_key}: stateKeyPattern drift")
    _require(isinstance(family.get("completionTrigger"), str) and bool(family["completionTrigger"].strip()), f"{family_key}: completionTrigger must be non-empty string")
    for section_key, required_fields in required_field_sets.items():
        actual = set(_require_string_list(family.get(section_key), f"{family_key}.{section_key}"))
        missing = sorted(set(required_fields) - actual)
        _require(not missing, f"{family_key}.{section_key} missing required fields: {missing}")
    _require(len(_require_string_list(family.get("replayBehavior"), f"{family_key}.replayBehavior")) >= 3, f"{family_key}: replayBehavior must cover replay/idempotency")
    _require(len(_require_string_list(family.get("enableBlockers"), f"{family_key}.enableBlockers")) >= 4, f"{family_key}: enableBlockers must cover runtime and bridge requirements")


def _validate_enable_criteria_family(
    family: Any,
    contract_family: Mapping[str, Any],
    family_key: str,
    slot_data_section: str,
    runtime_state_collection: str,
    runtime_key_pattern: str,
    required_ids: set[str],
) -> None:
    _require(isinstance(family, Mapping), f"{family_key}: enable criteria family must be object")
    _require(family.get("slotDataSection") == slot_data_section, f"{family_key}: slotDataSection drift")
    _require(family.get("slotDataSection") == contract_family.get("slotDataSection"), f"{family_key}: slotDataSection disagrees with runtime contract")
    _require(family.get("runtimeStateCollection") == runtime_state_collection, f"{family_key}: runtimeStateCollection drift")
    _require(family.get("runtimeStateCollection") == contract_family.get("runtimeStateCollection"), f"{family_key}: runtimeStateCollection disagrees with runtime contract")
    _require(family.get("runtimeKeyPattern") == runtime_key_pattern, f"{family_key}: runtimeKeyPattern drift")
    _require(family.get("runtimeKeyPattern") == contract_family.get("runtimeKeyPattern"), f"{family_key}: runtimeKeyPattern disagrees with runtime contract")
    actual_ids = set(_require_string_list(family.get("requiredCriteriaIds"), f"{family_key}.requiredCriteriaIds"))
    missing = sorted(required_ids - actual_ids)
    _require(not missing, f"{family_key}.requiredCriteriaIds missing required criteria: {missing}")
    _require(len(_require_string_list(family.get("familySpecificProof"), f"{family_key}.familySpecificProof")) >= 3, f"{family_key}: familySpecificProof must document family-specific proof")
    not_enough = set(_require_string_list(family.get("notEnoughToEnable"), f"{family_key}.notEnoughToEnable"))
    _require("Runtime state scaffold" in not_enough, f"{family_key}: notEnoughToEnable must include runtime state scaffold")
    _require("Local bridge future-state mirroring" in not_enough, f"{family_key}: notEnoughToEnable must include bridge state scaffold")


def _require_value_in(value: Any, allowed: Any, label: str) -> None:
    _require(isinstance(allowed, list), f"{label}: allowed values must be list")
    _require(isinstance(value, str) and value in allowed, f"{label} invalid: {value!r}")


def _require_list_contains(values: Any, expected: str, label: str) -> None:
    _require(isinstance(values, list), f"{label} must be a list")
    _require(expected in values, f"{label} missing {expected}")


def _require_string_list(values: Any, label: str) -> list[str]:
    _require(isinstance(values, list), f"{label} must be a list")
    _require(all(isinstance(value, str) and value.strip() for value in values), f"{label} must contain non-empty strings")
    return list(values)


def _track_unique(runtime_key: str, ap_location_id: int, seen_keys: set[str], seen_ids: set[int]) -> None:
    _require(runtime_key not in seen_keys, f"duplicate catalog runtime key: {runtime_key}")
    _require(ap_location_id not in seen_ids, f"duplicate catalog AP location ID: {ap_location_id}")
    seen_keys.add(runtime_key)
    seen_ids.add(ap_location_id)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LocationCatalogValidationError(message)
