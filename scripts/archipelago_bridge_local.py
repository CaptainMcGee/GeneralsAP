#!/usr/bin/env python3
"""Fixture-driven local Archipelago bridge for isolated in-game testing."""

from __future__ import annotations

import argparse
import json
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIPELAGO_DIR = REPO_ROOT / "build" / "localtest-install" / "UserData" / "Archipelago"
CORE_STRING_KEYS = ("unlockedUnits", "unlockedBuildings", "unlockedGroupIds", "completedChecks")
CORE_INT_KEYS = ("unlockedGenerals", "startingGenerals", "completedLocations")


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


def default_session() -> dict[str, Any]:
    return {
        "sessionVersion": 1,
        "seedId": "local-in-game-test",
        "slotName": "Local Test",
        "unlockedUnits": [],
        "unlockedBuildings": [],
        "unlockedGroupIds": [],
        "unlockedGenerals": [],
        "startingGenerals": [],
        "completedLocations": [],
        "completedChecks": [],
        "receivedItems": [],
        "lastAppliedReceivedItemSequence": -1,
        "notes": [],
    }


def canonicalize_session(payload: Any) -> dict[str, Any]:
    raw = deepcopy(payload) if isinstance(payload, dict) else {}
    session = default_session()
    session.update({k: v for k, v in raw.items() if k not in session})

    session["sessionVersion"] = int(raw.get("sessionVersion", session["sessionVersion"]))
    session["seedId"] = str(raw.get("seedId", session["seedId"]))
    session["slotName"] = str(raw.get("slotName", session["slotName"]))
    session["lastAppliedReceivedItemSequence"] = int(raw.get("lastAppliedReceivedItemSequence", session["lastAppliedReceivedItemSequence"]))
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


def build_inbound_payload(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "bridgeVersion": 1,
        "sessionVersion": session["sessionVersion"],
        "seedId": session["seedId"],
        "slotName": session["slotName"],
        "unlockedUnits": session["unlockedUnits"],
        "unlockedBuildings": session["unlockedBuildings"],
        "unlockedGroupIds": session["unlockedGroupIds"],
        "unlockedGenerals": session["unlockedGenerals"],
        "startingGenerals": session["startingGenerals"],
        "completedLocations": session["completedLocations"],
        "completedChecks": session["completedChecks"],
        "receivedItems": session["receivedItems"],
    }


def merge_outbound_into_session(session: dict[str, Any], outbound: Any) -> tuple[dict[str, Any], dict[str, list[Any]]]:
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


def initialize_session(session_path: Path, events_path: Path) -> dict[str, Any]:
    current = load_json(session_path)
    if current is None:
        session = canonicalize_session({})
        atomic_write_json(session_path, session)
        append_event(events_path, "session_created", {"sessionPath": str(session_path)})
        return session

    session = canonicalize_session(current)
    if current != session:
        atomic_write_json(session_path, session)
        append_event(events_path, "session_normalized", {"sessionPath": str(session_path)})
    return session


def run_cycle(archipelago_dir: Path, session_path: Path, inbound_path: Path, outbound_path: Path, events_path: Path) -> dict[str, Any]:
    archipelago_dir.mkdir(parents=True, exist_ok=True)
    session = initialize_session(session_path, events_path)

    inbound_payload = build_inbound_payload(session)
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
    merged_session, changes = merge_outbound_into_session(session, outbound)
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

        refreshed_inbound = build_inbound_payload(merged_session)
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
    }


def run_once(archipelago_dir: Path, session_path: Path, inbound_path: Path, outbound_path: Path, events_path: Path) -> tuple[bool, bool]:
    status = run_cycle(archipelago_dir, session_path, inbound_path, outbound_path, events_path)
    return status["wrote_inbound"], status["merged"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the fixture-driven local Archipelago bridge sidecar.")
    parser.add_argument("--archipelago-dir", type=Path, default=DEFAULT_ARCHIPELAGO_DIR, help="UserData/Archipelago directory to monitor.")
    parser.add_argument("--session", type=Path, default=None, help="Optional path to LocalBridgeSession.json.")
    parser.add_argument("--poll-interval", type=float, default=0.5, help="Polling interval in seconds.")
    parser.add_argument("--once", action="store_true", help="Process the current session/outbound files once and exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archipelago_dir = args.archipelago_dir.resolve()
    session_path = args.session.resolve() if args.session else archipelago_dir / "LocalBridgeSession.json"
    inbound_path = archipelago_dir / "Bridge-Inbound.json"
    outbound_path = archipelago_dir / "Bridge-Outbound.json"
    events_path = archipelago_dir / "Bridge-Events.jsonl"

    try:
        if args.once:
            status = run_cycle(archipelago_dir, session_path, inbound_path, outbound_path, events_path)
            print(
                "[archipelago-bridge-local] Ready: "
                f"counts={session_counts(status['session'])} merged={format_changes(status['changes'])}",
                flush=True,
            )
            return 0

        print(f"[archipelago-bridge-local] Monitoring {archipelago_dir}", flush=True)
        print(
            "[archipelago-bridge-local] Edit LocalBridgeSession.json to simulate incoming AP state. "
            "The game writes progress to Bridge-Outbound.json and this sidecar merges it back.",
            flush=True,
        )
        announced_ready = False
        while True:
            status = run_cycle(archipelago_dir, session_path, inbound_path, outbound_path, events_path)
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
