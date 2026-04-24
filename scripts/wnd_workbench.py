#!/usr/bin/env python3
"""Extract, compose, audit, and stage WND files for Archipelago shell work."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKING_SET = REPO_ROOT / "Data" / "Archipelago" / "wnd_working_set.json"
DEFAULT_SOURCE_ROOT = REPO_ROOT / "build" / "archipelago" / "wnd-work" / "source"
DEFAULT_OVERRIDE_ROOT = REPO_ROOT / "build" / "archipelago" / "wnd-work" / "override"
DEFAULT_MANIFEST_ROOT = REPO_ROOT / "build" / "archipelago" / "wnd-work" / "manifests"
DEFAULT_RUNTIME_DATA_ROOT = REPO_ROOT / "build" / "archipelago" / "wnd-work" / "runtime-data"
DEFAULT_TRANSITIONS_INI = REPO_ROOT / "Data" / "INI" / "WindowTransitions.ini"
DEFAULT_PATCH_RECIPE = REPO_ROOT / "Data" / "Archipelago" / "UI" / "main_menu_patch_recipe.json"
DEFAULT_REQUIRED_CONTROLS = REPO_ROOT / "Data" / "Archipelago" / "UI" / "ap_shell_required_controls.json"
DEFAULT_AP_WND_ROOT = REPO_ROOT / "Data" / "Archipelago" / "UI" / "Wnd"
DEFAULT_AP_STRINGS = REPO_ROOT / "Data" / "Archipelago" / "UI" / "ap_shell_strings.json"
DEFAULT_AP_FIXTURE = REPO_ROOT / "Data" / "Archipelago" / "UI" / "ap_shell_fixture.json"

STATEMENT_KEYWORDS = {
    "STARTLAYOUTBLOCK",
    "ENDLAYOUTBLOCK",
    "WINDOW",
    "CHILD",
    "ENDALLCHILDREN",
    "END",
}

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from archipelago_build_localized_name_map import DEFAULT_CSF, load_csf_strings  # noqa: E402


@dataclass
class WndWindow:
    """Parsed WND window node with ordered properties."""

    properties: list[tuple[str, str]] = field(default_factory=list)
    children: list["WndWindow"] = field(default_factory=list)

    def get_raw(self, key: str, default: str = "") -> str:
        key = key.upper()
        for existing_key, value in self.properties:
            if existing_key == key:
                return value
        return default

    def set_raw(self, key: str, value: str) -> None:
        key = key.upper()
        for index, (existing_key, _) in enumerate(self.properties):
            if existing_key == key:
                self.properties[index] = (existing_key, value)
                return
        self.properties.append((key, value))

    def get_name(self) -> str:
        return strip_quotes(self.get_raw("NAME"))


def load_working_set(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    files = data.get("files", [])
    normalized: list[dict[str, str]] = []
    for entry in files:
        raw_path = entry.get("path", "")
        if not raw_path:
            continue
        normalized.append(
            {
                "path": raw_path.replace("\\", "/"),
                "role": entry.get("role", ""),
            }
        )
    return normalized


def load_required_controls(path: Path) -> dict[str, set[str]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        file_name: {entry for entry in entries if entry}
        for file_name, entries in raw.items()
        if isinstance(entries, list)
    }


def auto_find_window_archive() -> Path:
    candidates = [
        REPO_ROOT / "build" / "win32-vcpkg-playtest" / "GeneralsMD" / "Release" / "WindowZH.big",
        REPO_ROOT / "build" / "win32-vcpkg-debug" / "GeneralsMD" / "Debug" / "WindowZH.big",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    matches = sorted(REPO_ROOT.glob("build/**/WindowZH.big"))
    if matches:
        return matches[0]

    raise FileNotFoundError("Unable to auto-locate WindowZH.big under build/.")


def parse_big_index(big_path: Path) -> list[tuple[str, int, int]]:
    data = big_path.read_bytes()
    if len(data) < 16:
        raise ValueError(f"{big_path} is too small to be a BIG archive")
    magic = data[:4]
    if magic not in (b"BIGF", b"BIG4"):
        raise ValueError(f"{big_path} is not a BIG archive (magic={magic!r})")

    file_count = int.from_bytes(data[8:12], "big")
    pos = 16
    entries: list[tuple[str, int, int]] = []
    for _ in range(file_count):
        offset = int.from_bytes(data[pos : pos + 4], "big")
        size = int.from_bytes(data[pos + 4 : pos + 8], "big")
        pos += 8
        name_end = data.index(b"\x00", pos)
        name = data[pos:name_end].decode("ascii", errors="replace").replace("\\", "/")
        pos = name_end + 1
        entries.append((name, offset, size))
    return entries


def extract_selected_from_big(big_path: Path, selected_paths: list[str], output_root: Path, force: bool) -> list[Path]:
    selected = {path.replace("\\", "/") for path in selected_paths}
    entries = parse_big_index(big_path)
    data = big_path.read_bytes()
    written: list[Path] = []
    found = set()
    for name, offset, size in entries:
        if name not in selected:
            continue
        out_path = output_root / Path(name)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists() and not force:
            written.append(out_path)
            found.add(name)
            continue
        out_path.write_bytes(data[offset : offset + size])
        written.append(out_path)
        found.add(name)

    missing = sorted(selected - found)
    if missing:
        raise FileNotFoundError(f"Missing selected WNDs in {big_path}: {missing}")
    return written


def normalize_statement_line(raw_line: str) -> str | None:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith(";;"):
        return None
    first_token = stripped.split(None, 1)[0]
    if first_token in STATEMENT_KEYWORDS and "=" not in stripped:
        return first_token
    return stripped


def iter_wnd_statements(text: str):
    buffer: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_statement_line(raw_line)
        if line is None:
            continue
        if not buffer and line in STATEMENT_KEYWORDS:
            yield line
            continue

        buffer.append(line)
        if ";" in line:
            statement = " ".join(buffer)
            statement = statement[: statement.rfind(";") + 1]
            yield statement
            buffer.clear()

    if buffer:
        yield " ".join(buffer)


def parse_assignment(statement: str) -> tuple[str, str] | None:
    if "=" not in statement or not statement.endswith(";"):
        return None
    key, value = statement[:-1].split("=", 1)
    return key.strip().upper(), value.strip()


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def quote_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def parse_screenrect(value: str) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for chunk in value.split(","):
        if ":" not in chunk:
            continue
        key, numbers = chunk.split(":", 1)
        ints = [int(part) for part in numbers.split()]
        result[key.strip().upper()] = ints
    return result


def set_ordered_property(properties: list[tuple[str, str]], key: str, value: str) -> None:
    key = key.upper()
    for index, (existing_key, _) in enumerate(properties):
        if existing_key == key:
            properties[index] = (existing_key, value)
            return
    properties.append((key, value))


def ordered_properties_to_dict(properties: list[tuple[str, str]]) -> dict[str, str]:
    return {key: value for key, value in properties}


def parse_wnd_text(text: str) -> dict[str, Any]:
    layout_properties: list[tuple[str, str]] = []
    file_version: str | None = None
    roots: list[WndWindow] = []
    stack: list[WndWindow] = []
    in_layout_block = False

    for statement in iter_wnd_statements(text):
        if statement == "STARTLAYOUTBLOCK":
            in_layout_block = True
            continue
        if statement == "ENDLAYOUTBLOCK":
            in_layout_block = False
            continue
        if statement == "WINDOW":
            node = WndWindow()
            if stack:
                stack[-1].children.append(node)
            else:
                roots.append(node)
            stack.append(node)
            continue
        if statement in {"CHILD", "ENDALLCHILDREN"}:
            continue
        if statement == "END":
            if stack:
                stack.pop()
            continue

        parsed = parse_assignment(statement)
        if parsed is None:
            continue
        key, value = parsed
        if key == "FILE_VERSION":
            file_version = strip_quotes(value)
            continue
        if in_layout_block:
            set_ordered_property(layout_properties, key, strip_quotes(value))
            continue
        if not stack:
            continue
        stack[-1].set_raw(key, value)

    if stack:
        raise ValueError("WND parse ended with unclosed WINDOW blocks")

    return {
        "file_version": file_version,
        "layout": ordered_properties_to_dict(layout_properties),
        "layout_properties": layout_properties,
        "windows": roots,
    }


def format_screenrect(upper_left: list[int], bottom_right: list[int], creation_resolution: list[int] | None = None) -> str:
    creation_resolution = creation_resolution or [800, 600]
    return (
        f"UPPERLEFT: {upper_left[0]} {upper_left[1]}, "
        f"BOTTOMRIGHT: {bottom_right[0]} {bottom_right[1]}, "
        f"CREATIONRESOLUTION: {creation_resolution[0]} {creation_resolution[1]}"
    )


def serialize_window(node: WndWindow, lines: list[str], depth: int) -> None:
    indent = "  " * depth
    lines.append(f"{indent}WINDOW")
    for key, value in node.properties:
        lines.append(f"{indent}  {key} = {value};")
    if node.children:
        for child in node.children:
            lines.append(f"{indent}  CHILD")
            serialize_window(child, lines, depth + 1)
        lines.append(f"{indent}  ENDALLCHILDREN")
    lines.append(f"{indent}END")


def serialize_wnd_document(document: dict[str, Any]) -> str:
    lines: list[str] = []
    file_version = document.get("file_version")
    if file_version:
        lines.append(f"FILE_VERSION = {file_version};")
    layout_props: list[tuple[str, str]] = document.get("layout_properties", [])
    if layout_props:
        lines.append("STARTLAYOUTBLOCK")
        for key, value in layout_props:
            lines.append(f"  {key} = {value};")
        lines.append("ENDLAYOUTBLOCK")
    for root in document.get("windows", []):
        serialize_window(root, lines, 0)
    return "\n".join(lines) + "\n"


def flatten_windows(windows: list[WndWindow], depth: int = 0, parent_name: str | None = None) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for node in windows:
        props = ordered_properties_to_dict(node.properties)
        name = strip_quotes(props.get("NAME", ""))
        record = {
            "name": name,
            "parent_name": parent_name,
            "depth": depth,
            "window_type": strip_quotes(props.get("WINDOWTYPE", "")),
            "style": strip_quotes(props.get("STYLE", "")),
            "screen_rect": parse_screenrect(props.get("SCREENRECT", "")) if "SCREENRECT" in props else {},
            "status": [part for part in strip_quotes(props.get("STATUS", "")).split("+") if part],
            "callbacks": {
                "system": strip_quotes(props.get("SYSTEMCALLBACK", "")),
                "input": strip_quotes(props.get("INPUTCALLBACK", "")),
                "tooltip": strip_quotes(props.get("TOOLTIPCALLBACK", "")),
                "draw": strip_quotes(props.get("DRAWCALLBACK", "")),
            },
            "child_count": len(node.children),
        }
        flat.append(record)
        flat.extend(flatten_windows(node.children, depth + 1, name or parent_name))
    return flat


def build_tree_windows(windows: list[WndWindow]) -> list[dict[str, Any]]:
    tree: list[dict[str, Any]] = []
    for node in windows:
        props = ordered_properties_to_dict(node.properties)
        tree.append(
            {
                "name": strip_quotes(props.get("NAME", "")),
                "window_type": strip_quotes(props.get("WINDOWTYPE", "")),
                "style": strip_quotes(props.get("STYLE", "")),
                "screen_rect": parse_screenrect(props.get("SCREENRECT", "")) if "SCREENRECT" in props else {},
                "status": [part for part in strip_quotes(props.get("STATUS", "")).split("+") if part],
                "children": build_tree_windows(node.children),
            }
        )
    return tree


def parse_transition_references(path: Path) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    if not path.exists():
        return refs
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("WinName"):
            continue
        _, value = stripped.split("=", 1)
        win_name = value.strip()
        if ":" not in win_name:
            continue
        wnd_name, control_name = win_name.split(":", 1)
        refs.setdefault(wnd_name.strip(), set()).add(f"{wnd_name.strip()}:{control_name.strip()}")
    return refs


def audit_flat_windows(flat_windows: list[dict[str, Any]], transition_refs: set[str], required_controls: set[str]) -> dict[str, Any]:
    names = [
        record["name"]
        for record in flat_windows
        if record.get("name") and not record["name"].endswith(":")
    ]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    missing_types = [record["name"] for record in flat_windows if record.get("name") and not record.get("window_type")]
    invalid_rects: list[str] = []
    for record in flat_windows:
        rect = record.get("screen_rect", {})
        upper_left = rect.get("UPPERLEFT")
        bottom_right = rect.get("BOTTOMRIGHT")
        if upper_left and bottom_right and (
            len(upper_left) < 2
            or len(bottom_right) < 2
            or bottom_right[0] < upper_left[0]
            or bottom_right[1] < upper_left[1]
        ):
            invalid_rects.append(record.get("name") or "<unnamed>")

    known_names = set(names)
    missing_transition_targets = sorted(name for name in transition_refs if name not in known_names)
    missing_required_controls = sorted(name for name in required_controls if name not in known_names)
    return {
        "duplicate_names": duplicates,
        "missing_name_count": sum(1 for record in flat_windows if not record.get("name")),
        "missing_windowtype": sorted(name for name in missing_types if name),
        "invalid_screenrect": invalid_rects,
        "missing_transition_targets": missing_transition_targets,
        "missing_required_controls": missing_required_controls,
    }


def build_manifest_entry(
    path: Path,
    transition_refs_by_file: dict[str, set[str]],
    required_controls_by_file: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    required_controls_by_file = required_controls_by_file or {}
    parsed = parse_wnd_text(path.read_text(encoding="latin-1"))
    flat_windows = flatten_windows(parsed["windows"])
    wnd_name = path.name
    audit = audit_flat_windows(
        flat_windows,
        transition_refs_by_file.get(wnd_name, set()),
        required_controls_by_file.get(wnd_name, set()),
    )
    return {
        "file": str(path),
        "wnd_name": wnd_name,
        "file_version": parsed["file_version"],
        "layout": {
            "init": parsed["layout"].get("LAYOUTINIT", ""),
            "update": parsed["layout"].get("LAYOUTUPDATE", ""),
            "shutdown": parsed["layout"].get("LAYOUTSHUTDOWN", ""),
        },
        "summary": {
            "window_count": len(flat_windows),
            "named_window_count": sum(1 for record in flat_windows if record.get("name")),
            "max_depth": max((record["depth"] for record in flat_windows), default=0),
        },
        "audit": audit,
        "flat_windows": flat_windows,
        "tree_windows": build_tree_windows(parsed["windows"]),
    }


def write_manifest(
    input_path: Path,
    output_path: Path,
    transitions_ini: Path,
    required_controls_path: Path | None = DEFAULT_REQUIRED_CONTROLS,
) -> dict[str, Any]:
    transition_refs_by_file = parse_transition_references(transitions_ini)
    required_controls = load_required_controls(required_controls_path) if required_controls_path else {}
    files = sorted(input_path.rglob("*.wnd")) if input_path.is_dir() else [input_path]

    manifest = {
        "input": str(input_path),
        "transitions_ini": str(transitions_ini),
        "required_controls_path": str(required_controls_path) if required_controls_path else "",
        "file_count": len(files),
        "files": [build_manifest_entry(path, transition_refs_by_file, required_controls) for path in files],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def print_extract_summary(written: list[Path], label: str) -> None:
    print(f"[wnd-workbench] {label}: {len(written)} file(s)")
    for path in written:
        print(f"  - {path}")


def find_window_reference(
    windows: list[WndWindow],
    target_name: str,
    parent: WndWindow | None = None,
) -> tuple[WndWindow, WndWindow | None, list[WndWindow], int] | None:
    for index, node in enumerate(windows):
        if node.get_name() == target_name:
            return node, parent, windows, index
        found = find_window_reference(node.children, target_name, node)
        if found:
            return found
    return None


def require_window(document: dict[str, Any], target_name: str) -> tuple[WndWindow, WndWindow | None, list[WndWindow], int]:
    found = find_window_reference(document.get("windows", []), target_name)
    if found is None:
        raise KeyError(f"Recipe target not found: {target_name}")
    return found


def apply_recipe_operation(document: dict[str, Any], operation: dict[str, Any]) -> None:
    op = operation["op"]
    if op == "copy_control":
        source_node, _, _, _ = require_window(document, operation["source"])
        clone = copy.deepcopy(source_node)
        clone.set_raw("NAME", quote_value(operation["new_name"]))
        if "insert_after" in operation:
            _, _, siblings, insert_index = require_window(document, operation["insert_after"])
            siblings.insert(insert_index + 1, clone)
        else:
            _, parent, siblings, source_index = require_window(document, operation["source"])
            _ = parent
            siblings.insert(source_index + 1, clone)
        return

    if op == "set_rect":
        node, _, _, _ = require_window(document, operation["target"])
        node.set_raw(
            "SCREENRECT",
            format_screenrect(operation["upper_left"], operation["bottom_right"]),
        )
        return

    if op == "set_text":
        node, _, _, _ = require_window(document, operation["target"])
        node.set_raw("TEXT", quote_value(operation["text"]))
        return

    if op == "set_name":
        node, _, _, _ = require_window(document, operation["target"])
        node.set_raw("NAME", quote_value(operation["name"]))
        return

    if op == "set_status":
        node, _, _, _ = require_window(document, operation["target"])
        node.set_raw("STATUS", operation["status"])
        return

    if op == "insert_after":
        node, _, siblings, index = require_window(document, operation["target"])
        siblings.pop(index)
        _, _, target_siblings, target_index = require_window(document, operation["after"])
        target_siblings.insert(target_index + 1, node)
        return

    if op == "move_control":
        node, _, siblings, index = require_window(document, operation["target"])
        siblings.pop(index)
        _, _, target_siblings, target_index = require_window(document, operation["after"])
        target_siblings.insert(target_index + 1, node)
        return

    if op == "delete_control":
        _, _, siblings, index = require_window(document, operation["target"])
        siblings.pop(index)
        return

    raise ValueError(f"Unsupported recipe op: {op}")


def apply_recipe_to_text(text: str, recipe: dict[str, Any]) -> str:
    document = parse_wnd_text(text)
    for operation in recipe.get("operations", []):
        apply_recipe_operation(document, operation)
    return serialize_wnd_document(document)


def prune_override_tree(override_root: Path) -> None:
    if override_root.exists():
        shutil.rmtree(override_root)
    override_root.mkdir(parents=True, exist_ok=True)


def write_string_file(base_strings: dict[str, str], extra_strings: dict[str, str], output_path: Path) -> Path:
    merged = dict(base_strings)
    merged.update(extra_strings)

    def escape_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for label in sorted(merged):
        lines.append(label)
        lines.append(f'"{escape_text(merged[label])}"')
        lines.append("END")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def compose_override_tree(
    source_root: Path,
    override_root: Path,
    runtime_data_root: Path,
    recipe_path: Path,
    ap_wnd_root: Path,
    strings_path: Path,
    fixture_path: Path,
    csf_path: Path,
) -> list[Path]:
    prune_override_tree(override_root)
    written: list[Path] = []

    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    source_file = source_root / Path(recipe["source"])
    if not source_file.exists():
        raise FileNotFoundError(f"Recipe source missing: {source_file}")
    output_file = override_root / Path(recipe["output"])
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        apply_recipe_to_text(source_file.read_text(encoding="latin-1"), recipe),
        encoding="latin-1",
    )
    written.append(output_file)

    for wnd_path in sorted(ap_wnd_root.glob("*.wnd")):
        target = override_root / "Window" / "Menus" / wnd_path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(wnd_path, target)
        written.append(target)

    if runtime_data_root.exists():
        shutil.rmtree(runtime_data_root)
    (runtime_data_root / "Data" / "Archipelago").mkdir(parents=True, exist_ok=True)
    base_strings = load_csf_strings(csf_path)
    extra_strings = json.loads(strings_path.read_text(encoding="utf-8"))
    string_file = write_string_file(base_strings, extra_strings, runtime_data_root / "Data" / "Generals.str")
    written.append(string_file)
    fixture_target = runtime_data_root / "Data" / "Archipelago" / "APShellReviewFixture.json"
    shutil.copy2(fixture_path, fixture_target)
    written.append(fixture_target)

    return written


def deploy_override_tree(override_root: Path, runtime_dir: Path, runtime_data_root: Path, force: bool) -> list[Path]:
    if not override_root.exists():
        raise FileNotFoundError(f"Override root does not exist: {override_root}")
    if not runtime_dir.exists():
        raise FileNotFoundError(f"Runtime directory does not exist: {runtime_dir}")

    deployed: list[Path] = []
    for src in sorted(override_root.rglob("*.wnd")):
        rel = src.relative_to(override_root)
        dst = runtime_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and not force:
            deployed.append(dst)
            continue
        shutil.copy2(src, dst)
        deployed.append(dst)

    if runtime_data_root.exists():
        for src in sorted(path for path in runtime_data_root.rglob("*") if path.is_file()):
            rel = src.relative_to(runtime_data_root)
            dst = runtime_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists() and not force:
                deployed.append(dst)
                continue
            shutil.copy2(src, dst)
            deployed.append(dst)
    return deployed


def command_extract(args: argparse.Namespace) -> int:
    archive = args.archive or auto_find_window_archive()
    working_set = load_working_set(args.working_set)
    selected_paths = [entry["path"] for entry in working_set]
    written = extract_selected_from_big(archive, selected_paths, args.source_root, args.force)
    print_extract_summary(written, "Extracted source working set")
    return 0


def command_compose(args: argparse.Namespace) -> int:
    written = compose_override_tree(
        args.source_root,
        args.override_root,
        args.runtime_data_root,
        args.recipe,
        args.ap_wnd_root,
        args.strings,
        args.fixture,
        args.csf,
    )
    print_extract_summary(written, "Composed AP shell overrides")
    return 0


def command_manifest(args: argparse.Namespace) -> int:
    manifest = write_manifest(args.input, args.output, args.transitions_ini, args.required_controls)
    print(f"[wnd-workbench] Manifest written: {args.output} ({manifest['file_count']} file(s))")
    for entry in manifest["files"]:
        audit = entry["audit"]
        print(
            "  - "
            f"{entry['wnd_name']}: windows={entry['summary']['window_count']}, "
            f"duplicates={len(audit['duplicate_names'])}, "
            f"missing_required={len(audit['missing_required_controls'])}, "
            f"missing_transition_targets={len(audit['missing_transition_targets'])}"
        )
    return 0


def command_deploy(args: argparse.Namespace) -> int:
    written = deploy_override_tree(args.override_root, args.runtime_dir, args.runtime_data_root, args.force)
    print_extract_summary(written, "Deployed override tree")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WND workbench automation for GeneralsAP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="Extract selected WNDs from WindowZH.big")
    extract.add_argument("--archive", type=Path, default=None, help="Path to WindowZH.big")
    extract.add_argument("--working-set", type=Path, default=DEFAULT_WORKING_SET, help="Path to WND working-set JSON")
    extract.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT, help="Output directory for extracted source WNDs")
    extract.add_argument("--force", action="store_true", help="Overwrite existing files")
    extract.set_defaults(func=command_extract)

    compose = subparsers.add_parser("compose", help="Generate recipe-driven overrides and runtime data")
    compose.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    compose.add_argument("--override-root", type=Path, default=DEFAULT_OVERRIDE_ROOT)
    compose.add_argument("--runtime-data-root", type=Path, default=DEFAULT_RUNTIME_DATA_ROOT)
    compose.add_argument("--recipe", type=Path, default=DEFAULT_PATCH_RECIPE)
    compose.add_argument("--ap-wnd-root", type=Path, default=DEFAULT_AP_WND_ROOT)
    compose.add_argument("--strings", type=Path, default=DEFAULT_AP_STRINGS)
    compose.add_argument("--fixture", type=Path, default=DEFAULT_AP_FIXTURE)
    compose.add_argument("--csf", type=Path, default=DEFAULT_CSF)
    compose.set_defaults(func=command_compose)

    manifest = subparsers.add_parser("manifest", help="Build JSON manifest and audit for a WND file or tree")
    manifest.add_argument("input", type=Path, help="WND file or directory to inspect")
    manifest.add_argument("--output", type=Path, required=True, help="Path to output manifest JSON")
    manifest.add_argument("--transitions-ini", type=Path, default=DEFAULT_TRANSITIONS_INI, help="WindowTransitions.ini path for cross-reference audit")
    manifest.add_argument("--required-controls", type=Path, default=DEFAULT_REQUIRED_CONTROLS, help="JSON file of required AP controls by WND file")
    manifest.set_defaults(func=command_manifest)

    deploy = subparsers.add_parser("deploy", help="Copy loose override WNDs into staged runtime")
    deploy.add_argument("--override-root", type=Path, default=DEFAULT_OVERRIDE_ROOT)
    deploy.add_argument("--runtime-data-root", type=Path, default=DEFAULT_RUNTIME_DATA_ROOT)
    deploy.add_argument("--runtime-dir", type=Path, required=True)
    deploy.add_argument("--force", action="store_true", help="Overwrite existing loose runtime files")
    deploy.set_defaults(func=command_deploy)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
