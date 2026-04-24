#!/usr/bin/env python3
"""Shared helpers for Archipelago data generation and validation."""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_DIR = REPO_ROOT / "Data" / "Archipelago"
DEFAULT_NON_SPAWNABLE = DEFAULT_CONFIG_DIR / "non_spawnable_templates.json"
DEFAULT_NAME_OVERRIDES = DEFAULT_CONFIG_DIR / "name_overrides.json"
ASSET_ROOT_ENV_VARS = ("GENERALS_ASSET_ROOT", "GENERALS_GAME_ROOT", "GENERALS_DATA_ROOT")

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


def _normalize_asset_relative_path(relative: Path | str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0].lower() == "data":
        return Path(*parts[1:]) if len(parts) > 1 else Path()
    return path


def _candidate_data_roots(root: Path | str) -> list[Path]:
    base = Path(root).expanduser()
    if not base.is_absolute():
        base = (REPO_ROOT / base).resolve()

    candidates: list[Path] = []
    if base.name.lower() == "data":
        candidates.append(base)
    else:
        candidates.append(base / "Data")
        candidates.append(base)
    return candidates


def iter_game_data_roots(explicit_root: Path | str | None = None) -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()

    raw_roots: list[Path | str] = []
    if explicit_root:
        raw_roots.append(explicit_root)
    for env_name in ASSET_ROOT_ENV_VARS:
        value = os.environ.get(env_name, "").strip()
        if value:
            raw_roots.append(value)
    raw_roots.append(REPO_ROOT)

    for raw_root in raw_roots:
        for candidate in _candidate_data_roots(raw_root):
            try:
                resolved = candidate.resolve()
            except OSError:
                resolved = candidate
            if resolved in seen:
                continue
            seen.add(resolved)
            roots.append(resolved)
    return roots


def default_game_asset_path(relative: Path | str, explicit_root: Path | str | None = None) -> Path:
    """
    Resolve a game-data path from either the repo checkout or an external retail asset root.

    `relative` may be either `Data/...` or a path already relative to the `Data/` directory.
    The first existing candidate wins. If none exist yet, return the first candidate so callers
    still get a deterministic path in error messages and argparse defaults.
    """
    relative_path = Path(relative)
    if relative_path.is_absolute():
        return relative_path

    data_relative = _normalize_asset_relative_path(relative_path)
    first_candidate: Path | None = None
    for data_root in iter_game_data_roots(explicit_root):
        candidate = data_root / data_relative
        if first_candidate is None:
            first_candidate = candidate
        if candidate.exists():
            return candidate
    if first_candidate is not None:
        return first_candidate
    return REPO_ROOT / "Data" / data_relative


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

