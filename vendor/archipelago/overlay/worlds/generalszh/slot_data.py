from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from .constants import (
    CLUSTER_UNIT_BASE,
    LOGIC_MODEL,
    MAP_SLOTS,
    SLOT_DATA_VERSION,
    build_slot_data_shell,
    cluster_runtime_key,
    cluster_unit_location_id,
    mission_runtime_key,
    mission_victory_location_id,
)
from .testing_catalog import (
    ALLOWED_CLUSTER_CLASSES,
    ALLOWED_MISSION_GATES,
    ALLOWED_TIERS,
    ALLOWED_WEAKNESSES,
    TIER_SCALING,
    selected_testing_clusters,
)

FLOORS = ("none", "low", "medium", "high")


class SlotDataValidationError(ValueError):
    pass


def canonical_slot_data_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def slot_data_sha256(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_slot_data_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def build_testing_slot_data(
    seed_id: str,
    slot_name: str,
    session_nonce: str,
    unlock_preset: str = "default",
) -> dict[str, Any]:
    payload = build_slot_data_shell(
        seed_id=seed_id,
        slot_name=slot_name,
        session_nonce=session_nonce,
        unlock_preset=unlock_preset,
    )
    selected = selected_testing_clusters(unlock_preset)

    for map_key, clusters in selected.items():
        map_payload = payload["maps"][map_key]
        map_payload["clusters"] = [
            _cluster_to_slot_data(map_key, cluster)
            for cluster in clusters
        ]

    validate_slot_data(payload)
    return payload


def _cluster_to_slot_data(map_key: str, cluster: dict[str, Any]) -> dict[str, Any]:
    cluster_index = int(cluster["clusterIndex"])
    cluster_key = f"c{cluster_index:02d}"
    requirements = list(cluster["requiredWeaknesses"])
    units = []
    for unit in cluster["units"]:
        unit_index = int(unit["unitIndex"])
        unit_key = f"u{unit_index:02d}"
        units.append(
            {
                "unitKey": unit_key,
                "runtimeKey": cluster_runtime_key(map_key, cluster_index, unit_index),
                "apLocationId": cluster_unit_location_id(map_key, cluster_index, unit_index),
                "defenderTemplate": unit["defenderTemplate"],
                "displayName": unit.get("displayName", unit["defenderTemplate"]),
            }
        )

    return {
        "clusterKey": cluster_key,
        "label": cluster["label"],
        "tier": cluster["tier"],
        "clusterClass": cluster["clusterClass"],
        "primaryRequirement": requirements[0],
        "requiredWeaknesses": requirements,
        "yellowRequirement": cluster.get("yellowRequirement"),
        "requiredMissionGate": cluster.get("requiredMissionGate", "none"),
        "center": deepcopy(cluster["center"]),
        "tierScaling": deepcopy(TIER_SCALING[cluster["tier"]]),
        "units": units,
    }


def runtime_key_to_location_id(payload: dict[str, Any]) -> dict[str, int]:
    validate_slot_data(payload)
    mapping: dict[str, int] = {}
    for map_payload in payload["maps"].values():
        mission = map_payload["missionVictory"]
        mapping[mission["runtimeKey"]] = int(mission["apLocationId"])
        for cluster in map_payload["clusters"]:
            for unit in cluster["units"]:
                mapping[unit["runtimeKey"]] = int(unit["apLocationId"])
    return mapping


def translate_runtime_checks(payload: dict[str, Any], runtime_keys: list[str]) -> list[int]:
    mapping = runtime_key_to_location_id(payload)
    translated: list[int] = []
    missing: list[str] = []
    for runtime_key in runtime_keys:
        if runtime_key not in mapping:
            missing.append(runtime_key)
        else:
            translated.append(mapping[runtime_key])
    if missing:
        raise SlotDataValidationError(f"Unknown runtime check key(s): {', '.join(sorted(missing))}")
    return sorted(set(translated))


def validate_slot_data(payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    _require(payload.get("version") == SLOT_DATA_VERSION, "invalid slot-data version")
    _require(payload.get("logicModel") == LOGIC_MODEL, "invalid logic model")
    _require(set(payload.get("maps", {})) == set(MAP_SLOTS), "maps must match canonical map keys")

    seen_ids: set[int] = set()
    seen_keys: set[str] = set()

    for map_key, expected_slot in MAP_SLOTS.items():
        map_payload = payload["maps"][map_key]
        _require(map_payload.get("mapSlot") == expected_slot, f"{map_key}: bad mapSlot")
        _validate_mission(map_key, map_payload, seen_ids, seen_keys, warnings)
        for cluster in map_payload.get("clusters", []):
            _validate_cluster(map_key, cluster, seen_ids, seen_keys)

    return warnings


def _validate_mission(
    map_key: str,
    map_payload: dict[str, Any],
    seen_ids: set[int],
    seen_keys: set[str],
    warnings: list[str],
) -> None:
    mission = map_payload.get("missionVictory")
    _require(isinstance(mission, dict), f"{map_key}: missing missionVictory")
    _require(mission.get("runtimeKey") == mission_runtime_key(map_key), f"{map_key}: bad mission runtime key")
    _require(mission.get("apLocationId") == mission_victory_location_id(map_key), f"{map_key}: bad mission AP ID")
    _track_unique(mission["runtimeKey"], mission["apLocationId"], seen_keys, seen_ids)

    gate = map_payload.get("missionGate")
    _require(isinstance(gate, dict), f"{map_key}: missing missionGate")
    _require(gate.get("statusModel") == "hold_win_v1", f"{map_key}: missionGate statusModel drift")
    for stage in ("hold", "win"):
        stage_gate = gate.get(stage)
        _require(isinstance(stage_gate, dict), f"{map_key}: missing {stage} gate")
        requirements = stage_gate.get("requirements")
        _require(isinstance(requirements, list), f"{map_key}: {stage} requirements must be a list")
        _require(all(req in ALLOWED_WEAKNESSES for req in requirements), f"{map_key}: unknown {stage} requirement")
        _require(stage_gate.get("startingMoneyFloor") in FLOORS, f"{map_key}: bad {stage} money floor")
        _require(stage_gate.get("productionFloor") in FLOORS, f"{map_key}: bad {stage} production floor")
    if not gate["hold"]["requirements"] or not gate["win"]["requirements"]:
        warnings.append(f"{map_key}: missionGate requirements empty until mission pass")


def _validate_cluster(
    map_key: str,
    cluster: dict[str, Any],
    seen_ids: set[int],
    seen_keys: set[str],
) -> None:
    tier = cluster.get("tier")
    requirements = cluster.get("requiredWeaknesses")
    gate = cluster.get("requiredMissionGate", "none")
    cluster_key = cluster.get("clusterKey")
    _require(tier in ALLOWED_TIERS, f"{map_key}.{cluster_key}: invalid tier")
    _require(cluster.get("clusterClass") in ALLOWED_CLUSTER_CLASSES, f"{map_key}.{cluster_key}: invalid class")
    _require(gate in ALLOWED_MISSION_GATES, f"{map_key}.{cluster_key}: invalid mission gate")
    _require(isinstance(requirements, list) and requirements, f"{map_key}.{cluster_key}: missing weaknesses")
    _require(all(req in ALLOWED_WEAKNESSES for req in requirements), f"{map_key}.{cluster_key}: unknown weakness")
    _require(cluster.get("primaryRequirement") == requirements[0], f"{map_key}.{cluster_key}: primary mismatch")
    _require(isinstance(cluster.get("units"), list) and cluster["units"], f"{map_key}.{cluster_key}: empty units")

    if tier == "easy":
        _require(len(requirements) == 1, f"{map_key}.{cluster_key}: easy must require one weakness")
        _require(gate == "none", f"{map_key}.{cluster_key}: easy must not require Hold/Win")
    elif tier == "medium":
        _require(1 <= len(requirements) <= 2, f"{map_key}.{cluster_key}: medium must require one/two weaknesses")
        _require(gate == "hold", f"{map_key}.{cluster_key}: medium must require Hold")
    elif tier == "hard":
        _require(len(requirements) == 2, f"{map_key}.{cluster_key}: hard must require two weaknesses")
        _require(gate == "win", f"{map_key}.{cluster_key}: hard must require Win")

    cluster_index = int(str(cluster_key).removeprefix("c"))
    for unit in cluster["units"]:
        _require(unit.get("defenderTemplate"), f"{map_key}.{cluster_key}: unit missing defenderTemplate")
        unit_index = int(str(unit["unitKey"]).removeprefix("u"))
        expected_key = cluster_runtime_key(map_key, cluster_index, unit_index)
        expected_id = cluster_unit_location_id(map_key, cluster_index, unit_index)
        _require(unit.get("runtimeKey") == expected_key, f"{map_key}.{cluster_key}: unit runtime key drift")
        _require(unit.get("apLocationId") == expected_id, f"{map_key}.{cluster_key}: unit AP ID drift")
        _require(expected_id >= CLUSTER_UNIT_BASE, f"{map_key}.{cluster_key}: unit AP ID below cluster base")
        _track_unique(expected_key, expected_id, seen_keys, seen_ids)


def _track_unique(runtime_key: str, ap_location_id: int, seen_keys: set[str], seen_ids: set[int]) -> None:
    _require(runtime_key not in seen_keys, f"duplicate runtime key: {runtime_key}")
    _require(ap_location_id not in seen_ids, f"duplicate AP location ID: {ap_location_id}")
    seen_keys.add(runtime_key)
    seen_ids.add(ap_location_id)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SlotDataValidationError(message)
