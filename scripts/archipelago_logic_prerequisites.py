"""
Defense and objective logic prerequisites for Archipelago.

- compute_player_strength(unlocks, player_general) -> number
- can_defend(player_strength, enemy_general_id, difficulty) -> bool
- can_beat_mission(player_strength, enemy_general_id, difficulty) -> bool

Excludes from strength: upgrades, strategy buildings, money buildings, super weapons
(unless include_superweapons_in_logic). Uses explicit unit lists from enemy_general_profiles.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILES = REPO_ROOT / "Data" / "Archipelago" / "enemy_general_profiles.json"


def load_enemy_profiles(path: Path | None = None) -> dict:
    """Load enemy_general_profiles.json."""
    path = path or DEFAULT_PROFILES
    if not path.exists():
        return {"generals": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def compute_player_strength(
    unlocks: set[str],
    player_general: str,
    *,
    include_superweapons: bool = False,
) -> float:
    """
    Compute dynamic player strength from unlocked units/buildings.

    Excludes: upgrades, strategy buildings, money buildings (Black Market,
    Supply Drop Zone, Internet Center), super weapons (unless include_superweapons).
    Returns a numeric value to compare to enemy defense_strength / objective_strength.
    """
    # Stub: in real implementation, map unlocks to unit/building templates per
    # player_general, then score by explicit counter coverage vs threat_units.
    _ = unlocks, player_general, include_superweapons
    return 50.0


def can_defend(
    player_strength: float,
    enemy_general_id: str,
    difficulty: str,
    profiles_path: Path | None = None,
) -> bool:
    """True if player_strength >= enemy defense_strength for this general and difficulty."""
    profiles = load_enemy_profiles(profiles_path)
    gens = profiles.get("generals", {})
    gen = gens.get(enemy_general_id, {})
    diff = gen.get("difficulty", {}).get(difficulty.lower(), {})
    defense = float(diff.get("defense_strength", 0))
    return player_strength >= defense


def can_beat_mission(
    player_strength: float,
    enemy_general_id: str,
    difficulty: str,
    profiles_path: Path | None = None,
) -> bool:
    """True if player_strength >= enemy objective_strength for this general and difficulty."""
    profiles = load_enemy_profiles(profiles_path)
    gens = profiles.get("generals", {})
    gen = gens.get(enemy_general_id, {})
    diff = gen.get("difficulty", {}).get(difficulty.lower(), {})
    objective = float(diff.get("objective_strength", 0))
    return player_strength >= objective


if __name__ == "__main__":
    profiles = load_enemy_profiles()
    for gid, gen in profiles.get("generals", {}).items():
        d = gen.get("difficulty", {}).get("medium", {})
        print(f"{gid}: defense={d.get('defense_strength')} objective={d.get('objective_strength')}")
    print("can_defend(60, 'TankGeneral', 'medium'):", can_defend(60, "TankGeneral", "medium"))
    print("can_beat_mission(90, 'TankGeneral', 'medium'):", can_beat_mission(90, "TankGeneral", "medium"))
