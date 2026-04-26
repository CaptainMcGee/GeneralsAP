#!/usr/bin/env python3
"""Sanity tests for the GeneralsZH AP world skeleton contract."""

from __future__ import annotations

import copy
import json
import re
import sys
import types
from enum import IntFlag
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OVERLAY_WORLDS = REPO / "vendor" / "archipelago" / "overlay" / "worlds"
LOCATION_CATALOG_PATH = REPO / "Data" / "Archipelago" / "location_families" / "catalog.json"
AUTHORING_SCHEMA_PATH = REPO / "Data" / "Archipelago" / "location_families" / "authoring_schema.json"
RUNTIME_PERSISTENCE_CONTRACT_PATH = REPO / "Data" / "Archipelago" / "location_families" / "runtime_persistence_contract.json"
ENABLE_CRITERIA_PATH = REPO / "Data" / "Archipelago" / "location_families" / "enable_criteria.json"
EXAMPLE_CANDIDATES_PATH = REPO / "Data" / "Archipelago" / "location_families" / "fixtures" / "example_candidates.json"

MISSION_KEY_RE = re.compile(r"^mission\.([a-z_]+)\.victory$")
CLUSTER_KEY_RE = re.compile(r"^cluster\.([a-z_]+)\.c(\d{2})\.u(\d{2})$")
CAPTURE_KEY_RE = re.compile(r"^capture\.([a-z_]+)\.b(\d{3})$")
SUPPLY_KEY_RE = re.compile(r"^supply\.([a-z_]+)\.p(\d{2})\.t(\d{2})$")


def import_generalszh():
    install_archipelago_stubs()

    from worlds.generalszh import constants, content_framework, items, locations, slot_data
    from worlds.generalszh import GeneralsZHWorld

    return GeneralsZHWorld, constants, content_framework, items, locations, slot_data


def install_archipelago_stubs() -> None:
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
                self.item = None

            def place_locked_item(self, item):
                self.item = item

        class Region:
            def __init__(self, name, player, multiworld):
                self.name = name
                self.player = player
                self.multiworld = multiworld
                self.locations = []
                self.exits = []

            def add_locations(self, names_to_ids, location_type):
                for name, address in names_to_ids.items():
                    self.locations.append(location_type(self.player, name, address, self))

            def add_event(self, name, item_name=None, rule=None, location_type=None, item_type=None, show_in_spoiler=True):
                location_type = location_type or Location
                item_type = item_type or Item
                item_name = item_name or name
                location = location_type(self.player, name, None, self)
                location.place_locked_item(item_type(item_name, ItemClassification.progression, None, self.player))
                self.locations.append(location)

            def connect(self, region, name, rule=None):
                self.exits.append((name, region, rule))

        baseclasses.ItemClassification = ItemClassification
        baseclasses.Item = Item
        baseclasses.Location = Location
        baseclasses.Region = Region
        sys.modules["BaseClasses"] = baseclasses

    if "Options" not in sys.modules:
        options = types.ModuleType("Options")

        class Choice:
            current_key = "default"

        class PerGameCommonOptions:
            pass

        options.Choice = Choice
        options.PerGameCommonOptions = PerGameCommonOptions
        sys.modules["Options"] = options

    worlds = types.ModuleType("worlds")
    worlds.__path__ = [str(OVERLAY_WORLDS)]
    sys.modules["worlds"] = worlds

    autoworld = types.ModuleType("worlds.AutoWorld")

    class World:
        pass

    autoworld.World = World
    sys.modules["worlds.AutoWorld"] = autoworld

    generic = types.ModuleType("worlds.generic")
    generic.__path__ = []
    sys.modules["worlds.generic"] = generic

    rules = types.ModuleType("worlds.generic.Rules")
    rules.set_rule = lambda target, rule: setattr(target, "access_rule", rule)
    sys.modules["worlds.generic.Rules"] = rules


