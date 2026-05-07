#!/usr/bin/env python3
"""Smoke GeneralsAPBridge against a real local Archipelago 0.6.7 server."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = REPO_ROOT / "build" / "archipelago"
AP_WORKTREE = BUILD_ROOT / "archipelago-worktree"
DEFAULT_VENV = BUILD_ROOT / "ap-smoke-venv"
SHARED_CACHE_LOCK = BUILD_ROOT / "ap-smoke-cache.lock"
REQUIREMENTS = REPO_ROOT / "scripts" / "requirements-archipelago-smoke.txt"
MATERIALIZE = REPO_ROOT / "scripts" / "archipelago_vendor_materialize.py"
SLOT_NAME = "Bridge Smoke"
GAME_NAME = "Command & Conquer Generals: Zero Hour"
RUNTIME_CHECKS = ("mission.tank.victory", "cluster.tank.c02.u01")
EXPECTED_LOCATION_IDS = (270000003, 270040201)
BOSS_RUNTIME_CHECK = "mission.boss.victory"
CLIENT_GOAL_STATUS = 30
VICTORY_MEDAL_ITEM_NAMES = (
    "Air Force General Medal",
    "Laser General Medal",
    "Superweapons General Medal",
    "Tank General Medal",
    "Nuke General Medal",
    "Stealth General Medal",
    "Toxin General Medal",
)


def log(message: str) -> None:
    print(f"[real-ap-smoke] {message}", flush=True)


@contextmanager
def exclusive_directory_lock(lock_dir: Path, timeout_seconds: float = 300.0):
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            lock_dir.mkdir()
            (lock_dir / "owner.json").write_text(
                json.dumps({"pid": os.getpid(), "createdAt": time.time()}, indent=2),
                encoding="utf-8",
            )
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for AP smoke cache lock: {lock_dir}")
            time.sleep(0.25)

    try:
        yield
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)


def venv_python(venv_dir: Path) -> Path:
    windows_python = venv_dir / "Scripts" / "python.exe"
    if windows_python.exists():
        return windows_python
    return venv_dir / "bin" / "python"


def run(args: list[str], cwd: Path = REPO_ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"command failed exit={completed.returncode}: {' '.join(args)}\n{completed.stdout}"
        )
    return completed


def ensure_venv(venv_dir: Path, skip_install: bool) -> Path:
    python = venv_python(venv_dir)
    if not python.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])
    python = venv_python(venv_dir)
    if not python.exists():
        raise RuntimeError(f"venv python missing after creation: {python}")
    if not skip_install:
        run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQUIREMENTS)])
    return python


def ensure_ap_worktree(skip_materialize: bool) -> None:
    if skip_materialize and not AP_WORKTREE.exists():
        raise FileNotFoundError(f"AP worktree missing and --skip-materialize was passed: {AP_WORKTREE}")
    if not skip_materialize:
        run([sys.executable, str(MATERIALIZE)])
    if not AP_WORKTREE.exists():
        raise FileNotFoundError(f"AP worktree missing after materialize: {AP_WORKTREE}")


def generate_archipelago_zip(python: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    code = f"""
import logging
import sys
import warnings
from argparse import Namespace
from pathlib import Path

root = Path({str(AP_WORKTREE)!r})
output = Path({str(output_dir)!r})
sys.path.insert(0, str(root))
logging.basicConfig(level=logging.CRITICAL)
warnings.filterwarnings("ignore", message="_speedups not available.*")

from BaseClasses import PlandoOptions
from Main import main as generate_multiworld
from worlds.AutoWorld import AutoWorldRegister
from worlds.generalszh import constants

game = constants.GAME_NAME
world_type = AutoWorldRegister.world_types[game]
args = Namespace()
args.multi = 1
args.outputpath = str(output)
args.outputname = "GeneralsAPBridgeSmoke"
args.race = False
args.plando = PlandoOptions.from_option_string("")
args.game = {{1: game}}
args.name = {{1: {SLOT_NAME!r}}}
args.sprite = {{1: ""}}
args.sprite_pool = {{1: []}}
args.csv_output = False
args.skip_output = False
args.spoiler_only = False
args.spoiler = 0
args.skip_prog_balancing = True

