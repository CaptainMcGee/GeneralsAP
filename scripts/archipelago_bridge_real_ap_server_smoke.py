#!/usr/bin/env python3
"""Smoke GeneralsAPBridge against a real local Archipelago 0.6.7 server."""

from __future__ import annotations

import argparse
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
REQUIREMENTS = REPO_ROOT / "scripts" / "requirements-archipelago-smoke.txt"
MATERIALIZE = REPO_ROOT / "scripts" / "archipelago_vendor_materialize.py"
SLOT_NAME = "Bridge Smoke"
RUNTIME_CHECKS = ("mission.tank.victory", "cluster.tank.c02.u01")
EXPECTED_LOCATION_IDS = (270000003, 270040201)


def log(message: str) -> None:
    print(f"[real-ap-smoke] {message}", flush=True)


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


def assert_completed_locations(session_path: Path, expected: set[int], context: str) -> None:
    session = load_json(session_path)
    completed = {int(value) for value in session.get("completedLocations", [])}
    missing = sorted(expected - completed)
    if missing:
        raise AssertionError(f"{context}: missing completed AP location IDs {missing}; session={session}")


def run_real_ap_server_smoke(
    bridge_exe: Path,
    venv_dir: Path,
    skip_install: bool,
    skip_materialize: bool,
    keep_temp: bool,
) -> dict[str, Any]:
    if not bridge_exe.is_file():
        raise FileNotFoundError(f"bridge executable missing: {bridge_exe}")

    python = ensure_venv(venv_dir, skip_install)
    ensure_ap_worktree(skip_materialize)

    temp_root = Path(tempfile.mkdtemp(prefix="generalsap-real-ap-server-"))
    server: subprocess.Popen[str] | None = None
    try:
        log("generating GeneralsZH multidata zip")
        multidata_zip = generate_archipelago_zip(python, temp_root / "ap-output")
        port = find_free_port()
        log(f"starting local Archipelago server on ws://127.0.0.1:{port}")
        server = start_ap_server(python, multidata_zip, port, temp_root)
        server_url = f"ws://127.0.0.1:{port}"

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
        expected = set(EXPECTED_LOCATION_IDS)
        assert_completed_locations(archipelago_dir / "BridgeSession.json", expected, "submit run")

        reconnect_dir = temp_root / "ReconnectProfile"
        log("reconnecting fresh bridge profile to verify server-persisted checked locations")
        run_bridge(bridge_exe, reconnect_dir, server_url, "--reset-session")
        assert_completed_locations(reconnect_dir / "BridgeSession.json", expected, "fresh reconnect")

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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_real_ap_server_smoke(
        bridge_exe=args.bridge_exe.resolve(),
        venv_dir=args.venv.resolve(),
        skip_install=args.skip_install,
        skip_materialize=args.skip_materialize,
        keep_temp=args.keep_temp,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
