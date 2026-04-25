from __future__ import annotations

from copy import deepcopy

GAME_NAME = "Command & Conquer Generals: Zero Hour"
LOGIC_MODEL = "generalszh-alpha-grouped-v1"
SLOT_DATA_VERSION = 2
LOCATION_NAMESPACE_BASE = 270000000
MISSION_VICTORY_BASE = 270000000
CLUSTER_UNIT_BASE = 270010000

MAP_SLOTS: dict[str, int] = {
    "air_force": 0,
    "laser": 1,
    "superweapon": 2,
    "tank": 3,
    "nuke": 4,
    "stealth": 5,
    "toxin": 6,
    "boss": 7,
}

MAIN_MAP_KEYS: tuple[str, ...] = tuple(key for key in MAP_SLOTS if key != "boss")

MAP_DISPLAY_NAMES: dict[str, str] = {
    "air_force": "Air Force General",
    "laser": "Laser General",
    "superweapon": "Superweapons General",
    "tank": "Tank General",
    "nuke": "Nuke General",
    "stealth": "Stealth General",
    "toxin": "Toxin General",
    "boss": "Boss General",
}

VICTORY_MEDAL_ITEM_NAMES: dict[str, str] = {
    key: f"{MAP_DISPLAY_NAMES[key]} Medal" for key in MAIN_MAP_KEYS
}


def validate_map_key(map_key: str) -> None:
    if map_key not in MAP_SLOTS:
        raise ValueError(f"Unknown GeneralsZH map key: {map_key!r}")


def victory_medal_item_name(map_key: str) -> str:
    validate_map_key(map_key)
    if map_key == "boss":
        raise ValueError("Boss victory is the final goal event, not a shuffled medal item")
    return VICTORY_MEDAL_ITEM_NAMES[map_key]


def mission_victory_location_id(map_key: str) -> int:
    validate_map_key(map_key)
    return MISSION_VICTORY_BASE + MAP_SLOTS[map_key]


def cluster_unit_location_id(map_key: str, cluster_index: int, unit_index: int) -> int:
    validate_map_key(map_key)
    if not 0 <= cluster_index <= 99:
        raise ValueError(f"cluster_index must be 0..99, got {cluster_index!r}")
    if not 1 <= unit_index <= 99:
        raise ValueError(f"unit_index must be 1..99, got {unit_index!r}")
    return CLUSTER_UNIT_BASE + (MAP_SLOTS[map_key] * 10000) + (cluster_index * 100) + unit_index


def mission_runtime_key(map_key: str) -> str:
    validate_map_key(map_key)
    return f"mission.{map_key}.victory"


def cluster_runtime_key(map_key: str, cluster_index: int, unit_index: int) -> str:
    validate_map_key(map_key)
    if not 0 <= cluster_index <= 99:
        raise ValueError(f"cluster_index must be 0..99, got {cluster_index!r}")
    if not 1 <= unit_index <= 99:
        raise ValueError(f"unit_index must be 1..99, got {unit_index!r}")
    return f"cluster.{map_key}.c{cluster_index:02d}.u{unit_index:02d}"


def cluster_location_name(map_key: str, cluster_index: int, unit_index: int) -> str:
    validate_map_key(map_key)
    if not 0 <= cluster_index <= 99:
        raise ValueError(f"cluster_index must be 0..99, got {cluster_index!r}")
    if not 1 <= unit_index <= 99:
        raise ValueError(f"unit_index must be 1..99, got {unit_index!r}")
    return f"Cluster Unit - {MAP_DISPLAY_NAMES[map_key]} c{cluster_index:02d} u{unit_index:02d}"


def mission_location_name(map_key: str) -> str:
    validate_map_key(map_key)
    return f"Mission Victory - {MAP_DISPLAY_NAMES[map_key]}"


def build_empty_mission_gate() -> dict[str, object]:
    gate = {
        "statusModel": "hold_win_v1",
        "hold": {
            "requirements": [],
            "startingMoneyFloor": "none",
            "productionFloor": "none",
        },
        "win": {
            "requirements": [],
            "startingMoneyFloor": "none",
            "productionFloor": "none",
        },
    }
    return deepcopy(gate)


def build_slot_data_shell(
    seed_id: str,
    slot_name: str,
    session_nonce: str,
    unlock_preset: str = "default",
) -> dict[str, object]:
    maps: dict[str, object] = {}
    for map_key, map_slot in MAP_SLOTS.items():
        maps[map_key] = {
            "mapSlot": map_slot,
            "missionVictory": {
                "runtimeKey": mission_runtime_key(map_key),
                "apLocationId": mission_victory_location_id(map_key),
            },
            "missionGate": build_empty_mission_gate(),
            "clusters": [],
        }

    return {
        "version": SLOT_DATA_VERSION,
        "logicModel": LOGIC_MODEL,
        "seedId": seed_id,
        "slotName": slot_name,
        "sessionNonce": session_nonce,
        "unlockPreset": unlock_preset,
        "locationNamespaceBase": LOCATION_NAMESPACE_BASE,
        "maps": maps,
    }
