#!/usr/bin/env python3
"""Checkpoint 3 smoke: prove seeded/fallback boundary stays explicit."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.archipelago_bridge_local import atomic_write_json, run_cycle  # noqa: E402

BAD_HASH = "sha256:" + "0" * 64


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_contains(path: Path, needle: str, label: str, passed: list[str]) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if needle not in text:
        raise AssertionError(f"{label}: missing {needle!r} in {path}")
    passed.append(label)


def _assert_runtime_source_contract() -> list[str]:
    passed: list[str] = []
    state_cpp = REPO_ROOT / "GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp"
    spawner_cpp = REPO_ROOT / "GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp"
    score_cpp = REPO_ROOT / "GeneralsMD/Code/GameEngine/Source/GameClient/GUI/GUICallbacks/Menus/ScoreScreen.cpp"

    _assert_contains(
        state_cpp,
        "const Bool hasReference = slotDataPath.isNotEmpty() || slotDataHash.isNotEmpty() || slotDataVersion != 0;",
        "runtime treats any slot-data metadata as seeded reference",
        passed,
    )
    _assert_contains(
        state_cpp,
        "[Archipelago] No slot-data reference in inbound; using demo fallback",
        "runtime logs no-reference fallback",
        passed,
    )
    _assert_contains(
        state_cpp,
        "m_slotDataReferencePresent = FALSE;",
        "runtime clears slot-data reference for no-reference fallback",
        passed,
    )
    _assert_contains(
        state_cpp,
        "m_slotDataLoadFailed = TRUE;",
        "runtime records slot-data rejection",
        passed,
    )
    _assert_contains(
        state_cpp,
        "if ( m_slotDataReferencePresent && !hasVerifiedSlotData() )",
        "runtime ignores completions when seeded reference is unverified",
        passed,
    )
    _assert_contains(
        state_cpp,
        "if ( raw != \"Seed-Slot-Data.json\" )",
        "runtime accepts only canonical slot-data path",
        passed,
    )

    _assert_contains(
        spawner_cpp,
        "if ( !m_enabled && ( TheArchipelagoState == NULL || !TheArchipelagoState->hasSlotDataReference() ) )",
        "spawner loads demo INI only without slot-data reference",
        passed,
    )
    _assert_contains(
        spawner_cpp,
        "Slot-data reference exists but is not verified; seeded spawning disabled, no demo fallback",
        "spawner rejects bad seeded reference without fallback",
        passed,
    )
    _assert_contains(
        spawner_cpp,
        "config.usesSlotData ? \"Seed-Slot-Data.json\" : \"UnlockableChecksDemo.ini fallback\"",
        "spawner reports seeded versus fallback source",
        passed,
    )
    _assert_contains(
        spawner_cpp,
        "if ( !config.usesSlotData )\n\t\tremapCurrentMapRewardGroupsForUnlockedState();",
        "seeded mode skips demo reward-group remap",
        passed,
    )
    _assert_contains(
        spawner_cpp,
        "Seeded check %s recorded; AP bridge handles reward",
        "seeded mode skips local fallback rewards",
        passed,
    )
    _assert_contains(
        spawner_cpp,
        "seeded mode must not invent or respawn completed selected checks",
        "seeded mode does not invent completed checks",
        passed,
    )

    _assert_contains(
        score_cpp,
        "else if ( TheArchipelagoState->hasSlotDataReference() )",
        "mission victory does not use legacy numeric fallback when seeded reference is bad",
        passed,
    )
    _assert_contains(
        score_cpp,
        "Mission victory ignored because slot-data reference is present but not verified",
        "mission victory logs bad seeded reference",
        passed,
    )

    return passed


def run_runtime_fallback_contract_check() -> dict[str, Any]:
    source_checks = _assert_runtime_source_contract()

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        fallback_dir = root / "fallback" / "Archipelago"
        fallback_status = run_cycle(
            fallback_dir,
            fallback_dir / "LocalBridgeSession.json",
            fallback_dir / "Bridge-Inbound.json",
            fallback_dir / "Bridge-Outbound.json",
            fallback_dir / "Bridge-Events.jsonl",
            reset_session=True,
            emit_slot_data=False,
        )
        fallback_inbound = _load_json(fallback_dir / "Bridge-Inbound.json")
        slot_keys = [key for key in fallback_inbound if key.startswith("slotData")]
        if slot_keys:
            raise AssertionError(f"no-reference fallback inbound unexpectedly has slot-data fields: {slot_keys}")
        if (fallback_dir / "Seed-Slot-Data.json").exists():
            raise AssertionError("no-reference fallback unexpectedly emitted Seed-Slot-Data.json")

        bad_hash_dir = root / "bad_hash" / "Archipelago"
        run_cycle(
            bad_hash_dir,
            bad_hash_dir / "LocalBridgeSession.json",
            bad_hash_dir / "Bridge-Inbound.json",
            bad_hash_dir / "Bridge-Outbound.json",
            bad_hash_dir / "Bridge-Events.jsonl",
            reset_session=True,
            emit_slot_data=True,
        )
        bad_hash_inbound = _load_json(bad_hash_dir / "Bridge-Inbound.json")
        bad_hash_payload = copy.deepcopy(bad_hash_inbound)
        bad_hash_payload["slotDataHash"] = BAD_HASH
        atomic_write_json(bad_hash_dir / "Bridge-Inbound.json", bad_hash_payload)

        seeded_dir = root / "seeded" / "Archipelago"
        run_cycle(
            seeded_dir,
            seeded_dir / "LocalBridgeSession.json",
            seeded_dir / "Bridge-Inbound.json",
            seeded_dir / "Bridge-Outbound.json",
            seeded_dir / "Bridge-Events.jsonl",
            reset_session=True,
            emit_slot_data=True,
            unlock_preset="minimal",
        )
        atomic_write_json(seeded_dir / "Bridge-Outbound.json", {"completedChecks": ["cluster.tank.c02.u01"]})
        unselected_rejected = False
        try:
            run_cycle(
                seeded_dir,
                seeded_dir / "LocalBridgeSession.json",
                seeded_dir / "Bridge-Inbound.json",
                seeded_dir / "Bridge-Outbound.json",
                seeded_dir / "Bridge-Events.jsonl",
                emit_slot_data=True,
                unlock_preset="minimal",
            )
        except ValueError:
            unselected_rejected = True
        if not unselected_rejected:
            raise AssertionError("seeded minimal preset accepted unselected hard-cluster runtime key")

    return {
        "no_slot_data_reference": {
            "inbound_has_slot_data_fields": False,
            "slot_data_file_emitted": False,
            "session_counts": {
                key: len(fallback_status["session"][key])
                for key in ("completedChecks", "completedLocations")
            },
        },
        "bad_hash_reference": {
            "slotDataPath": bad_hash_payload["slotDataPath"],
            "slotDataVersion": bad_hash_payload["slotDataVersion"],
            "slotDataHash": bad_hash_payload["slotDataHash"],
            "expected_runtime_behavior": "reject seeded mode; no demo fallback",
        },
        "selected_seeded_mode": {
            "unselected_runtime_key_rejected": unselected_rejected,
            "expected_runtime_behavior": "spawn/use selected slot-data checks only",
        },
        "source_contract_checks": source_checks,
    }


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description="Check runtime slot-data fallback boundaries.").parse_args()


def main() -> int:
    parse_args()
    print(json.dumps(run_runtime_fallback_contract_check(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
