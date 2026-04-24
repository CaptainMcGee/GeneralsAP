#!/usr/bin/env python3
"""Sanity tests for WND workbench extraction and manifest tooling."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.wnd_workbench import (  # noqa: E402
    apply_recipe_to_text,
    build_manifest_entry,
    extract_selected_from_big,
    flatten_windows,
    load_required_controls,
    load_working_set,
    parse_transition_references,
    parse_wnd_text,
)


def build_big(entries: list[tuple[str, bytes]]) -> bytes:
    index_parts: list[bytes] = []
    data_parts: list[bytes] = []
    offset = 16
    for path, _ in entries:
        offset += 8 + len(path.encode("ascii")) + 1

    current_offset = offset
    for path, payload in entries:
        index_parts.append(current_offset.to_bytes(4, "big"))
        index_parts.append(len(payload).to_bytes(4, "big"))
        index_parts.append(path.encode("ascii") + b"\x00")
        data_parts.append(payload)
        current_offset += len(payload)

    archive = bytearray()
    archive.extend(b"BIGF")
    archive.extend((16 + sum(len(part) for part in index_parts) + sum(len(part) for part in data_parts)).to_bytes(4, "little"))
    archive.extend(len(entries).to_bytes(4, "big"))
    archive.extend((16 + sum(len(part) for part in index_parts)).to_bytes(4, "big"))
    for part in index_parts:
        archive.extend(part)
    for part in data_parts:
        archive.extend(part)
    return bytes(archive)


def test_wnd_working_set_exists() -> None:
    entries = load_working_set(REPO / "Data/Archipelago/wnd_working_set.json")
    paths = {entry["path"] for entry in entries}
    assert "Window/Menus/MainMenu.wnd" in paths
    assert "Window/Menus/NetworkDirectConnect.wnd" in paths


def test_parse_wnd_text_hierarchy() -> None:
    text = """FILE_VERSION = 2;
STARTLAYOUTBLOCK
  LAYOUTINIT = DemoInit;
  LAYOUTUPDATE = DemoUpdate;
  LAYOUTSHUTDOWN = DemoShutdown;
ENDLAYOUTBLOCK
WINDOW
  WINDOWTYPE = USER;
  NAME = "Demo.wnd:Root";
  SCREENRECT = UPPERLEFT: 0 0,
               BOTTOMRIGHT: 800 600,
               CREATIONRESOLUTION: 800 600;
  CHILD
  WINDOW ; child button
    WINDOWTYPE = PUSHBUTTON;
    NAME = "Demo.wnd:ButtonGo";
    STATUS = ENABLED+IMAGE;
    SCREENRECT = UPPERLEFT: 10 20,
                 BOTTOMRIGHT: 30 40,
                 CREATIONRESOLUTION: 800 600;
  END
  ENDALLCHILDREN
END
"""
    parsed = parse_wnd_text(text)
    assert parsed["file_version"] == "2"
    assert parsed["layout"]["LAYOUTINIT"] == "DemoInit"
    assert len(parsed["windows"]) == 1
    root = parsed["windows"][0]
    assert root.get_raw("NAME") == '"Demo.wnd:Root"'
    assert len(root.children) == 1
    assert root.children[0].get_raw("NAME") == '"Demo.wnd:ButtonGo"'


def test_recipe_copy_and_reflow_deterministic() -> None:
    text = """FILE_VERSION = 2;
