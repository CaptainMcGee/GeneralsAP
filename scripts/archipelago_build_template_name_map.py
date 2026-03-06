#!/usr/bin/env python3
"""Build template_ingame_names.json from INI metadata, build buttons, and generals.csf."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from archipelago_build_localized_name_map import load_csf_strings
from archipelago_data_helpers import default_game_asset_path, load_name_overrides

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_DISPLAY_NAMES = (
    REPO_ROOT / "Data" / "Archipelago" / "reference" / "archipelago_template_display_names.json"
)
DEFAULT_CSF = default_game_asset_path(Path("Data") / "English" / "generals.csf")
DEFAULT_COMMAND_BUTTON = default_game_asset_path(Path("Data") / "INI" / "CommandButton.ini")
DEFAULT_FACTION_UNIT = default_game_asset_path(Path("Data") / "INI" / "Object" / "FactionUnit.ini")
DEFAULT_FACTION_BUILDING = default_game_asset_path(Path("Data") / "INI" / "Object" / "FactionBuilding.ini")
DEFAULT_NAME_OVERRIDES = REPO_ROOT / "Data" / "Archipelago" / "name_overrides.json"
DEFAULT_UNRESOLVED_NOTES = REPO_ROOT / "Data" / "Archipelago" / "reference" / "unresolved_template_name_notes.json"
DEFAULT_OUTPUT = REPO_ROOT / "Data" / "Archipelago" / "template_ingame_names.json"
BUILD_COMMANDS = frozenset(("UNIT_BUILD", "DOZER_CONSTRUCT"))


@dataclass
class TemplateMeta:
    display_name: str | None = None
    parent: str | None = None
    build_variations: list[str] = field(default_factory=list)


def strip_comment(line: str) -> str:
    pos = line.find(";")
    if pos >= 0:
        return line[:pos]
    return line


def load_unresolved_notes(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(template): value
        for template, value in raw.items()
        if isinstance(template, str) and not template.startswith("_") and isinstance(value, dict)
    }


def parse_object_metadata(path: Path) -> dict[str, TemplateMeta]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    result: dict[str, TemplateMeta] = {}
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        stripped = raw.strip()
        is_top_level = raw == raw.lstrip()
        name: str | None = None
        parent: str | None = None

        if is_top_level and stripped.startswith("ObjectReskin "):
            parts = stripped.split()
            if len(parts) >= 3:
                name = parts[1].strip()
                parent = parts[2].strip()
        elif is_top_level and stripped.startswith("Object "):
            parts = stripped.split()
            if len(parts) >= 2:
                name = parts[1].strip()

        if not name:
            i += 1
            continue

        i += 1
        body_lines: list[str] = []
        while i < n:
            end_line = lines[i]
            if end_line == end_line.lstrip() and end_line.strip() == "End":
                break
            body_lines.append(end_line)
            i += 1

        meta = result.get(name, TemplateMeta())
        meta.parent = parent
        for raw_body in body_lines:
            line = strip_comment(raw_body).strip()
            if not line:
                continue
            if line.startswith("DisplayName"):
                match = re.search(r"=\s*(\S+)", line)
                if match:
                    meta.display_name = match.group(1).strip()
            elif line.startswith("BuildVariations"):
                match = re.search(r"=\s*(.+)$", line)
                if match:
                    meta.build_variations = [token for token in match.group(1).split() if token]
        result[name] = meta
        i += 1

    return result


def parse_command_button_labels(path: Path) -> dict[str, list[str]]:
    content = path.read_text(encoding="utf-8", errors="replace")
    buttons: dict[str, list[str]] = {}
    pattern = re.compile(r"^CommandButton\s+(\w+)\s*\n(.*?)^End\s*$", re.MULTILINE | re.DOTALL)
    for match in pattern.finditer(content):
        body = match.group(2)
        command = ""
        target = ""
        text_label = ""
        for raw in body.splitlines():
            line = strip_comment(raw).strip()
            if not line:
                continue
            if line.startswith("Command"):
                command = re.sub(r"^Command\s*=\s*", "", line, flags=re.I).strip()
            elif line.startswith("Object"):
                target = re.sub(r"^Object\s*=\s*", "", line, flags=re.I).strip()
            elif line.startswith("TextLabel"):
                text_label = re.sub(r"^TextLabel\s*=\s*", "", line, flags=re.I).strip()
        if command not in BUILD_COMMANDS or not target or not text_label:
            continue
        buttons.setdefault(target, [])
        if text_label not in buttons[target]:
            buttons[target].append(text_label)
    return buttons


def resolve_localized_key(key: str, csf_strings: dict[str, str], display_name_overrides: dict[str, str]) -> str | None:
    candidates = [key]
    if ":" in key:
        candidates.append(key.split(":", 1)[1])
    for candidate in candidates:
        if candidate in display_name_overrides:
            return display_name_overrides[candidate]
        if candidate in csf_strings:
            return csf_strings[candidate]
    lowered = {candidate.lower() for candidate in candidates}
    for source, value in display_name_overrides.items():
        if source.lower() in lowered:
            return value
    for source, value in csf_strings.items():
        if source.lower() in lowered:
            return value
    return None


def resolve_template_name(
    template: str,
    metadata: dict[str, TemplateMeta],
    build_button_labels: dict[str, list[str]],
    csf_strings: dict[str, str],
    display_name_overrides: dict[str, str],
    template_name_overrides: dict[str, str],
    memo: dict[str, str | None],
    source_info: dict[str, dict[str, object]],
    stack: set[str] | None = None,
) -> str | None:
    if template in template_name_overrides:
        source_info[template] = {"source": "template_override"}
        return template_name_overrides[template]
    if template in memo:
        return memo[template]

    stack = stack or set()
    if template in stack:
        memo[template] = None
        return None
    stack.add(template)

    meta = metadata.get(template, TemplateMeta())

    if meta.display_name:
        localized = resolve_localized_key(meta.display_name, csf_strings, display_name_overrides)
        if localized:
            source_info[template] = {"source": "display_name", "key": meta.display_name}
            memo[template] = localized
            return localized

    if meta.parent:
        localized = resolve_template_name(
            meta.parent,
            metadata,
            build_button_labels,
            csf_strings,
            display_name_overrides,
            template_name_overrides,
            memo,
            source_info,
            stack,
        )
        if localized:
            source_info[template] = {"source": "parent", "template": meta.parent}
            memo[template] = localized
            return localized

    if meta.build_variations:
        names = []
        unresolved = []
        for child in meta.build_variations:
            child_name = resolve_template_name(
                child,
                metadata,
                build_button_labels,
                csf_strings,
                display_name_overrides,
                template_name_overrides,
                memo,
                source_info,
                stack,
            )
            if child_name:
                names.append(child_name)
            else:
                unresolved.append(child)
        unique_names = sorted(set(names))
        if len(unique_names) == 1:
            source_info[template] = {
                "source": "build_variations",
                "templates": meta.build_variations,
                "unresolved": unresolved,
            }
            memo[template] = unique_names[0]
            return unique_names[0]

    button_keys = build_button_labels.get(template, [])
    localized_buttons = [
        resolve_localized_key(button_key, csf_strings, display_name_overrides)
        for button_key in button_keys
    ]
    unique_buttons = sorted({label for label in localized_buttons if label})
    if len(unique_buttons) == 1:
        source_info[template] = {"source": "build_button", "key": button_keys[0]}
        memo[template] = unique_buttons[0]
        return unique_buttons[0]

    memo[template] = None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build template_ingame_names.json from INI metadata and generals.csf")
    parser.add_argument("--template-display-names", type=Path, default=DEFAULT_TEMPLATE_DISPLAY_NAMES)
    parser.add_argument("--csf", type=Path, default=DEFAULT_CSF)
    parser.add_argument("--command-buttons", type=Path, default=DEFAULT_COMMAND_BUTTON)
    parser.add_argument("--faction-unit", type=Path, default=DEFAULT_FACTION_UNIT)
    parser.add_argument("--faction-building", type=Path, default=DEFAULT_FACTION_BUILDING)
    parser.add_argument("--name-overrides", type=Path, default=DEFAULT_NAME_OVERRIDES)
    parser.add_argument("--unresolved-notes", type=Path, default=DEFAULT_UNRESOLVED_NOTES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    template_to_display = json.loads(args.template_display_names.read_text(encoding="utf-8"))
    csf_strings = load_csf_strings(args.csf)
    display_name_overrides, template_name_overrides = load_name_overrides(args.name_overrides)
    unresolved_notes = load_unresolved_notes(args.unresolved_notes)
    metadata = parse_object_metadata(args.faction_unit)
    metadata.update(parse_object_metadata(args.faction_building))
    build_button_labels = parse_command_button_labels(args.command_buttons)

    for template, display_name in template_to_display.items():
        if template.startswith("_") or not isinstance(display_name, str) or not display_name.strip():
            continue
        meta = metadata.get(template, TemplateMeta())
        if not meta.display_name:
            meta.display_name = display_name.strip()
        metadata[template] = meta

    templates = sorted(set(metadata) | set(build_button_labels))
    memo: dict[str, str | None] = {}
    source_info: dict[str, dict[str, object]] = {}
    output: dict[str, object] = {
        "_comment": (
            "Maps template names to player-facing localized strings. Uses object DisplayName first, "
            "then inherited parent/build-variation names, then build-button TextLabel when a template "
            "has no direct DisplayName."
        ),
        "_sources": source_info,
        "_unresolved": [],
        "_unresolved_notes": {},
    }

    unresolved: list[str] = []
    for template in templates:
        localized = resolve_template_name(
            template,
            metadata,
            build_button_labels,
            csf_strings,
            display_name_overrides,
            template_name_overrides,
            memo,
            source_info,
        )
        if localized:
            output[template] = localized
        else:
            unresolved.append(template)

    output["_unresolved"] = unresolved
    missing_notes = [template for template in unresolved if template not in unresolved_notes]
    if missing_notes:
        raise ValueError(
            "Missing unresolved-template review notes for: " + ", ".join(sorted(missing_notes))
        )
    output["_unresolved_notes"] = {template: unresolved_notes[template] for template in unresolved}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    resolved_count = len([k for k, v in output.items() if isinstance(v, str) and not k.startswith("_")])
    print(f"Wrote {args.output} ({resolved_count} templates, {len(unresolved)} unresolved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

