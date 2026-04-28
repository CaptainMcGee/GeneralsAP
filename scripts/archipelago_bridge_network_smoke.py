#!/usr/bin/env python3
"""Smoke test GeneralsAPBridge live AP protocol mode against a local fake AP server."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import websockets

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.archipelago_bridge_local import DEFAULT_SLOT_DATA_FILENAME, load_generalszh_slot_helpers  # noqa: E402

BUILD_TESTING_SLOT_DATA, _, _, VALIDATE_SLOT_DATA = load_generalszh_slot_helpers()

from generalszh.constants import (  # noqa: E402
    GAME_NAME,
    ITEM_NAMESPACE_BASE,
    MAIN_MAP_KEYS,
    MAP_SLOTS,
    VICTORY_MEDAL_ITEM_NAMES,
)

ITEM_NAME_TO_ID: dict[str, int] = {
    "Shared Rocket Infantry": ITEM_NAMESPACE_BASE + 1,
    "Shared Tanks": ITEM_NAMESPACE_BASE + 2,
    "Shared Machine Gun Vehicles": ITEM_NAMESPACE_BASE + 3,
    "Shared Artillery": ITEM_NAMESPACE_BASE + 4,
    "Upgrade Radar": ITEM_NAMESPACE_BASE + 5,
    "Progressive Starting Money": ITEM_NAMESPACE_BASE + 6,
    "Progressive Production": ITEM_NAMESPACE_BASE + 7,
    "Supply Cache": ITEM_NAMESPACE_BASE + 8,
    **{
        VICTORY_MEDAL_ITEM_NAMES[map_key]: ITEM_NAMESPACE_BASE + 100 + MAP_SLOTS[map_key]
        for map_key in MAIN_MAP_KEYS
    },
}

DEFAULT_RUNTIME_CHECKS = ("mission.tank.victory", "cluster.tank.c02.u01")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def make_slot_data() -> dict[str, Any]:
    slot_data = BUILD_TESTING_SLOT_DATA(
        seed_id="network-smoke-seed",
        slot_name="Bridge Smoke",
        session_nonce="network-smoke-seed:1",
        unlock_preset="default",
    )
    VALIDATE_SLOT_DATA(slot_data)
    return slot_data


class FakeAPServer:
    def __init__(self, slot_data: dict[str, Any]) -> None:
        self.slot_data = slot_data
        self.checked_locations: set[int] = set()
        self.location_checks_seen: list[list[int]] = []
        self.connect_packets: list[dict[str, Any]] = []
        self.status_updates: list[int] = []

    async def handler(self, websocket: Any) -> None:
        await websocket.send(json.dumps([{
            "cmd": "RoomInfo",
            "version": {"major": 0, "minor": 6, "build": 7, "class": "Version"},
            "generator_version": {"major": 0, "minor": 6, "build": 7, "class": "Version"},
            "tags": ["AP"],
            "password": False,
            "permissions": {},
            "hint_cost": 0,
            "location_check_points": 1,
            "games": [GAME_NAME],
            "datapackage_checksums": {},
            "seed_name": "network-smoke-seed",
        }]))

        try:
            async for raw_message in websocket:
                packets = json.loads(raw_message)
                for packet in packets:
                    cmd = packet.get("cmd")
                    if cmd == "GetDataPackage":
                        await websocket.send(json.dumps([{
                            "cmd": "DataPackage",
                            "data": {
                                "games": {
                                    GAME_NAME: {
                                        "item_name_to_id": ITEM_NAME_TO_ID,
                                        "location_name_to_id": {},
                                        "checksum": "network-smoke",
                                    }
                                }
                            },
                        }]))
                    elif cmd == "Connect":
                        self.connect_packets.append(packet)
                        if packet.get("game") != GAME_NAME:
                            await websocket.send(json.dumps([{"cmd": "ConnectionRefused", "errors": ["InvalidGame"]}]))
                            continue
                        if packet.get("name") != "Bridge Smoke":
                            await websocket.send(json.dumps([{"cmd": "ConnectionRefused", "errors": ["InvalidSlot"]}]))
                            continue
                        await websocket.send(json.dumps([
                            {
                                "cmd": "Connected",
                                "team": 0,
                                "slot": 1,
                                "players": [[0, 1, "Bridge Smoke", "Bridge Smoke"]],
                                "missing_locations": [],
                                "checked_locations": sorted(self.checked_locations),
                                "slot_info": {"1": {"name": "Bridge Smoke", "game": GAME_NAME, "type": 1, "group_members": []}},
                                "hint_points": 0,
                                "slot_data": self.slot_data,
                            },
                            {
                                "cmd": "ReceivedItems",
                                "index": 0,
                                "items": [
                                    [ITEM_NAME_TO_ID["Shared Tanks"], 270000003, 1, 1],
                                    [ITEM_NAME_TO_ID["Progressive Starting Money"], 270000004, 1, 1],
                                    [ITEM_NAME_TO_ID["Progressive Production"], 270000005, 1, 1],
                                    [ITEM_NAME_TO_ID["Air Force General Medal"], 270000006, 1, 1],
                                    [ITEM_NAME_TO_ID["Supply Cache"], 270000007, 1, 0],
                                ],
                            },
                        ]))
                    elif cmd == "LocationChecks":
                        locations = [int(value) for value in packet.get("locations", [])]
                        self.location_checks_seen.append(locations)
                        self.checked_locations.update(locations)
                        await websocket.send(json.dumps([{
                            "cmd": "RoomUpdate",
                            "checked_locations": locations,
                        }]))
                    elif cmd == "StatusUpdate":
                        self.status_updates.append(int(packet.get("status", 0)))
        except websockets.ConnectionClosed:
            return


async def run_bridge(bridge_exe: Path, archipelago_dir: Path, server_url: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
    command = [
        str(bridge_exe),
        "--once",
        "--connect",
        server_url,
        "--slot-name",
        "Bridge Smoke",
        "--archipelago-dir",
        str(archipelago_dir),
        *extra_args,
    ]
    completed = await asyncio.to_thread(
        subprocess.run,
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"bridge network command failed with exit {completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return completed


async def run_smoke_async(bridge_exe: Path) -> dict[str, Any]:
    if not bridge_exe.is_file():
        raise FileNotFoundError(f"Bridge executable missing: {bridge_exe}")

    slot_data = make_slot_data()
    fake_server = FakeAPServer(slot_data)
    temp_root = Path(tempfile.mkdtemp(prefix="generalsap-bridge-network-"))
    server = await websockets.serve(fake_server.handler, "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        server_url = f"ws://127.0.0.1:{port}"
        archipelago_dir = temp_root / "Archipelago"

        await run_bridge(bridge_exe, archipelago_dir, server_url, "--reset-session")
        inbound_path = archipelago_dir / "Bridge-Inbound.json"
        session_path = archipelago_dir / "BridgeSession.json"
        slot_data_path = archipelago_dir / DEFAULT_SLOT_DATA_FILENAME
        inbound = load_json(inbound_path)
        session = load_json(session_path)

        if inbound.get("slotDataPath") != DEFAULT_SLOT_DATA_FILENAME:
            raise AssertionError("network bridge did not write slotDataPath")
        if not slot_data_path.is_file():
            raise AssertionError("network bridge did not materialize Seed-Slot-Data.json")
        if inbound.get("slotName") != "Bridge Smoke":
            raise AssertionError("network bridge did not preserve slotName")

        received = session.get("receivedItems", [])
        group_ids = {item.get("groupId") for item in received}
        if "Shared_Tanks" not in group_ids:
            raise AssertionError(f"ReceivedItems did not map Shared Tanks into runtime group IDs: {received}")
        if any(item.get("itemName", "").endswith("Medal") for item in received):
            raise AssertionError("victory medal item incorrectly became a runtime unlock group")
        if any(item.get("itemName") == "Supply Cache" for item in received):
            raise AssertionError("Supply Cache should wait for one-time cash runtime support, not become an unlock group")

        options = session.get("sessionOptions", {})
        if options.get("startingCashBonus") != 2000:
            raise AssertionError(f"startingCashBonus mismatch: {options}")
        if abs(float(options.get("productionMultiplier", 0.0)) - 1.25) > 0.001:
            raise AssertionError(f"productionMultiplier mismatch: {options}")

        (archipelago_dir / "Bridge-Outbound.json").write_text(
            json.dumps({"completedChecks": list(DEFAULT_RUNTIME_CHECKS)}, indent=2),
            encoding="utf-8",
        )
        await run_bridge(bridge_exe, archipelago_dir, server_url)
        expected_locations = {270000003, 270040201}
        submitted = {location for batch in fake_server.location_checks_seen for location in batch}
        missing = sorted(expected_locations - submitted)
        if missing:
            raise AssertionError(f"network bridge did not submit expected AP location IDs: {missing}")

        await run_bridge(bridge_exe, archipelago_dir, server_url)
        flattened = [location for batch in fake_server.location_checks_seen for location in batch]
        for location in expected_locations:
            if flattened.count(location) != 1:
                raise AssertionError(f"location {location} submitted {flattened.count(location)} times")

        return {
            "bridge_exe": str(bridge_exe),
            "server_connects": len(fake_server.connect_packets),
            "submitted_locations": sorted(submitted),
            "received_runtime_groups": sorted(group_ids),
            "startingCashBonus": options.get("startingCashBonus"),
            "productionMultiplier": options.get("productionMultiplier"),
            "slot_data_path": str(slot_data_path),
            "session_path": str(session_path),
        }
    finally:
        server.close()
        await server.wait_closed()
        shutil.rmtree(temp_root, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test GeneralsAPBridge AP network mode with a fake AP server.")
    parser.add_argument("--bridge-exe", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = asyncio.run(run_smoke_async(args.bridge_exe.resolve()))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