WINDOW
  WINDOWTYPE = USER;
  NAME = "MainMenu.wnd:Root";
  SCREENRECT = UPPERLEFT: 0 0,
               BOTTOMRIGHT: 800 600,
               CREATIONRESOLUTION: 800 600;
  CHILD
  WINDOW
    WINDOWTYPE = USER;
    NAME = "MainMenu.wnd:MapBorder2";
    SCREENRECT = UPPERLEFT: 532 108,
                 BOTTOMRIGHT: 756 318,
                 CREATIONRESOLUTION: 800 600;
  END
  CHILD
  WINDOW
    WINDOWTYPE = PUSHBUTTON;
    NAME = "MainMenu.wnd:ButtonSinglePlayer";
    SCREENRECT = UPPERLEFT: 540 114,
                 BOTTOMRIGHT: 748 146,
                 CREATIONRESOLUTION: 800 600;
    TEXT = "GUI:SinglePlayer";
  END
  CHILD
  WINDOW
    WINDOWTYPE = PUSHBUTTON;
    NAME = "MainMenu.wnd:ButtonMultiplayer";
    SCREENRECT = UPPERLEFT: 540 148,
                 BOTTOMRIGHT: 748 180,
                 CREATIONRESOLUTION: 800 600;
    TEXT = "GUI:Multiplayer";
  END
  CHILD
  WINDOW
    WINDOWTYPE = PUSHBUTTON;
    NAME = "MainMenu.wnd:ButtonLoadReplay";
    SCREENRECT = UPPERLEFT: 540 182,
                 BOTTOMRIGHT: 748 214,
                 CREATIONRESOLUTION: 800 600;
    TEXT = "GUI:LoadReplay";
  END
  CHILD
  WINDOW
    WINDOWTYPE = PUSHBUTTON;
    NAME = "MainMenu.wnd:ButtonOptions";
    SCREENRECT = UPPERLEFT: 540 216,
                 BOTTOMRIGHT: 748 248,
                 CREATIONRESOLUTION: 800 600;
    TEXT = "GUI:Options";
  END
  CHILD
  WINDOW
    WINDOWTYPE = PUSHBUTTON;
    NAME = "MainMenu.wnd:ButtonCredits";
    SCREENRECT = UPPERLEFT: 540 250,
                 BOTTOMRIGHT: 748 282,
                 CREATIONRESOLUTION: 800 600;
    TEXT = "GUI:Credits";
  END
  CHILD
  WINDOW
    WINDOWTYPE = PUSHBUTTON;
    NAME = "MainMenu.wnd:ButtonExit";
    SCREENRECT = UPPERLEFT: 540 284,
                 BOTTOMRIGHT: 748 316,
                 CREATIONRESOLUTION: 800 600;
    TEXT = "GUI:Exit";
  END
  ENDALLCHILDREN
END
"""
    recipe = json.loads((REPO / "Data/Archipelago/UI/main_menu_patch_recipe.json").read_text(encoding="utf-8"))
    first = apply_recipe_to_text(text, recipe)
    second = apply_recipe_to_text(text, recipe)
    assert first == second
    parsed = parse_wnd_text(first)
    names = [window.get_name() for window in parsed["windows"][0].children]
    assert names == [
        "MainMenu.wnd:MapBorder2",
        "MainMenu.wnd:ButtonSinglePlayer",
        "MainMenu.wnd:ButtonMultiplayer",
        "MainMenu.wnd:ButtonArchipelago",
        "MainMenu.wnd:ButtonLoadReplay",
        "MainMenu.wnd:ButtonOptions",
        "MainMenu.wnd:ButtonCredits",
        "MainMenu.wnd:ButtonExit",
    ]
    archipelago = parsed["windows"][0].children[3]
    assert archipelago.get_raw("TEXT") == '"GUI:Archipelago"'
    assert "UPPERLEFT: 540 182" in archipelago.get_raw("SCREENRECT")
    assert "BOTTOMRIGHT: 748 214" in archipelago.get_raw("SCREENRECT")


def test_insert_after_moves_existing_control() -> None:
    text = """FILE_VERSION = 2;
