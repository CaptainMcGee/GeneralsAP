#!/usr/bin/env python3
"""Full Archipelago smoke test for the GeneralsZH overlay scaffold.

This is intentionally heavier than the pure importer tests. Run it from the
repo root with a venv that has scripts/requirements-archipelago-smoke.txt.
"""

from __future__ import annotations

import importlib
import pickle
import shutil
import subprocess
import sys
import zipfile
import zlib
from types import SimpleNamespace
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
WORKTREE = REPO / "build" / "archipelago" / "archipelago-worktree"
PLAYER_DIR = REPO / "build" / "archipelago" / "generalszh-test-players"
OUTPUT_DIR = REPO / "build" / "archipelago" / "generalszh-test-output"
GAME_NAME = "Command & Conquer: Generals - Zero Hour"
SEED = "270101"
ROUTE_CASES: list[tuple[str, str, str, str, str | None]] = [
    ("usa", "usa", "general_specific", "USA", None),
    ("air_force", "usa", "general_specific", "USA", "Air Force"),
    ("laser", "usa", "general_specific", "USA", "Laser"),
    ("superweapon", "usa", "general_specific", "USA", "Superweapon"),
    ("china", "china", "general_specific", "China", None),
    ("tank", "china", "faction_shared", "China", "Tank"),
    ("nuke", "china", "general_specific", "China", "Nuke"),
    ("infantry", "china", "general_specific", "China", "Infantry"),
    ("gla", "gla", "general_specific", "GLA", None),
    ("stealth", "gla", "general_specific", "GLA", "Stealth"),
    ("toxin", "gla", "general_specific", "GLA", "Toxin"),
    ("demolition", "gla", "general_specific", "GLA", "Demolition"),
]


def assert_inside_repo(path: Path) -> None:
    path.resolve().relative_to(REPO.resolve())


def run(args: list[str], cwd: Path = REPO) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise AssertionError(f"Command failed ({result.returncode}): {' '.join(args)}\n{output}")
    return output


