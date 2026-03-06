#!/usr/bin/env python3
"""
Extract template name -> DisplayName mapping from game INI files.

Outputs a mapping of Object/Upgrade template names to their DisplayName keys
(OBJECT:X or UPGRADE:X), which can be resolved to in-game text via CSF files.

Usage: python scripts/archipelago_extract_template_display_names.py [--output FILE]
Output: JSON or stdout (default: Data/Archipelago/reference/archipelago_template_display_names.json)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from archipelago_data_helpers import default_game_asset_path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_INI = REPO_ROOT / "Data" / "INI"
FACTION_UNIT = default_game_asset_path(Path("Data") / "INI" / "Object" / "FactionUnit.ini")
FACTION_BUILDING = default_game_asset_path(Path("Data") / "INI" / "Object" / "FactionBuilding.ini")
UPGRADE_INI = default_game_asset_path(Path("Data") / "INI" / "Upgrade.ini")


def _extract_display_name_from_body(body: str) -> str | None:
    match = re.search(r"DisplayName\s*=\s*(\S+)", body, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def extract_object_display_names(filepath: Path) -> dict[str, str]:
    """Extract top-level Object/ObjectReskin name -> DisplayName from INI."""
    result: dict[str, str] = {}
    lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        stripped = raw.strip()
        is_top_level = raw == raw.lstrip()

        if is_top_level and stripped.startswith("ObjectReskin "):
            parts = stripped.split()
            if len(parts) >= 3:
                name = parts[1].strip()
                i += 1
                body_lines: list[str] = []
                while i < n:
                    end_line = lines[i]
                    if end_line == end_line.lstrip() and end_line.strip() == "End":
                        break
                    body_lines.append(end_line)
                    i += 1
                display_name = _extract_display_name_from_body("\n".join(body_lines))
                if display_name:
                    result[name] = display_name
            i += 1
            continue

        if is_top_level and stripped.startswith("Object "):
            parts = stripped.split()
            if len(parts) >= 2:
                name = parts[1].strip()
                i += 1
                body_lines: list[str] = []
                while i < n:
                    end_line = lines[i]
                    if end_line == end_line.lstrip() and end_line.strip() == "End":
                        break
                    body_lines.append(end_line)
                    i += 1
                display_name = _extract_display_name_from_body("\n".join(body_lines))
                if display_name:
                    result[name] = display_name
            i += 1
            continue

        i += 1

    return result


def extract_upgrade_display_names(filepath: Path) -> dict[str, str]:
    """Extract top-level Upgrade name -> DisplayName from INI."""
    result: dict[str, str] = {}
    lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        stripped = raw.strip()
        is_top_level = raw == raw.lstrip()

        if is_top_level and stripped.startswith("Upgrade "):
            parts = stripped.split()
            if len(parts) >= 2:
                name = parts[1].strip()
                i += 1
                body_lines: list[str] = []
                while i < n:
                    end_line = lines[i]
                    if end_line == end_line.lstrip() and end_line.strip() == "End":
                        break
                    body_lines.append(end_line)
                    i += 1
                display_name = _extract_display_name_from_body("\n".join(body_lines))
                if display_name:
                    result[name] = display_name
            i += 1
            continue

        i += 1

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract template->DisplayName mapping")
    parser.add_argument(
        "--output",
        "-o",
        default=str(REPO_ROOT / "Data" / "Archipelago" / "reference" / "archipelago_template_display_names.json"),
        help="Output JSON file path",
    )
    args = parser.parse_args()

    mapping: dict[str, str] = {}
    if FACTION_UNIT.exists():
        mapping.update(extract_object_display_names(FACTION_UNIT))
    if FACTION_BUILDING.exists():
        mapping.update(extract_object_display_names(FACTION_BUILDING))
    if UPGRADE_INI.exists():
        mapping.update(extract_upgrade_display_names(UPGRADE_INI))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(mapping)} mappings to {out_path}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())