WINDOW
  WINDOWTYPE = USER;
  NAME = "Demo.wnd:Root";
  SCREENRECT = UPPERLEFT: 0 0,
               BOTTOMRIGHT: 100 100,
               CREATIONRESOLUTION: 800 600;
  CHILD
  WINDOW
    WINDOWTYPE = USER;
    NAME = "Demo.wnd:A";
    SCREENRECT = UPPERLEFT: 0 0,
                 BOTTOMRIGHT: 10 10,
                 CREATIONRESOLUTION: 800 600;
  END
  CHILD
  WINDOW
    WINDOWTYPE = USER;
    NAME = "Demo.wnd:B";
    SCREENRECT = UPPERLEFT: 0 0,
                 BOTTOMRIGHT: 10 10,
                 CREATIONRESOLUTION: 800 600;
  END
  CHILD
  WINDOW
    WINDOWTYPE = USER;
    NAME = "Demo.wnd:C";
    SCREENRECT = UPPERLEFT: 0 0,
                 BOTTOMRIGHT: 10 10,
                 CREATIONRESOLUTION: 800 600;
  END
  ENDALLCHILDREN
END
"""
    updated = apply_recipe_to_text(
        text,
        {
            "operations": [
                {
                    "op": "insert_after",
                    "target": "Demo.wnd:A",
                    "after": "Demo.wnd:C",
                }
            ]
        },
    )
    parsed = parse_wnd_text(updated)
    names = [window.get_name() for window in parsed["windows"][0].children]
    assert names == ["Demo.wnd:B", "Demo.wnd:C", "Demo.wnd:A"]


def test_transition_audit_missing_control() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        wnd_path = temp / "Demo.wnd"
        wnd_path.write_text(
            """FILE_VERSION = 2;
WINDOW
  WINDOWTYPE = USER;
  NAME = "Demo.wnd:Root";
  SCREENRECT = UPPERLEFT: 0 0,
               BOTTOMRIGHT: 100 100,
               CREATIONRESOLUTION: 800 600;
