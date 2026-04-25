#!/usr/bin/env python3
"""Optional real-Archipelago generation smoke for the materialized GeneralsZH world."""

from __future__ import annotations

import textwrap
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AP_WORKTREE = REPO / "build" / "archipelago" / "archipelago-worktree"


def main() -> int:
    if not AP_WORKTREE.exists():
        print(f"SKIP: materialized Archipelago worktree missing: {AP_WORKTREE}")
        return 0

    code = f"""
import logging
import random
import sys
import warnings
from argparse import Namespace
from pathlib import Path

root = Path({str(AP_WORKTREE)!r})
sys.path.insert(0, str(root))
logging.basicConfig(level=logging.CRITICAL)
warnings.filterwarnings("ignore", message="_speedups not available.*")

try:
    import schema  # noqa: F401
except ModuleNotFoundError as exc:
    print(f"SKIP: optional Archipelago dependency missing: {{exc}}")
    raise SystemExit(0)

try:
    from BaseClasses import CollectionState, MultiWorld
    from Fill import distribute_items_restrictive
    from worlds.AutoWorld import AutoWorldRegister, call_all
    from worlds.generalszh import constants, items
    from worlds.generalszh.regions import MAIN_TO_BOSS_ENTRANCE
except ModuleNotFoundError as exc:
    print(f"SKIP: optional Archipelago dependency missing: {{exc}}")
    raise SystemExit(0)
except Exception as exc:
    print(f"FAIL: GeneralsZH real Archipelago import failed: {{exc}}")
    raise SystemExit(1)

try:
    game = constants.GAME_NAME
    world_type = AutoWorldRegister.world_types[game]
    multiworld = MultiWorld(1)
    multiworld.game[1] = game
    multiworld.player_name = {{1: "Tester"}}
    multiworld.set_seed(12345)
    random.seed(multiworld.seed)
    multiworld.seed_name = "GeneralsAPSmoke12345"

    args = Namespace()
    for name, option in world_type.options_dataclass.type_hints.items():
        setattr(args, name, {{1: option.from_any(option.default)}})
    multiworld.set_options(args)
    multiworld.state = CollectionState(multiworld)

    for step in ("generate_early", "create_regions", "create_items", "set_rules", "connect_entrances", "generate_basic", "pre_fill"):
        call_all(multiworld, step)

    medals = tuple(constants.VICTORY_MEDAL_ITEM_NAMES.values())
    medal_counts = {{name: sum(1 for item in multiworld.itempool if item.name == name) for name in medals}}
    assert all(count == 1 for count in medal_counts.values()), medal_counts
    assert "Boss General Medal" not in items.ITEM_NAME_TO_ID
    assert not any(name.endswith(" Defeated") for name in items.ITEM_NAME_TO_ID), items.ITEM_NAME_TO_ID
    assert len(multiworld.itempool) == len([loc for loc in multiworld.get_locations() if loc.item is None]), (
        len(multiworld.itempool),
        len([loc for loc in multiworld.get_locations() if loc.item is None]),
    )

    boss_location = multiworld.get_location(constants.mission_location_name("boss"), 1)
    assert boss_location.address == constants.mission_victory_location_id("boss")
    assert boss_location.item is not None
    assert boss_location.item.name == "Victory"
    assert boss_location.item.code is None
    assert boss_location.item not in multiworld.itempool

    entrance = multiworld.get_entrance(MAIN_TO_BOSS_ENTRANCE, 1)
    empty_state = CollectionState(multiworld)
    assert not entrance.can_reach(empty_state)

    six_medal_state = CollectionState(multiworld)
    for item in [item for item in multiworld.itempool if item.name in medals[:-1]]:
        six_medal_state.collect(item, True)
    assert not entrance.can_reach(six_medal_state)

    all_medal_state = CollectionState(multiworld)
    for item in [item for item in multiworld.itempool if item.name in medals]:
        all_medal_state.collect(item, True)
    assert entrance.can_reach(all_medal_state)
    assert all_medal_state.count("Victory", 1) == 0
    assert not multiworld.completion_condition[1](all_medal_state)

    all_medal_state.collect(boss_location.item, True, boss_location)
    assert multiworld.completion_condition[1](all_medal_state)

    distribute_items_restrictive(multiworld)
    call_all(multiworld, "post_fill")
    call_all(multiworld, "finalize_multiworld")
except Exception as exc:
    print(f"FAIL: GeneralsZH real Archipelago generation smoke failed: {{exc}}")
    raise SystemExit(1)

print("PASS: generated/fill-smoked GeneralsZH world with shuffled medals and locked Boss Victory")
"""
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=str(AP_WORKTREE)).returncode


if __name__ == "__main__":
    raise SystemExit(main())