def validate_slot_data(data: dict[str, object], constants) -> None:
    assert data["version"] == constants.SLOT_DATA_VERSION
    assert data["logicModel"] == constants.LOGIC_MODEL
    assert data["locationNamespaceBase"] == constants.LOCATION_NAMESPACE_BASE
    assert set(data["maps"]) == set(constants.MAP_SLOTS)

    seen_ids: set[int] = set()
    seen_keys: set[str] = set()

    for map_key, expected_slot in constants.MAP_SLOTS.items():
        mission = data["maps"][map_key]
        assert mission["mapSlot"] == expected_slot
        assert mission["missionVictory"] == {
            "runtimeKey": constants.mission_runtime_key(map_key),
            "apLocationId": constants.mission_victory_location_id(map_key),
        }

        mission_key = mission["missionVictory"]["runtimeKey"]
        location_id = mission["missionVictory"]["apLocationId"]
        assert MISSION_KEY_RE.match(mission_key), mission_key
        assert mission_key not in seen_keys
        assert location_id not in seen_ids
        seen_keys.add(mission_key)
        seen_ids.add(location_id)

        gate = mission["missionGate"]
        assert gate["statusModel"] == "hold_win_v1"
        for stage in ("hold", "win"):
            assert gate[stage]["requirements"] == []
            assert gate[stage]["startingMoneyFloor"] == "none"
            assert gate[stage]["productionFloor"] == "none"

        assert mission["capturedBuildings"] == []
        assert mission["supplyPileThresholds"] == []

        for cluster in mission["clusters"]:
            for unit in cluster["units"]:
                runtime_key = unit["runtimeKey"]
                ap_id = unit["apLocationId"]
                assert CLUSTER_KEY_RE.match(runtime_key), runtime_key
                assert runtime_key not in seen_keys
                assert ap_id not in seen_ids
                seen_keys.add(runtime_key)
                seen_ids.add(ap_id)


def test_world_imports() -> None:
    GeneralsZHWorld, constants, _, items, locations, _ = import_generalszh()
    assert GeneralsZHWorld.game == constants.GAME_NAME
    assert GeneralsZHWorld.item_name_to_id == items.ITEM_NAME_TO_ID
    assert GeneralsZHWorld.location_name_to_id == locations.LOCATION_NAME_TO_ID


def test_manifest_targets_archipelago_067() -> None:
    manifest = json.loads(
        (OVERLAY_WORLDS / "generalszh" / "archipelago.json").read_text(encoding="utf-8")
    )
    vendor = json.loads((REPO / "vendor" / "archipelago" / "vendor.json").read_text(encoding="utf-8"))
    assert manifest["minimum_ap_version"] == "0.6.7"
    assert vendor["upstream"]["current_release_tag"] == "0.6.7"
    assert manifest["game"] == "Command & Conquer Generals: Zero Hour"


def test_mission_ids_and_names() -> None:
    _, constants, _, _, locations, _ = import_generalszh()
    expected_ids = {
        "air_force": 270000000,
        "laser": 270000001,
        "superweapon": 270000002,
        "tank": 270000003,
        "nuke": 270000004,
        "stealth": 270000005,
        "toxin": 270000006,
        "boss": 270000007,
    }
    for map_key, expected_id in expected_ids.items():
        assert constants.mission_victory_location_id(map_key) == expected_id
        assert locations.LOCATION_NAME_TO_ID[constants.mission_location_name(map_key)] == expected_id


def test_victory_medal_items_gate_boss() -> None:
    _, constants, _, items, locations, _ = import_generalszh()
    expected_medals = {
        "air_force": "Air Force General Medal",
        "laser": "Laser General Medal",
        "superweapon": "Superweapons General Medal",
        "tank": "Tank General Medal",
        "nuke": "Nuke General Medal",
        "stealth": "Stealth General Medal",
        "toxin": "Toxin General Medal",
    }
    assert constants.VICTORY_MEDAL_ITEM_NAMES == expected_medals
    for map_key, medal_name in expected_medals.items():
        assert constants.victory_medal_item_name(map_key) == medal_name
        assert medal_name in items.ITEM_NAME_TO_ID
        assert items.DEFAULT_ITEM_CLASSIFICATIONS[medal_name] == items.ItemClassification.progression

    try:
        constants.victory_medal_item_name("boss")
    except ValueError:
        pass
    else:
        raise AssertionError("Boss map must not have a shuffled medal item")

    pool = items.item_pool_for_location_count(locations.enabled_location_count_for_preset("default"))
    assert [name for name in pool if name.endswith(" Medal")] == list(expected_medals.values())
    assert all(not name.endswith(" Defeated") for name in items.ITEM_NAME_TO_ID)


