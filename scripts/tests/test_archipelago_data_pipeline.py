#!/usr/bin/env python3
"""Sanity tests for Archipelago generation, config, graph, cluster, and logic."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
import importlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def get_powershell_executable() -> str | None:
    if platform.system() != "Windows":
        return None
    return shutil.which("powershell.exe") or shutil.which("pwsh") or shutil.which("powershell")



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
        ("Data/Archipelago/location_families/catalog.json", ["version", "status", "maps"]),
        ("Data/Archipelago/location_families/authoring_schema.json", ["version", "status", "families"]),
        ("Data/Archipelago/location_families/runtime_persistence_contract.json", ["version", "status", "shared", "families"]),
        ("Data/Archipelago/location_families/enable_criteria.json", ["version", "status", "requiredCriteria", "families"]),
        ("Data/Archipelago/location_families/capacity_targets.json", ["version", "status", "thresholdsPerSupplyPile", "maps"]),
        ("Data/Archipelago/location_families/fixtures/example_candidates.json", ["version", "status", "maps"]),
        ("Data/Archipelago/release_manifest_schema.json", ["$schema", "required", "properties"]),
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


def test_matchup_graph_generation_preserves_timestamp_when_unchanged() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        out_json = tmp_path / "graph.json"
        out_csv = tmp_path / "graph.csv"
        out_readable = tmp_path / "graph.txt"
        cmd = [
            sys.executable,
            str(REPO / "scripts/archipelago_generate_matchup_graph.py"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-readable",
            str(out_readable),
        ]
        subprocess.run(cmd, cwd=REPO, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first = json.loads(out_json.read_text(encoding="utf-8"))
        first["generated_at_utc"] = "2000-01-01T00:00:00+00:00"
        out_json.write_text(json.dumps(first, indent=2, sort_keys=False), encoding="utf-8")
        subprocess.run(cmd, cwd=REPO, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = json.loads(out_json.read_text(encoding="utf-8"))
        assert second["generated_at_utc"] == "2000-01-01T00:00:00+00:00"



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
    import hashlib

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
        _, _, _, validate_slot_data = load_generalszh_slot_helpers()
        validate_slot_data(slot_data)
        assert inbound["slotDataVersion"] == 2
        assert inbound["slotDataPath"] == "Seed-Slot-Data.json"
        assert inbound["slotDataHash"] == f"sha256:{hashlib.sha256(slot_data_path.read_bytes()).hexdigest()}"
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
        atomic_write_json(outbound_path, {"completedChecks": ["mission.tank.victory", "cluster.tank.c02.u01"]})
        status = run_cycle(
            archipelago_dir,
            session_path,
            inbound_path,
            outbound_path,
            events_path,
            emit_slot_data=True,
            unlock_preset="default",
        )
        assert 270000003 in status["session"]["completedLocations"]
        assert 270040201 in status["session"]["completedLocations"]

        status_duplicate = run_cycle(
            archipelago_dir,
            session_path,
            inbound_path,
            outbound_path,
            events_path,
            emit_slot_data=True,
            unlock_preset="default",
        )
        assert status_duplicate["changes"] == {}

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

        atomic_write_json(outbound_path, {"completedChecks": ["mission.tank.fake"]})
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
            raise AssertionError("Unknown mission runtime check was not rejected")


def test_local_bridge_minimal_preset_does_not_invent_hard_cluster_checks() -> None:
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
            unlock_preset="minimal",
        )

        atomic_write_json(outbound_path, {"completedChecks": ["cluster.tank.c02.u01"]})
        try:
            run_cycle(
                archipelago_dir,
                session_path,
                inbound_path,
                outbound_path,
                events_path,
                emit_slot_data=True,
                unlock_preset="minimal",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Minimal preset invented/accepted unselected hard cluster check")


def test_local_bridge_preserves_future_location_state_scaffold() -> None:
    sys.path.insert(0, str(REPO))
    from scripts.archipelago_bridge_local import atomic_write_json, run_cycle

    fixture_session = {
        "seedId": "future-state-seed",
        "slotName": "Local Test",
        "capturedBuildingState": [
            {
                "runtimeKey": "capture.tank.b001",
                "mapKey": "tank",
                "buildingKey": "b001",
                "apLocationId": 270091501,
                "completed": False,
            }
        ],
        "supplyPileState": [
            {
                "mapKey": "tank",
                "pileKey": "p02",
                "persistentCollectedAmount": 0,
                "completedThresholdKeys": [],
                "dry": False,
            }
        ],
    }

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
            fixture_session=fixture_session,
            reset_session=True,
            emit_slot_data=True,
            unlock_preset="minimal",
        )
        inbound = json.loads(inbound_path.read_text(encoding="utf-8"))
        assert inbound["capturedBuildingState"] == fixture_session["capturedBuildingState"]
        assert inbound["supplyPileState"] == fixture_session["supplyPileState"]
        assert status["session"]["completedLocations"] == []

        runtime_capture_state = [
            {
                "runtimeKey": "capture.tank.b001",
                "mapKey": "tank",
                "buildingKey": "b001",
                "apLocationId": 270091501,
                "completed": True,
                "firstCompletedSeedId": "future-state-seed",
                "firstCompletedSlotDataHash": "sha256:test",
                "firstCompletedSessionNonce": status["session"]["sessionNonce"],
            }
        ]
        runtime_supply_state = [
            {
                "mapKey": "tank",
                "pileKey": "p02",
                "startingAmount": 30000,
                "persistentCollectedAmount": 7500,
                "completedThresholdKeys": ["t01"],
                "dry": False,
                "lastSeenSeedId": "future-state-seed",
                "lastSeenSlotDataHash": "sha256:test",
            }
        ]
        atomic_write_json(
            outbound_path,
            {
                "capturedBuildingState": runtime_capture_state,
                "supplyPileState": runtime_supply_state,
            },
        )
        status = run_cycle(
            archipelago_dir,
            session_path,
            inbound_path,
            outbound_path,
            events_path,
            emit_slot_data=True,
            unlock_preset="minimal",
        )

        assert status["changes"]["capturedBuildingState"] == runtime_capture_state
        assert status["changes"]["supplyPileState"] == runtime_supply_state
        assert status["session"]["capturedBuildingState"] == runtime_capture_state
        assert status["session"]["supplyPileState"] == runtime_supply_state
        assert status["session"]["completedLocations"] == []

        refreshed_inbound = json.loads(inbound_path.read_text(encoding="utf-8"))
        assert refreshed_inbound["capturedBuildingState"] == runtime_capture_state
        assert refreshed_inbound["supplyPileState"] == runtime_supply_state


def test_seeded_bridge_loop_smoke_harness() -> None:
    sys.path.insert(0, str(REPO))
    from scripts.archipelago_seeded_bridge_loop_smoke import run_seeded_bridge_loop_smoke

    with tempfile.TemporaryDirectory() as temp_dir:
        summary = run_seeded_bridge_loop_smoke(Path(temp_dir) / "Archipelago")

    assert summary["runtime_checks"] == ["mission.tank.victory", "cluster.tank.c02.u01"]
    assert summary["translated_locations"] == [270000003, 270040201]
    assert set(summary["first_merge_changes"]) == {"completedChecks", "completedLocations"}
    assert summary["duplicate_merge_changes"] == {}


def test_runtime_fallback_contract_check() -> None:
    sys.path.insert(0, str(REPO))
    from scripts.archipelago_runtime_fallback_contract_check import run_runtime_fallback_contract_check

    summary = run_runtime_fallback_contract_check()
    assert summary["no_slot_data_reference"]["inbound_has_slot_data_fields"] is False
    assert summary["no_slot_data_reference"]["slot_data_file_emitted"] is False
    assert summary["bad_hash_reference"]["slotDataHash"].startswith("sha256:")
    assert summary["selected_seeded_mode"]["unselected_runtime_key_rejected"] is True
    assert len(summary["source_contract_checks"]) >= 10


def assert_ordered(source: str, *needles: str) -> None:
    cursor = 0
    for needle in needles:
        index = source.find(needle, cursor)
        assert index >= 0, f"Missing ordered source fragment: {needle}"
        cursor = index + len(needle)


def source_slice(source: str, start: str, end: str) -> str:
    start_index = source.find(start)
    assert start_index >= 0, f"Missing source slice start: {start}"
    end_index = source.find(end, start_index)
    assert end_index >= 0, f"Missing source slice end: {end}"
    return source[start_index:end_index]


def test_runtime_natural_completion_callbacks_use_selected_runtime_keys() -> None:
    score_screen = (REPO / "GeneralsMD/Code/GameEngine/Source/GameClient/GUI/GUICallbacks/Menus/ScoreScreen.cpp").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    object_source = (REPO / "GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Object.cpp").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    state_source = (REPO / "GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    spawner_source = (REPO / "GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp").read_text(
        encoding="utf-8",
        errors="ignore",
    )

    victory_block = source_slice(
        score_screen,
        "if (isChallengeCampaign && TheCampaignManager && TheCampaignManager->isVictorious()",
        "// Make Sure the layout is visible",
    )
    assert_ordered(
        victory_block,
        "TheCampaignManager->isVictorious()",
        "hasVerifiedSlotData()",
        "getMissionRuntimeKeyForGeneralIndex( generalIndex )",
        'markRuntimeCheckComplete( missionRuntimeKey, AsciiString( "mission-victory" ) )',
        "hasSlotDataReference()",
        "Mission victory ignored because slot-data reference is present but not verified",
        "markLocationComplete(locationId)",
    )

    kill_header = source_slice(
        object_source,
        "void Object::scoreTheKill( const Object *victim )",
        "Relationship r = getRelationship(victim);",
    )
    assert_ordered(
        kill_header,
        "isSpawnedUnit( victim )",
        "if ( isSpawnedArchipelagoUnit )",
        'grantCheckForKill( victim->getArchipelagoCheckId(), victim->getTemplate()->getName(), TRUE )',
        "onArchipelagoCheckKilled( victim, isNewCheck )",
        "if (victimController && victimController->isPlayableSide() == FALSE)",
        "return;",
    )
    non_spawned_kill_block = source_slice(
        object_source,
        "// Archipelago kill check: when local player destroys a unit with ArchipelagoCheckId, grant the check",
        "// Now handle experience, if we can gain any",
    )
    assert_ordered(
        non_spawned_kill_block,
        "!isSpawnedArchipelagoUnit",
        'grantCheckForKill( victim->getArchipelagoCheckId(), victim->getTemplate()->getName(), FALSE )',
        "onArchipelagoCheckKilled( victim, isNewCheck )",
    )

    assert 'isSpawnedUnitKill ? AsciiString( "spawned-kill" ) : AsciiString( "kill" )' in state_source
    assert "markRuntimeCheckComplete( const AsciiString& checkId, const AsciiString& sourceTag )" in state_source
    assert "m_slotData.isSelectedRuntimeKey( checkId )" in state_source

    slot_config_block = source_slice(
        spawner_source,
        "Bool UnlockableCheckSpawner::buildSlotDataConfigForMap",
        "void UnlockableCheckSpawner::resetProtectionRegistry",
    )
    assert_ordered(
        slot_config_block,
        "const ArchipelagoSlotUnit& unit = cluster.units[unitIndex];",
        "outConfig.unitTemplates.push_back( unit.defenderTemplate );",
        "outConfig.unitCheckIds.push_back( unit.runtimeKey );",
        "outConfig.unitClusterIds.push_back( cluster.clusterKey );",
    )
    spawn_assignment_block = source_slice(
        spawner_source,
        "for ( size_t plannedIndex = 0; plannedIndex < clusterPlan.size(); ++plannedIndex )",
        "TheAI->pathfinder()->addObjectToPathfindMap( obj );",
    )
    assert_ordered(
        spawn_assignment_block,
        "Object* obj = planned.object;",
        "obj->setArchipelagoCheckId( planned.checkId );",
        "m_spawnedUnits.push_back( obj );",
    )
    assert "Built seeded slot-data spawn config" in spawner_source


def test_extract_ini_config_requires_force_for_tracked_output() -> None:
    script = REPO / "scripts/archipelago_extract_ini_config.py"
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert completed.returncode != 0
    assert "--force" in completed.stdout
    assert "tracked Data/Archipelago" in completed.stdout


def test_runtime_slot_data_future_family_parse_only() -> None:
    header = (REPO / "GeneralsMD/Code/GameEngine/Include/GameLogic/ArchipelagoSlotData.h").read_text(encoding="utf-8")
    source = (REPO / "GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoSlotData.cpp").read_text(encoding="utf-8")
    spawner = (REPO / "GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp").read_text(encoding="utf-8")

    assert "struct ArchipelagoSlotCapturedBuilding" in header
    assert "struct ArchipelagoSlotSupplyPileThreshold" in header
    assert "std::vector<ArchipelagoSlotCapturedBuilding> capturedBuildings" in header
    assert "std::vector<ArchipelagoSlotSupplyPileThreshold> supplyPileThresholds" in header
    assert "Int getFutureLocationCount() const;" in header
    assert 'mapObj.get( "capturedBuildings" )' in source
    assert 'mapObj.get( "supplyPileThresholds" )' in source
    assert "m_runtimeKeys.insert( captured.runtimeKey )" in source
    assert "m_runtimeKeys.insert( threshold.runtimeKey )" in source
    assert "getFutureLocationCount" in source
    assert "capturedBuildings" not in spawner
    assert "supplyPileThresholds" not in spawner


def test_runtime_future_location_state_scaffold() -> None:
    contract = load_json("Data/Archipelago/location_families/runtime_persistence_contract.json")
    header = (REPO / "GeneralsMD/Code/GameEngine/Include/GameLogic/ArchipelagoState.h").read_text(encoding="utf-8")
    source = (REPO / "GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp").read_text(encoding="utf-8")

    assert contract["families"]["capturedBuildings"]["runtimeStateCollection"] == "capturedBuildingState"
    assert contract["families"]["supplyPiles"]["runtimeStateCollection"] == "supplyPileState"
    assert "std::string m_capturedBuildingStateJson" in header
    assert "std::string m_supplyPileStateJson" in header
    assert "parseRawArrayField" in source
    assert 'parseRawArrayField(content, "\\"capturedBuildingState\\"")' in source
    assert 'parseRawArrayField(content, "\\"supplyPileState\\"")' in source
    assert "writeFutureLocationStateArrays(file, m_capturedBuildingStateJson, m_supplyPileStateJson, TRUE)" in source
    assert 'file << "  \\"version\\": 4,\\n";' in source
    assert 'file << "  \\"stateVersion\\": 4,\\n";' in source
    assert "markCapturedBuilding" not in source
    assert "markSupplyPile" not in source
    assert "completeSupplyPile" not in source


def test_item_location_capacity_report() -> None:
    sys.path.insert(0, str(REPO))
    from scripts.archipelago_item_location_capacity_report import build_capacity_report, format_markdown

    report = build_capacity_report(target_item_counts=[15, 100, 300], buffer_percent=25, min_spare_locations=25)
    assert report["summary"]["scope"] == "accounting_only_no_new_locations_enabled"
    assert report["presets"]["minimal"]["enabled_locations"] == 35
    assert report["presets"]["minimal"]["extra_supply_cache_copies"] == 20
    assert report["presets"]["minimal"]["selected_future_locations"] == 0
    assert report["presets"]["default"]["enabled_locations"] == 51
    assert report["presets"]["default"]["extra_supply_cache_copies"] == 36
    assert report["presets"]["default"]["selected_future_locations"] == 0
    assert report["future_location_capacity"]["authored_catalog_counts"]["total"] == 0
    assert report["future_location_capacity"]["total_disabled_future_id_lanes"] == 7520
    assert report["future_location_capacity"]["production_guard_active"] is True
    assert report["planned_item_pool"]["status"] == "planning_only_not_active_generation"
    assert report["planned_item_pool"]["modes"]["target"]["planned_total_items"] == 109
    assert report["planned_item_pool"]["modes"]["target"]["required_locations_with_buffer"] == 137
    assert report["planned_item_pool"]["modes"]["target"]["default_shortfall"] == 86
    assert report["planned_item_pool"]["modes"]["max"]["planned_copy_counts"]["Progressive Production"] == 12
    assert report["planned_location_targets"]["status"] == "planning_only_not_active_generation"
    assert report["planned_location_targets"]["counts"]["min"]["total_future_checks"] == 28
    assert report["planned_location_targets"]["counts"]["target"]["total_future_checks"] == 107
    assert report["planned_location_targets"]["counts"]["target"]["captured_buildings"] == 15
    assert report["planned_location_targets"]["counts"]["target"]["supply_thresholds"] == 92
    assert report["planned_location_targets"]["projected_modes"]["target"]["projected_default_locations"] == 158
    assert report["planned_location_targets"]["projected_modes"]["target"]["projected_default_shortfall"] == 0
    assert report["planned_location_targets"]["projected_modes"]["max"]["projected_default_locations"] == 345
    assert report["target_scenarios"]["300"]["required_locations_with_buffer"] == 375
    assert report["target_scenarios"]["300"]["default_shortfall"] == 324

    markdown = format_markdown(report)
    assert "Planned item-copy pressure" in markdown
    assert "Planned location-family targets" in markdown
    assert "Planned target item pool is 109 items" in markdown
    assert "Planned target location families add 107 inactive future checks" in markdown
    assert "Current active presets can absorb some new items" in markdown
    assert "runtime completion/persistence must land" in markdown


def test_human_demo_director_contract() -> None:
    fixture = load_json("Data/Archipelago/bridge_fixtures/human_demo_tank.json")
    assert fixture["seedId"] == "demo-human-tank"
    assert fixture["slotName"] == "Human Demo Tank"
    assert fixture["startingGenerals"] == [2]
    assert fixture["unlockedGenerals"] == [2]
    received_groups = [item["groupId"] for item in fixture["receivedItems"]]
    assert received_groups == [
        "Shared_RocketInfantry",
        "Upgrade_Vehicles",
        "Shared_WarFactoriesArmsDealers",
        "Shared_Tanks",
        "Shared_MachineGunVehicles",
        "Shared_Artillery",
        "Shared_AirFields",
        "Shared_Superweapons",
    ]
    assert fixture["sessionOptions"]["startingCashBonus"] == 100000
    assert fixture["sessionOptions"]["productionMultiplier"] == 3.0
    assert fixture["sessionOptions"]["disableZoomLimit"] is True

    demo_director = (REPO / "scripts/run_generalsap_demo_director.ps1").read_text(encoding="utf-8")
    clean_runtime_smoke_script = (REPO / "scripts/smoke_generalsap_clean_runtime.ps1").read_text(encoding="utf-8")
    assert "human_demo_tank" in demo_director
    assert "Demo-Proof.json" in demo_director
    assert "GENERALSAP_DEMO_PROOF_OK" in demo_director
    assert "Maps\\GC_TankGeneral.map" in demo_director
    assert "cluster.tank.c02.u01" in demo_director
    assert "mission.tank.victory" in demo_director
    assert "WaitForSpawnedRuntimeKey" in demo_director
    assert "SmokeCompleteRuntimeKey" in demo_director
    assert "--clean-runtime-smoke" in demo_director
    assert "LocalBridgeFixture" in clean_runtime_smoke_script
    assert "live AP slot data must come from the AP server" in clean_runtime_smoke_script


def test_release_manifest_and_packaging_contract() -> None:
    schema = load_json("Data/Archipelago/release_manifest_schema.json")
    properties = schema["properties"]
    assert properties["requiresExternalBasePatcher"]["const"] is False
    assert properties["retailAssetsIncluded"]["const"] is False
    assert properties["requiredBaseGame"]["const"] == "Command & Conquer Generals Zero Hour 1.04-compatible healthy install"
    assert properties["slotDataVersion"]["const"] == 2
    assert properties["logicModel"]["const"] == "generalszh-alpha-grouped-v1"
    assert "bridgeKind" in schema["required"]
    assert properties["bridgeKind"]["enum"] == ["none", "staging_stub", "file_bridge", "real"]
    assert "payload" in schema["required"]
    assert ".big" in properties["payload"]["properties"]["forbiddenRetailExtensions"]["contains"]["const"]

    package_script = (REPO / "scripts/package_generalsap_alpha.ps1").read_text(encoding="utf-8")
    bridge_stub_script = (REPO / "scripts/build_generalsap_bridge_stub.ps1").read_text(encoding="utf-8")
    bridge_build_script = (REPO / "scripts/build_generalsap_bridge.ps1").read_text(encoding="utf-8")
    bridge_program = (REPO / "tools/bridge/GeneralsAPBridge/Program.cs").read_text(encoding="utf-8")
    bridge_smoke_script = (REPO / "scripts/archipelago_bridge_executable_smoke.py").read_text(encoding="utf-8")
    bridge_network_smoke_script = (REPO / "scripts/archipelago_bridge_network_smoke.py").read_text(encoding="utf-8")
    real_ap_server_smoke_script = (REPO / "scripts/archipelago_bridge_real_ap_server_smoke.py").read_text(encoding="utf-8")
    package_smoke_script = (REPO / "scripts/smoke_generalsap_alpha_package.ps1").read_text(encoding="utf-8")
    package_validator_script = (REPO / "scripts/validate_generalsap_alpha_package.ps1").read_text(encoding="utf-8")
    clean_runtime_smoke_script = (REPO / "scripts/smoke_generalsap_clean_runtime.ps1").read_text(encoding="utf-8")
    nonhuman_release_script = (REPO / "scripts/run_generalsap_nonhuman_release_checks.ps1").read_text(encoding="utf-8")
    assert "requiresExternalBasePatcher = $false" in package_script
    assert "retailAssetsIncluded = $false" in package_script
    assert "bridgeKind = $manifestBridgeKind" in package_script
    assert "Assert-NoRetailArchives" in package_script
    assert "Copy-ApWorldOverlayFiltered" in package_script
    assert "Test-IsTransientApWorldFile" in package_script
    assert "__pycache__" in package_script
    assert "BridgePath requires explicit non-staging bridge kind" in package_script
    assert "validate_generalsap_alpha_package.ps1" in package_script
    assert '"generalszh.exe"' in package_script
    assert '"zlib1.dll"' in package_script
    assert '"Data\\INI\\Archipelago.ini"' in package_script
    assert '"*.big"' not in package_script
    assert "release_manifest_schema.json" in package_validator_script
    assert "Assert-ManifestSchemaIfAvailable" in package_validator_script
    assert "Expand-Archive" in package_validator_script
    assert "PACKAGE_ZIP_VALIDATION_OK" in package_validator_script
    assert "payload/Game contains an unclaimed file" in package_validator_script
    assert "Assert-NoTransientApWorldPayload" in package_validator_script
    assert "Package contains transient APWorld artifacts" in package_validator_script
    assert "content_framework.py" in package_validator_script
    assert "location_catalog.py" in package_validator_script
    assert "testing_catalog.py" in package_validator_script
    assert "bundles a bridge executable but bridgeKind is staging_stub" in package_validator_script
    assert "staging stub only" in bridge_stub_script
    assert "dotnet publish" in bridge_build_script
    assert "UnsafeRelaxedJsonEscaping" in bridge_program
    assert "unknown runtime check key" in bridge_smoke_script
    assert "unknown AP location id" in bridge_smoke_script
    assert "duplicate bridge cycle changed LocalBridgeSession.json" in bridge_smoke_script
    assert "GetDataPackage" in bridge_network_smoke_script
    assert "LocationChecks" in bridge_network_smoke_script
    assert "ReceivedItems" in bridge_network_smoke_script
    assert "Air Force General Medal" in bridge_network_smoke_script
    assert "Progressive Production" in bridge_network_smoke_script
    assert "one-time cash runtime support" in bridge_network_smoke_script
    assert "mission.boss.victory" in bridge_network_smoke_script
    assert "StatusUpdate" in bridge_network_smoke_script
    assert "include_boss_event_marker" in bridge_network_smoke_script
    assert "Boss event marker was incorrectly submitted as a LocationChecks ID" in bridge_network_smoke_script
    assert "network bridge did not submit selected future-family AP IDs" in bridge_network_smoke_script
    assert "capture.tank.b001" in bridge_network_smoke_script
    assert "supply.tank.p02.t02" in bridge_network_smoke_script
    assert "capture.tank.b001" in bridge_smoke_script
    assert "supply.tank.p02.t02" in bridge_smoke_script
    assert "bridge did not translate selected future-family checks" in bridge_smoke_script
    assert "completedLocations outbound did not persist expected ID" in bridge_smoke_script
    assert "future_state_scaffold_preserved" in bridge_smoke_script
    assert "MultiServer.py" in real_ap_server_smoke_script
    assert "fresh reconnect" in real_ap_server_smoke_script
    assert "duplicate completions" in real_ap_server_smoke_script
    assert "exclusive_directory_lock" in real_ap_server_smoke_script
    assert "ap-smoke-cache.lock" in real_ap_server_smoke_script
    assert "start_ap_server_on_free_port" in real_ap_server_smoke_script
    assert "server startup failed on port" in real_ap_server_smoke_script
    assert "--clean-runtime-smoke" in real_ap_server_smoke_script
    assert "--full-world-simulation" in real_ap_server_smoke_script
    assert "full-world simulation did not receive all seven shuffled medals" in real_ap_server_smoke_script
    assert "Boss General Medal must not exist" in real_ap_server_smoke_script
    assert "Victory should remain locked to Boss mission event" in real_ap_server_smoke_script
    assert "submitting full main-world simulated runtime completions" in real_ap_server_smoke_script
    assert "submitting Boss-cluster simulated runtime completions after medals" in real_ap_server_smoke_script
    assert "submitting Boss victory simulated runtime completion as AP goal status" in real_ap_server_smoke_script
    assert "smoke_generalsap_clean_runtime.ps1" in real_ap_server_smoke_script
    assert "clean runtime fresh reconnect" in real_ap_server_smoke_script
    assert "bridgeKind -ne \"file_bridge\"" in package_smoke_script
    assert "GeneralsAP-0.1.0-alpha.zip" in package_smoke_script
    assert "archipelago_bridge_executable_smoke.py" in package_smoke_script
    assert "BaseRuntimeDir is required" in clean_runtime_smoke_script
    assert "Generals.exe" in clean_runtime_smoke_script
    assert "SmokeMapFile" in clean_runtime_smoke_script
    assert "WaitForSpawnedRuntimeKey" in clean_runtime_smoke_script
    assert "Runtime-Smoke-DumpSpawned.flag" in clean_runtime_smoke_script
    assert "ArchipelagoSpawnedUnitState.json" in clean_runtime_smoke_script
    assert "spawnedStateAlreadySatisfied" in clean_runtime_smoke_script
    assert "RequireLaunchExe" in clean_runtime_smoke_script
    assert "AllowEmptyCollection" in clean_runtime_smoke_script
    assert "Bridge-Outbound.json" in clean_runtime_smoke_script
    assert "WaitForRuntimeKey" in clean_runtime_smoke_script
    assert "SmokeCompleteRuntimeKey" in clean_runtime_smoke_script
    assert "BridgeConnect" in clean_runtime_smoke_script
    assert "BridgeSession.json" in clean_runtime_smoke_script
    assert "bridgeMode" in clean_runtime_smoke_script
    assert "localBridgeFixture" in clean_runtime_smoke_script
    assert "Normalize-RuntimeKeyArgs" in clean_runtime_smoke_script
    assert "Enable-Runtime-Smoke.flag" in clean_runtime_smoke_script
    assert "Runtime-Smoke-Complete.json" in clean_runtime_smoke_script
    assert "Get-RuntimeKeyLocationIdMap" in clean_runtime_smoke_script
    assert "translate runtime keys to AP numeric location IDs" in clean_runtime_smoke_script
    assert "Assert-GameProcessStillRunning" in clean_runtime_smoke_script
    assert "after runtime completion proof" in clean_runtime_smoke_script
    assert "WaitForExit(10000)" in clean_runtime_smoke_script
    assert "UseFixtureRuntime" in clean_runtime_smoke_script
    assert "bridgeKind=real" in clean_runtime_smoke_script
    runtime_state_source = (REPO / "GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp").read_text(encoding="utf-8", errors="ignore")
    runtime_state_header = (REPO / "GeneralsMD/Code/GameEngine/Include/GameLogic/ArchipelagoState.h").read_text(encoding="utf-8", errors="ignore")
    assert "processRuntimeSmokeCompletionFile" in runtime_state_header
    assert "processRuntimeSmokeCompletionFile" in runtime_state_source
    assert "Enable-Runtime-Smoke.flag" in runtime_state_source
    assert "Runtime-Smoke-Complete.json" in runtime_state_source
    assert "Runtime-Smoke-DumpSpawned.flag" in runtime_state_source
    assert "TheUnlockableCheckSpawner->dumpDebugState()" in runtime_state_source
    assert "decodeJsonStringLiteral" in runtime_state_source
    assert "markRuntimeCheckComplete( *it, AsciiString( \"runtime-smoke\" ) )" in runtime_state_source
    spawner_source = (REPO / "GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp").read_text(encoding="utf-8", errors="ignore")
    assert "hasRuntimeSmokeSpawnedDumpRequest" in spawner_source
    assert "Runtime smoke spawned-unit dump requested after map load" in spawner_source
    assert "Archipelago data/world suite" in nonhuman_release_script
    assert "PR scope audit" in nonhuman_release_script
    assert "ScopeAuditBase" in nonhuman_release_script
    assert "SkipScopeAudit" in nonhuman_release_script
    assert "archipelago_pr_scope_audit.py" in nonhuman_release_script
    assert "Packaged bridge real local AP server smoke" in nonhuman_release_script
    assert "Full AP world simulated completion smoke" in nonhuman_release_script
    assert "--full-world-simulation" in nonhuman_release_script
    assert "Clean-runtime fixture harness smoke" in nonhuman_release_script
    assert "GENERALSAP_BASE_RUNTIME_DIR" in nonhuman_release_script
    assert "[int]$RuntimeStartupWaitSeconds = 20" in nonhuman_release_script
    assert "[int]$RuntimeSmokeTimeoutSeconds = 180" in nonhuman_release_script
    assert "Build prepared game runtime" in nonhuman_release_script
    assert "Clean-runtime legal runtime auto-completion smoke" in nonhuman_release_script
    assert "RunIntegratedRealApRuntimeSmoke" in nonhuman_release_script
    assert "Integrated real AP clean-runtime network smoke" in nonhuman_release_script
    assert "RunSpawnedMaterializationSmoke" in nonhuman_release_script
    assert "Clean-runtime spawned materialization smoke" in nonhuman_release_script
    assert "Logic Foundry export handoff smoke" in nonhuman_release_script
    assert "tools\\logic-foundry" in nonhuman_release_script
    assert "logic-foundry-export-smoke.json" in nonhuman_release_script
    assert "Maps\\GC_TankGeneral.map" in nonhuman_release_script
    assert "do not pass Maps\\GC_TankGeneral\\GC_TankGeneral.map" in clean_runtime_smoke_script
    assert "mission.tank.victory,cluster.tank.c02.u01" in nonhuman_release_script
    assert "nonhuman-release-checks.json" in nonhuman_release_script
    assert "LocalBridgeFixture" in clean_runtime_smoke_script

    command_line_source = (REPO / "GeneralsMD/Code/GameEngine/Source/Common/CommandLine.cpp").read_text(encoding="utf-8", errors="ignore")
    assert "#if defined(RTS_DEBUG) || defined(_ALLOW_DEBUG_CHEATS_IN_RELEASE)" in command_line_source
    assert '{ "-file", parseFile }' in command_line_source

    workflow = (REPO / ".github/workflows/validate-archipelago-data.yml").read_text(encoding="utf-8")
    build_toolchain_workflow = (REPO / ".github/workflows/build-toolchain.yml").read_text(encoding="utf-8")
    assert "codex/ap-world-skeleton-checkpoint" in workflow
    assert "Validate AP Framework Contracts" in workflow
    assert "test_archipelago_data_pipeline.py" in workflow
    assert "test_archipelago_world_contract.py" in workflow
    assert "smoke_generalsap_alpha_package.ps1" in workflow
    assert "Check generated outputs are committed" in workflow
    assert "archipelago_bridge_executable_smoke.py" in workflow
    assert "archipelago_bridge_network_smoke.py" in workflow
    assert "archipelago_bridge_real_ap_server_smoke.py" in workflow
    assert "Run bridge full AP world simulation smoke" in workflow
    assert "Set up Node" in workflow
    assert "Run Logic Foundry export handoff smoke" in workflow
    assert "npm --prefix tools\\logic-foundry ci" in workflow
    assert "logicFoundryExportSmokeOutcome" in workflow
    assert "logic-foundry-export-smoke.json" in workflow
    assert "--full-world-simulation --keep-temp" in workflow
    assert "bridgeFullWorldSmokeOutcome" in workflow
    assert "--keep-temp" in workflow
    assert "Stage AP framework smoke artifacts" in workflow
    assert "Upload AP framework smoke artifacts" in workflow
    assert "ci-package-smoke" in workflow
    assert "ci-framework-smoke-artifacts" in workflow
    assert "[System.IO.Path]::GetTempPath()" in workflow
    assert "$requireCompleteArtifacts = ($strict -eq 0)" in workflow
    assert "if ($requireCompleteArtifacts)" in workflow
    assert "throw \"Missing retained smoke temp directory matching $prefix under $tempRoot\"" in workflow
    assert "throw \"Retained smoke temp directory $prefix was not staged into $stage\"" in workflow
    assert "path: build\\archipelago\\ci-framework-smoke-artifacts" in workflow
    assert "generalsap-bridge-exe-*" in workflow
    assert "generalsap-bridge-network-*" in workflow
    assert "generalsap-real-ap-server-*" in workflow
    assert "${{ runner.temp }}\\generalsap-" not in workflow
    assert "if-no-files-found: error" in workflow
    assert "-NoSeededBridgeLoop" not in workflow
    assert "pull-requests: write" not in workflow
    assert "pull-requests: write" not in build_toolchain_workflow
    assert "Test-Path -LiteralPath" in build_toolchain_workflow
    assert "No artifact files found under existing directories" in build_toolchain_workflow
    assert "Compile GeneralsMD Runtime Smoke" in workflow
    assert "win32-vcpkg-playtest" in workflow

    release_doc = (REPO / "Docs/Archipelago/Operations/Player-Release-Architecture.md").read_text(encoding="utf-8")
    testing_doc = (REPO / "TESTING.md").read_text(encoding="utf-8")
    assert "archipelago_bridge_network_smoke.py" in release_doc
    assert "archipelago_bridge_network_smoke.py" in testing_doc
    assert "archipelago_bridge_real_ap_server_smoke.py" in release_doc
    assert "archipelago_bridge_real_ap_server_smoke.py" in testing_doc
    assert "smoke_generalsap_clean_runtime.ps1" in release_doc
    assert "smoke_generalsap_clean_runtime.ps1" in testing_doc
    assert "run_generalsap_nonhuman_release_checks.ps1" in release_doc
    assert "run_generalsap_nonhuman_release_checks.ps1" in testing_doc
    assert "run_generalsap_demo_director.ps1" in testing_doc
    assert "human_demo_tank" in testing_doc
    forbidden_name = "Gen" + "Patcher"
    forbidden_lower = forbidden_name.lower()
    for text in (release_doc, testing_doc, package_script):
        assert forbidden_name not in text
        assert forbidden_lower not in text.lower()


ALPHA_PACKAGE_GAME_FILES = [
    "generalszh.exe",
    "zlib1.dll",
    "Run-GeneralsAP.cmd",
    "Data/INI/Archipelago.ini",
    "Data/INI/ArchipelagoChallengeUnitProtection.ini",
    "Data/INI/UnlockableChecksDemo.ini",
]

ALPHA_PACKAGE_APWORLD_FILES = [
    "archipelago.json",
    "__init__.py",
    "constants.py",
    "content_framework.py",
    "world.py",
    "items.py",
    "locations.py",
    "location_catalog.py",
    "options.py",
    "regions.py",
    "rules.py",
    "testing_catalog.py",
    "slot_data.py",
]


def _write_alpha_package_fixture(
    package_root: Path,
    *,
    bridge_bundled: bool = True,
    claimed_game_files: list[str] | None = None,
) -> None:
    game_root = package_root / "payload" / "Game"
    bridge_root = package_root / "payload" / "Bridge"
    apworld_root = package_root / "payload" / "APWorld" / "generalszh"
    docs_root = package_root / "payload" / "Docs"
    for path in (game_root, bridge_root, apworld_root, docs_root):
        path.mkdir(parents=True, exist_ok=True)

    for relative_path in ALPHA_PACKAGE_GAME_FILES:
        path = game_root / Path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="ascii")

    if bridge_bundled:
        (bridge_root / "GeneralsAPBridge.exe").write_text("fixture bridge\n", encoding="ascii")
        bridge_kind = "file_bridge"
        bridge_path = "payload/Bridge/GeneralsAPBridge.exe"
    else:
        (bridge_root / "README-BRIDGE-NOT-BUNDLED.txt").write_text("fixture no bridge\n", encoding="ascii")
        bridge_kind = "none"
        bridge_path = None

    for relative_path in ALPHA_PACKAGE_APWORLD_FILES:
        (apworld_root / relative_path).write_text("fixture\n", encoding="ascii")
    (package_root / "README-PACKAGE.txt").write_text("fixture package\n", encoding="ascii")
    manifest_game_files = claimed_game_files if claimed_game_files is not None else ALPHA_PACKAGE_GAME_FILES

    manifest = {
        "packageVersion": "0.1.0-alpha",
        "releaseChannel": "alpha",
        "generalsApCommit": "fixture",
        "superHackersRef": "fixture",
        "archipelagoVersion": "0.6.7",
        "apworldName": "generalszh.apworld",
        "apworldVersion": "0.1.0",
        "bridgeVersion": 1,
        "bridgeBundled": bridge_bundled,
        "bridgeKind": bridge_kind,
        "slotDataVersion": 2,
        "logicModel": "generalszh-alpha-grouped-v1",
        "requiresExternalBasePatcher": False,
        "requiredBaseGame": "Command & Conquer Generals Zero Hour 1.04-compatible healthy install",
        "retailAssetsIncluded": False,
        "userDataDirRequired": True,
        "launchArgs": ["-win", "-userDataDir", ".\\UserData\\"],
        "payload": {
            "gameOverlayFiles": sorted(manifest_game_files),
            "forbiddenRetailExtensions": [".big"],
            "bridgePath": bridge_path,
            "apworldPayload": "folder",
        },
    }
    (package_root / "GeneralsAP-Release-Manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_alpha_package_validator(
    *,
    package_root: Path | None = None,
    zip_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    powershell = get_powershell_executable()
    assert powershell is not None, "PowerShell is required for package validator tests"
    validator = REPO / "scripts/validate_generalsap_alpha_package.ps1"
    args = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(validator),
    ]
    if package_root is not None:
        args.extend(["-PackageRoot", str(package_root)])
    else:
        assert zip_path is not None
        args.extend(["-ZipPath", str(zip_path)])

    return subprocess.run(
        args,
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )


def _write_package_zip(package_root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w") as archive:
        for path in package_root.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(package_root).as_posix())


def test_alpha_package_validator_fixture_root_and_zip() -> None:
    if get_powershell_executable() is None:
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        package_root = tmp_path / "GeneralsAP-0.1.0-alpha"
        _write_alpha_package_fixture(package_root)

        root_completed = _run_alpha_package_validator(package_root=package_root)
        assert root_completed.returncode == 0, root_completed.stdout
        assert "PACKAGE_VALIDATION_OK" in root_completed.stdout

        zip_path = tmp_path / "GeneralsAP-0.1.0-alpha.zip"
        _write_package_zip(package_root, zip_path)

        zip_completed = _run_alpha_package_validator(zip_path=zip_path)
        assert zip_completed.returncode == 0, zip_completed.stdout
        assert "PACKAGE_ZIP_VALIDATION_OK" in zip_completed.stdout

        (package_root / "payload" / "Game" / "retail.big").write_text("forbidden\n", encoding="ascii")
        forbidden_completed = _run_alpha_package_validator(package_root=package_root)
        assert forbidden_completed.returncode != 0
        assert "forbidden retail payload" in forbidden_completed.stdout


def test_alpha_package_validator_rejects_unsafe_zip_path_traversal() -> None:
    if get_powershell_executable() is None:
        return

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "GeneralsAP-0.1.0-alpha.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("../escape.txt", "unsafe\n")

        completed = _run_alpha_package_validator(zip_path=zip_path)
        assert completed.returncode != 0
        assert "unsafe entry path" in completed.stdout


def test_alpha_package_validator_rejects_zip_sibling_outside_package_root() -> None:
    if get_powershell_executable() is None:
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        package_root = tmp_path / "GeneralsAP-0.1.0-alpha"
        _write_alpha_package_fixture(package_root)

        zip_path = tmp_path / "GeneralsAP-0.1.0-alpha.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            for path in package_root.rglob("*"):
                if path.is_file():
                    archive_name = Path(package_root.name) / path.relative_to(package_root)
                    archive.write(path, archive_name.as_posix())
            archive.writestr("sibling.txt", "unexpected\n")

        completed = _run_alpha_package_validator(zip_path=zip_path)
        assert completed.returncode != 0
        assert "entries outside selected package root" in completed.stdout
        assert "sibling.txt" in completed.stdout


def test_alpha_package_validator_rejects_unclaimed_game_file() -> None:
    if get_powershell_executable() is None:
        return

    with tempfile.TemporaryDirectory() as tmp:
        package_root = Path(tmp) / "GeneralsAP-0.1.0-alpha"
        _write_alpha_package_fixture(package_root)
        unclaimed_path = package_root / "payload" / "Game" / "Data" / "INI" / "Unclaimed.ini"
        unclaimed_path.write_text("unclaimed\n", encoding="ascii")

        completed = _run_alpha_package_validator(package_root=package_root)
        assert completed.returncode != 0
        assert "payload/Game contains an unclaimed file: Data/INI/Unclaimed.ini" in completed.stdout


def test_alpha_package_validator_rejects_missing_claimed_game_file() -> None:
    if get_powershell_executable() is None:
        return

    with tempfile.TemporaryDirectory() as tmp:
        package_root = Path(tmp) / "GeneralsAP-0.1.0-alpha"
        missing_claim = "Data/INI/MissingClaimed.ini"
        _write_alpha_package_fixture(package_root, claimed_game_files=ALPHA_PACKAGE_GAME_FILES + [missing_claim])

        completed = _run_alpha_package_validator(package_root=package_root)
        assert completed.returncode != 0
        assert f"Package missing expected file: {missing_claim}" in completed.stdout


def test_alpha_package_validator_accepts_no_bridge_package() -> None:
    if get_powershell_executable() is None:
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        package_root = tmp_path / "GeneralsAP-0.1.0-alpha"
        _write_alpha_package_fixture(package_root, bridge_bundled=False)

        root_completed = _run_alpha_package_validator(package_root=package_root)
        assert root_completed.returncode == 0, root_completed.stdout
        assert "PACKAGE_VALIDATION_OK" in root_completed.stdout

        zip_path = tmp_path / "GeneralsAP-0.1.0-alpha.zip"
        _write_package_zip(package_root, zip_path)
        zip_completed = _run_alpha_package_validator(zip_path=zip_path)
        assert zip_completed.returncode == 0, zip_completed.stdout
        assert "PACKAGE_ZIP_VALIDATION_OK" in zip_completed.stdout


def test_alpha_package_validator_rejects_transient_apworld_artifacts() -> None:
    if get_powershell_executable() is None:
        return

    with tempfile.TemporaryDirectory() as tmp:
        package_root = Path(tmp) / "GeneralsAP-0.1.0-alpha"
        _write_alpha_package_fixture(package_root)
        transient_path = package_root / "payload" / "APWorld" / "generalszh" / "__pycache__" / "slot_data.cpython-312.pyc"
        transient_path.parent.mkdir(parents=True, exist_ok=True)
        transient_path.write_bytes(b"fixture pyc\n")

        completed = _run_alpha_package_validator(package_root=package_root)
        assert completed.returncode != 0
        assert "Package contains transient APWorld artifacts" in completed.stdout
        assert "payload/APWorld/generalszh/__pycache__/slot_data.cpython-312.pyc" in completed.stdout


def test_alpha_package_validator_rejects_missing_required_apworld_module() -> None:
    if get_powershell_executable() is None:
        return

    with tempfile.TemporaryDirectory() as tmp:
        package_root = Path(tmp) / "GeneralsAP-0.1.0-alpha"
        _write_alpha_package_fixture(package_root)
        missing_module = package_root / "payload" / "APWorld" / "generalszh" / "content_framework.py"
        missing_module.unlink()

        completed = _run_alpha_package_validator(package_root=package_root)
        assert completed.returncode != 0
        assert "payload/APWorld/generalszh/content_framework.py" in completed.stdout


def test_alpha_package_validator_rejects_bundled_bridge_with_staging_stub_kind() -> None:
    if get_powershell_executable() is None:
        return

    with tempfile.TemporaryDirectory() as tmp:
        package_root = Path(tmp) / "GeneralsAP-0.1.0-alpha"
        _write_alpha_package_fixture(package_root)
        manifest_path = package_root / "GeneralsAP-Release-Manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["bridgeKind"] = "staging_stub"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        completed = _run_alpha_package_validator(package_root=package_root)
        assert completed.returncode != 0
        assert "bundles a bridge executable but bridgeKind is staging_stub" in completed.stdout


def test_package_script_requires_explicit_non_stub_bridge_kind_when_bridge_path_supplied() -> None:
    powershell = get_powershell_executable()
    if powershell is None:
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        runtime_root = tmp_path / "Runtime"
        for relative_path in (
            "generalszh.exe",
            "zlib1.dll",
            "Data/INI/Archipelago.ini",
            "Data/INI/ArchipelagoChallengeUnitProtection.ini",
            "Data/INI/UnlockableChecksDemo.ini",
        ):
            path = runtime_root / Path(relative_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n", encoding="ascii")
        bridge_path = tmp_path / "GeneralsAPBridge.exe"
        bridge_path.write_text("fixture bridge\n", encoding="ascii")

        completed = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(REPO / "scripts/package_generalsap_alpha.ps1"),
                "-RuntimeDir",
                str(runtime_root),
                "-OutputDir",
                str(tmp_path / "out"),
                "-BridgePath",
                str(bridge_path),
                "-NoZip",
            ],
            cwd=REPO,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
        assert completed.returncode != 0
        assert "BridgePath requires explicit non-staging bridge kind" in completed.stdout


def test_alpha_package_smoke_imports_packaged_apworld_payload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        package_root = Path(tmp) / "GeneralsAP-0.1.0-alpha"
        _write_alpha_package_fixture(package_root)
        apworld_root = package_root / "payload" / "APWorld" / "generalszh"
        shutil.rmtree(apworld_root)
        shutil.copytree(REPO / "vendor" / "archipelago" / "overlay" / "worlds" / "generalszh", apworld_root)

        sys.path.insert(0, str(REPO))
        from scripts.tests import test_archipelago_world_contract as world_contract

        old_overlay_worlds = world_contract.OVERLAY_WORLDS
        managed_module_names = [
            module_name
            for module_name in list(sys.modules)
            if module_name == "worlds" or module_name.startswith("worlds.") or module_name in {"BaseClasses", "Options"}
        ]
        old_modules = {module_name: sys.modules[module_name] for module_name in managed_module_names}
        for module_name in managed_module_names:
            sys.modules.pop(module_name, None)

        try:
            world_contract.OVERLAY_WORLDS = package_root / "payload" / "APWorld"
            world_contract.install_archipelago_stubs()
            packaged_world = importlib.import_module("worlds.generalszh")
            importlib.import_module("worlds.generalszh.slot_data")
            importlib.import_module("worlds.generalszh.location_catalog")
            assert hasattr(packaged_world, "GeneralsZHWorld")
        finally:
            world_contract.OVERLAY_WORLDS = old_overlay_worlds
            for module_name in list(sys.modules):
                if module_name == "worlds" or module_name.startswith("worlds.") or module_name in {"BaseClasses", "Options"}:
                    sys.modules.pop(module_name, None)
            sys.modules.update(old_modules)


def test_clean_runtime_harness_requires_real_runtime_or_fixture() -> None:
    powershell = get_powershell_executable()
    if powershell is None:
        return

    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO / "scripts/smoke_generalsap_clean_runtime.ps1"),
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "BaseRuntimeDir is required" in completed.stdout
    assert "UseFixtureRuntime" in completed.stdout


def test_clean_runtime_smoke_completion_requires_real_launch() -> None:
    powershell = get_powershell_executable()
    if powershell is None:
        return

    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO / "scripts/smoke_generalsap_clean_runtime.ps1"),
            "-UseFixtureRuntime",
            "-SmokeCompleteRuntimeKey",
            "mission.tank.victory",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "SmokeCompleteRuntimeKey requires launching the game runtime" in completed.stdout


def test_clean_runtime_smoke_rejects_expanded_smoke_map_path() -> None:
    powershell = get_powershell_executable()
    if powershell is None:
        return

    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO / "scripts/smoke_generalsap_clean_runtime.ps1"),
            "-UseFixtureRuntime",
            "-SmokeMapFile",
            "Maps\\GC_TankGeneral\\GC_TankGeneral.map",
            "-WaitForSpawnedRuntimeKey",
            "cluster.tank.c02.u01",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "must use the short map form" in completed.stdout


def test_archipelago_vendor_capture_ignores_runtime_artifacts() -> None:
    sys.path.insert(0, str(REPO / "scripts"))
    from archipelago_vendor_capture import should_skip_capture

    assert should_skip_capture(Path("host.yaml"))
    assert should_skip_capture(Path("logs/Server_2026_05_02_21_50_30.txt"))
    assert should_skip_capture(Path("worlds/adventure/__pycache__/Items.cpython-312.pyc"))
    assert should_skip_capture(Path(".pytest_cache/v/cache/nodeids"))
    assert not should_skip_capture(Path("worlds/generalszh/world.py"))
    assert not should_skip_capture(Path("worlds/generalszh/docs/setup_en.md"))


def test_pr_scope_audit_contract() -> None:
    sys.path.insert(0, str(REPO / "scripts"))
    import archipelago_pr_scope_audit as scope_audit

    assert scope_audit.is_allowed_file("Data/Archipelago/location_families/catalog.json")
    assert scope_audit.is_allowed_file("Data/Archipelago/logic_contracts/capability_sources_schema.json")
    assert scope_audit.is_allowed_file("Data/Archipelago/logic_contracts/logic_foundry_export_schema.json")
    assert scope_audit.is_allowed_file("Data/Archipelago/logic_contracts/requirement_aliases.json")
    assert scope_audit.is_allowed_file("Data/Archipelago/logic_contracts/fixtures/example_logic_contracts.json")
    assert scope_audit.is_allowed_file("Data/Archipelago/logic_contracts/fixtures/logic_foundry_export_fixture.json")
    assert scope_audit.is_allowed_file("Data/Archipelago/bridge_fixtures/human_demo_tank.json")
    assert scope_audit.is_allowed_file("scripts/archipelago_logic_contract_validate.py")
    assert scope_audit.is_allowed_file("scripts/run_generalsap_demo_director.ps1")
    assert scope_audit.is_allowed_file("Docs/Archipelago/Planning/Item-Location-Framework-Branch-Readiness.md")
    assert scope_audit.is_allowed_file("GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp")
    assert scope_audit.is_allowed_file("tools/bridge/GeneralsAPBridge/Program.cs")
    assert scope_audit.is_allowed_file("vendor/archipelago/overlay/worlds/generalszh/slot_data.py")
    assert scope_audit.is_allowed_file(".github/workflows/build-toolchain.yml")
    assert scope_audit.is_allowed_file(".github/workflows/validate-archipelago-data.yml")
    assert scope_audit.is_allowed_file("GeneralsMD/Code/GameEngine/Source/Common/CommandLine.cpp")
    assert scope_audit.is_allowed_file("GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp")
    assert scope_audit.is_allowed_file("tools/logic-foundry")
    assert not scope_audit.is_allowed_file("tools/cluster-editor/src/App.tsx")
    assert not scope_audit.is_allowed_file(".github/workflows/release-polish.yml")
    assert not scope_audit.is_allowed_file("scripts/unrelated_release_polish.py")
    assert not scope_audit.is_allowed_file("Docs/Archipelago/Planning/New-Logic-Model.md")
    assert not scope_audit.is_allowed_file("tools/bridge/GeneralsAPBridge/LauncherUi.cs")
    assert scope_audit.FORBIDDEN_FILE_RE.search("Data/Archipelago/weaknesses.json")
    assert scope_audit.FORBIDDEN_FILE_RE.search("Docs/Archipelago/Planning/hold_logic.md")
    assert scope_audit.FORBIDDEN_FILE_RE.search("tools/tracker-ui/App.tsx")

    diff = "\n".join(
        [
            "diff --git a/scripts/example.py b/scripts/example.py",
            "+++ b/scripts/example.py",
            "+# weakness evaluator should not land on this branch",
        ]
    )
    matches = scope_audit.find_forbidden_matches(diff)
    assert len(matches) == 1
    assert matches[0]["file"] == "scripts/example.py"

    allowed_planning_note_diff = "\n".join(
        [
            "diff --git a/vendor/archipelago/overlay/worlds/generalszh/content_framework.py b/vendor/archipelago/overlay/worlds/generalszh/content_framework.py",
            "+++ b/vendor/archipelago/overlay/worlds/generalszh/content_framework.py",
            "+        notes=\"Permanent starting-cash floor. Count range is planning-only until Hold/Win logic consumes economy floors.\",",
        ]
    )
    assert scope_audit.find_forbidden_matches(allowed_planning_note_diff) == []

    exempt_diff = "\n".join(
        [
            "diff --git a/scripts/archipelago_pr_scope_audit.py b/scripts/archipelago_pr_scope_audit.py",
            "+++ b/scripts/archipelago_pr_scope_audit.py",
            "+    r\"weakness evaluator|hold logic|tracker ui\"",
        ]
    )
    assert scope_audit.find_forbidden_matches(exempt_diff) == []

    original_git = scope_audit.git
    try:
        def fake_git(args: list[str]) -> str:
            if args == ["merge-base", "HEAD", "origin/codex/ap-world-skeleton-checkpoint"]:
                return "abc123\n"
            if args == ["diff", "--name-only", "origin/codex/ap-world-skeleton-checkpoint...HEAD"]:
                return "\n".join(
                    [
                        "scripts/archipelago_pr_scope_audit.py",
                        "scripts/unrelated_release_polish.py",
                        "Docs/Archipelago/Planning/New-Logic-Model.md",
                    ]
                )
            if args[:2] == ["diff", "origin/codex/ap-world-skeleton-checkpoint...HEAD"]:
                return ""
            raise AssertionError(args)

        scope_audit.git = fake_git
        report = scope_audit.run_scope_audit("origin/codex/ap-world-skeleton-checkpoint", "HEAD")
        assert report["status"] == "failed"
        assert report["unexpectedFiles"] == [
            "scripts/unrelated_release_polish.py",
            "Docs/Archipelago/Planning/New-Logic-Model.md",
        ]
    finally:
        scope_audit.git = original_git

    assert "vendor/archipelago/overlay/worlds/generalszh/content_framework.py" in scope_audit.IMPLEMENTATION_DIFF_PATHS

    workflow = (REPO / ".github/workflows/validate-archipelago-data.yml").read_text(encoding="utf-8")
    assert "pull_request:\n    branches:\n      - main\n      - codex/ap-world-skeleton-checkpoint" in workflow
    assert "if: github.event_name == 'pull_request'" in workflow
    assert "python scripts\\archipelago_pr_scope_audit.py --base origin/${{ github.base_ref }} --head HEAD" in workflow
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/codex/ap-item-location-framework'" in workflow
    assert "python scripts\\archipelago_pr_scope_audit.py --base origin/codex/ap-world-skeleton-checkpoint --head HEAD" in workflow
    assert "Compile GeneralsMD Runtime Smoke" in workflow
    assert "preset: \"win32-vcpkg-playtest\"" in workflow
    assert "tools: false" in workflow
    assert "extras: false" in workflow

    testing_doc = (REPO / "TESTING.md").read_text(encoding="utf-8")
    readiness_doc = (REPO / "Docs/Archipelago/Planning/Item-Location-Framework-Branch-Readiness.md").read_text(encoding="utf-8")
    assert "archipelago_pr_scope_audit.py" in testing_doc
    assert "archipelago_pr_scope_audit.py" in readiness_doc


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
        test_matchup_graph_generation_preserves_timestamp_when_unchanged,
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
        test_local_bridge_minimal_preset_does_not_invent_hard_cluster_checks,
        test_local_bridge_preserves_future_location_state_scaffold,
        test_seeded_bridge_loop_smoke_harness,
        test_runtime_fallback_contract_check,
        test_runtime_natural_completion_callbacks_use_selected_runtime_keys,
        test_extract_ini_config_requires_force_for_tracked_output,
        test_runtime_slot_data_future_family_parse_only,
        test_runtime_future_location_state_scaffold,
        test_item_location_capacity_report,
        test_human_demo_director_contract,
        test_release_manifest_and_packaging_contract,
        test_alpha_package_validator_fixture_root_and_zip,
        test_alpha_package_validator_rejects_unsafe_zip_path_traversal,
        test_alpha_package_validator_rejects_zip_sibling_outside_package_root,
        test_alpha_package_validator_rejects_unclaimed_game_file,
        test_alpha_package_validator_rejects_missing_claimed_game_file,
        test_alpha_package_validator_accepts_no_bridge_package,
        test_alpha_package_validator_rejects_transient_apworld_artifacts,
        test_alpha_package_validator_rejects_missing_required_apworld_module,
        test_alpha_package_validator_rejects_bundled_bridge_with_staging_stub_kind,
        test_package_script_requires_explicit_non_stub_bridge_kind_when_bridge_path_supplied,
        test_alpha_package_smoke_imports_packaged_apworld_payload,
        test_clean_runtime_harness_requires_real_runtime_or_fixture,
        test_clean_runtime_smoke_completion_requires_real_launch,
        test_clean_runtime_smoke_rejects_expanded_smoke_map_path,
        test_archipelago_vendor_capture_ignores_runtime_artifacts,
        test_pr_scope_audit_contract,
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