END
""",
            encoding="latin-1",
        )
        transitions = temp / "WindowTransitions.ini"
        transitions.write_text(
            "WindowTransition Demo\n  Window\n    WinName = Demo.wnd:MissingButton\n  END\nEND\n",
            encoding="utf-8",
        )
        refs = parse_transition_references(transitions)
        entry = build_manifest_entry(wnd_path, refs)
        assert entry["audit"]["missing_transition_targets"] == ["Demo.wnd:MissingButton"]


def test_extract_selected_from_big() -> None:
    wnd_payload = b'FILE_VERSION = 2;\nWINDOW\n  WINDOWTYPE = USER;\nEND\n'
    extra_payload = b'noop'
    archive_bytes = build_big(
        [
            ("Window/Menus/MainMenu.wnd", wnd_payload),
            ("Window/Menus/Unused.wnd", extra_payload),
        ]
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        archive = temp / "WindowZH.big"
        archive.write_bytes(archive_bytes)
        output = temp / "out"
        written = extract_selected_from_big(
            archive,
            ["Window/Menus/MainMenu.wnd"],
            output,
            force=True,
        )
        assert len(written) == 1
        target = output / "Window" / "Menus" / "MainMenu.wnd"
        assert target.exists()
        assert target.read_bytes() == wnd_payload


def test_ap_wnd_required_controls_present() -> None:
    refs = parse_transition_references(REPO / "Data/INI/WindowTransitions.ini")
    required = load_required_controls(REPO / "Data/Archipelago/UI/ap_shell_required_controls.json")
    wnd_root = REPO / "Data/Archipelago/UI/Wnd"
    for wnd_path in sorted(wnd_root.glob("*.wnd")):
        entry = build_manifest_entry(wnd_path, refs, required)
        assert entry["audit"]["missing_required_controls"] == [], f"{wnd_path.name} missing required controls"
        assert entry["audit"]["duplicate_names"] == [], f"{wnd_path.name} has duplicate control names"
        assert entry["audit"]["invalid_screenrect"] == [], f"{wnd_path.name} has invalid screen rects"


def test_ap_wnd_fonts_follow_reset_palette() -> None:
    allowed_fonts = {
        ("Generals", "24", "0"),
        ("Generals", "22", "0"),
        ("Generals", "18", "0"),
        ("Generals", "16", "0"),
        ("Generals", "15", "0"),
        ("Generals", "14", "0"),
        ("Generals", "13", "0"),
        ("Arial", "12", "0"),
        ("Arial", "13", "0"),
        ("Arial", "11", "0"),
    }
    wnd_root = REPO / "Data/Archipelago/UI/Wnd"
    for wnd_path in sorted(wnd_root.glob("*.wnd")):
        text = wnd_path.read_text(encoding="latin-1")
        fonts = re.findall(r'FONT = NAME: "([^"]+)", SIZE: (\d+), BOLD: (\d+);', text)
        unexpected = sorted({font for font in fonts if font not in allowed_fonts})
        assert not unexpected, f"{wnd_path.name} has unexpected fonts: {unexpected}"
        assert "Times New Roman" not in text, f"{wnd_path.name} still references Times New Roman"


def test_mission_intel_uses_map_first_controls() -> None:
    path = REPO / "Data/Archipelago/UI/Wnd/APMissionIntel.wnd"
    parsed = parse_wnd_text(path.read_text(encoding="latin-1"))
    flat = flatten_windows(parsed["windows"])
    names = {record["name"] for record in flat}
    assert "APMissionIntel.wnd:WinMapPreview" in names
    assert "APMissionIntel.wnd:ComboMissionSelect" not in names
    assert "APMissionIntel.wnd:ListMissions" not in names
    assert "APMissionIntel.wnd:ListClusters" not in names
    for index in range(1, 9):
        assert f"APMissionIntel.wnd:ButtonClusterMarker{index:02d}" in names
    assert "APMissionIntel.wnd:ButtonClusterMarker09" not in names


def test_ap_action_controls_live_in_expected_panels() -> None:
    expectations = {
        "ArchipelagoHub.wnd": {
            "ArchipelagoHub.wnd:ButtonMissionIntel": "ArchipelagoHub.wnd:PanelActions",
            "ArchipelagoHub.wnd:ButtonCheckTracker": "ArchipelagoHub.wnd:PanelActions",
            "ArchipelagoHub.wnd:ButtonConnect": "ArchipelagoHub.wnd:PanelActions",
            "ArchipelagoHub.wnd:ButtonBack": "ArchipelagoHub.wnd:PanelFooter",
        },
        "APConnect.wnd": {
            "APConnect.wnd:ButtonConnect": "APConnect.wnd:PanelFooter",
            "APConnect.wnd:ButtonDisconnect": "APConnect.wnd:PanelFooter",
            "APConnect.wnd:ButtonBack": "APConnect.wnd:PanelFooter",
        },
        "APMissionIntel.wnd": {
            "APMissionIntel.wnd:ButtonLaunch": "APMissionIntel.wnd:PanelFooter",
            "APMissionIntel.wnd:ButtonBack": "APMissionIntel.wnd:PanelFooter",
        },
        "APCheckTracker.wnd": {
            "APCheckTracker.wnd:ButtonBack": "APCheckTracker.wnd:PanelFooter",
        },
    }

    for wnd_name, controls in expectations.items():
        path = REPO / "Data/Archipelago/UI/Wnd" / wnd_name
        parsed = parse_wnd_text(path.read_text(encoding="latin-1"))
        by_name = {record["name"]: record for record in flatten_windows(parsed["windows"])}
        for control_name, expected_parent in controls.items():
            assert by_name[control_name]["parent_name"] == expected_parent, (
                f"{control_name} expected parent {expected_parent}, got {by_name[control_name]['parent_name']}"
            )


def main() -> int:
    tests = [
        test_wnd_working_set_exists,
        test_parse_wnd_text_hierarchy,
        test_recipe_copy_and_reflow_deterministic,
        test_insert_after_moves_existing_control,
        test_transition_audit_missing_control,
        test_extract_selected_from_big,
        test_ap_wnd_required_controls_present,
        test_ap_wnd_fonts_follow_reset_palette,
        test_mission_intel_uses_map_first_controls,
        test_ap_action_controls_live_in_expected_panels,
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
