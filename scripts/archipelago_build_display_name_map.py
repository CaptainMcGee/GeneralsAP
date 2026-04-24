#!/usr/bin/env python3
"""
Build display_names.json (display name -> templates) from template->display_name mapping.

Templates sharing an in-game display name are tied together - e.g. OBJECT:Redguard
maps to ChinaInfantryRedguard, ChinaInfantryParadeRedGuard, CINE_ChinaInfantryParadeRedGuard.

Usage:
  python archipelago_build_display_name_map.py [--input FILE] [--output FILE]
"""

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPO_ROOT / "Data" / "Archipelago" / "reference" / "archipelago_template_display_names.json"
DEFAULT_OUTPUT = REPO_ROOT / "Data" / "Archipelago" / "display_names.json"


def main():
    ap = argparse.ArgumentParser(description="Build display name -> templates mapping")
    ap.add_argument("--input", "-i", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found. Run archipelago_extract_template_display_names.py first.")
        return 1

    template_to_display = json.loads(args.input.read_text(encoding="utf-8"))
    display_to_templates: dict[str, list[str]] = {}

    for template, display_name in template_to_display.items():
        if not display_name or not template:
            continue
        if display_name not in display_to_templates:
            display_to_templates[display_name] = []
        display_to_templates[display_name].append(template)

    for key in display_to_templates:
        display_to_templates[key] = sorted(display_to_templates[key])

    out = dict(display_to_templates)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {args.output} ({len(display_to_templates)} display names)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