for option_name, option in world_type.options_dataclass.type_hints.items():
    setattr(args, option_name, {{1: option.from_any(option.default)}})

generate_multiworld(args, seed=8675309)
print("GENERATED_AP_ZIP_READY")
"""
    completed = run([str(python), "-c", textwrap.dedent(code)], cwd=AP_WORKTREE)
    if "GENERATED_AP_ZIP_READY" not in completed.stdout:
        raise AssertionError(f"AP generation did not finish cleanly:\n{completed.stdout}")
    zips = sorted(output_dir.glob("AP_*.zip"), key=lambda path: path.stat().st_mtime)
    if not zips:
        raise FileNotFoundError(f"AP generation produced no AP_*.zip in {output_dir}\n{completed.stdout}")
    return zips[-1]


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_port(port: int, process: subprocess.Popen[str], log_path: Path, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
            raise RuntimeError(f"AP server exited before listening on {port}\n{stdout}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    stdout = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    raise TimeoutError(f"AP server did not listen on {port}\n{stdout}")


def start_ap_server(python: Path, multidata_zip: Path, port: int, temp_root: Path) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["SKIP_REQUIREMENTS_UPDATE"] = "1"
    command = [
        str(python),
        "-u",
        str(AP_WORKTREE / "MultiServer.py"),
        str(multidata_zip),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--disable_save",
        "--loglevel",
        "info",
    ]
    log_path = temp_root / "ap-server.log"
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=str(AP_WORKTREE),
        env=env,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    process._generalsap_log_handle = log_handle  # type: ignore[attr-defined]
    try:
        wait_for_port(port, process, log_path)
    except Exception:
        terminate_process_tree(process)
        log_handle.close()
        raise
    return process


def start_ap_server_on_free_port(
    python: Path,
    multidata_zip: Path,
    temp_root: Path,
    attempts: int = 5,
) -> tuple[subprocess.Popen[str], str]:
    errors: list[str] = []
    for attempt in range(1, attempts + 1):
        port = find_free_port()
        log(f"starting local Archipelago server on ws://127.0.0.1:{port}")
        try:
            server = start_ap_server(python, multidata_zip, port, temp_root)
            return server, f"ws://127.0.0.1:{port}"
        except Exception as exc:
            errors.append(f"attempt {attempt} on port {port}: {exc}")
            if attempt == attempts:
                break
            log(f"server startup failed on port {port}; retrying")
            time.sleep(0.5)
    raise RuntimeError("failed to start local AP server after retries:\n" + "\n".join(errors))


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def run_bridge(bridge_exe: Path, archipelago_dir: Path, server_url: str, *extra: str) -> subprocess.CompletedProcess[str]:
    command = [
        str(bridge_exe),
        "--once",
        "--connect",
        server_url,
        "--slot-name",
        SLOT_NAME,
        "--archipelago-dir",
        str(archipelago_dir),
        "--poll-interval",
        "0.1",
        *extra,
    ]
    try:
        completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            f"bridge timed out\nSTDOUT:\n{exc.stdout or ''}\nSTDERR:\n{exc.stderr or ''}"
        ) from exc
    if completed.returncode != 0:
        raise AssertionError(
            f"bridge failed exit={completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return completed


def assert_completed_locations(
    session_path: Path,
    expected_locations: set[int],
    expected_runtime_keys: set[str],
    context: str,
) -> None:
    session = load_json(session_path)
    completed = {int(value) for value in session.get("completedLocations", [])}
    missing_locations = sorted(expected_locations - completed)
    if missing_locations:
        raise AssertionError(f"{context}: missing completed AP location IDs {missing_locations}; session={session}")
    completed_checks = {str(value) for value in session.get("completedChecks", [])}
    missing_checks = sorted(expected_runtime_keys - completed_checks)
    if missing_checks:
        raise AssertionError(f"{context}: missing completed runtime keys {missing_checks}; session={session}")


def selected_runtime_keys(slot_data: dict[str, Any]) -> dict[str, list[str]]:
    main_keys: list[str] = []
    boss_cluster_keys: list[str] = []
    boss_keys: list[str] = []
    for map_key, map_payload in slot_data["maps"].items():
        mission_key = str(map_payload["missionVictory"]["runtimeKey"])
        if mission_key == BOSS_RUNTIME_CHECK:
            boss_keys.append(mission_key)
        elif map_key != "boss":
            main_keys.append(mission_key)

        for cluster in map_payload["clusters"]:
            for unit in cluster["units"]:
                runtime_key = str(unit["runtimeKey"])
                if map_key == "boss":
                    boss_cluster_keys.append(runtime_key)
                else:
                    main_keys.append(runtime_key)

    return {
        "main": sorted(main_keys),
        "boss_clusters": sorted(boss_cluster_keys),
        "boss": sorted(boss_keys),
        "all_non_goal": sorted(main_keys + boss_cluster_keys),
    }


def runtime_key_ids(slot_data: dict[str, Any], runtime_keys: list[str]) -> set[int]:
    mapping: dict[str, int] = {}
    for map_payload in slot_data["maps"].values():
        mission = map_payload["missionVictory"]
        mapping[str(mission["runtimeKey"])] = int(mission["apLocationId"])
        for cluster in map_payload["clusters"]:
            for unit in cluster["units"]:
                mapping[str(unit["runtimeKey"])] = int(unit["apLocationId"])

    missing = sorted(runtime_key for runtime_key in runtime_keys if runtime_key not in mapping)
    if missing:
        raise AssertionError(f"slot data did not contain runtime keys: {missing}")
    return {mapping[runtime_key] for runtime_key in runtime_keys}


def network_item_id(network_item: Any) -> int | None:
    if isinstance(network_item, dict) and "item" in network_item:
        return int(network_item["item"])
    if isinstance(network_item, list) and network_item:
        return int(network_item[0])
    return None


async def collect_received_item_names_async(server_url: str) -> list[str]:
    import websockets

    async with websockets.connect(server_url) as websocket:
        item_name_by_id: dict[int, str] = {}
        received_item_names: list[str] = []
        connected = False
        saw_received_items = False
        deadline = time.monotonic() + 20.0

        while time.monotonic() < deadline:
            try:
                raw_message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
            except TimeoutError:
                if connected and saw_received_items:
                    break
                continue

            packets = json.loads(raw_message)
            for packet in packets:
                cmd = packet.get("cmd")
                if cmd == "RoomInfo":
                    await websocket.send(json.dumps([{
                        "cmd": "GetDataPackage",
                        "games": [GAME_NAME],
                    }]))
                elif cmd == "DataPackage":
                    game_payload = packet.get("data", {}).get("games", {}).get(GAME_NAME, {})
                    for item_name, item_id in game_payload.get("item_name_to_id", {}).items():
                        item_name_by_id[int(item_id)] = str(item_name)
                    await websocket.send(json.dumps([{
                        "cmd": "Connect",
                        "password": None,
                        "game": GAME_NAME,
                        "name": SLOT_NAME,
                        "uuid": "generalsap-full-world-simulation-observer",
                        "version": {"major": 0, "minor": 6, "build": 7, "class": "Version"},
                        "items_handling": 0b111,
                        "tags": ["GeneralsAPFullWorldSimulationObserver"],
                        "slot_data": False,
                    }]))
                elif cmd == "Connected":
                    connected = True
                elif cmd == "ReceivedItems":
                    saw_received_items = True
                    for network_item in packet.get("items", []):
                        item_id = network_item_id(network_item)
                        if item_id is None:
                            continue
                        if item_id in item_name_by_id:
                            received_item_names.append(item_name_by_id[item_id])

            if connected and saw_received_items and received_item_names:
                # Give the server one more receive window in case it chunks items.
                try:
                    raw_message = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                except TimeoutError:
                    break
                for packet in json.loads(raw_message):
                    if packet.get("cmd") == "ReceivedItems":
                        for network_item in packet.get("items", []):
                            item_id = network_item_id(network_item)
                            if item_id is None:
                                continue
                            item_name = item_name_by_id.get(item_id)
                            if item_name:
                                received_item_names.append(item_name)
                break

    return received_item_names


def collect_received_item_names(server_url: str) -> list[str]:
    return asyncio.run(collect_received_item_names_async(server_url))


def assert_received_medals(server_url: str) -> dict[str, Any]:
    item_names = collect_received_item_names(server_url)
    medal_counts = {name: item_names.count(name) for name in VICTORY_MEDAL_ITEM_NAMES}
    missing = sorted(name for name, count in medal_counts.items() if count != 1)
    if missing:
        raise AssertionError(f"full-world simulation did not receive all seven shuffled medals: {medal_counts}")
    if "Boss General Medal" in item_names:
        raise AssertionError("Boss General Medal must not exist in received AP items")
    if "Victory" in item_names:
        raise AssertionError("Victory should remain locked to Boss mission event, not arrive as normal received item")
    return {
        "receivedItemCount": len(item_names),
        "medalCounts": medal_counts,
    }


def run_real_ap_server_smoke(
    bridge_exe: Path,
    venv_dir: Path,
    skip_install: bool,
    skip_materialize: bool,
    keep_temp: bool,
    clean_runtime_smoke: bool = False,
    base_runtime_dir: Path | None = None,
    prepared_runtime_dir: Path | None = None,
    runtime_startup_wait_seconds: int = 20,
    runtime_completion_timeout_seconds: int = 180,
    full_world_simulation: bool = False,
) -> dict[str, Any]:
    if not bridge_exe.is_file():
        raise FileNotFoundError(f"bridge executable missing: {bridge_exe}")
    if clean_runtime_smoke and base_runtime_dir is None:
        raise ValueError("--base-runtime-dir is required with --clean-runtime-smoke")

    temp_root = Path(tempfile.mkdtemp(prefix="generalsap-real-ap-server-"))
    server: subprocess.Popen[str] | None = None
    try:
        with exclusive_directory_lock(SHARED_CACHE_LOCK):
            python = ensure_venv(venv_dir, skip_install)
            ensure_ap_worktree(skip_materialize)
            log("generating GeneralsZH multidata zip")
            multidata_zip = generate_archipelago_zip(python, temp_root / "ap-output")
            server, server_url = start_ap_server_on_free_port(python, multidata_zip, temp_root)
        expected = set(EXPECTED_LOCATION_IDS)
        expected_checks = set(RUNTIME_CHECKS)

        if full_world_simulation and clean_runtime_smoke:
            raise ValueError("--full-world-simulation cannot be combined with --clean-runtime-smoke")

        if clean_runtime_smoke:
            clean_work_dir = temp_root / "CleanRuntime"
            command = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(REPO_ROOT / "scripts" / "smoke_generalsap_clean_runtime.ps1"),
                "-BaseRuntimeDir",
                str(base_runtime_dir),
                "-BridgePath",
                str(bridge_exe),
                "-BridgeConnect",
                server_url,
                "-BridgeSlotName",
                SLOT_NAME,
                "-WorkDir",
                str(clean_work_dir),
                "-StartupWaitSeconds",
                str(runtime_startup_wait_seconds),
                "-SmokeCompleteRuntimeKey",
                ",".join(RUNTIME_CHECKS),
                "-CompletionTimeoutSeconds",
                str(runtime_completion_timeout_seconds),
            ]
            if prepared_runtime_dir is not None:
                command.extend(["-PreparedRuntimeDir", str(prepared_runtime_dir)])

            log("running clean-runtime smoke through live AP network bridge")
            run(command)

            clean_archipelago_dir = clean_work_dir / "InstalledRuntime" / "UserData" / "Archipelago"
            assert_completed_locations(
                clean_archipelago_dir / "BridgeSession.json",
                expected,
                expected_checks,
                "clean runtime network submit",
            )

            reconnect_dir = temp_root / "ReconnectAfterCleanRuntime"
            log("reconnecting fresh bridge profile after clean-runtime submit")
            run_bridge(bridge_exe, reconnect_dir, server_url, "--reset-session")
            assert_completed_locations(reconnect_dir / "BridgeSession.json", expected, expected_checks, "clean runtime fresh reconnect")

            return {
                "bridge_exe": str(bridge_exe),
                "ap_python": str(python),
                "clean_runtime_smoke": True,
                "clean_runtime_work_dir": str(clean_work_dir),
                "multidata_zip": str(multidata_zip),
                "server_url": server_url,
                "submitted_locations": list(EXPECTED_LOCATION_IDS),
                "reconnect_session_path": str(reconnect_dir / "BridgeSession.json"),
            }

        if full_world_simulation:
            archipelago_dir = temp_root / "FullWorldBridgeProfile"
            log("connecting bridge and materializing full-world simulation slot data")
            run_bridge(bridge_exe, archipelago_dir, server_url, "--reset-session")
            slot_data_path = archipelago_dir / "Seed-Slot-Data.json"
            if not slot_data_path.is_file():
                raise AssertionError("full-world simulation did not materialize Seed-Slot-Data.json")
            slot_data = load_json(slot_data_path)
            key_groups = selected_runtime_keys(slot_data)
            if not key_groups["main"]:
                raise AssertionError("full-world simulation found no main mission/cluster runtime keys")
            if key_groups["boss"] != [BOSS_RUNTIME_CHECK]:
                raise AssertionError(f"full-world simulation expected one Boss victory key: {key_groups['boss']}")

            outbound_path = archipelago_dir / "Bridge-Outbound.json"
            main_location_ids = runtime_key_ids(slot_data, key_groups["main"])
            outbound_path.write_text(json.dumps({"completedChecks": key_groups["main"]}, indent=2), encoding="utf-8")
            log(f"submitting full main-world simulated runtime completions ({len(key_groups['main'])} keys)")
            run_bridge(bridge_exe, archipelago_dir, server_url)
            assert_completed_locations(
                archipelago_dir / "BridgeSession.json",
                main_location_ids,
                set(key_groups["main"]),
                "full-world main submit",
            )

            reconnect_dir = temp_root / "FullWorldReconnectMain"
            log("reconnecting after main-world submit to verify AP server persistence")
            run_bridge(bridge_exe, reconnect_dir, server_url, "--reset-session")
            assert_completed_locations(
                reconnect_dir / "BridgeSession.json",
                main_location_ids,
                set(key_groups["main"]),
                "full-world main reconnect",
            )

            medal_summary = assert_received_medals(server_url)

            boss_cluster_location_ids = runtime_key_ids(slot_data, key_groups["boss_clusters"])
            if key_groups["boss_clusters"]:
                outbound_path.write_text(json.dumps({"completedChecks": key_groups["boss_clusters"]}, indent=2), encoding="utf-8")
                log(f"submitting Boss-cluster simulated runtime completions after medals ({len(key_groups['boss_clusters'])} keys)")
                run_bridge(bridge_exe, archipelago_dir, server_url)
                assert_completed_locations(
                    archipelago_dir / "BridgeSession.json",
                    main_location_ids | boss_cluster_location_ids,
                    set(key_groups["main"] + key_groups["boss_clusters"]),
                    "full-world boss-cluster submit",
                )

            outbound_path.write_text(json.dumps({"completedChecks": key_groups["boss"]}, indent=2), encoding="utf-8")
            log("submitting Boss victory simulated runtime completion as AP goal status")
            run_bridge(bridge_exe, archipelago_dir, server_url)
            boss_session = load_json(archipelago_dir / "BridgeSession.json")
            if BOSS_RUNTIME_CHECK not in set(map(str, boss_session.get("completedChecks", []))):
                raise AssertionError(f"Boss victory key missing from bridge session: {boss_session}")
            if int(slot_data["maps"]["boss"]["missionVictory"]["apLocationId"]) not in {int(value) for value in boss_session.get("completedLocations", [])}:
                raise AssertionError(f"Boss victory AP marker missing from bridge session: {boss_session}")

            duplicate_session_before = canonical_json(load_json(archipelago_dir / "BridgeSession.json"))
            outbound_path.write_text(json.dumps({"completedChecks": key_groups["main"] + key_groups["boss_clusters"] + key_groups["boss"]}, indent=2), encoding="utf-8")
            log("resubmitting full simulated completion set to verify idempotency")
            run_bridge(bridge_exe, archipelago_dir, server_url)
            duplicate_session_after = canonical_json(load_json(archipelago_dir / "BridgeSession.json"))
            if duplicate_session_before != duplicate_session_after:
                raise AssertionError("full-world duplicate completion changed BridgeSession.json")

            return {
                "bridge_exe": str(bridge_exe),
                "ap_python": str(python),
                "full_world_simulation": True,
                "multidata_zip": str(multidata_zip),
                "server_url": server_url,
                "slot_data_path": str(slot_data_path),
                "main_runtime_key_count": len(key_groups["main"]),
                "boss_cluster_runtime_key_count": len(key_groups["boss_clusters"]),
                "boss_runtime_key": BOSS_RUNTIME_CHECK,
                "main_location_count": len(main_location_ids),
                "boss_cluster_location_count": len(boss_cluster_location_ids),
                **medal_summary,
            }

        archipelago_dir = temp_root / "BridgeProfile"
        log("connecting bridge and materializing slot data")
        run_bridge(bridge_exe, archipelago_dir, server_url, "--reset-session")
        slot_data_path = archipelago_dir / "Seed-Slot-Data.json"
        inbound_path = archipelago_dir / "Bridge-Inbound.json"
        if not slot_data_path.is_file():
            raise AssertionError("bridge did not materialize Seed-Slot-Data.json from real AP slot_data")
        inbound = load_json(inbound_path)
        if inbound.get("slotName") != SLOT_NAME:
            raise AssertionError(f"slotName mismatch from real AP: {inbound}")

        outbound_path = archipelago_dir / "Bridge-Outbound.json"
        outbound_path.write_text(json.dumps({"completedChecks": list(RUNTIME_CHECKS)}, indent=2), encoding="utf-8")
        log("submitting one mission victory and one cluster check")
        run_bridge(bridge_exe, archipelago_dir, server_url)
        assert_completed_locations(archipelago_dir / "BridgeSession.json", expected, expected_checks, "submit run")

        reconnect_dir = temp_root / "ReconnectProfile"
        log("reconnecting fresh bridge profile to verify server-persisted checked locations")
        run_bridge(bridge_exe, reconnect_dir, server_url, "--reset-session")
        assert_completed_locations(reconnect_dir / "BridgeSession.json", expected, expected_checks, "fresh reconnect")

        outbound_path.write_text(json.dumps({"completedChecks": list(RUNTIME_CHECKS)}, indent=2), encoding="utf-8")
        log("resubmitting duplicate completions to verify idempotency")
        run_bridge(bridge_exe, archipelago_dir, server_url)

        return {
            "bridge_exe": str(bridge_exe),
            "ap_python": str(python),
            "multidata_zip": str(multidata_zip),
            "server_url": server_url,
            "slot_data_path": str(slot_data_path),
            "submitted_locations": list(EXPECTED_LOCATION_IDS),
            "reconnect_session_path": str(reconnect_dir / "BridgeSession.json"),
        }
    finally:
        if server is not None:
            terminate_process_tree(server)
            log_handle = getattr(server, "_generalsap_log_handle", None)
            if log_handle is not None:
                log_handle.close()
        if keep_temp:
            print(f"kept temp directory: {temp_root}", file=sys.stderr)
        else:
            shutil.rmtree(temp_root, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke GeneralsAPBridge against a real local Archipelago server.")
    parser.add_argument("--bridge-exe", type=Path, required=True)
    parser.add_argument("--venv", type=Path, default=DEFAULT_VENV)
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--skip-materialize", action="store_true")
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--clean-runtime-smoke", action="store_true")
    parser.add_argument("--base-runtime-dir", type=Path)
    parser.add_argument("--prepared-runtime-dir", type=Path)
    parser.add_argument("--runtime-startup-wait-seconds", type=int, default=20)
    parser.add_argument("--runtime-completion-timeout-seconds", type=int, default=180)
    parser.add_argument("--full-world-simulation", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_real_ap_server_smoke(
        bridge_exe=args.bridge_exe.resolve(),
        venv_dir=args.venv.resolve(),
        skip_install=args.skip_install,
        skip_materialize=args.skip_materialize,
        keep_temp=args.keep_temp,
        clean_runtime_smoke=args.clean_runtime_smoke,
        base_runtime_dir=args.base_runtime_dir.resolve() if args.base_runtime_dir else None,
        prepared_runtime_dir=args.prepared_runtime_dir.resolve() if args.prepared_runtime_dir else None,
        runtime_startup_wait_seconds=args.runtime_startup_wait_seconds,
        runtime_completion_timeout_seconds=args.runtime_completion_timeout_seconds,
        full_world_simulation=args.full_world_simulation,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
