#!/usr/bin/env python3
"""Build ingame_names.json from display_names.json and Data/English/generals.csf."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DISPLAY_NAMES = REPO_ROOT / "Data" / "Archipelago" / "display_names.json"
DEFAULT_CSF = REPO_ROOT / "Data" / "English" / "generals.csf"
DEFAULT_OUTPUT = REPO_ROOT / "Data" / "Archipelago" / "ingame_names.json"
DEFAULT_NAME_OVERRIDES = REPO_ROOT / "Data" / "Archipelago" / "name_overrides.json"

LABEL_ID = b" LBL"
STRING_ID = b" RTS"
WIDE_STRING_ID = b"WRTS"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from archipelago_data_helpers import load_name_overrides


def decode_csf_string(data: bytes, offset: int) -> tuple[str, int]:
    string_id = data[offset : offset + 4]
    offset += 4
    if string_id not in {STRING_ID, WIDE_STRING_ID}:
        raise ValueError(f"Unexpected CSF string id: {string_id!r}")
    (length,) = struct.unpack_from("<I", data, offset)
    offset += 4
    values = struct.unpack_from(f"<{length}H", data, offset)
    offset += length * 2
    text = "".join(chr((~value) & 0xFFFF) for value in values).rstrip("\x00")
    if string_id == WIDE_STRING_ID:
        (extra_length,) = struct.unpack_from("<I", data, offset)
        offset += 4 + extra_length
    return text, offset



def load_csf_strings(path: Path) -> dict[str, str]:
    data = path.read_bytes()
    if len(data) < 24:
        raise ValueError(f"CSF file is too small: {path}")
    file_id = data[:4]
    if file_id != b" FSC":
        raise ValueError(f"Unexpected CSF header: {file_id!r}")

    _, version, num_labels, _, _, _ = struct.unpack_from("<6I", data, 0)
    if version == 0:
        raise ValueError(f"Unexpected CSF version 0 in {path}")

    offset = 24
    strings: dict[str, str] = {}
    for _ in range(num_labels):
        label_id = data[offset : offset + 4]
        offset += 4
        if label_id != LABEL_ID:
            raise ValueError(f"Unexpected CSF label id: {label_id!r}")
        string_count, label_length = struct.unpack_from("<II", data, offset)
        offset += 8
        label = data[offset : offset + label_length].decode("ascii")
        offset += label_length
        resolved = ""
        for _entry in range(string_count):
            resolved, offset = decode_csf_string(data, offset)
        strings[label] = resolved
    return strings



def main() -> int:
    ap = argparse.ArgumentParser(description="Build ingame_names.json from generals.csf")
    ap.add_argument("--display-names", type=Path, default=DEFAULT_DISPLAY_NAMES)
    ap.add_argument("--csf", type=Path, default=DEFAULT_CSF)
    ap.add_argument("--name-overrides", type=Path, default=DEFAULT_NAME_OVERRIDES)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    display = json.loads(args.display_names.read_text(encoding="utf-8"))
    csf = load_csf_strings(args.csf)
    display_name_overrides, _ = load_name_overrides(args.name_overrides)

    missing: list[str] = []
    output: dict[str, str] = {
        "_comment": "Maps DisplayName localization keys to exact in-game strings from Data/English/generals.csf, with explicit fallback overrides when a key is missing.",
    }
    for display_key in sorted(k for k, v in display.items() if isinstance(v, list) and not k.startswith("_")):
        value = display_name_overrides.get(display_key) or csf.get(display_key)
        if value is None and ":" in display_key:
            value = display_name_overrides.get(display_key.split(":", 1)[1])
        if value is None:
            missing.append(display_key)
            continue
        output[display_key] = value

    if missing:
        print(
            "Warning: missing localized strings for display keys without explicit overrides: "
            + ", ".join(missing[:20])
            + (" ..." if len(missing) > 20 else ""),
            file=sys.stderr,
        )

    args.output.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {args.output} ({len(output) - 1} labels, {len(missing)} unresolved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
