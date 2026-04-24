#!/usr/bin/env python3
"""Sanity tests for Archipelago generation, config, graph, cluster, and logic."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]



def load_json(rel_path: str):
    path = REPO / rel_path
    assert path.exists(), f"Missing {rel_path}"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)



def test_json_configs() -> None:
    configs = [
        (
            "Data/Archipelago/unit_matchup_archetypes.json",
            [
                "defender_cluster_tier_medium_regexes",
                "defender_cluster_tier_hard_include_templates",
                "easy_cluster_non_combat_weight_ratio",
                "balance_model",
            ],
        ),
        ("Data/Archipelago/cluster_config.json", ["defaults", "maps"]),
        ("Data/Archipelago/enemy_general_profiles.json", ["generals"]),
        (
            "Data/Archipelago/challenge_unit_protection.json",
        [
            "zero_damage",
            "reduced_damage_95_fighters",
            "reduced_damage_75_fields",
            "reduced_damage_98_general_powers",
            "immunities",
        ],
        ),
    ]
    for rel_path, keys in configs:
        data = load_json(rel_path)
        for key in keys:
            assert key in data, f"{rel_path} missing key {key}"



def test_non_spawnable_denylist() -> None:
    data = load_json("Data/Archipelago/non_spawnable_templates.json")
    templates = set(data.get("templates", [])) if isinstance(data, dict) else set(data)
    expected = {
        "GLATunnelNetworkNoSpawn",
        "AmericaInfantryOfficer",
        "ChinaInfantryOfficer",
        "ChinaInfantryAgent",
        "ChinaInfantryParadeRedGuard",
        "ChinaInfantrySecretPolice",
        "AmericaCheckpoint",
        "ChinaMoat",
    }
    missing = expected - templates
    assert not missing, f"non_spawnable_templates.json missing: {sorted(missing)}"



def test_name_override_files_exist() -> None:
    overrides = load_json("Data/Archipelago/name_overrides.json")
    assert "display_name_overrides" in overrides
    assert "template_overrides" in overrides


def test_challenge_unit_protection_contains_required_entries() -> None:
    data = load_json("Data/Archipelago/challenge_unit_protection.json")
    names = set()
    for bucket in (
        "zero_damage",
        "reduced_damage_95_fighters",
        "reduced_damage_75_fields",
        "reduced_damage_98_general_powers",
        "immunities",
    ):
        for entry in data.get(bucket, []):
            names.add(entry.get("player_name"))

    expected = {
        "SCUD Storm",
        "Particle Cannon",
        "Neutron Missile",
        "Daisy Cutter",
        "EMP Pulse",
        "Ground toxin fields",
        "Ground radiation fields",
        "Hijacker capture",
        "Jarmen Kell vehicle snipe",
        "Black Lotus disable / hack",
    }
    missing = sorted(name for name in expected if name not in names)
    assert not missing, f"challenge_unit_protection.json missing entries: {missing}"



def test_ingame_name_map_known_labels() -> None:
    data = load_json("Data/Archipelago/ingame_names.json")
    assert data.get("OBJECT:Ranger") == "Ranger"
    assert data.get("OBJECT:Redguard") == "Red Guard"
    assert data.get("OBJECT:TunnelNetwork") == "Tunnel Network"


def test_template_name_map_known_templates() -> None:
    data = load_json("Data/Archipelago/template_ingame_names.json")
    assert data.get("AmericaInfantryRanger") == "Ranger"
    assert data.get("ChinaInfantryRedguard") == "Red Guard"
    assert data.get("GLAVehicleTechnical") == "Technical"


def test_template_name_map_tracks_wrapper_sources() -> None:
    data = load_json("Data/Archipelago/template_ingame_names.json")
    sources = data.get("_sources", {})
    technical_source = sources.get("GLAVehicleTechnical", {})
    assert technical_source.get("source") in {"build_button", "build_variations"}


def test_template_name_map_has_review_notes_for_unresolved_templates() -> None:
    data = load_json("Data/Archipelago/template_ingame_names.json")
    unresolved = data.get("_unresolved", [])
    notes = data.get("_unresolved_notes", {})
    missing = [template for template in unresolved if template not in notes]
    assert not missing, f"Missing review notes for unresolved templates: {sorted(missing)}"
    if unresolved:
        assert notes[unresolved[0]].get("suspected_name")
        assert notes[unresolved[0]].get("note")

def test_balance_model_veterancy() -> None:
    data = load_json("Data/Archipelago/unit_matchup_archetypes.json")
    factors = data.get("balance_model", {}).get("cluster_tier_veterancy_factors", {})
    assert "easy" in factors and "medium" in factors and "hard" in factors



def test_base_defense_exclude_demo_traps() -> None:
    data = load_json("Data/Archipelago/unit_matchup_archetypes.json")
    exclude = data.get("defender_base_defense_exclude_regexes", [])
    has_demo = any("DemoTrap" in entry for entry in exclude)
    has_advanced = any("AdvancedDemoTrap" in entry for entry in exclude)
    assert has_demo and has_advanced, "Base defense exclude must include Demo Trap and Advanced Demo Trap"



def test_enemy_profiles_seven_generals() -> None:
    data = load_json("Data/Archipelago/enemy_general_profiles.json")
    generals = data.get("generals", {})
    assert len(generals) == 7
    assert "TankGeneral" in generals and "SuperweaponGeneral" in generals
    for general in generals.values():
        assert "difficulty" in general
        for difficulty in ("easy", "medium", "hard"):
            assert difficulty in general["difficulty"]
            assert "defense_strength" in general["difficulty"][difficulty]
            assert "objective_strength" in general["difficulty"][difficulty]



def test_graph_script_output_schema() -> None:
    path = REPO / "Data/Archipelago/generated_unit_matchup_graph.json"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        graph = json.load(handle)
    assert "defenders" in graph and "attackers" in graph
    for defender in graph["defenders"]:
        assert "cluster_tier" in defender, f"Defender missing cluster_tier: {defender.get('template')}"
    for attacker in graph["attackers"]:
        assert attacker.get("name"), f"Attacker missing localized name: {attacker.get('template')}"



def test_graph_names_use_localized_strings() -> None:
    path = REPO / "Data/Archipelago/generated_unit_matchup_graph.json"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        graph = json.load(handle)
    names = {node.get("template"): node.get("name") for node in graph.get("attackers", []) + graph.get("defenders", [])}
    if "AmericaInfantryRanger" in names:
        assert names["AmericaInfantryRanger"] == "Ranger"
    if "ChinaInfantryRedguard" in names:
        assert names["ChinaInfantryRedguard"] == "Red Guard"
    assert "Redguard" not in set(names.values()), "Graph should use localized strings, not raw display labels"



def test_graph_readable_output_includes_template_labels() -> None:
    path = REPO / "Data/Archipelago/generated_unit_matchup_graph_readable.txt"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return
    first_line = text.splitlines()[0]
    assert "[" in first_line and "]" in first_line, "Readable graph output should include template labels for verification"



def test_chinook_hard_defender() -> None:
    path = REPO / "Data/Archipelago/generated_unit_matchup_graph.json"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        graph = json.load(handle)
    chinook = [d for d in graph["defenders"] if "Chinook" in d.get("template", "")]
    assert chinook, "Chinook (Battle Chinook) should be hard defender"
    assert chinook[0].get("cluster_tier") == "hard"



def test_excluded_units_not_defenders() -> None:
    path = REPO / "Data/Archipelago/generated_unit_matchup_graph.json"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        graph = json.load(handle)
    defenders = [d.get("template", "") for d in graph["defenders"]]
    excluded_patterns = [
        "BlackLotus",
        "SuperBlackLotus",
        "SupplyOutpost",
        "SupplyDropZone",
        "ListeningOutpost",
        "TroopCrawler",
        "Terrorist",
        "Saboteur",
        "Hacker",
        "Hijacker",
        "Pilot",
        "RadarVan",
        "ScoutDrone",
        "SpyDrone",
        "RepairDrone",
        "CargoPlane",
    ]
    for pattern in excluded_patterns:
        found = [template for template in defenders if pattern in template]
        assert not found, f"Excluded unit pattern {pattern!r} should not be in defenders: {found}"
    chinooks = [template for template in defenders if "Chinook" in template]
    assert all("AmericaVehicleChinook" in template for template in chinooks), "Only Battle Chinook (America) allowed as defender"



def test_no_demo_trap_in_defenders() -> None:
    path = REPO / "Data/Archipelago/generated_unit_matchup_graph.json"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        graph = json.load(handle)
    defenders = [d.get("template", "") for d in graph["defenders"]]
    for template in defenders:
        assert "DemoTrap" not in template and "AdvancedDemoTrap" not in template, f"Demo traps must not be defenders: {template}"



def test_base_defenses_medium_only() -> None:
    path = REPO / "Data/Archipelago/generated_unit_matchup_graph.json"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        graph = json.load(handle)
    for defender in graph["defenders"]:
        if defender.get("archetype") == "base_defense":
            assert defender.get("cluster_tier") == "medium", f"Base defense must be medium only: {defender.get('template')}"




def test_archipelago_vendor_metadata() -> None:
    data = load_json("vendor/archipelago/vendor.json")
    assert data.get("upstream", {}).get("repo") == "ArchipelagoMW/Archipelago"
    assert data.get("layout", {}).get("upstream_dir") == "vendor/archipelago/upstream"


def test_archipelago_vendor_tree_exists() -> None:
    assert (REPO / "vendor/archipelago/upstream/README.md").exists()
    assert (REPO / "vendor/archipelago/overlay/README.md").exists()
    assert (REPO / "vendor/archipelago/patches/README.md").exists()

def test_logic_prereqs() -> None:
    sys.path.insert(0, str(REPO))
    from scripts.archipelago_logic_prerequisites import can_beat_mission, can_defend

    assert can_defend(60, "TankGeneral", "medium") is True
    assert can_defend(40, "TankGeneral", "medium") is False
    assert can_beat_mission(90, "TankGeneral", "medium") is True



def test_cluster_selection() -> None:
    sys.path.insert(0, str(REPO))
    from scripts.archipelago_cluster_selection import load_cluster_config, select_clusters_for_map
    import random

    cfg = load_cluster_config()
    defaults = cfg.get("defaults", {})
    rng = random.Random(42)
    locations = select_clusters_for_map(
        "_example_map",
        defaults.get("clusters_per_map", 3),
        defaults.get("slots_per_cluster", 2),
        rng,
    )
    assert locations
    for location in locations:
        assert "location_id" in location and "tier" in location



def test_cluster_editor_submodule() -> None:
    gitmodules = (REPO / ".gitmodules").read_text(encoding="utf-8")
    assert 'path = tools/cluster-editor' in gitmodules

    package_path = REPO / "tools/cluster-editor/package.json"
    testing_path = REPO / "tools/cluster-editor/TESTING.md"
    assert package_path.exists(), "Cluster editor submodule checkout is missing package.json"
    assert testing_path.exists(), "Cluster editor submodule checkout is missing TESTING.md"

    package = json.loads(package_path.read_text(encoding="utf-8"))
    scripts = package.get("scripts", {})
    assert "dev" in scripts and "build" in scripts


def test_wnd_workbench_files_exist() -> None:
    working_set_path = REPO / "Data/Archipelago/wnd_working_set.json"
    script_path = REPO / "scripts/wnd_workbench.py"
    wrapper_path = REPO / "scripts/windows_wnd_workbench.ps1"
    capture_path = REPO / "scripts/windows_ap_shell_review_capture.ps1"
    doc_path = REPO / "Docs/Archipelago/Operations/WND-UI-Workbench.md"
    fixture_path = REPO / "Data/Archipelago/UI/ap_shell_fixture.json"
    strings_path = REPO / "Data/Archipelago/UI/ap_shell_strings.json"
    required_controls_path = REPO / "Data/Archipelago/UI/ap_shell_required_controls.json"
    wnd_root = REPO / "Data/Archipelago/UI/Wnd"

    assert working_set_path.exists(), "WND working-set manifest is missing"
    assert script_path.exists(), "WND workbench script is missing"
    assert wrapper_path.exists(), "WND workbench PowerShell wrapper is missing"
    assert capture_path.exists(), "AP shell review capture script is missing"
    assert doc_path.exists(), "WND UI workbench doc is missing"
    assert fixture_path.exists(), "AP shell review fixture is missing"
    assert strings_path.exists(), "AP shell string overrides are missing"
    assert required_controls_path.exists(), "AP shell required-controls manifest is missing"
    assert wnd_root.exists(), "AP-owned WND root is missing"

    working_set = json.loads(working_set_path.read_text(encoding="utf-8"))
    files = working_set.get("files", [])
    paths = {entry.get("path") for entry in files}
    assert "Window/Menus/MainMenu.wnd" in paths
    assert "Window/Menus/NetworkDirectConnect.wnd" in paths

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert set(fixture.keys()) == {"deck", "connection", "mission_selector", "missions", "checks"}
    assert set(fixture["deck"].keys()) == {
        "hint",
        "completed_check_count",
        "pending_check_count",
        "player_slot_label",
    }
    assert {"current_id", "options"} == set(fixture["mission_selector"].keys())
    assert fixture["connection"]["state"] in {"disconnected", "connecting", "connected"}
    mission_states = {mission["status"] for mission in fixture["missions"]}
    cluster_states = {
        cluster["state"]
        for mission in fixture["missions"]
        for cluster in mission.get("clusters", [])
    }
    assert {"locked", "hold", "win", "completed"}.issubset(mission_states)
    assert {"green", "yellow", "red"} == cluster_states
    assert all("minimap_image" in mission for mission in fixture["missions"])
    assert all("emblem_image" in mission for mission in fixture["missions"])
    assert all("emblem_abbrev" in mission for mission in fixture["missions"])
    assert any(mission.get("selected") for mission in fixture["missions"])
    assert any(
        cluster.get("selected")
        for mission in fixture["missions"]
        for cluster in mission.get("clusters", [])
    )
    assert all("marker_x" in cluster and "marker_y" in cluster for mission in fixture["missions"] for cluster in mission.get("clusters", []))
    assert any(check["checked"] for check in fixture["checks"])
    assert any(not check["checked"] for check in fixture["checks"])

    wnd_names = {path.name for path in wnd_root.glob("*.wnd")}
    assert {
        "ArchipelagoHub.wnd",
        "APConnect.wnd",
        "APMissionIntel.wnd",
        "APCheckTracker.wnd",
    }.issubset(wnd_names)


def test_local_bridge_writes_slot_data_metadata() -> None:
    sys.path.insert(0, str(REPO))
    from scripts.archipelago_bridge_local import load_generalszh_slot_helpers, run_cycle

    with tempfile.TemporaryDirectory() as temp_dir:
        archipelago_dir = Path(temp_dir) / "Archipelago"
        session_path = archipelago_dir / "LocalBridgeSession.json"
        inbound_path = archipelago_dir / "Bridge-Inbound.json"
        outbound_path = archipelago_dir / "Bridge-Outbound.json"
        events_path = archipelago_dir / "Bridge-Events.jsonl"

        status = run_cycle(
            archipelago_dir,
            session_path,
            inbound_path,
            outbound_path,
            events_path,
            reset_session=True,
            emit_slot_data=True,
            unlock_preset="minimal",
        )

        slot_data_path = archipelago_dir / "Seed-Slot-Data.json"
        assert slot_data_path.exists()
        inbound = json.loads(inbound_path.read_text(encoding="utf-8"))
        slot_data = json.loads(slot_data_path.read_text(encoding="utf-8"))
        _, slot_data_sha256, _, validate_slot_data = load_generalszh_slot_helpers()
        validate_slot_data(slot_data)
        assert inbound["slotDataVersion"] == 2
        assert inbound["slotDataPath"] == "Seed-Slot-Data.json"
        assert inbound["slotDataHash"] == slot_data_sha256(slot_data)
        assert status["slot_reference"]["slotDataHash"] == inbound["slotDataHash"]


def test_local_bridge_translates_runtime_checks() -> None:
    sys.path.insert(0, str(REPO))
    from scripts.archipelago_bridge_local import atomic_write_json, run_cycle

    with tempfile.TemporaryDirectory() as temp_dir:
        archipelago_dir = Path(temp_dir) / "Archipelago"
        session_path = archipelago_dir / "LocalBridgeSession.json"
        inbound_path = archipelago_dir / "Bridge-Inbound.json"
        outbound_path = archipelago_dir / "Bridge-Outbound.json"
        events_path = archipelago_dir / "Bridge-Events.jsonl"

        run_cycle(
            archipelago_dir,
            session_path,
            inbound_path,
            outbound_path,
            events_path,
            reset_session=True,
            emit_slot_data=True,
            unlock_preset="default",
        )
        atomic_write_json(outbound_path, {"completedChecks": ["cluster.tank.c02.u01"]})
        status = run_cycle(
            archipelago_dir,
            session_path,
            inbound_path,
            outbound_path,
            events_path,
            emit_slot_data=True,
            unlock_preset="default",
        )
        assert 270040201 in status["session"]["completedLocations"]

        atomic_write_json(outbound_path, {"completedChecks": ["cluster.tank.c99.u99"]})
        try:
            run_cycle(
                archipelago_dir,
                session_path,
                inbound_path,
                outbound_path,
                events_path,
                emit_slot_data=True,
                unlock_preset="default",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Unknown runtime check was not rejected")



def main() -> int:
    tests = [
        test_json_configs,
        test_non_spawnable_denylist,
        test_name_override_files_exist,
        test_challenge_unit_protection_contains_required_entries,
        test_ingame_name_map_known_labels,
        test_template_name_map_known_templates,
        test_template_name_map_tracks_wrapper_sources,
        test_template_name_map_has_review_notes_for_unresolved_templates,
        test_balance_model_veterancy,
        test_base_defense_exclude_demo_traps,
        test_enemy_profiles_seven_generals,
        test_graph_script_output_schema,
        test_graph_names_use_localized_strings,
        test_graph_readable_output_includes_template_labels,
        test_chinook_hard_defender,
        test_excluded_units_not_defenders,
        test_no_demo_trap_in_defenders,
        test_base_defenses_medium_only,
        test_archipelago_vendor_metadata,
        test_archipelago_vendor_tree_exists,
        test_logic_prereqs,
        test_cluster_selection,
        test_cluster_editor_submodule,
        test_wnd_workbench_files_exist,
        test_local_bridge_writes_slot_data_metadata,
        test_local_bridge_translates_runtime_checks,
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
