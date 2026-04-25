#!/usr/bin/env python3
"""Fixture-driven local Archipelago bridge for isolated in-game testing."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
import types
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIPELAGO_DIR = REPO_ROOT / "build" / "win32-vcpkg-playtest" / "GeneralsMD" / "Release" / "UserData" / "Archipelago"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "Data" / "Archipelago" / "bridge_fixtures"
DEFAULT_CONFIG_DIR = REPO_ROOT / "Data" / "Archipelago"
DEFAULT_OVERLAY_WORLD_DIR = REPO_ROOT / "vendor" / "archipelago" / "overlay" / "worlds" / "generalszh"
DEFAULT_SLOT_DATA_FILENAME = "Seed-Slot-Data.json"
DEFAULT_VALIDATED_REFERENCE_INI = (
    REPO_ROOT
    / "Data"
    / "Archipelago"
    / "runtime_profiles"
    / "reference-clean"
    / "Data"
    / "INI"
    / "Archipelago.ini"
)
CORE_STRING_KEYS = ("unlockedUnits", "unlockedBuildings", "unlockedGroupIds", "completedChecks")
CORE_INT_KEYS = ("unlockedGenerals", "startingGenerals", "completedLocations")
GENERAL_NAME_TO_INDEX = {
    "airforce": 0,
    "air": 0,
    "laser": 1,
    "superweapon": 2,
    "super": 2,
    "tank": 3,
    "infantry": 4,
    "nuke": 5,
    "toxin": 6,
    "demolition": 7,
    "demo": 7,
    "stealth": 8,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    return json.loads(raw)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    temp_path.replace(path)


def file_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def load_generalszh_slot_helpers():
    package = types.ModuleType("generalszh")
    package.__path__ = [str(DEFAULT_OVERLAY_WORLD_DIR)]
    sys.modules["generalszh"] = package
    from generalszh.slot_data import (  # type: ignore[import-not-found]
        build_testing_slot_data,
        slot_data_sha256,
        translate_runtime_checks,
        validate_slot_data,
    )

    return build_testing_slot_data, slot_data_sha256, translate_runtime_checks, validate_slot_data


def append_event(path: Path, event_type: str, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestampUtc": utc_now(),
        "event": event_type,
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def normalize_string_list(values: Any) -> list[str]:
    if values is None:
        return []
    normalized = {str(value).strip() for value in values if str(value).strip()}
    return sorted(normalized)


def normalize_int_list(values: Any) -> list[int]:
    if values is None:
        return []
    normalized: set[int] = set()
    for value in values:
        normalized.add(int(value))
    return sorted(normalized)


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def canonicalize_session_options(payload: Any) -> dict[str, Any]:
    raw = deepcopy(payload) if isinstance(payload, dict) else {}
    production_multiplier = float(raw.get("productionMultiplier", 1.0) or 1.0)
    if production_multiplier <= 0.0:
        production_multiplier = 1.0
    return {
        "startingCashBonus": int(raw.get("startingCashBonus", 0) or 0),
        "productionMultiplier": production_multiplier,
        "disableZoomLimit": normalize_bool(raw.get("disableZoomLimit", False)),
        "starterGenerals": normalize_int_list(raw.get("starterGenerals")),
    }


def default_session() -> dict[str, Any]:
    return {
        "sessionVersion": 1,
        "seedId": "local-in-game-test",
        "slotName": "Local Test",
        "sessionNonce": "",
        "unlockedUnits": [],
        "unlockedBuildings": [],
        "unlockedGroupIds": [],
        "unlockedGenerals": [],
        "startingGenerals": [],
        "completedLocations": [],
        "completedChecks": [],
        "receivedItems": [],
        "lastAppliedReceivedItemSequence": -1,
        "sessionOptions": canonicalize_session_options({}),
        "notes": [],
    }


def resolve_fixture_path(value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_file():
        return candidate.resolve()
    fixture_candidate = DEFAULT_FIXTURE_DIR / value
    if fixture_candidate.is_file():
        return fixture_candidate.resolve()
    if fixture_candidate.suffix.lower() != ".json":
        fixture_with_suffix = fixture_candidate.with_suffix(".json")
        if fixture_with_suffix.is_file():
            return fixture_with_suffix.resolve()
    raise FileNotFoundError(f"Fixture not found: {value}")


def load_fixture_payload(fixture_path: Path | None) -> dict[str, Any] | None:
    if fixture_path is None:
        return None
    payload = load_json(fixture_path)
    if payload is None:
        raise ValueError(f"Fixture is empty: {fixture_path}")
    return canonicalize_session(payload)


def canonicalize_session(payload: Any) -> dict[str, Any]:
    raw = deepcopy(payload) if isinstance(payload, dict) else {}
    session = default_session()
    session.update({k: v for k, v in raw.items() if k not in session})

    session["sessionVersion"] = int(raw.get("sessionVersion", session["sessionVersion"]))
    session["seedId"] = str(raw.get("seedId", session["seedId"]))
    session["slotName"] = str(raw.get("slotName", session["slotName"]))
    session["sessionNonce"] = str(raw.get("sessionNonce", session["sessionNonce"]))
    session["lastAppliedReceivedItemSequence"] = int(raw.get("lastAppliedReceivedItemSequence", session["lastAppliedReceivedItemSequence"]))
    session["sessionOptions"] = canonicalize_session_options(raw.get("sessionOptions"))
    session["notes"] = raw.get("notes", session["notes"])

    for key in CORE_STRING_KEYS:
        session[key] = normalize_string_list(raw.get(key))
    for key in CORE_INT_KEYS:
        session[key] = normalize_int_list(raw.get(key))
    received_items = []
    for item in raw.get("receivedItems", []) or []:
        if not isinstance(item, dict):
            continue
        group_id = str(item.get("groupId", "")).strip()
        kind = str(item.get("kind", "unlock_group")).strip() or "unlock_group"
        try:
            sequence = int(item.get("sequence"))
        except (TypeError, ValueError):
            continue
        if not group_id:
            continue
        received_items.append({"sequence": sequence, "kind": kind, "groupId": group_id})
    session["receivedItems"] = sorted(received_items, key=lambda item: item["sequence"])

    return session


def build_inbound_payload(session: dict[str, Any], slot_reference: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "bridgeVersion": 1,
        "sessionVersion": session["sessionVersion"],
        "seedId": session["seedId"],
        "slotName": session["slotName"],
        "sessionNonce": session.get("sessionNonce", ""),
        "unlockedUnits": session["unlockedUnits"],
        "unlockedBuildings": session["unlockedBuildings"],
        "unlockedGroupIds": session["unlockedGroupIds"],
        "unlockedGenerals": session["unlockedGenerals"],
        "startingGenerals": session["startingGenerals"],
        "completedLocations": session["completedLocations"],
        "completedChecks": session["completedChecks"],
        "receivedItems": session["receivedItems"],
        "sessionOptions": session["sessionOptions"],
    }
    if slot_reference is not None:
        payload.update(slot_reference)
    return payload


def materialize_seed_slot_data(
    archipelago_dir: Path,
    session: dict[str, Any],
    unlock_preset: str = "default",
) -> tuple[dict[str, Any], dict[str, Any]]:
    build_testing_slot_data, _, _, validate_slot_data = load_generalszh_slot_helpers()
    slot_data = build_testing_slot_data(
        seed_id=session["seedId"],
        slot_name=session["slotName"],
        session_nonce=session.get("sessionNonce", ""),
        unlock_preset=unlock_preset,
    )
    validate_slot_data(slot_data)
    slot_data_path = archipelago_dir / DEFAULT_SLOT_DATA_FILENAME
    atomic_write_json(slot_data_path, slot_data)
    slot_reference = {
        "slotDataVersion": slot_data["version"],
        "slotDataPath": DEFAULT_SLOT_DATA_FILENAME,
        "slotDataHash": file_sha256(slot_data_path),
    }
    return slot_data, slot_reference


def translate_outbound_runtime_checks(slot_data: dict[str, Any], outbound: Any) -> list[int]:
    if not isinstance(outbound, dict):
        return []
    completed_checks = normalize_string_list(outbound.get("completedChecks"))
    if not completed_checks:
        return []
    _, _, translate_runtime_checks, _ = load_generalszh_slot_helpers()
    return translate_runtime_checks(slot_data, completed_checks)


def normalize_general_token(value: str) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def resolve_general_index(name: str) -> int:
    token = normalize_general_token(name)
    if token not in GENERAL_NAME_TO_INDEX:
        known = ", ".join(sorted(GENERAL_NAME_TO_INDEX.keys()))
        raise ValueError(f"Unknown starter general '{name}'. Known values: {known}")
    return GENERAL_NAME_TO_INDEX[token]


def load_unlock_group_catalog(preset_name: str = "default", ini_path: Path | None = None) -> list[str]:
    """Load the list of item-pool group names.

    When *ini_path* points to a regenerated Archipelago.ini (e.g. with
    granularity overrides), group names are read directly from that file
    so synthetic received-items match the runtime group names.
    """
    if ini_path is not None and ini_path.exists():
        ini_text = ini_path.read_text(encoding="utf-8", errors="replace")
        group_names = re.findall(r"^UnlockGroup\s+(\S+)\s*$", ini_text, re.MULTILINE)
        # Parse ItemPool per group; default is Yes when absent
        catalog: list[str] = []
        for gname in group_names:
            # Find the group block and check ItemPool
            pattern = rf"^UnlockGroup\s+{re.escape(gname)}\s*\n(.*?)^End\s*$"
            match = re.search(pattern, ini_text, re.MULTILINE | re.DOTALL)
            if not match:
                continue
            block = match.group(1)
            item_pool_match = re.search(r"ItemPool\s*=\s*(\S+)", block)
            if item_pool_match and item_pool_match.group(1).lower() in ("no", "false", "0", "off"):
                continue
            catalog.append(gname)
        return catalog

    groups_path = DEFAULT_CONFIG_DIR / "groups.json"
    presets_path = DEFAULT_CONFIG_DIR / "presets.json"
    if not groups_path.exists() or not presets_path.exists() or not DEFAULT_VALIDATED_REFERENCE_INI.exists():
        return []

    groups = json.loads(groups_path.read_text(encoding="utf-8"))
    presets = json.loads(presets_path.read_text(encoding="utf-8"))
    preset = presets.get(preset_name, {})
    group_order = preset.get("group_order", list(groups.keys()))
    validated_group_names = set(
        re.findall(r"^UnlockGroup\s+(\S+)\s*$", DEFAULT_VALIDATED_REFERENCE_INI.read_text(encoding="utf-8"), re.MULTILINE)
    )

    catalog: list[str] = []
    for group_id in group_order:
        group = groups.get(group_id)
        if not isinstance(group, dict):
            continue
        if group_id not in validated_group_names:
            continue
        if not bool(group.get("item_pool", True)):
            continue
        catalog.append(group_id)
    return catalog


def build_synthetic_received_items(count: int, seed: int, preset_name: str = "default", ini_path: Path | None = None) -> list[dict[str, Any]]:
    if count <= 0:
        return []

    unlockable_groups = load_unlock_group_catalog(preset_name=preset_name, ini_path=ini_path)
    if not unlockable_groups:
        return []

    pool = list(unlockable_groups)
    random.Random(seed).shuffle(pool)
    selected = pool[: min(count, len(pool))]
    return [
        {"sequence": sequence + 1, "kind": "unlock_group", "groupId": group_id}
        for sequence, group_id in enumerate(selected)
    ]


def apply_session_seed(
    session: dict[str, Any],
    starter_general: str | None,
    random_unlock_count: int | None,
    random_unlock_seed: int,
    starting_cash_bonus: int,
    production_multiplier: float,
    disable_zoom_limit: bool,
    ini_path: Path | None = None,
) -> dict[str, Any]:
    seeded = canonicalize_session(session)
    session_options = canonicalize_session_options(seeded.get("sessionOptions"))

    if starter_general:
        starter_index = resolve_general_index(starter_general)
        seeded["startingGenerals"] = [starter_index]
        seeded["unlockedGenerals"] = [starter_index]
        session_options["starterGenerals"] = [starter_index]

    if random_unlock_count is not None:
        seeded["receivedItems"] = build_synthetic_received_items(random_unlock_count, random_unlock_seed, ini_path=ini_path)
        seeded["lastAppliedReceivedItemSequence"] = -1
        seeded["unlockedUnits"] = []
        seeded["unlockedBuildings"] = []
        seeded["unlockedGroupIds"] = []

    session_options["startingCashBonus"] = int(starting_cash_bonus)
    session_options["productionMultiplier"] = float(production_multiplier) if production_multiplier > 0.0 else 1.0
    session_options["disableZoomLimit"] = bool(disable_zoom_limit)
    seeded["sessionOptions"] = canonicalize_session_options(session_options)
    return seeded


def merge_outbound_into_session(
    session: dict[str, Any],
    outbound: Any,
    slot_data: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, list[Any]]]:
    merged = deepcopy(session)
    changes: dict[str, list[Any]] = {}

    if not isinstance(outbound, dict):
        return merged, changes

    for key in CORE_STRING_KEYS:
        before = set(merged[key])
        after = before | set(normalize_string_list(outbound.get(key)))
        if after != before:
            merged[key] = sorted(after)
            changes[key] = sorted(after - before)

    for key in CORE_INT_KEYS:
        before_int = set(merged[key])
        after_int = before_int | set(normalize_int_list(outbound.get(key)))
        if key == "completedLocations" and slot_data is not None:
            after_int |= set(translate_outbound_runtime_checks(slot_data, outbound))
        if after_int != before_int:
            merged[key] = sorted(after_int)
            changes[key] = sorted(after_int - before_int)

    outbound_sequence = outbound.get("lastAppliedReceivedItemSequence")
    if outbound_sequence is not None:
        outbound_sequence = int(outbound_sequence)
        if outbound_sequence > int(merged.get("lastAppliedReceivedItemSequence", -1)):
            merged["lastAppliedReceivedItemSequence"] = outbound_sequence
            changes["lastAppliedReceivedItemSequence"] = [outbound_sequence]

    return merged, changes


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def session_counts(session: dict[str, Any]) -> dict[str, int]:
    return {key: len(session[key]) for key in (*CORE_STRING_KEYS, *CORE_INT_KEYS)}


def format_changes(changes: dict[str, list[Any]]) -> str:
    if not changes:
        return "none"
    parts = [f"{key}={len(values)}" for key, values in changes.items()]
    return ", ".join(parts)


def initialize_session(
    session_path: Path,
    events_path: Path,
    fixture_session: dict[str, Any] | None = None,
    reset_session: bool = False,
    preserve_session: bool = False,
    starter_general: str | None = None,
    random_unlock_count: int | None = None,
    random_unlock_seed: int = 0,
    starting_cash_bonus: int = 0,
    production_multiplier: float = 1.0,
    disable_zoom_limit: bool = False,
    ini_path: Path | None = None,
) -> dict[str, Any]:
    current = load_json(session_path)
    if preserve_session and current is not None:
        session = canonicalize_session(current)
        session = apply_session_seed(
            session,
            starter_general=None,
            random_unlock_count=None,
            random_unlock_seed=random_unlock_seed,
            starting_cash_bonus=starting_cash_bonus,
            production_multiplier=production_multiplier,
            disable_zoom_limit=disable_zoom_limit,
        )
        atomic_write_json(session_path, session)
        append_event(events_path, "session_preserved", {"sessionPath": str(session_path)})
        return session

    if current is None or reset_session:
        session = canonicalize_session(fixture_session if fixture_session is not None else {})
        session["sessionNonce"] = utc_now()
        session = apply_session_seed(
            session,
            starter_general=starter_general,
            random_unlock_count=random_unlock_count,
            random_unlock_seed=random_unlock_seed,
            starting_cash_bonus=starting_cash_bonus,
            production_multiplier=production_multiplier,
            disable_zoom_limit=disable_zoom_limit,
            ini_path=ini_path,
        )
        atomic_write_json(session_path, session)
        append_event(
            events_path,
            "session_created" if current is None else "session_reset",
            {
                "sessionPath": str(session_path),
                "fromFixture": fixture_session is not None,
            },
        )
        return session

    session = canonicalize_session(current)
    session = apply_session_seed(
        session,
        starter_general=None,
        random_unlock_count=None,
        random_unlock_seed=random_unlock_seed,
        starting_cash_bonus=starting_cash_bonus,
        production_multiplier=production_multiplier,
        disable_zoom_limit=disable_zoom_limit,
    )
    if current != session:
        atomic_write_json(session_path, session)
        append_event(events_path, "session_normalized", {"sessionPath": str(session_path)})
    return session


def run_cycle(
    archipelago_dir: Path,
    session_path: Path,
    inbound_path: Path,
    outbound_path: Path,
    events_path: Path,
    fixture_session: dict[str, Any] | None = None,
    reset_session: bool = False,
    preserve_session: bool = False,
    starter_general: str | None = None,
    random_unlock_count: int | None = None,
    random_unlock_seed: int = 0,
    starting_cash_bonus: int = 0,
    production_multiplier: float = 1.0,
    disable_zoom_limit: bool = False,
    ini_path: Path | None = None,
    emit_slot_data: bool = True,
    unlock_preset: str = "default",
) -> dict[str, Any]:
    archipelago_dir.mkdir(parents=True, exist_ok=True)
    session = initialize_session(
        session_path,
        events_path,
        fixture_session=fixture_session,
        reset_session=reset_session,
        preserve_session=preserve_session,
        starter_general=starter_general,
        random_unlock_count=random_unlock_count,
        random_unlock_seed=random_unlock_seed,
        starting_cash_bonus=starting_cash_bonus,
        production_multiplier=production_multiplier,
        disable_zoom_limit=disable_zoom_limit,
        ini_path=ini_path,
    )

    if reset_session and outbound_path.exists():
        outbound_path.unlink()
        append_event(events_path, "outbound_cleared", {"path": str(outbound_path)})

    slot_data = None
    slot_reference = None
    if emit_slot_data:
        slot_data, slot_reference = materialize_seed_slot_data(archipelago_dir, session, unlock_preset=unlock_preset)

    inbound_payload = build_inbound_payload(session, slot_reference=slot_reference)
    inbound_text = canonical_json(inbound_payload)
    existing_inbound = load_json(inbound_path)
    wrote_inbound = existing_inbound != inbound_payload
    if wrote_inbound:
        atomic_write_json(inbound_path, inbound_payload)
        append_event(
            events_path,
            "inbound_written",
            {
                "path": str(inbound_path),
                "sessionVersion": session["sessionVersion"],
                "counts": session_counts(inbound_payload),
                "hash": hash(inbound_text),
            },
        )

    outbound = load_json(outbound_path)
    merged_session, changes = merge_outbound_into_session(session, outbound, slot_data=slot_data)
    merged = bool(changes)
    if merged:
        atomic_write_json(session_path, merged_session)
        append_event(
            events_path,
            "outbound_merged",
            {
                "path": str(outbound_path),
                "changes": changes,
            },
        )

        if emit_slot_data:
            slot_data, slot_reference = materialize_seed_slot_data(archipelago_dir, merged_session, unlock_preset=unlock_preset)
        refreshed_inbound = build_inbound_payload(merged_session, slot_reference=slot_reference)
        if refreshed_inbound != inbound_payload:
            atomic_write_json(inbound_path, refreshed_inbound)
            append_event(
                events_path,
                "inbound_written",
                {
                    "path": str(inbound_path),
                    "sessionVersion": merged_session["sessionVersion"],
                    "counts": session_counts(refreshed_inbound),
                    "hash": hash(canonical_json(refreshed_inbound)),
                },
            )
            wrote_inbound = True

    return {
        "wrote_inbound": wrote_inbound,
        "merged": merged,
        "changes": changes,
        "session": merged_session if merged else session,
        "slot_data": slot_data,
        "slot_reference": slot_reference,
    }


def run_once(archipelago_dir: Path, session_path: Path, inbound_path: Path, outbound_path: Path, events_path: Path) -> tuple[bool, bool]:
    status = run_cycle(archipelago_dir, session_path, inbound_path, outbound_path, events_path)
    return status["wrote_inbound"], status["merged"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the fixture-driven local Archipelago bridge sidecar.")
    parser.add_argument("--archipelago-dir", type=Path, default=DEFAULT_ARCHIPELAGO_DIR, help="UserData/Archipelago directory to monitor.")
    parser.add_argument("--session", type=Path, default=None, help="Optional path to LocalBridgeSession.json.")
    parser.add_argument("--fixture", type=str, default=None, help="Optional fixture name or JSON path used to seed/reset LocalBridgeSession.json.")
    parser.add_argument("--reset-session", action="store_true", help="Overwrite LocalBridgeSession.json from the selected fixture or the default empty session before monitoring.")
    parser.add_argument("--preserve-session", action="store_true", help="Preserve LocalBridgeSession.json progression state and only update transient session options.")
    parser.add_argument("--starter-general", type=str, default=None, help="Starter general to seed for a reset session (default handled by wrapper).")
    parser.add_argument("--random-unlock-count", type=int, default=None, help="Seed a deterministic random set of unlocked AP items by generating synthetic receivedItems.")
    parser.add_argument("--random-unlock-seed", type=int, default=0, help="Seed used when generating synthetic random receivedItems.")
    parser.add_argument("--starting-cash-bonus", type=int, default=0, help="Additional starting cash granted at mission start.")
    parser.add_argument("--production-multiplier", type=float, default=1.0, help="Production-speed multiplier for the local player. 2.0 means double speed.")
    parser.add_argument("--disable-zoom-limit", action="store_true", help="Disable the tactical camera zoom limit for this session.")
    parser.add_argument("--poll-interval", type=float, default=0.5, help="Polling interval in seconds.")
    parser.add_argument("--once", action="store_true", help="Process the current session/outbound files once and exit.")
    parser.add_argument("--ini-path", type=Path, default=None, help="Path to the runtime Archipelago.ini. When set, synthetic received-items use group names from this INI instead of the reference INI.")
    parser.add_argument("--unlock-preset", type=str, default="default", choices=("default", "minimal"), help="Testing slot-data preset to emit.")
    parser.add_argument("--no-slot-data", action="store_true", help="Keep legacy local bridge mode and do not emit Seed-Slot-Data.json.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archipelago_dir = args.archipelago_dir.resolve()
    session_path = args.session.resolve() if args.session else archipelago_dir / "LocalBridgeSession.json"
    inbound_path = archipelago_dir / "Bridge-Inbound.json"
    outbound_path = archipelago_dir / "Bridge-Outbound.json"
    events_path = archipelago_dir / "Bridge-Events.jsonl"
    fixture_path = resolve_fixture_path(args.fixture)
    fixture_session = load_fixture_payload(fixture_path)
    ini_path = args.ini_path.resolve() if args.ini_path else None

    try:
        if args.once:
            status = run_cycle(
                archipelago_dir,
                session_path,
                inbound_path,
                outbound_path,
                events_path,
                fixture_session=fixture_session,
                reset_session=args.reset_session,
                preserve_session=args.preserve_session,
                starter_general=args.starter_general,
                random_unlock_count=args.random_unlock_count,
                random_unlock_seed=args.random_unlock_seed,
                starting_cash_bonus=args.starting_cash_bonus,
                production_multiplier=args.production_multiplier,
                disable_zoom_limit=args.disable_zoom_limit,
                ini_path=ini_path,
                emit_slot_data=not args.no_slot_data,
                unlock_preset=args.unlock_preset,
            )
            print(
                "[archipelago-bridge-local] Ready: "
                f"counts={session_counts(status['session'])} merged={format_changes(status['changes'])}",
                flush=True,
            )
            return 0

        print(f"[archipelago-bridge-local] Monitoring {archipelago_dir}", flush=True)
        if fixture_path is not None:
            print(f"[archipelago-bridge-local] Fixture: {fixture_path}", flush=True)
        print(
            "[archipelago-bridge-local] Edit LocalBridgeSession.json to simulate incoming AP state. "
            "The game writes progress to Bridge-Outbound.json and this sidecar merges it back.",
            flush=True,
        )
        announced_ready = False
        while True:
            status = run_cycle(
                archipelago_dir,
                session_path,
                inbound_path,
                outbound_path,
                events_path,
                fixture_session=fixture_session,
                reset_session=args.reset_session and not announced_ready,
                preserve_session=args.preserve_session,
                starter_general=args.starter_general,
                random_unlock_count=args.random_unlock_count,
                random_unlock_seed=args.random_unlock_seed,
                starting_cash_bonus=args.starting_cash_bonus,
                production_multiplier=args.production_multiplier,
                disable_zoom_limit=args.disable_zoom_limit,
                ini_path=ini_path,
                emit_slot_data=not args.no_slot_data,
                unlock_preset=args.unlock_preset,
            )
            if not announced_ready:
                print(
                    "[archipelago-bridge-local] Inbound ready: "
                    f"counts={session_counts(status['session'])}",
                    flush=True,
                )
                announced_ready = True
            if status["wrote_inbound"]:
                print(
                    "[archipelago-bridge-local] Wrote Bridge-Inbound.json "
                    f"with counts={session_counts(status['session'])}",
                    flush=True,
                )
            if status["merged"]:
                print(
                    "[archipelago-bridge-local] Merged Bridge-Outbound.json changes: "
                    f"{format_changes(status['changes'])}",
                    flush=True,
                )
            time.sleep(max(args.poll_interval, 0.1))
    except KeyboardInterrupt:
        print("[archipelago-bridge-local] Stopped.", flush=True)
        return 0
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in bridge/session file: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - script-level guard
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
