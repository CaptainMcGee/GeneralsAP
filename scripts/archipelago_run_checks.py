#!/usr/bin/env python3
"""Run the lightweight Archipelago generation and validation suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
TESTS = SCRIPTS / "tests" / "test_archipelago_data_pipeline.py"
WND_TESTS = SCRIPTS / "tests" / "test_wnd_workbench.py"
WORLD_TESTS = SCRIPTS / "tests" / "test_archipelago_world_contract.py"
OPTIONAL_AP_SMOKE = SCRIPTS / "tests" / "test_archipelago_generation_smoke_optional.py"
AP_SMOKE_VENV = REPO_ROOT / "build" / "archipelago" / "ap-smoke-venv"


def ap_smoke_python() -> Path | None:
    candidates = [
        AP_SMOKE_VENV / "Scripts" / "python.exe",
        AP_SMOKE_VENV / "bin" / "python",
    ]
    return next((path for path in candidates if path.exists()), None)


def run_path(path: Path, *args: str, python: Path | None = None) -> int:
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    executable = python or Path(sys.executable)
    result = subprocess.run([str(executable), str(path), *args], cwd=str(REPO_ROOT))
    return result.returncode



def main() -> int:
    steps = [
        ("=== Building localized in-game name map ===", SCRIPTS / "archipelago_build_localized_name_map.py", []),
        ("=== Building template name map ===", SCRIPTS / "archipelago_build_template_name_map.py", []),
        ("=== Generating Archipelago.ini from config ===", SCRIPTS / "archipelago_generate_ini.py", []),
        ("=== Generating challenge unit protection INI ===", SCRIPTS / "archipelago_generate_challenge_unit_protection.py", []),
        ("=== Validating Archipelago.ini templates ===", SCRIPTS / "archipelago_validate_ini.py", []),
        ("=== Generating matchup graph ===", SCRIPTS / "archipelago_generate_matchup_graph.py", []),
        ("=== Running Archipelago audit ===", SCRIPTS / "archipelago_audit_groups.py", []),
        ("=== Running Archipelago sanity tests ===", TESTS, []),
        ("=== Running WND workbench sanity tests ===", WND_TESTS, []),
        ("=== Running AP world contract tests ===", WORLD_TESTS, []),
        ("=== Running optional real AP generation smoke ===", OPTIONAL_AP_SMOKE, []),
    ]
    for heading, path, args in steps:
        print(heading, flush=True)
        python = ap_smoke_python() if path == OPTIONAL_AP_SMOKE else None
        if python:
            print(f"Using AP smoke venv: {python}", flush=True)
        if run_path(path, *args, python=python) != 0:
            return 1
        print("", flush=True)

    print("=== All Archipelago checks passed ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