def test_boss_mission_victory_owns_locked_final_victory() -> None:
    _, constants, _, _, locations, _ = import_generalszh()
    region_type = sys.modules["BaseClasses"].Region

    class FakeWorld:
        player = 1
        multiworld = object()

        def __init__(self) -> None:
            self.regions = {
                locations.region_name_for_map(map_key): region_type(locations.region_name_for_map(map_key), 1, self.multiworld)
                for map_key in constants.MAP_SLOTS
            }

        def get_region(self, name):
            return self.regions[name]

    world = FakeWorld()
    locations.create_mission_locations(world)
    locations.create_mission_events(world)

    for map_key in constants.MAIN_MAP_KEYS:
        region_locations = world.regions[locations.region_name_for_map(map_key)].locations
        assert len(region_locations) == 1
        assert region_locations[0].name == constants.mission_location_name(map_key)
        assert region_locations[0].item is None

    boss_locations = world.regions[locations.region_name_for_map("boss")].locations
    assert len(boss_locations) == 1
    assert boss_locations[0].name == constants.mission_location_name("boss")
    assert boss_locations[0].address == constants.mission_victory_location_id("boss")
    assert boss_locations[0].item.name == "Victory"


def test_cluster_ids_and_runtime_keys() -> None:
    _, constants, _, _, _, _ = import_generalszh()
    assert constants.cluster_unit_location_id("tank", 3, 1) == 270040301
    assert constants.cluster_runtime_key("tank", 3, 1) == "cluster.tank.c03.u01"
    assert constants.cluster_location_name("tank", 3, 1) == "Cluster Unit - Tank General c03 u01"
    assert constants.cluster_unit_location_id("boss", 99, 99) == 270089999
    assert constants.cluster_runtime_key("boss", 99, 99) == "cluster.boss.c99.u99"

    ids = {
        constants.cluster_unit_location_id(map_key, cluster_index, unit_index)
        for map_key in constants.MAP_SLOTS
        for cluster_index in (0, 3, 99)
        for unit_index in (1, 2, 99)
    }
    assert len(ids) == len(constants.MAP_SLOTS) * 3 * 3


def test_future_location_family_ids_and_runtime_keys() -> None:
    _, constants, content_framework, _, _, _ = import_generalszh()
    assert constants.captured_building_location_id("tank", 1) == 270091501
    assert constants.captured_building_runtime_key("tank", 1) == "capture.tank.b001"
    assert constants.captured_building_location_name("tank", 1) == "Captured Building - Tank General b001"
    assert constants.supply_pile_location_id("tank", 2, 3) == 270096523
    assert constants.supply_pile_runtime_key("tank", 2, 3) == "supply.tank.p02.t03"
    assert constants.supply_pile_location_name("tank", 2, 3) == "Supply Pile - Tank General p02 t03"
    assert CAPTURE_KEY_RE.match(constants.captured_building_runtime_key("toxin", 499))
    assert SUPPLY_KEY_RE.match(constants.supply_pile_runtime_key("boss", 49, 9))

    max_cluster_id = constants.cluster_unit_location_id("boss", 99, 99)
    max_capture_id = constants.captured_building_location_id("boss", 499)
    max_supply_id = constants.supply_pile_location_id("boss", 49, 9)
    assert constants.MISSION_VICTORY_BASE < constants.CLUSTER_UNIT_BASE
    assert max_cluster_id < constants.CAPTURED_BUILDING_BASE
    assert max_capture_id < constants.SUPPLY_PILE_BASE
    assert max_supply_id < constants.ITEM_NAMESPACE_BASE

    families = content_framework.LOCATION_FAMILIES
    assert families["mission_victory"].default_enabled is True
    assert families["cluster_unit"].default_enabled is True
    assert families["captured_building"].default_enabled is False
    assert families["supply_pile_threshold"].default_enabled is False


