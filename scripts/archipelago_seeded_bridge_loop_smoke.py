#!/usr/bin/env python3
"""Checkpoint 2 smoke: fixture slot data -> inbound -> runtime outbound -> AP IDs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.archipelago_bridge_local import (  # noqa: E402
    DEFAULT_SLOT_DATA_FILENAME,
    atomic_write_json,
    load_generalszh_slot_helpers,
    run_cycle,
)

DEFAULT_RUNTIME_CHECKS = ("mission.tank.victory", "cluster.tank.c02.u01")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_seeded_bridge_loop_smoke(
    archipelago_dir: Path,
    runtime_checks: tuple[str, ...] = DEFAULT_RUNTIME_CHECKS,
    unlock_preset: str = "default",
) -> dict[str, Any]:
    session_path = archipelago_dir / "LocalBridgeSession.json"
    inbound_path = archipelago_dir / "Bridge-Inbound.json"
    outbound_path = archipelago_dir / "Bridge-Outbound.json"
    events_path = archipelago_dir / "Bridge-Events.jsonl"
    slot_data_path = archipelago_dir / DEFAULT_SLOT_DATA_FILENAME

    status_initial = run_cycle(
        archipelago_dir,
        session_path,
        inbound_path,
        outbound_path,
        events_path,
        reset_session=True,
        emit_slot_data=True,
        unlock_preset=unlock_preset,
    )

    if not slot_data_path.exists():
        raise AssertionError(f"missing {slot_data_path}")
    if not inbound_path.exists():
        raise AssertionError(f"missing {inbound_path}")

    inbound = _load_json(inbound_path)
    slot_data = _load_json(slot_data_path)
    _, _, translate_runtime_checks, validate_slot_data = load_generalszh_slot_helpers()
    validate_slot_data(slot_data)

    expected_hash = f"sha256:{hashlib.sha256(slot_data_path.read_bytes()).hexdigest()}"
    required_inbound = {
        "slotDataPath": DEFAULT_SLOT_DATA_FILENAME,
        "slotDataVersion": 2,
        "seedId": status_initial["session"]["seedId"],
        "slotName": status_initial["session"]["slotName"],
        "sessionNonce": status_initial["session"]["sessionNonce"],
    }
    for key, expected in required_inbound.items():
        actual = inbound.get(key)
        if actual != expected:
            raise AssertionError(f"inbound {key} mismatch: expected={expected!r} actual={actual!r}")
    if inbound.get("slotDataHash") != expected_hash:
        raise AssertionError("inbound slotDataHash does not match written Seed-Slot-Data.json bytes")

    translated = translate_runtime_checks(slot_data, list(runtime_checks))
    atomic_write_json(outbound_path, {"completedChecks": list(runtime_checks)})

    status_runtime = run_cycle(
        archipelago_dir,
        session_path,
        inbound_path,
        outbound_path,
        events_path,
        emit_slot_data=True,
        unlock_preset=unlock_preset,
    )
    completed_locations = set(status_runtime["session"]["completedLocations"])
    missing_ids = sorted(set(translated) - completed_locations)
    if missing_ids:
        raise AssertionError(f"runtime checks did not translate to completed AP IDs: {missing_ids}")

    status_duplicate = run_cycle(
        archipelago_dir,
        session_path,
        inbound_path,
        outbound_path,
        events_path,
        emit_slot_data=True,
        unlock_preset=unlock_preset,
    )
    if status_duplicate["changes"]:
        raise AssertionError(f"duplicate runtime completion changed session: {status_duplicate['changes']}")

    return {
        "archipelago_dir": str(archipelago_dir),
        "slot_data_path": str(slot_data_path),
        "inbound_path": str(inbound_path),
        "outbound_path": str(outbound_path),
        "slot_data_hash": expected_hash,
        "runtime_checks": list(runtime_checks),
        "translated_locations": translated,
        "first_merge_changes": status_runtime["changes"],
        "duplicate_merge_changes": status_duplicate["changes"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run seeded local bridge loop smoke without launching the game.")
    parser.add_argument("--archipelago-dir", type=Path, default=None, help="UserData/Archipelago directory. Defaults to a temp directory.")
    parser.add_argument("--unlock-preset", choices=("default", "minimal"), default="default", help="Testing slot-data preset.")
    parser.add_argument("--runtime-check", action="append", dest="runtime_checks", help="Runtime key to simulate in Bridge-Outbound.json. Repeatable.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temp directory when --archipelago-dir is omitted.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_checks = tuple(args.runtime_checks) if args.runtime_checks else DEFAULT_RUNTIME_CHECKS

    if args.archipelago_dir is not None:
        summary = run_seeded_bridge_loop_smoke(args.archipelago_dir.resolve(), runtime_checks, args.unlock_preset)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    temp_root = Path(tempfile.mkdtemp(prefix="generalsap-seeded-bridge-"))
    try:
        archipelago_dir = temp_root / "Archipelago"
        summary = run_seeded_bridge_loop_smoke(archipelago_dir, runtime_checks, args.unlock_preset)
        print(json.dumps(summary, indent=2, sort_keys=True))
        if args.keep_temp:
            print(f"kept temp directory: {temp_root}", file=sys.stderr)
        return 0
    finally:
        if not args.keep_temp:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
