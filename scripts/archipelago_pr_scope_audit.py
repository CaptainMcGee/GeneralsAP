#!/usr/bin/env python3
"""Audit the item/location framework PR for scope drift."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]

ALLOWED_FILE_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"^\.gitignore$",
        r"^\.github/workflows/build-toolchain\.yml$",
        r"^\.github/workflows/validate-archipelago-data\.yml$",
        r"^ARCHIPELAGO_CONTEXT_INDEX\.md$",
        r"^TESTING\.md$",
        r"^Data/Archipelago/(README\.md|Slot-Data-Format\.md|release_manifest_schema\.json)$",
        r"^Data/Archipelago/logic_contracts/(README\.md|capability_sources_schema\.json|logic_foundry_export_schema\.json|mission_gate_schema\.json|requirement_aliases\.json)$",
        r"^Data/Archipelago/logic_contracts/fixtures/(example_logic_contracts|logic_foundry_export_fixture)\.json$",
        r"^Data/Archipelago/location_families/(README\.md|authoring_schema\.json|capacity_targets\.json|catalog\.json|enable_criteria\.json|runtime_persistence_contract\.json)$",
        r"^Data/Archipelago/location_families/fixtures/example_candidates\.json$",
        r"^Docs/Archipelago/Operations/(Archipelago-State-Sync-Architecture|Archipelago-Vendor-Sync|Player-Release-Architecture)\.md$",
        r"^Docs/Archipelago/Planning/(AP-World-Skeleton-Notes|Archipelago-Implementation-Todo|Archipelago-Logic-Implementation-Guide|Item-Location-Framework|Item-Location-Framework-Branch-Readiness)\.md$",
        r"^GeneralsMD/Code/GameEngine/Include/GameLogic/Archipelago(SlotData|State)\.h$",
        r"^GeneralsMD/Code/GameEngine/Source/Common/CommandLine\.cpp$",
        r"^GeneralsMD/Code/GameEngine/Source/GameLogic/Archipelago(SlotData|State)\.cpp$",
        r"^GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner\.cpp$",
        r"^scripts/(archipelago_bridge_executable_smoke|archipelago_bridge_local|archipelago_bridge_network_smoke|archipelago_bridge_real_ap_server_smoke|archipelago_extract_ini_config|archipelago_generate_matchup_graph|archipelago_item_location_capacity_report|archipelago_location_catalog_validate|archipelago_logic_contract_validate|archipelago_pr_scope_audit|archipelago_run_checks|archipelago_vendor_capture)\.py$",
        r"^scripts/(build_generalsap_bridge_stub|build_generalsap_bridge|package_generalsap_alpha|run_generalsap_nonhuman_release_checks|smoke_generalsap_alpha_package|smoke_generalsap_clean_runtime|validate_generalsap_alpha_package)\.ps1$",
        r"^scripts/requirements-archipelago-smoke\.txt$",
        r"^scripts/tests/test_archipelago_(data_pipeline|generation_smoke_optional|world_contract)\.py$",
        r"^tools/bridge/GeneralsAPBridge/(ApNetworkBridge\.cs|GeneralsAPBridge\.csproj|Program\.cs)$",
        r"^vendor/archipelago/overlay/worlds/generalszh/(constants|content_framework|items|location_catalog|locations|slot_data)\.py$",
        r"^vendor/archipelago/overlay/worlds/generalszh/docs/setup_en\.md$",
    )
]

IMPLEMENTATION_DIFF_PATHS = (
    "GeneralsMD",
    "tools/bridge",
    "scripts",
    "vendor/archipelago/overlay/worlds/generalszh/constants.py",
    "vendor/archipelago/overlay/worlds/generalszh/content_framework.py",
    "vendor/archipelago/overlay/worlds/generalszh/items.py",
    "vendor/archipelago/overlay/worlds/generalszh/location_catalog.py",
    "vendor/archipelago/overlay/worlds/generalszh/locations.py",
    "vendor/archipelago/overlay/worlds/generalszh/slot_data.py",
)
FORBIDDEN_FILE_RE = re.compile(
    r"(^|/)(weakness|weaknesses|hold|win|tracker|difficulty|yaml)(\.|/|-|_)",
    re.IGNORECASE,
)
FORBIDDEN_IMPLEMENTATION_RE = re.compile(
    r"compute_player_strength|weakness evaluator|capability evaluator|hold logic|win logic|"
    r"tracker ui|authoring ui|yaml difficulty|difficulty mode",
    re.IGNORECASE,
)
FORBIDDEN_IMPLEMENTATION_ALLOWED_LINE_RE = re.compile(
    r"planning-only until Hold/Win logic consumes economy floors",
    re.IGNORECASE,
)
FORBIDDEN_IMPLEMENTATION_EXEMPT_FILES = {
    "scripts/archipelago_pr_scope_audit.py",
    "scripts/tests/test_archipelago_data_pipeline.py",
}


def git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{completed.stderr.strip()}")
    return completed.stdout


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def is_allowed_file(path: str) -> bool:
    normalized = normalize_path(path)
    return any(pattern.search(normalized) for pattern in ALLOWED_FILE_PATTERNS)


def find_forbidden_matches(diff_text: str) -> list[dict[str, str | int]]:
    matches: list[dict[str, str | int]] = []
    current_file = ""
    for line_number, line in enumerate(diff_text.splitlines(), start=1):
        if line.startswith("diff --git "):
            parts = line.split()
            current_file = parts[3][2:] if len(parts) >= 4 and parts[3].startswith("b/") else ""
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if current_file in FORBIDDEN_IMPLEMENTATION_EXEMPT_FILES:
            continue
        if FORBIDDEN_IMPLEMENTATION_ALLOWED_LINE_RE.search(line):
            continue
        if FORBIDDEN_IMPLEMENTATION_RE.search(line):
            matches.append(
                {
                    "file": current_file,
                    "line": line_number,
                    "text": line[:240],
                }
            )
    return matches


def run_scope_audit(base: str, head: str) -> dict[str, object]:
    merge_base = git(["merge-base", head, base]).strip()
    changed_files = [
        normalize_path(path)
        for path in git(["diff", "--name-only", f"{base}...{head}"]).splitlines()
        if path.strip()
    ]
    unexpected_files = [path for path in changed_files if not is_allowed_file(path)]
    forbidden_files = [path for path in changed_files if FORBIDDEN_FILE_RE.search(path)]

    implementation_diff = git(["diff", f"{base}...{head}", "--", *IMPLEMENTATION_DIFF_PATHS])
    forbidden_matches = find_forbidden_matches(implementation_diff)

    return {
        "base": base,
        "head": head,
        "mergeBase": merge_base,
        "changedFileCount": len(changed_files),
        "unexpectedFileCount": len(unexpected_files),
        "unexpectedFiles": unexpected_files,
        "forbiddenFileCount": len(forbidden_files),
        "forbiddenFiles": forbidden_files,
        "forbiddenImplementationMatchCount": len(forbidden_matches),
        "forbiddenImplementationMatches": forbidden_matches,
        "status": "passed" if not unexpected_files and not forbidden_files and not forbidden_matches else "failed",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/codex/ap-world-skeleton-checkpoint")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args(argv)

    report = run_scope_audit(base=args.base, head=args.head)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