def write_player_yaml(general_key: str, army_key: str, item_mode: str) -> None:
    assert_inside_repo(PLAYER_DIR)
    if PLAYER_DIR.exists():
        shutil.rmtree(PLAYER_DIR)
    PLAYER_DIR.mkdir(parents=True, exist_ok=True)
    (PLAYER_DIR / "GeneralsZH.yaml").write_text(
        "\n".join(
            [
                f"name: Generals{general_key.replace('_', '').title()}",
                f'game: "{GAME_NAME}"',
                f'description: "GeneralsZH {general_key} generation test"',
                f'"{GAME_NAME}":',
                f"  starting_army: {army_key}",
                f"  start_general: {general_key}",
                f"  item_mode: {item_mode}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def materialize_archipelago() -> None:
    run([sys.executable, "scripts/archipelago_vendor_materialize.py"])


def option(options_module, option_class: str, value: str):
    return getattr(options_module, option_class).from_text(value)


def fake_world(options_module, general_key: str, army_key: str, item_mode: str):
    return SimpleNamespace(
        options=SimpleNamespace(
            starting_army=option(options_module, "StartingArmy", army_key),
            start_general=option(options_module, "StartGeneral", general_key),
            item_mode=option(options_module, "ItemMode", item_mode),
        )
    )


def load_generalszh_world() -> tuple[object, object]:
    sys.path.insert(0, str(WORKTREE))
    worlds = importlib.import_module("worlds")
    generalszh = importlib.import_module("worlds.generalszh")
    items = importlib.import_module("worlds.generalszh.Items")
    options = importlib.import_module("worlds.generalszh.Options")
    rules = importlib.import_module("worlds.generalszh.Rules")
    baseclasses = importlib.import_module("BaseClasses")

    assert worlds.failed_world_loads == [], f"AP world load failures: {worlds.failed_world_loads}"
    assert generalszh.GeneralsZHWorld.game == GAME_NAME
    assert "Victory" in generalszh.GeneralsZHWorld.item_name_to_id
    assert generalszh.GeneralsZHWorld.item_name_to_id["Victory"] is not None
    assert items.FILLER_ITEM_NAME == "Supply Drop"
    assert items.item_classification(items.FILLER_ITEM_NAME) == baseclasses.ItemClassification.filler
    assert items.item_classification("Air Force General Medal") == baseclasses.ItemClassification.progression
    assert len(generalszh.GeneralsZHWorld.location_name_to_id) == 14
    return options, rules


def assert_route_options(options_module, rules_module) -> None:
    for general_key, army_key, item_mode, expected_faction, expected_general in ROUTE_CASES:
        route = rules_module.route_for_world(fake_world(options_module, general_key, army_key, item_mode))
        assert route.faction == expected_faction
        assert route.general == expected_general
        assert route.yaml_mode == item_mode


def run_generation(general_key: str, army_key: str, item_mode: str, seed_offset: int) -> Path:
    case_output_dir = OUTPUT_DIR / general_key
    assert_inside_repo(case_output_dir)
    if case_output_dir.exists():
        shutil.rmtree(case_output_dir)
    case_output_dir.mkdir(parents=True)
    write_player_yaml(general_key, army_key, item_mode)

    output = run(
        [
            sys.executable,
            str(WORKTREE / "Generate.py"),
            "--player_files_path",
            str(PLAYER_DIR),
            "--outputpath",
            str(case_output_dir),
            "--seed",
            str(int(SEED) + seed_offset),
            "--multi",
            "1",
            "--spoiler",
            "1",
            "--log_level",
            "info",
        ]
    )
    assert "Done. Enjoy." in output
    archives = sorted(case_output_dir.glob("AP_*.zip"))
    assert len(archives) == 1, f"Expected one AP output zip for {general_key}, found {archives}"
    return archives[0]


def load_archipelago_multidata(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        archipelago_names = [name for name in names if name.endswith(".archipelago")]
        assert len(archipelago_names) == 1, names
        raw = archive.read(archipelago_names[0])
    # AP .archipelago files are zlib-compressed pickles with one leading format byte.
    return pickle.loads(zlib.decompress(raw[1:]))


def assert_output_zip(path: Path, expected_faction: str, expected_general: str | None, expected_item_mode: str) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    assert any(name.endswith(".archipelago") for name in names), names
    assert any(name.endswith("_Spoiler.txt") for name in names), names

    multidata = load_archipelago_multidata(path)
    slot_data = multidata["slot_data"][1]
    assert slot_data["sourceKind"] == "generalsap_logic_foundry_ap_world_import"
    assert slot_data["route"] == {
        "faction": expected_faction,
        "general": expected_general,
        "itemMode": expected_item_mode,
    }
    assert len(slot_data["missions"]) == 8
    assert len(slot_data["clusterAccessRules"]) == 4
    assert len(slot_data["worldGoal"]["requiredMedalItemNames"]) == 7

    datapackage = multidata["datapackage"][GAME_NAME]
    item_name_to_id = datapackage["item_name_to_id"]
    location_name_to_id = datapackage["location_name_to_id"]
    assert "Victory" in item_name_to_id
    assert "Supply Drop" in item_name_to_id
    medal_item_ids = set()
    for medal in slot_data["worldGoal"]["requiredMedalItemNames"]:
        assert medal in item_name_to_id
        medal_item_ids.add(item_name_to_id[medal])

    boss_location_name = "Mission: China Boss General Victory"
    assert boss_location_name in location_name_to_id
    boss_location_id = location_name_to_id[boss_location_name]
    victory_item_id = item_name_to_id["Victory"]
    player_locations = multidata["locations"][1]
    player_location_ids = set(player_locations)
    assert player_location_ids == set(location_name_to_id.values())
    assert player_locations[boss_location_id][0] == victory_item_id

    placed_item_ids = [item_id for item_id, _player, _flags in player_locations.values()]
    assert placed_item_ids.count(victory_item_id) == 1
    assert medal_item_ids.issubset(set(placed_item_ids))

    precollected_item_ids = set(multidata["precollected_items"].get(1, []))
    assert victory_item_id not in precollected_item_ids
    assert medal_item_ids.isdisjoint(precollected_item_ids)


def test_full_generation_smoke() -> None:
    materialize_archipelago()
    options, rules = load_generalszh_world()
    assert_route_options(options, rules)
    for index, (general_key, army_key, item_mode, expected_faction, expected_general) in enumerate(ROUTE_CASES):
        output_zip = run_generation(general_key, army_key, item_mode, index)
        assert_output_zip(output_zip, expected_faction, expected_general, item_mode)


def main() -> int:
    try:
        test_full_generation_smoke()
        print("PASS: test_full_generation_smoke")
        return 0
    except Exception as exc:
        print(f"FAIL: test_full_generation_smoke - {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
