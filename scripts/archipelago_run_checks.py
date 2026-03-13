#!/usr/bin/env python3
"""Run the lightweight Archipelago generation and validation suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
TESTS = SCRIPTS / "tests" / "test_archipelago_data_pipeline.py"



def run_path(path: Path, *args: str) -> int:
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    result = subprocess.run([sys.executable, str(path), *args], cwd=str(REPO_ROOT))
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
    ]
    for heading, path, args in steps:
        print(heading, flush=True)
        if run_path(path, *args) != 0:
            return 1
        print("", flush=True)

    print("=== All Archipelago checks passed ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
