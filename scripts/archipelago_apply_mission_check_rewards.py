#!/usr/bin/env python3
"""Inject deterministic mission/check reward groups into UnlockableChecksDemo.ini."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REWARDS = REPO_ROOT / "Data" / "Archipelago" / "mission_check_rewards.json"


def parse_comma_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_reward_line(check_ids: list[str], reward_map: dict[str, str]) -> str:
    reward_groups = [reward_map.get(check_id, "") for check_id in check_ids]
    if not reward_groups or any(not reward_group for reward_group in reward_groups):
        missing = [check_id for check_id, reward_group in zip(check_ids, reward_groups) if not reward_group]
        raise ValueError(f"Missing reward-group assignments for check IDs: {', '.join(missing)}")
    return ",".join(reward_groups)


def upsert_assignment_line(section_lines: list[str], key_name: str, value: str, insert_after: str) -> list[str]:
    updated: list[str] = []
    replaced = False
    inserted = False
    for line in section_lines:
        stripped = line.strip()
        if stripped.lower().startswith(f"{key_name.lower()} ="):
            updated.append(f"{key_name} = {value}")
            replaced = True
            continue
        updated.append(line)
        if (not replaced and not inserted) and stripped.lower().startswith(f"{insert_after.lower()} ="):
            updated.append(f"{key_name} = {value}")
            inserted = True
    if not replaced and not inserted:
        updated.append(f"{key_name} = {value}")
    return updated


def apply_rewards_to_ini(ini_text: str, rewards: dict[str, dict[str, str]]) -> str:
    lines = ini_text.splitlines()
    output: list[str] = []
    current_section: str | None = None
    section_lines: list[str] = []

    def flush_section() -> None:
        nonlocal current_section, section_lines
        if current_section is None:
            output.extend(section_lines)
            section_lines = []
            return

        reward_map = rewards.get(current_section, {})
        if reward_map:
            unit_check_ids: list[str] = []
            building_check_ids: list[str] = []
            for line in section_lines:
                stripped = line.strip()
                if stripped.lower().startswith("unitcheckids ="):
                    unit_check_ids = parse_comma_list(stripped.split("=", 1)[1].strip())
                elif stripped.lower().startswith("buildingcheckids ="):
                    building_check_ids = parse_comma_list(stripped.split("=", 1)[1].strip())

            if unit_check_ids:
                section_lines = upsert_assignment_line(
                    section_lines,
                    "UnitRewardGroups",
                    build_reward_line(unit_check_ids, reward_map),
                    "UnitCheckIds",
                )
            if building_check_ids:
                section_lines = upsert_assignment_line(
                    section_lines,
                    "BuildingRewardGroups",
                    build_reward_line(building_check_ids, reward_map),
                    "BuildingCheckIds",
                )

        output.extend(section_lines)
        section_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            flush_section()
            current_section = stripped[1:-1]
            section_lines = [line]
            continue
        if current_section is None:
            section_lines.append(line)
        else:
            section_lines.append(line)

    flush_section()
    return "\n".join(output) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply deterministic check reward groups to UnlockableChecksDemo.ini")
    parser.add_argument("--ini", type=Path, required=True, help="Path to UnlockableChecksDemo.ini to update")
    parser.add_argument("--rewards", type=Path, default=DEFAULT_REWARDS, help="Path to mission_check_rewards.json")
    args = parser.parse_args()

    rewards = json.loads(args.rewards.read_text(encoding="utf-8"))
    ini_text = args.ini.read_text(encoding="utf-8")
    updated = apply_rewards_to_ini(ini_text, rewards)
    args.ini.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