def test_location_catalog_validates_and_derives_records() -> None:
    _, constants, _, _, _, _ = import_generalszh()
    from worlds.generalszh import location_catalog

    catalog = json.loads(LOCATION_CATALOG_PATH.read_text(encoding="utf-8"))
    warnings = location_catalog.validate_location_catalog(catalog)
    assert warnings == ["location catalog contains no future checks yet; this is valid while families stay disabled"]
    assert location_catalog.catalog_location_counts(catalog) == {
        "captured_building": 0,
        "supply_pile_threshold": 0,
        "total": 0,
    }
    for map_key in constants.MAP_SLOTS:
        assert (REPO / catalog["maps"][map_key]["mapSource"]).exists()

    fixture = copy.deepcopy(catalog)
    fixture["maps"]["tank"]["capturedBuildings"].append(
        {
            "buildingIndex": 1,
            "label": "Near-base Oil Derrick",
            "template": "CivilianTechOilDerrick",
            "position": {"x": 1000.0, "y": 1200.0},
            "sphere": 0,
            "authorStatus": "candidate",
        }
    )
    fixture["maps"]["tank"]["supplyPiles"].append(
        {
            "pileIndex": 2,
            "label": "Near-base supply pile",
            "template": "SupplyPile",
            "startingAmount": 30000,
            "position": {"x": 900.0, "y": 1100.0},
            "sphere": 0,
            "authorStatus": "candidate",
            "thresholds": [
                {"thresholdIndex": 1, "fractionCollected": 0.33},
                {"thresholdIndex": 2, "fractionCollected": 0.66},
                {"thresholdIndex": 3, "fractionCollected": 1.0},
            ],
        }
    )

    assert location_catalog.validate_location_catalog(fixture) == []
    records = list(location_catalog.iter_catalog_location_records(fixture))
    assert [record["runtimeKey"] for record in records] == [
        "capture.tank.b001",
        "supply.tank.p02.t01",
        "supply.tank.p02.t02",
        "supply.tank.p02.t03",
    ]
    assert [record["apLocationId"] for record in records] == [
        270091501,
        270096521,
        270096522,
        270096523,
    ]
    assert location_catalog.catalog_location_counts(fixture) == {
        "captured_building": 1,
        "supply_pile_threshold": 3,
        "total": 4,
    }

    bad_drift = copy.deepcopy(fixture)
    bad_drift["maps"]["tank"]["supplyPiles"][0]["thresholds"][0]["runtimeKey"] = "supply.tank.p99.t99"
    try:
        location_catalog.validate_location_catalog(bad_drift)
    except location_catalog.LocationCatalogValidationError:
        pass
    else:
        raise AssertionError("Catalog runtime-key drift was not rejected")


