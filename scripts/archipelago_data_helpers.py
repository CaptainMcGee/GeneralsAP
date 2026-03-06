#!/usr/bin/env python3
"""Shared helpers for Archipelago data generation and validation."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_DIR = REPO_ROOT / "Data" / "Archipelago"
DEFAULT_NON_SPAWNABLE = DEFAULT_CONFIG_DIR / "non_spawnable_templates.json"
DEFAULT_NAME_OVERRIDES = DEFAULT_CONFIG_DIR / "name_overrides.json"

KNOWN_PREFIX_TO_GENERAL = {
    "AirF": "Air Force",
    "Lazr": "Laser",
    "SupW": "Superweapon",
    "Tank": "Tank",
    "Infa": "Infantry",
    "Nuke": "Nuke",
    "Demo": "Demolition",
    "Slth": "Stealth",
    "Toxin": "Toxin",
    "Chem": "Toxin",
}
KNOWN_PREFIX_LOWER = frozenset(x.lower() for x in KNOWN_PREFIX_TO_GENERAL.keys())


def strip_known_general_prefix(name: str) -> tuple[str, str | None]:
    pos = name.find("_")
    if pos < 0:
        return (name, None)
    prefix = name[:pos]
    if prefix.lower() in KNOWN_PREFIX_LOWER:
        return (name[pos + 1 :], prefix)
    return (name, None)



def load_non_spawnable_templates(path: Path | None = None) -> set[str]:
    path = path or DEFAULT_NON_SPAWNABLE
    if not path.exists():
        return set()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        templates = raw
    else:
        templates = raw.get("templates", [])
    return {str(x).strip() for x in templates if str(x).strip()}



def is_denied_template(template: str, denied: set[str]) -> bool:
    if not template or not denied:
        return False
    base, _ = strip_known_general_prefix(template)
    return template in denied or base in denied



def filter_denied_templates_preserve_order(items: list[str], denied: set[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        if is_denied_template(item, denied):
            continue
        result.append(item)
    return result



def ensure_no_denied_templates(items, denied: set[str], context: str) -> None:
    violations = sorted({item for item in items if is_denied_template(str(item), denied)})
    if violations:
        raise ValueError(f"{context} resolved denylisted templates: {', '.join(violations)}")



def load_name_overrides(path: Path | None = None) -> tuple[dict[str, str], dict[str, str]]:
    path = path or DEFAULT_NAME_OVERRIDES
    if not path.exists():
        return ({}, {})
    raw = json.loads(path.read_text(encoding="utf-8"))
    display_name_overrides = {
        str(k): str(v)
        for k, v in raw.get("display_name_overrides", {}).items()
        if str(k).strip() and str(v).strip()
    }
    template_overrides = {
        str(k): str(v)
        for k, v in raw.get("template_overrides", {}).items()
        if str(k).strip() and str(v).strip()
    }
    return (display_name_overrides, template_overrides)
