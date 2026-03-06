#!/usr/bin/env python3
"""
Validate that all templates in Archipelago.ini exist in game INI files.

Exits 0 if valid, 1 if any template is missing or denylisted. Used in CI to catch typos,
stale references, and non-spawnable templates before they cause runtime issues.

Sources (in order of precedence):
- DUMP_FILE (Data/Archipelago/reference/ArchipelagoThingFactoryTemplates_filtered.txt): Full list from
  game dump (run DEMO_AP_DUMP_TEMPLATES in-game). Includes retail templates.
- FactionUnit.ini, FactionBuilding.ini: Object and ObjectReskin names
- Upgrade.ini: Upgrade definitions
- CommandButton.ini: CommandButton definitions (for Command_* names)

General-prefixed names (AirF_, Lazr_, Slth_, etc.) are accepted if the
base name exists, since variants may come from retail INIZH.big.

Usage: python archipelago_validate_ini.py [--warn-non-spawnable]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_INI = REPO_ROOT / "Data" / "INI"
FACTION_UNIT = DATA_INI / "Object" / "FactionUnit.ini"
FACTION_BUILDING = DATA_INI / "Object" / "FactionBuilding.ini"
UPGRADE_INI = DATA_INI / "Upgrade.ini"
COMMAND_BUTTON_INI = DATA_INI / "CommandButton.ini"
ARCHIPELAGO_INI = DATA_INI / "Archipelago.ini"
DUMP_FILE = REPO_ROOT / "Data" / "Archipelago" / "reference" / "ArchipelagoThingFactoryTemplates_filtered.txt"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "archipelago_validate_allowlist.txt"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from archipelago_data_helpers import is_denied_template, load_non_spawnable_templates, strip_known_general_prefix



def collect_object_names(filepath: Path) -> set[str]:
    """Extract Object and ObjectReskin names from INI."""
    names: set[str] = set()
    content = filepath.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"^Object\s+(\w+)\s*\n", content, re.MULTILINE):
        names.add(m.group(1))
    for m in re.finditer(r"^ObjectReskin\s+(\w+)\s+\w+\s*\n", content, re.MULTILINE):
        names.add(m.group(1))
    return names



def collect_upgrade_names(filepath: Path) -> set[str]:
    """Extract Upgrade names from INI."""
    names: set[str] = set()
    content = filepath.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"^Upgrade\s+(\w+)\s*\n", content, re.MULTILINE):
        names.add(m.group(1))
    return names



def collect_command_names(filepath: Path) -> set[str]:
    """Extract CommandButton names from INI."""
    names: set[str] = set()
    content = filepath.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"^CommandButton\s+(\w+)\s*\n", content, re.MULTILINE):
        names.add(m.group(1))
    return names



def collect_allowlist(filepath: Path) -> set[str]:
    """Read allowlist of known-good templates (one per line, # = comment)."""
    names: set[str] = set()
    for line in filepath.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip().split("#")[0].strip()
        if line:
            names.add(line)
    return names



def collect_dump_templates(filepath: Path) -> set[str]:
    """Extract template names from ThingFactory dump (name\tunit|building)."""
    names: set[str] = set()
    for line in filepath.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if parts:
            names.add(parts[0].strip())
    return names



def collect_all_valid_templates() -> set[str]:
    """Collect all template names from INI files and optional dump (union of all)."""
    valid: set[str] = set()
    if UPGRADE_INI.exists():
        valid |= collect_upgrade_names(UPGRADE_INI)
    if COMMAND_BUTTON_INI.exists():
        valid |= collect_command_names(COMMAND_BUTTON_INI)
    if FACTION_UNIT.exists():
        valid |= collect_object_names(FACTION_UNIT)
    if FACTION_BUILDING.exists():
        valid |= collect_object_names(FACTION_BUILDING)
    if DUMP_FILE.exists():
        valid |= collect_dump_templates(DUMP_FILE)
    if ALLOWLIST_FILE.exists():
        valid |= collect_allowlist(ALLOWLIST_FILE)
    return valid



def parse_archipelago_templates(filepath: Path) -> set[str]:
    """Extract all template names from Archipelago.ini Units= and Buildings=."""
    templates: set[str] = set()
    content = filepath.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"^\s*(Units|Buildings)\s*=\s*(.+)$", content, re.MULTILINE):
        val = m.group(2).split(";")[0].strip()
        for token in re.split(r"[\s,]+", val):
            if token:
                templates.add(token)
    return templates



def is_template_valid(template: str, valid_bases: set[str]) -> bool:
    """Check if template exists or is a valid general-prefixed variant."""
    if template in valid_bases:
        return True
    base, prefix = strip_known_general_prefix(template)
    if prefix and base in valid_bases:
        return True
    return False



def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Archipelago.ini templates")
    parser.add_argument(
        "--warn-non-spawnable",
        action="store_true",
        help="Reserved for future soft warnings; denylisted templates are always errors.",
    )
    _ = parser.parse_args()

    if not ARCHIPELAGO_INI.exists():
        print(f"ERROR: {ARCHIPELAGO_INI} not found", file=sys.stderr)
        return 1

    valid = collect_all_valid_templates()
    archipelago = parse_archipelago_templates(ARCHIPELAGO_INI)
    denylist = load_non_spawnable_templates()

    missing = sorted(t for t in archipelago if not is_template_valid(t, valid))
    if missing:
        print("ERROR: The following templates in Archipelago.ini are not defined in game INI files:", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        print("\nCheck for typos or ensure the template exists in FactionUnit.ini, FactionBuilding.ini, Upgrade.ini, or CommandButton.ini.", file=sys.stderr)
        return 1

    denylisted = sorted(t for t in archipelago if is_denied_template(t, denylist))
    if denylisted:
        print("ERROR: The following templates in Archipelago.ini are denylisted as non-spawnable or unusable:", file=sys.stderr)
        for name in denylisted:
            print(f"  - {name}", file=sys.stderr)
        print("\nRemove them from Data/Archipelago/groups.json or the display-name expansion that produced them.", file=sys.stderr)
        return 1

    print(f"OK: All {len(archipelago)} Archipelago.ini templates are defined and allowed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