def test_location_authoring_schema_validates() -> None:
    _, _, _, _, _, _ = import_generalszh()
    from worlds.generalszh import location_catalog

    schema = json.loads(AUTHORING_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert location_catalog.validate_location_authoring_schema(schema) == []
    assert schema["status"] == "planning_only_disabled"
    assert schema["families"]["capturedBuildings"]["completionOwner"] == "runtime_capture_event"
    assert schema["families"]["supplyPiles"]["completionOwner"] == "runtime_supply_collection_tracker"
    assert "mission_replay_persistent" in schema["allowedPersistenceRequirements"]
    assert "missabilityRisk" in schema["sharedAuthoringRequiredFields"]
    assert "screenshotRef" in schema["visualRequiredFields"]

    bad_schema = copy.deepcopy(schema)
    bad_schema["status"] = "enabled"
    try:
        location_catalog.validate_location_authoring_schema(bad_schema)
    except location_catalog.LocationCatalogValidationError:
        pass
    else:
        raise AssertionError("Enabled authoring schema status was not rejected")


def test_location_runtime_persistence_contract_validates() -> None:
    _, _, _, _, _, _ = import_generalszh()
    from worlds.generalszh import location_catalog

    catalog = json.loads(LOCATION_CATALOG_PATH.read_text(encoding="utf-8"))
    schema = json.loads(AUTHORING_SCHEMA_PATH.read_text(encoding="utf-8"))
    contract = json.loads(RUNTIME_PERSISTENCE_CONTRACT_PATH.read_text(encoding="utf-8"))

    assert location_catalog.validate_runtime_persistence_contract(contract, schema) == []
    assert contract["status"] == "planning_only_disabled"
    assert contract["scope"] == "runtime_persistence_contract_only"
    assert contract["familiesDefaultEnabled"] is False
    assert contract["shared"]["runtimeKeySource"] == "verified Seed-Slot-Data.json only"
    assert contract["shared"]["duplicateCompletionPolicy"] == "idempotent_noop"
    assert contract["shared"]["missionRestartPolicy"] == "preserve_family_state"
    assert contract["shared"]["wrongSeedPolicy"] == "reject_without_import"
    assert contract["shared"]["demoFallbackPolicy"] == "future_location_families_unavailable_in_demo_fallback"
    assert "completedChecks" in contract["shared"]["completedCheckCollections"]
    assert "completedLocations" in contract["shared"]["completedCheckCollections"]

    captured = contract["families"]["capturedBuildings"]
    supply = contract["families"]["supplyPiles"]
    assert captured["completionOwner"] == schema["families"]["capturedBuildings"]["completionOwner"]
    assert supply["completionOwner"] == schema["families"]["supplyPiles"]["completionOwner"]
    assert captured["persistenceRequirement"] == "mission_replay_persistent"
    assert supply["persistenceRequirement"] == "mission_replay_persistent"
    assert "firstCompletedSlotDataHash" in captured["requiredStateFields"]
    assert "persistentCollectedAmount" in supply["requiredPileStateFields"]
    assert "Bridge rejects unknown or unselected supply runtime keys instead of deriving IDs." in supply["enableBlockers"]

    assert location_catalog.catalog_location_counts(catalog)["total"] == 0

    bad_contract = copy.deepcopy(contract)
    bad_contract["shared"]["duplicateCompletionPolicy"] = "append_duplicate"
    try:
        location_catalog.validate_runtime_persistence_contract(bad_contract, schema)
    except location_catalog.LocationCatalogValidationError:
        pass
    else:
        raise AssertionError("Non-idempotent duplicate completion policy was not rejected")


def test_future_location_enable_criteria_validates() -> None:
    _, _, _, _, _, _ = import_generalszh()
    from worlds.generalszh import location_catalog

    contract = json.loads(RUNTIME_PERSISTENCE_CONTRACT_PATH.read_text(encoding="utf-8"))
    criteria = json.loads(ENABLE_CRITERIA_PATH.read_text(encoding="utf-8"))

    assert location_catalog.validate_future_location_enable_criteria(criteria, contract) == []
    assert criteria["status"] == "planning_only_disabled"
    assert criteria["scope"] == "future_location_family_enable_criteria"
    assert criteria["familiesDefaultEnabled"] is False
    assert criteria["productionGuardRequired"] is True

    required_ids = {entry["id"] for entry in criteria["requiredCriteria"]}
    expected = {
        "author_catalog_approved_disabled",
        "runtime_object_identity",
        "runtime_completion_event",
        "runtime_replay_persistence",
        "bridge_translation_selected_only",
        "ap_generation_selection_option",
        "production_guard_removal_test",
        "manual_playtest_proof",
    }
    assert expected.issubset(required_ids)

    captured = criteria["families"]["capturedBuildings"]
    supply = criteria["families"]["supplyPiles"]
    assert captured["slotDataSection"] == contract["families"]["capturedBuildings"]["slotDataSection"]
    assert supply["slotDataSection"] == contract["families"]["supplyPiles"]["slotDataSection"]
    assert "Runtime state scaffold" in captured["notEnoughToEnable"]
    assert "Local bridge future-state mirroring" in supply["notEnoughToEnable"]
    assert "manual_playtest_proof" in captured["requiredCriteriaIds"]
    assert "manual_playtest_proof" in supply["requiredCriteriaIds"]

    bad_criteria = copy.deepcopy(criteria)
    bad_criteria["productionGuardRequired"] = False
    try:
        location_catalog.validate_future_location_enable_criteria(bad_criteria, contract)
    except location_catalog.LocationCatalogValidationError:
        pass
    else:
        raise AssertionError("Future location enable criteria allowed production guard removal")

    bad_missing = copy.deepcopy(criteria)
    bad_missing["families"]["capturedBuildings"]["requiredCriteriaIds"].remove("manual_playtest_proof")
    try:
        location_catalog.validate_future_location_enable_criteria(bad_missing, contract)
    except location_catalog.LocationCatalogValidationError:
        pass
    else:
        raise AssertionError("Future location enable criteria allowed missing manual playtest proof")


def test_location_authoring_fixture_examples_validate() -> None:
    _, _, _, _, _, slot_data = import_generalszh()
    from worlds.generalszh import location_catalog

    production_catalog = json.loads(LOCATION_CATALOG_PATH.read_text(encoding="utf-8"))
    fixture = json.loads(EXAMPLE_CANDIDATES_PATH.read_text(encoding="utf-8"))
    schema = json.loads(AUTHORING_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert location_catalog.catalog_location_counts(production_catalog) == {
        "captured_building": 0,
        "supply_pile_threshold": 0,
        "total": 0,
    }
    assert location_catalog.validate_location_catalog(fixture) == []
    assert location_catalog.validate_catalog_authoring_metadata(fixture, schema, require_authoring=True) == []

    records = list(location_catalog.iter_catalog_location_records(fixture))
    assert [record["runtimeKey"] for record in records] == [
        "capture.tank.b001",
        "supply.tank.p02.t01",
        "supply.tank.p02.t02",
        "supply.tank.p02.t03",
        "supply.tank.p02.t04",
    ]
    assert [record["apLocationId"] for record in records] == [
        270091501,
        270096521,
        270096522,
        270096523,
        270096524,
    ]

    payload = slot_data.build_testing_slot_data("seed-001", "Player 1", "run-001", "minimal")
    slot_data.add_catalog_location_records(payload, records)
    assert slot_data.selected_future_location_count(payload) == 5
    try:
        slot_data.validate_production_slot_data(payload)
    except slot_data.SlotDataValidationError:
        pass
    else:
        raise AssertionError("Test-only authoring fixture leaked through production slot-data guard")

    bad_fixture = copy.deepcopy(fixture)
    del bad_fixture["maps"]["tank"]["capturedBuildings"][0]["authoring"]["visual"]["screenshotRef"]
    try:
        location_catalog.validate_catalog_authoring_metadata(bad_fixture, schema, require_authoring=True)
    except location_catalog.LocationCatalogValidationError:
        pass
    else:
        raise AssertionError("Missing visual screenshotRef was not rejected")


def test_invalid_ids_fail() -> None:
    _, constants, _, _, _, _ = import_generalszh()
    failures = [
        lambda: constants.mission_victory_location_id("demo"),
        lambda: constants.cluster_unit_location_id("tank", -1, 1),
        lambda: constants.cluster_unit_location_id("tank", 100, 1),
        lambda: constants.cluster_unit_location_id("tank", 1, 0),
        lambda: constants.cluster_runtime_key("tank", 1, 100),
        lambda: constants.captured_building_location_id("tank", 0),
        lambda: constants.captured_building_runtime_key("tank", 500),
        lambda: constants.captured_building_location_name("tank", 500),
        lambda: constants.supply_pile_location_id("tank", 0, 1),
        lambda: constants.supply_pile_runtime_key("tank", 1, 10),
        lambda: constants.supply_pile_location_name("tank", 50, 1),
    ]
    for call in failures:
        try:
            call()
        except ValueError:
            continue
        raise AssertionError("Expected ValueError")


def test_slot_data_shell_validates() -> None:
    _, constants, _, _, _, slot_data = import_generalszh()
    data = constants.build_slot_data_shell(
        seed_id="seed-001",
        slot_name="Player 1",
        session_nonce="run-001",
    )
    validate_slot_data(data, constants)
    warnings = slot_data.validate_slot_data(
        slot_data.build_testing_slot_data("seed-001", "Player 1", "run-001", "default")
    )
    assert warnings


def test_slot_data_validation_catches_drift() -> None:
    _, constants, _, _, _, _ = import_generalszh()
    data = constants.build_slot_data_shell("seed-001", "Player 1", "run-001")

    duplicate = copy.deepcopy(data)
    duplicate["maps"]["laser"]["missionVictory"]["apLocationId"] = duplicate["maps"]["air_force"]["missionVictory"]["apLocationId"]
    try:
        validate_slot_data(duplicate, constants)
    except AssertionError:
        pass
    else:
        raise AssertionError("Duplicate AP location ID was not rejected")

    bad_key = copy.deepcopy(data)
    bad_key["maps"]["tank"]["missionVictory"]["runtimeKey"] = "mission.tank.complete"
    try:
        validate_slot_data(bad_key, constants)
    except AssertionError:
        pass
    else:
        raise AssertionError("Invalid mission runtime key was not rejected")

    missing_gate = copy.deepcopy(data)
    del missing_gate["maps"]["nuke"]["missionGate"]
    try:
        validate_slot_data(missing_gate, constants)
    except KeyError:
        pass
    else:
        raise AssertionError("Missing missionGate was not rejected")


def test_testing_slot_data_default_and_minimal() -> None:
    _, constants, _, items, locations, slot_data = import_generalszh()
    default_payload = slot_data.build_testing_slot_data("seed-001", "Player 1", "run-001", "default")
    minimal_payload = slot_data.build_testing_slot_data("seed-001", "Player 1", "run-001", "minimal")

    default_cluster_count = sum(len(map_data["clusters"]) for map_data in default_payload["maps"].values())
    minimal_cluster_count = sum(len(map_data["clusters"]) for map_data in minimal_payload["maps"].values())
    assert default_cluster_count > minimal_cluster_count

    default_locations = locations.enabled_location_count_for_preset("default")
    minimal_locations = locations.enabled_location_count_for_preset("minimal")
    assert default_locations > minimal_locations
    assert len(items.item_pool_for_location_count(default_locations)) == default_locations
    assert len(items.item_pool_for_location_count(minimal_locations)) == minimal_locations

    selected_names = set(locations.selected_cluster_location_names("default"))
    assert selected_names
    assert selected_names.issubset(locations.LOCATION_NAME_TO_ID)
    assert all(locations.LOCATION_NAME_TO_ID[name] >= constants.CLUSTER_UNIT_BASE for name in selected_names)


def test_slot_data_validator_rejects_bad_clusters() -> None:
    _, _, _, _, _, slot_data = import_generalszh()
    payload = slot_data.build_testing_slot_data("seed-001", "Player 1", "run-001", "default")

    bad_duplicate = copy.deepcopy(payload)
    tank_units = bad_duplicate["maps"]["tank"]["clusters"][0]["units"]
    tank_units[1]["apLocationId"] = tank_units[0]["apLocationId"]
    try:
        slot_data.validate_slot_data(bad_duplicate)
    except slot_data.SlotDataValidationError:
        pass
    else:
        raise AssertionError("Duplicate cluster AP ID was not rejected")

    bad_medium_gate = copy.deepcopy(payload)
    bad_medium_gate["maps"]["tank"]["clusters"][1]["requiredMissionGate"] = "none"
    try:
        slot_data.validate_slot_data(bad_medium_gate)
    except slot_data.SlotDataValidationError:
        pass
    else:
        raise AssertionError("Medium cluster without Hold was not rejected")

    bad_hard_width = copy.deepcopy(payload)
    bad_hard_width["maps"]["tank"]["clusters"][2]["requiredWeaknesses"] = ["anti_vehicle"]
    try:
        slot_data.validate_slot_data(bad_hard_width)
    except slot_data.SlotDataValidationError:
        pass
    else:
        raise AssertionError("Hard cluster without two weaknesses was not rejected")


def test_slot_data_runtime_translation() -> None:
    _, _, _, _, _, slot_data = import_generalszh()
    payload = slot_data.build_testing_slot_data("seed-001", "Player 1", "run-001", "default")
    translated = slot_data.translate_runtime_checks(
        payload,
        ["mission.tank.victory", "cluster.tank.c02.u01"],
    )
    assert translated == [270000003, 270040201]
    try:
        slot_data.translate_runtime_checks(payload, ["cluster.tank.c99.u99"])
    except slot_data.SlotDataValidationError:
        pass
    else:
        raise AssertionError("Unknown runtime key was not rejected")


def test_slot_data_selected_catalog_translation() -> None:
    _, _, _, _, _, slot_data = import_generalszh()
    from worlds.generalszh import location_catalog

    catalog = json.loads(LOCATION_CATALOG_PATH.read_text(encoding="utf-8"))
    fixture = copy.deepcopy(catalog)
    fixture["maps"]["tank"]["capturedBuildings"].append(
        {
            "buildingIndex": 1,
            "label": "Near-base Oil Derrick",
            "template": "CivilianTechOilDerrick",
            "position": {"x": 1000.0, "y": 1200.0},
            "sphere": 0,
            "authorStatus": "candidate",
        }
    )
    fixture["maps"]["tank"]["supplyPiles"].append(
        {
            "pileIndex": 2,
            "label": "Near-base supply pile",
            "template": "SupplyPile",
            "startingAmount": 30000,
            "position": {"x": 900.0, "y": 1100.0},
            "sphere": 0,
            "authorStatus": "candidate",
            "thresholds": [
                {"thresholdIndex": 1, "fractionCollected": 0.33},
                {"thresholdIndex": 2, "fractionCollected": 0.66},
            ],
        }
    )
    records = list(location_catalog.iter_catalog_location_records(fixture))
    payload = slot_data.build_testing_slot_data("seed-001", "Player 1", "run-001", "minimal")
    slot_data.add_catalog_location_records(payload, records)

    tank = payload["maps"]["tank"]
    assert [entry["runtimeKey"] for entry in tank["capturedBuildings"]] == ["capture.tank.b001"]
    assert [entry["runtimeKey"] for entry in tank["supplyPileThresholds"]] == [
        "supply.tank.p02.t01",
        "supply.tank.p02.t02",
    ]
    translated = slot_data.translate_runtime_checks(
        payload,
        ["capture.tank.b001", "supply.tank.p02.t02"],
    )
    assert translated == [270091501, 270096522]

    try:
        slot_data.translate_runtime_checks(payload, ["supply.tank.p02.t03"])
    except slot_data.SlotDataValidationError:
        pass
    else:
        raise AssertionError("Unselected supply threshold was not rejected")

    bad_drift = copy.deepcopy(payload)
    bad_drift["maps"]["tank"]["capturedBuildings"][0]["runtimeKey"] = "capture.tank.b999"
    try:
        slot_data.validate_slot_data(bad_drift)
    except slot_data.SlotDataValidationError:
        pass
    else:
        raise AssertionError("Selected captured-building runtime-key drift was not rejected")


def test_production_slot_data_future_families_guarded() -> None:
    _, _, _, _, _, slot_data = import_generalszh()
    from worlds.generalszh import location_catalog

    payload = slot_data.build_testing_slot_data("seed-001", "Player 1", "run-001", "minimal")
    assert slot_data.selected_future_location_count(payload) == 0
    assert slot_data.validate_production_slot_data(payload)

    catalog = json.loads(LOCATION_CATALOG_PATH.read_text(encoding="utf-8"))
    fixture = copy.deepcopy(catalog)
    fixture["maps"]["tank"]["capturedBuildings"].append(
        {
            "buildingIndex": 1,
            "label": "Near-base Oil Derrick",
            "template": "CivilianTechOilDerrick",
            "sphere": 0,
            "authorStatus": "candidate",
        }
    )
    fixture["maps"]["tank"]["supplyPiles"].append(
        {
            "pileIndex": 2,
            "label": "Near-base supply pile",
            "template": "SupplyPile",
            "startingAmount": 30000,
            "sphere": 0,
            "authorStatus": "candidate",
            "thresholds": [
                {"thresholdIndex": 1, "fractionCollected": 1.0},
            ],
        }
    )

    future_payload = slot_data.build_testing_slot_data("seed-001", "Player 1", "run-001", "minimal")
    slot_data.add_catalog_location_records(
        future_payload,
        list(location_catalog.iter_catalog_location_records(fixture)),
    )
    assert slot_data.selected_future_location_count(future_payload) == 2
    assert slot_data.validate_slot_data(future_payload)
    try:
        slot_data.validate_production_slot_data(future_payload)
    except slot_data.SlotDataValidationError as exc:
        assert "production-disabled" in str(exc)
        assert "tank.capturedBuildings=1" in str(exc)
        assert "tank.supplyPileThresholds=1" in str(exc)
    else:
        raise AssertionError("Production slot-data guard allowed future location-family checks")


def test_economy_item_framework() -> None:
    _, _, content_framework, items, _, _ = import_generalszh()
    effects = content_framework.ECONOMY_ITEM_EFFECTS
    assert effects["Progressive Production"].min_step_percent == 25
    assert effects["Progressive Production"].max_step_percent == 100
    assert effects["Progressive Production"].total_cap_percent == 300
    assert content_framework.production_bonus_copy_count(25) == 12
    assert content_framework.production_bonus_copy_count(100) == 3
    assert content_framework.production_multiplier_for_copies(0, 25) == 1.0
    assert content_framework.production_multiplier_for_copies(4, 25) == 2.0
    assert content_framework.production_multiplier_for_copies(20, 25) == 4.0
    assert effects["Supply Cache"].effect_key == "cash_drop_once"
    assert content_framework.planned_item_copy_counts("target") == {
        "Progressive Starting Money": 6,
        "Progressive Production": 6,
        "Supply Cache": 50,
        "Future Filler Slot": 25,
        "Future Trap Slot": 10,
    }
    assert content_framework.planned_item_copy_total("target") == 97
    assert content_framework.planned_item_copy_counts("max")["Progressive Production"] == content_framework.production_bonus_copy_count(25)
    assert "Future Trap Slot" not in items.ITEM_NAME_TO_ID
    assert "Future Filler Slot" not in items.ITEM_NAME_TO_ID


def main() -> int:
    tests = [
        test_world_imports,
        test_manifest_targets_archipelago_067,
        test_mission_ids_and_names,
        test_victory_medal_items_gate_boss,
        test_boss_mission_victory_owns_locked_final_victory,
        test_cluster_ids_and_runtime_keys,
        test_future_location_family_ids_and_runtime_keys,
        test_location_catalog_validates_and_derives_records,
        test_location_authoring_schema_validates,
        test_location_runtime_persistence_contract_validates,
        test_future_location_enable_criteria_validates,
        test_location_authoring_fixture_examples_validate,
        test_invalid_ids_fail,
        test_slot_data_shell_validates,
        test_slot_data_validation_catches_drift,
        test_testing_slot_data_default_and_minimal,
        test_slot_data_validator_rejects_bad_clusters,
        test_slot_data_runtime_translation,
        test_slot_data_selected_catalog_translation,
        test_production_slot_data_future_families_guarded,
        test_economy_item_framework,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
        except Exception as exc:
            print(f"FAIL: {test.__name__} - {exc}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
