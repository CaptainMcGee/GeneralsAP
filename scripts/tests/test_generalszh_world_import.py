#!/usr/bin/env python3
"""Tests for the GeneralsZH AP overlay consuming Logic Foundry source."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
IMPORTER_PATH = REPO / "vendor" / "archipelago" / "overlay" / "worlds" / "generalszh" / "logic_foundry_import.py"


def load_importer():
    spec = importlib.util.spec_from_file_location("generalszh_logic_foundry_import", IMPORTER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeState:
    def __init__(self, items: set[str] | None = None):
        self.items = items or set()

    def has(self, item_name: str, player: int) -> bool:
        return item_name in self.items


def items_for_route(source: dict, route) -> set[str]:
    items: set[str] = set()
    for unit_rule in source["unitBuildRules"]:
        if unit_rule["faction"] != route.faction:
            continue
        if unit_rule.get("general") not in (None, route.general):
            continue
        items.update(unit_rule["allRequiredItemIds"])
    return items


def easy_cluster(source: dict) -> dict:
    return next(rule for rule in source["clusterAccessRules"] if rule["gate"] == "none")


def medium_cluster(source: dict) -> dict:
    return next(rule for rule in source["clusterAccessRules"] if rule["gate"] == "mission_hold")


def hard_cluster(source: dict) -> dict:
    return next(rule for rule in source["clusterAccessRules"] if rule["gate"] in {"mission_win", "mission_defeat"})


def test_source_loads_and_builds_tables() -> None:
    importer = load_importer()
    source = importer.load_logic_foundry_source()
    importer.validate_logic_foundry_source(source)

    items = importer.item_name_to_id(source)
    locations = importer.location_name_to_id(source)
    assert items["Victory"] is None
    assert items["Air Force General Medal"] == 270100100
    assert "Shared_CommandCenters" in items
    assert locations["Mission: China Boss General Victory"] == 270000007
    assert any(name.startswith("Cluster: ") for name in locations)


def test_unit_buildable_requires_unit_and_building_items() -> None:
    importer = load_importer()
    source = importer.load_logic_foundry_source()
    route = importer.Route("USA", "Air Force")
    unit_rule = next(
        rule for rule in source["unitBuildRules"]
        if rule["faction"] == "USA" and rule.get("general") in (None, "Air Force")
        and rule["requiredItemIds"] and rule["productionFacilityItemIds"]
    )

    empty = FakeState()
    assert not importer.unit_buildable(empty.has, 1, unit_rule, route)

    buildings_only = FakeState(set(unit_rule["productionFacilityItemIds"]))
    assert not importer.unit_buildable(buildings_only.has, 1, unit_rule, route)

    complete = FakeState(set(unit_rule["allRequiredItemIds"]))
    assert importer.unit_buildable(complete.has, 1, unit_rule, route)


def test_cluster_access_uses_authored_weaknesses_and_separate_mission_gates() -> None:
    importer = load_importer()
    source = importer.load_logic_foundry_source()
    route = importer.Route("USA", "Air Force")
    owned = items_for_route(source, route)
    state = FakeState(owned)

    assert importer.cluster_access(state, state.has, 1, source, easy_cluster(source), route)
    assert not importer.cluster_access(state, state.has, 1, source, medium_cluster(source), route)
    assert importer.cluster_access(
        state,
        state.has,
        1,
        source,
        medium_cluster(source),
        route,
        mission_hold=lambda _state, _mission_id, _route: True,
    )
    assert not importer.cluster_access(
        state,
        state.has,
        1,
        source,
        hard_cluster(source),
        route,
        mission_win=lambda _state, _mission_id, _route: False,
    )


def test_route_does_not_borrow_wrong_faction_or_general() -> None:
    importer = load_importer()
    source = importer.load_logic_foundry_source()
    cases = [
        ("USA", "Air Force", importer.Route("USA", "Laser"), importer.Route("USA", "Air Force")),
        ("GLA", "Toxin", importer.Route("GLA", "Stealth"), importer.Route("GLA", "Toxin")),
        ("China", "Tank", importer.Route("China", "Nuke", "faction_shared"), importer.Route("China", "Tank", "faction_shared")),
    ]
    for faction, general, wrong_route, correct_route in cases:
        unit = next(rule for rule in source["unitBuildRules"] if rule["faction"] == faction and rule.get("general") == general)
        owned = FakeState(set(unit["allRequiredItemIds"]))
        assert not importer.unit_buildable(owned.has, 1, unit, wrong_route), (unit["unitId"], wrong_route)
        assert importer.unit_buildable(owned.has, 1, unit, correct_route), (unit["unitId"], correct_route)


def test_abstract_shared_route_requires_explicit_group_callback() -> None:
    importer = load_importer()
    source = importer.load_logic_foundry_source()
    unit = next(rule for rule in source["unitBuildRules"] if rule.get("sourceUnlockGroupIds"))
    owned = FakeState(set(unit["allRequiredItemIds"]))

    no_callback_route = importer.Route(unit["faction"], unit.get("general"), "abstract_shared")
    assert not importer.unit_buildable(owned.has, 1, unit, no_callback_route)

    group_ids = set(unit["sourceUnlockGroupIds"])
    callback_route = importer.Route(
        unit["faction"],
        unit.get("general"),
        "abstract_shared",
        abstract_group_can_field=lambda candidate_group_ids: bool(group_ids.intersection(candidate_group_ids)),
    )
    assert importer.unit_buildable(owned.has, 1, unit, callback_route)


def test_boss_access_and_completion_are_distinct() -> None:
    importer = load_importer()
    source = importer.load_logic_foundry_source()
    medals = set(source["worldGoal"]["requiredMedalItemNames"])

    assert len(medals) == 7
    assert importer.boss_access(FakeState(medals).has, 1, source)
    assert not importer.completion_condition(FakeState(medals).has, 1, source)
    assert importer.completion_condition(FakeState({"Victory"}).has, 1, source)


def main() -> int:
    tests = [
        test_source_loads_and_builds_tables,
        test_unit_buildable_requires_unit_and_building_items,
        test_cluster_access_uses_authored_weaknesses_and_separate_mission_gates,
        test_route_does_not_borrow_wrong_faction_or_general,
        test_abstract_shared_route_requires_explicit_group_callback,
        test_boss_access_and_completion_are_distinct,
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
