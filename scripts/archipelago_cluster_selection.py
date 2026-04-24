"""
Random cluster selection for Archipelago seed generation.

Given per-map cluster definitions and options (clusters_per_map, slots_per_cluster),
samples which clusters and slots are used for locations. To be consumed by the
Archipelago Python world at seed generation.
"""

from __future__ import annotations

import json
import random
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLUSTER_CONFIG = REPO_ROOT / "Data" / "Archipelago" / "cluster_config.json"


def load_cluster_config(path: Path | None = None) -> dict:
    """Load cluster_config.json."""
    path = path or DEFAULT_CLUSTER_CONFIG
    if not path.exists():
        return {"version": 1, "defaults": {"clusters_per_map": 3, "slots_per_cluster": 2}, "maps": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def select_clusters_for_map(
    map_name: str,
    clusters_per_map: int,
    slots_per_cluster: int,
    rng: random.Random,
    config_path: Path | None = None,
) -> list[dict]:
    """
    For a given map, randomly select clusters_per_map clusters and return
    one entry per location (cluster + slot index).

    Returns list of:
      {
        "cluster_id": str,
        "waypoint_name": str,
        "x": int, "y": int, "tier": str,
        "slot_index": int,
        "location_id": str  (e.g. "MapName_Cluster_1_Slot_0")
      }
    """
    cfg = load_cluster_config(config_path)
    maps_def = cfg.get("maps", {})
    clusters = list(maps_def.get(map_name, []))
    if not clusters:
        return []

    n = min(clusters_per_map, len(clusters))
    selected = rng.sample(clusters, n)
    locations = []
    for idx, cluster in enumerate(selected):
        cid = cluster.get("cluster_id", f"Cluster_{idx}")
        waypoint = cluster.get("waypoint_name", cid)
        for slot in range(slots_per_cluster):
            loc_id = f"{map_name}_{cid}_Slot_{slot}"
            locations.append({
                "cluster_id": cid,
                "waypoint_name": waypoint,
                "x": cluster.get("x", 0),
                "y": cluster.get("y", 0),
                "tier": cluster.get("tier", "medium"),
                "slot_index": slot,
                "location_id": loc_id,
            })
    return locations


def stub_for_world():
    """
    Stub for Archipelago world set_rules/create_regions:
    - Call select_clusters_for_map for each of the 7 challenge maps.
    - Create one location per entry in the returned list.
    - At fill time, assign spawn (defender template) per slot from matchup graph
      defender pool for that cluster tier.
    """
    rng = random.Random(12345)
    cfg = load_cluster_config()
    defaults = cfg.get("defaults", {})
    clusters_per_map = defaults.get("clusters_per_map", 3)
    slots_per_cluster = defaults.get("slots_per_cluster", 2)
    map_names = [k for k in cfg.get("maps", {}).keys() if not k.startswith("_")]
    for map_name in map_names:
        locs = select_clusters_for_map(
            map_name, clusters_per_map, slots_per_cluster, rng
        )
        # In real world: create_regions with one location per loc["location_id"]
        for loc in locs:
            pass  # location_id -> Archipelago location name


if __name__ == "__main__":
    rng = random.Random(42)
    cfg = load_cluster_config()
    defaults = cfg.get("defaults", {})
    for map_name in list(cfg.get("maps", {}).keys())[:1]:
        locs = select_clusters_for_map(
            map_name,
            defaults.get("clusters_per_map", 3),
            defaults.get("slots_per_cluster", 2),
            rng,
        )
        print(f"Map: {map_name} -> {len(locs)} locations")
        for loc in locs[:4]:
            print(f"  {loc['location_id']} tier={loc['tier']}")
