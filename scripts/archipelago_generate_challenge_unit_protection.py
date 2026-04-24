#!/usr/bin/env python3
"""Generate and validate the spawned cluster protection runtime config."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from archipelago_data_helpers import REPO_ROOT, iter_game_data_roots


DEFAULT_CONFIG = REPO_ROOT / "Data" / "Archipelago" / "challenge_unit_protection.json"
DEFAULT_OUTPUT = REPO_ROOT / "Data" / "INI" / "ArchipelagoChallengeUnitProtection.ini"
DEFAULT_REPORT = REPO_ROOT / "Data" / "Archipelago" / "generated_challenge_unit_protection_report.txt"

BUCKETS = (
    "zero_damage",
    "reduced_damage_95_fighters",
    "reduced_damage_75_fields",
    "reduced_damage_75_artillery",
    "reduced_damage_98_general_powers",
    "reduced_damage_75_helicopters",
    "immunities",
)
REQUIRED_ENTRY_KEYS = ("player_name", "player_category", "match_kind", "internal_labels", "effect")
VALID_MATCH_KINDS = frozenset(
    {
        "special_power",
        "weapon",
        "object",
        "damage_type",
        "disabled_type",
        "action_type",
    }
)
VALID_ACTION_TYPES = frozenset(
    {
        "ACTION_HIJACK",
        "ACTION_PILOT_SNIPE",
        "ACTION_NEUTRON_CREW_KILL",
        "ACTION_EMP_DISABLE",
        "ACTION_LEAFLET_DROP",
        "ACTION_DISABLE_HACK",
        "ACTION_DEFECTOR",
    }
)
REQUIRED_PLAYER_NAMES = frozenset(
    {
        "SCUD Storm",
        "Particle Cannon",
        "Neutron Missile",
        "Daisy Cutter",
        "EMP Pulse",
        "Anthrax Bomb",
        "Carpet Bomb",
        "China Carpet Bomber",
        "Fuel Air Bomb",
        "A-10 Strike",
        "Artillery Barrage",
        "Spectre Gunship",
        "Comanche",
        "Helix",
        "MOAB",
        "Raptor",
        "King Raptor",
        "Stealth Fighter",
        "Aurora Bomber",
        "Aurora Alpha",
        "Superweapon Aurora variant",
        "MiG",
        "Nuke MiG",
        "Black Napalm MiG",
        "Tomahawk",
        "Crusader/Paladin shells",
        "Humvee missile",
        "Inferno Cannon",
        "Nuke Cannon",
        "Ground toxin fields",
        "Ground radiation fields",
        "Hijacker capture",
        "Jarmen Kell vehicle snipe",
        "Neutron crew kill",
        "EMP disable",
        "Leaflet Drop disable",
        "Black Lotus disable / hack",
        "Defector conversion",
        "EMP / Leaflet disabled state",
        "Black Lotus hacked state",
        "Crew-kill unmanned state",
    }
)

POWER_COVERAGE_EXPECTATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Particle Cannon", ("special_power", "object", "weapon")),
    ("Daisy Cutter", ("special_power", "object", "weapon")),
    ("Fuel Air Bomb", ("special_power", "object", "weapon")),
    ("Carpet Bomb", ("special_power", "object", "weapon")),
    ("China Carpet Bomber", ("special_power",)),
    ("A-10 Strike", ("special_power", "object", "weapon")),
    ("Spectre Gunship", ("special_power", "object", "weapon")),
)

NAME_RE = re.compile(r"^\s*(Object|Weapon|SpecialPower)\s+([A-Za-z0-9_]+)\s*$", re.MULTILINE)
QUOTED_NAME_RE = re.compile(r'"([A-Z][A-Z0-9_]+)"')
REFERENCE_TEMPLATE_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s+(?:unit|building)\s*$", re.MULTILINE)
BIG_ARCHIVE_LABEL_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s+(object|weapon)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ProtectionEntry:
    bucket: str
    player_name: str
    player_category: str
    match_kind: str
    internal_labels: tuple[str, ...]
    effect_kind: str
    damage_multiplier: float | None
    notes: str


class ValidationError(RuntimeError):
    pass


def normalize_notes(value: str) -> str:
    return " ".join(value.split())


def parse_effect(raw: str) -> tuple[str, float | None]:
    if raw == "immunity":
        return ("immunity", None)
    prefix = "damage_multiplier:"
    if not raw.startswith(prefix):
        raise ValidationError(f"Unsupported effect value: {raw}")
    try:
        multiplier = float(raw[len(prefix) :])
    except ValueError as exc:
        raise ValidationError(f"Invalid damage multiplier effect: {raw}") from exc
    if multiplier < 0.0 or multiplier > 1.0:
        raise ValidationError(f"Damage multiplier out of range: {raw}")
    return ("damage_multiplier", multiplier)


def load_entries(config_path: Path) -> list[ProtectionEntry]:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValidationError(f"{config_path} must contain a top-level object")

    entries: list[ProtectionEntry] = []
    seen_required_names: set[str] = set()
    for bucket in BUCKETS:
        bucket_entries = raw.get(bucket)
        if not isinstance(bucket_entries, list) or not bucket_entries:
            raise ValidationError(f"{config_path} bucket {bucket!r} must be a non-empty list")
        for index, entry in enumerate(bucket_entries):
            if not isinstance(entry, dict):
                raise ValidationError(f"{config_path} bucket {bucket!r} entry {index} must be an object")
            missing = [key for key in REQUIRED_ENTRY_KEYS if key not in entry]
            if missing:
                raise ValidationError(
                    f"{config_path} bucket {bucket!r} entry {index} missing keys: {', '.join(missing)}"
                )
            match_kind = str(entry["match_kind"]).strip()
            if match_kind not in VALID_MATCH_KINDS:
                raise ValidationError(
                    f"{config_path} bucket {bucket!r} entry {index} uses unsupported match_kind {match_kind!r}"
                )
            labels = entry["internal_labels"]
            if not isinstance(labels, list) or not labels:
                raise ValidationError(
                    f"{config_path} bucket {bucket!r} entry {index} must declare at least one internal label"
                )
            clean_labels = tuple(str(label).strip() for label in labels if str(label).strip())
            if not clean_labels:
                raise ValidationError(
                    f"{config_path} bucket {bucket!r} entry {index} must declare non-empty internal labels"
                )
            effect_kind, damage_multiplier = parse_effect(str(entry["effect"]).strip())
            notes = normalize_notes(str(entry.get("notes", "")).strip())
            player_name = str(entry["player_name"]).strip()
            if player_name:
                seen_required_names.add(player_name)
            entries.append(
                ProtectionEntry(
                    bucket=bucket,
                    player_name=player_name,
                    player_category=str(entry["player_category"]).strip(),
                    match_kind=match_kind,
                    internal_labels=clean_labels,
                    effect_kind=effect_kind,
                    damage_multiplier=damage_multiplier,
                    notes=notes,
                )
            )

    missing_names = sorted(REQUIRED_PLAYER_NAMES - seen_required_names)
    if missing_names:
        raise ValidationError(
            "challenge_unit_protection.json is missing required player_name coverage: "
            + ", ".join(missing_names)
        )
    return entries


def parse_names_from_ini(data_root: Path) -> tuple[set[str], set[str], set[str]]:
    ini_root = data_root / "INI"
    if not ini_root.is_dir():
        raise ValidationError(f"Expected INI root under {data_root}")

    objects: set[str] = set()
    weapons: set[str] = set()
    special_powers: set[str] = set()
    for path in ini_root.rglob("*.ini"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            raise ValidationError(f"Unable to read {path}") from exc
        for match in NAME_RE.finditer(text):
            kind, name = match.groups()
            if kind == "Object":
                objects.add(name)
            elif kind == "Weapon":
                weapons.add(name)
            elif kind == "SpecialPower":
                special_powers.add(name)
    return (objects, weapons, special_powers)


def parse_quoted_names(path: Path, prefix: str) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {match.group(1) for match in QUOTED_NAME_RE.finditer(text) if match.group(1).startswith(prefix)}


def parse_reference_templates(path: Path) -> set[str]:
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {match.group(1) for match in REFERENCE_TEMPLATE_RE.finditer(text)}


def build_label_catalog() -> dict[str, set[str]]:
    data_roots = [root for root in iter_game_data_roots() if (root / "INI").is_dir()]
    if not data_roots:
        raise ValidationError("Unable to locate a local Data/INI root for protection-label validation")

    objects: set[str] = set()
    weapons: set[str] = set()
    special_powers: set[str] = set()
    for data_root in data_roots:
        root_objects, root_weapons, root_special_powers = parse_names_from_ini(data_root)
        objects.update(root_objects)
        weapons.update(root_weapons)
        special_powers.update(root_special_powers)

    objects.update(
        parse_reference_templates(
            REPO_ROOT / "Data" / "Archipelago" / "reference" / "ArchipelagoThingFactoryTemplates_filtered.txt"
        )
    )

    big_labels_path = REPO_ROOT / "Data" / "Archipelago" / "reference" / "ArchipelagoBIGArchiveLabels.txt"
    if big_labels_path.exists():
        big_text = big_labels_path.read_text(encoding="utf-8", errors="ignore")
        for big_match in BIG_ARCHIVE_LABEL_RE.finditer(big_text):
            name, kind = big_match.groups()
            if kind == "object":
                objects.add(name)
            elif kind == "weapon":
                weapons.add(name)

    special_power_code = parse_quoted_names(
        REPO_ROOT / "GeneralsMD" / "Code" / "GameEngine" / "Source" / "Common" / "RTS" / "SpecialPower.cpp",
        "SPECIAL",
    )
    special_power_code.update(
        parse_quoted_names(
            REPO_ROOT / "GeneralsMD" / "Code" / "GameEngine" / "Source" / "Common" / "RTS" / "SpecialPower.cpp",
            "EARLY_SPECIAL",
        )
    )
    special_power_code.update(
        parse_quoted_names(
            REPO_ROOT / "GeneralsMD" / "Code" / "GameEngine" / "Source" / "Common" / "RTS" / "SpecialPower.cpp",
            "AIRF_SPECIAL",
        )
    )
    special_power_code.update(
        parse_quoted_names(
            REPO_ROOT / "GeneralsMD" / "Code" / "GameEngine" / "Source" / "Common" / "RTS" / "SpecialPower.cpp",
            "SUPW_SPECIAL",
        )
    )
    special_power_code.update(
        parse_quoted_names(
            REPO_ROOT / "GeneralsMD" / "Code" / "GameEngine" / "Source" / "Common" / "RTS" / "SpecialPower.cpp",
            "NUKE_SPECIAL",
        )
    )
    special_power_code.update(
        parse_quoted_names(
            REPO_ROOT / "GeneralsMD" / "Code" / "GameEngine" / "Source" / "Common" / "RTS" / "SpecialPower.cpp",
            "LAZR_SPECIAL",
        )
    )

    damage_types = parse_quoted_names(
        REPO_ROOT / "GeneralsMD" / "Code" / "GameEngine" / "Source" / "GameLogic" / "System" / "Damage.cpp",
        "",
    )
    disabled_types = parse_quoted_names(
        REPO_ROOT / "GeneralsMD" / "Code" / "GameEngine" / "Source" / "Common" / "System" / "DisabledTypes.cpp",
        "DISABLED",
    )

    return {
        "object": objects,
        "weapon": weapons,
        "special_power": special_powers | special_power_code,
        "damage_type": damage_types,
        "disabled_type": disabled_types,
        "action_type": set(VALID_ACTION_TYPES),
    }


def validate_entries(entries: list[ProtectionEntry], catalog: dict[str, set[str]]) -> list[str]:
    unresolved: list[str] = []
    for entry in entries:
        valid_labels = catalog[entry.match_kind]
        for label in entry.internal_labels:
            if label not in valid_labels:
                unresolved.append(
                    f"{entry.bucket}:{entry.player_name}:{entry.match_kind}:{label}"
                )
    return unresolved


def write_output(entries: list[ProtectionEntry], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "; Generated from Data/Archipelago/challenge_unit_protection.json",
        "; Do not edit this file directly.",
        "[ProtectionMeta]",
        f"RuleCount = {len(entries)}",
        "",
    ]
    for index, entry in enumerate(entries):
        lines.extend(
            [
                f"[ProtectionRule{index:03d}]",
                f"Bucket = {entry.bucket}",
                f"PlayerName = {entry.player_name}",
                f"PlayerCategory = {entry.player_category}",
                f"MatchKind = {entry.match_kind}",
                f"InternalLabels = {','.join(entry.internal_labels)}",
                f"EffectKind = {entry.effect_kind}",
                f"DamageMultiplier = {entry.damage_multiplier if entry.damage_multiplier is not None else 0.0}",
                f"Notes = {entry.notes}",
                "",
            ]
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_report(entries: list[ProtectionEntry], report_path: Path, catalog: dict[str, set[str]]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    bucket_counts: dict[str, int] = {bucket: 0 for bucket in BUCKETS}
    player_names = sorted({entry.player_name for entry in entries})
    by_player_name: dict[str, list[ProtectionEntry]] = {}
    for entry in entries:
        by_player_name.setdefault(entry.player_name, []).append(entry)
    lines = [
        "Spawned Cluster Protection Matrix Coverage",
        "=========================================",
        "",
        f"Rules: {len(entries)}",
        f"Player-known entries: {len(player_names)}",
        "",
    ]
    for entry in entries:
        bucket_counts[entry.bucket] += 1
    lines.append("Bucket counts:")
    for bucket in BUCKETS:
        lines.append(f"- {bucket}: {bucket_counts[bucket]}")
    lines.append("")
    lines.append("Power coverage focus:")
    for player_name, expected_match_kinds in POWER_COVERAGE_EXPECTATIONS:
        power_entries = by_player_name.get(player_name, [])
        present_match_kinds = sorted({entry.match_kind for entry in power_entries})
        missing_match_kinds = [kind for kind in expected_match_kinds if kind not in present_match_kinds]
        lines.append(f"- {player_name}:")
        lines.append(f"  expected match kinds: {', '.join(expected_match_kinds)}")
        lines.append(f"  present match kinds: {', '.join(present_match_kinds) if present_match_kinds else '<none>'}")
        lines.append(f"  missing match kinds: {', '.join(missing_match_kinds) if missing_match_kinds else '<none>'}")
        if not power_entries:
            continue
        for entry in power_entries:
            labels = ", ".join(entry.internal_labels)
            effect = (
                "immunity"
                if entry.effect_kind == "immunity"
                else f"damage x{entry.damage_multiplier:.2f}"
            )
            lines.append(
                f"  - [{entry.bucket}] {entry.match_kind} -> {labels} :: {effect}"
            )
            if entry.notes:
                lines.append(f"    note: {entry.notes}")
    lines.append("")
    lines.append("Resolved rules:")
    for entry in entries:
        labels = ", ".join(entry.internal_labels)
        effect = (
            "immunity"
            if entry.effect_kind == "immunity"
            else f"damage x{entry.damage_multiplier:.2f}"
        )
        lines.append(
            f"- [{entry.bucket}] {entry.player_name} ({entry.player_category}) :: "
            f"{entry.match_kind} -> {labels} :: {effect}"
        )
        if entry.notes:
            lines.append(f"  note: {entry.notes}")
    lines.append("")
    lines.append("Catalog sizes:")
    for key in ("object", "weapon", "special_power", "damage_type", "disabled_type", "action_type"):
        lines.append(f"- {key}: {len(catalog[key])}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Archipelago spawned cluster protection config")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Source JSON config path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Generated runtime INI output path.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Readable coverage report path.")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    output_path = Path(args.output)
    report_path = Path(args.report)
    if not config_path.exists():
        print(f"ERROR: {config_path} not found", file=sys.stderr)
        return 1

    try:
        entries = load_entries(config_path)
        catalog = build_label_catalog()
        unresolved = validate_entries(entries, catalog)
        if unresolved:
            sample = "\n".join(f" - {item}" for item in unresolved[:50])
            extra = "" if len(unresolved) <= 50 else f"\n - ... and {len(unresolved) - 50} more"
            raise ValidationError(
                "challenge_unit_protection.json contains unresolved internal labels:\n"
                + sample
                + extra
            )
        write_output(entries, output_path)
        write_report(entries, report_path, catalog)
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote protection runtime config to {output_path}")
    print(f"Wrote protection coverage report to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
