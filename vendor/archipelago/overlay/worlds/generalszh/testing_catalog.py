from __future__ import annotations

from copy import deepcopy
from typing import Any

from .constants import MAP_SLOTS

ClusterDef = dict[str, Any]

TIER_SCALING: dict[str, dict[str, float | int]] = {
    "easy": {"hpMult": 1.0, "dmgMult": 1.0, "veterancyRank": 1},
    "medium": {"hpMult": 2.0, "dmgMult": 1.25, "veterancyRank": 2},
    "hard": {"hpMult": 3.0, "dmgMult": 1.5, "veterancyRank": 3},
}

WEAKNESS_TO_ITEMS: dict[str, tuple[str, ...]] = {
    "anti_infantry": ("Shared Machine Gun Vehicles",),
    "anti_vehicle": ("Shared Rocket Infantry", "Shared Tanks"),
    "siege_units": ("Shared Artillery",),
    "frontline_units": ("Shared Tanks",),
    "detectors": ("Upgrade Radar",),
    "anti_air": ("Shared Rocket Infantry", "Shared Machine Gun Vehicles"),
}

ALLOWED_WEAKNESSES: tuple[str, ...] = tuple(WEAKNESS_TO_ITEMS)
ALLOWED_TIERS: tuple[str, ...] = ("easy", "medium", "hard")
ALLOWED_CLUSTER_CLASSES: tuple[str, ...] = (
    "infantry_swarm",
    "vehicle_pack",
    "armor",
    "fort",
    "artillery",
)
ALLOWED_MISSION_GATES: tuple[str, ...] = ("none", "hold", "win")


def _unit(unit_index: int, template: str, display_name: str) -> dict[str, Any]:
    return {
        "unitIndex": unit_index,
        "defenderTemplate": template,
        "displayName": display_name,
    }


def _cluster(
    cluster_index: int,
    label: str,
    tier: str,
    cluster_class: str,
    requirements: tuple[str, ...],
    yellow_requirement: str | None,
    required_mission_gate: str,
    x: float,
    y: float,
    radius: float,
    units: tuple[dict[str, Any], ...],
) -> ClusterDef:
    return {
        "clusterIndex": cluster_index,
        "label": label,
        "tier": tier,
        "clusterClass": cluster_class,
        "requiredWeaknesses": list(requirements),
        "yellowRequirement": yellow_requirement,
        "requiredMissionGate": required_mission_gate,
        "center": {"x": x, "y": y, "radius": radius},
        "units": [deepcopy(unit) for unit in units],
    }


def _main_map_clusters(map_slot: int) -> list[ClusterDef]:
    x_offset = float(map_slot * 90)
    y_offset = float(map_slot * 55)
    return [
        _cluster(
            0,
            "Infantry Screen",
            "easy",
            "infantry_swarm",
            ("anti_infantry",),
            "frontline_units",
            "none",
            900.0 + x_offset,
            1200.0 + y_offset,
            150.0,
            (
                _unit(1, "GLAInfantryAngryMobNexus", "Angry Mob"),
                _unit(2, "GLAInfantryWorker", "Worker"),
            ),
        ),
        _cluster(
            1,
            "Armor Pocket",
            "medium",
            "armor",
            ("anti_vehicle",),
            "frontline_units",
            "hold",
            1400.0 + x_offset,
            1600.0 + y_offset,
            175.0,
            (
                _unit(1, "GLATankScorpion", "Scorpion"),
                _unit(2, "GLAVehicleQuadCannon", "Quad Cannon"),
            ),
        ),
        _cluster(
            2,
            "Fortified Push",
            "hard",
            "fort",
            ("anti_vehicle", "siege_units"),
            None,
            "win",
            1900.0 + x_offset,
            2100.0 + y_offset,
            210.0,
            (
                _unit(1, "ChinaTankOverlord", "Overlord"),
                _unit(2, "AmericaVehicleTomahawk", "Tomahawk"),
            ),
        ),
    ]


def _boss_clusters() -> list[ClusterDef]:
    return [
        _cluster(
            0,
            "Boss Perimeter",
            "hard",
            "fort",
            ("frontline_units", "siege_units"),
            None,
            "win",
            2200.0,
            2200.0,
            240.0,
            (
                _unit(1, "AmericaTankPaladin", "Paladin"),
                _unit(2, "ChinaVehicleNukeLauncher", "Nuke Cannon"),
            ),
        )
    ]


def all_testing_clusters() -> dict[str, list[ClusterDef]]:
    catalog: dict[str, list[ClusterDef]] = {}
    for map_key, map_slot in MAP_SLOTS.items():
        catalog[map_key] = _boss_clusters() if map_key == "boss" else _main_map_clusters(map_slot)
    return catalog


def selected_testing_clusters(unlock_preset: str = "default") -> dict[str, list[ClusterDef]]:
    allowed_tiers = {"easy", "medium"} if unlock_preset == "minimal" else {"easy", "medium", "hard"}
    selected: dict[str, list[ClusterDef]] = {}
    for map_key, clusters in all_testing_clusters().items():
        selected[map_key] = [
            deepcopy(cluster)
            for cluster in clusters
            if cluster["tier"] in allowed_tiers
        ]
    return selected
