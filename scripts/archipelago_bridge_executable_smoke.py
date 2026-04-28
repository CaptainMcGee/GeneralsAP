#!/usr/bin/env python3
"""Smoke test the packaged GeneralsAPBridge executable file-bridge path."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.archipelago_bridge_local import DEFAULT_SLOT_DATA_FILENAME, atomic_write_json, load_generalszh_slot_helpers  # noqa: E402

DEFAULT_RUNTIME_CHECKS = ("mission.tank.victory", "cluster.tank.c02.u01")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_bridge(bridge_exe: Path, archipelago_dir: Path, *extra_args: str, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    command = [
        str(bridge_exe),
        "--once",
        "--archipelago-dir",
        str(archipelago_dir),
        *extra_args,
    ]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if expect_success and completed.returncode != 0:
        raise AssertionError(
            f"bridge failed with exit {completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    if not expect_success and completed.returncode == 0:
        raise AssertionError(f"bridge unexpectedly accepted invalid input\nSTDOUT:\n{completed.stdout}")
    return completed


def write_slot_data(path: Path, unlock_preset: str) -> dict[str, Any]:
    build_testing_slot_data, _, _, validate_slot_data = load_generalszh_slot_helpers()
    slot_data = build_testing_slot_data(
        seed_id="bridge-executable-smoke",
        slot_name="Bridge Smoke",
        session_nonce="bridge-executable-smoke:1",
        unlock_preset=unlock_preset,
    )
    validate_slot_data(slot_data)
    atomic_write_json(path, slot_data)
    return slot_data


def run_smoke(bridge_exe: Path, unlock_preset: str, runtime_checks: tuple[str, ...]) -> dict[str, Any]:
    if not bridge_exe.is_file():
        raise FileNotFoundError(f"Bridge executable missing: {bridge_exe}")

    temp_root = Path(tempfile.mkdtemp(prefix="generalsap-bridge-exe-"))
    try:
        archipelago_dir = temp_root / "Archipelago"
        archipelago_dir.mkdir(parents=True)
        source_slot_data_path = temp_root / "Input-Seed-Slot-Data.json"
        slot_data = write_slot_data(source_slot_data_path, unlock_preset)
        _, _, translate_runtime_checks, _ = load_generalszh_slot_helpers()
        translated = translate_runtime_checks(slot_data, list(runtime_checks))

        version = subprocess.run([str(bridge_exe), "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if version.returncode != 0 or "file-bridge" not in version.stdout:
            raise AssertionError(f"bridge --version did not report file-bridge\nSTDOUT:\n{version.stdout}\nSTDERR:\n{version.stderr}")

        run_bridge(bridge_exe, archipelago_dir, "--slot-data", str(source_slot_data_path), "--reset-session")
        inbound_path = archipelago_dir / "Bridge-Inbound.json"
        slot_data_path = archipelago_dir / DEFAULT_SLOT_DATA_FILENAME
        if not inbound_path.is_file():
            raise AssertionError("bridge did not write Bridge-Inbound.json")
        if not slot_data_path.is_file():
            raise AssertionError("bridge did not materialize Seed-Slot-Data.json")

        inbound = load_json(inbound_path)
        expected_hash = f"sha256:{hashlib.sha256(slot_data_path.read_bytes()).hexdigest()}"
        expected_inbound = {
            "slotDataPath": DEFAULT_SLOT_DATA_FILENAME,
            "slotDataVersion": 2,
            "slotDataHash": expected_hash,
            "seedId": "bridge-executable-smoke",
            "slotName": "Bridge Smoke",
            "sessionNonce": "bridge-executable-smoke:1",
        }
        for key, expected in expected_inbound.items():
            if inbound.get(key) != expected:
                raise AssertionError(f"inbound {key} mismatch: expected={expected!r} actual={inbound.get(key)!r}")

        outbound_path = archipelago_dir / "Bridge-Outbound.json"
        atomic_write_json(outbound_path, {"completedChecks": list(runtime_checks)})
        run_bridge(bridge_exe, archipelago_dir)
        session_path = archipelago_dir / "LocalBridgeSession.json"
        session = load_json(session_path)
        missing = sorted(set(translated) - set(session.get("completedLocations", [])))
        if missing:
            raise AssertionError(f"bridge did not translate runtime checks to AP IDs: {missing}")

        before_duplicate = session_path.read_text(encoding="utf-8")
        run_bridge(bridge_exe, archipelago_dir)
        after_duplicate = session_path.read_text(encoding="utf-8")
        if before_duplicate != after_duplicate:
            raise AssertionError("duplicate bridge cycle changed LocalBridgeSession.json")

        bad_dir = temp_root / "BadArchipelago"
        bad_dir.mkdir(parents=True)
        run_bridge(bridge_exe, bad_dir, "--slot-data", str(source_slot_data_path), "--reset-session")
        atomic_write_json(bad_dir / "Bridge-Outbound.json", {"completedChecks": ["cluster.tank.c99.u99"]})
        bad = run_bridge(bridge_exe, bad_dir, expect_success=False)
        if "unknown runtime check key" not in bad.stderr:
            raise AssertionError(f"unknown key failure did not explain problem\nSTDERR:\n{bad.stderr}")

        bad_id_dir = temp_root / "BadIdArchipelago"
        bad_id_dir.mkdir(parents=True)
        run_bridge(bridge_exe, bad_id_dir, "--slot-data", str(source_slot_data_path), "--reset-session")
        atomic_write_json(bad_id_dir / "Bridge-Outbound.json", {"completedLocations": [999999999]})
        bad_id = run_bridge(bridge_exe, bad_id_dir, expect_success=False)
        if "unknown AP location id" not in bad_id.stderr:
            raise AssertionError(f"unknown AP location id failure did not explain problem\nSTDERR:\n{bad_id.stderr}")

        return {
            "bridge_exe": str(bridge_exe),
            "runtime_checks": list(runtime_checks),
            "translated_locations": translated,
            "slot_data_hash": expected_hash,
            "inbound_path": str(inbound_path),
            "session_path": str(session_path),
            "unknown_key_rejected": True,
            "unknown_location_id_rejected": True,
        }
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test GeneralsAPBridge.exe file-bridge behavior.")
    parser.add_argument("--bridge-exe", type=Path, required=True)
    parser.add_argument("--unlock-preset", choices=("default", "minimal"), default="default")
    parser.add_argument("--runtime-check", action="append", dest="runtime_checks")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checks = tuple(args.runtime_checks) if args.runtime_checks else DEFAULT_RUNTIME_CHECKS
    summary = run_smoke(args.bridge_exe.resolve(), args.unlock_preset, checks)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
