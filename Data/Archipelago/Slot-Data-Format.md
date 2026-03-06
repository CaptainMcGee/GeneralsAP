# Slot Data Format (Archipelago → Game Client)

Used by the Archipelago Python world to pass spawn assignments and cluster data to the game client. `UnlockableCheckSpawner` reads slot data when available; otherwise it falls back to `UnlockableChecksDemo.ini`.

## JSON structure (per seed)

```json
{
  "version": 1,
  "maps": {
    "MapName": {
      "cluster_waypoints": [
        { "cluster_id": "Cluster_1", "waypoint_name": "Waypoint_1", "x": 100, "y": 200, "tier": "easy" }
      ],
      "spawn_assignments": [
        {
          "location_id": "MapName_Cluster_1_Slot_0",
          "defender_template": "AmericaInfantryPathfinder",
          "waypoint_name": "Waypoint_1",
          "hp_mult": 2.0,
          "dmg_mult": 1.0,
          "veterancy_rank": 1
        }
      ]
    }
  }
}
```

- **cluster_waypoints**: From cluster definition tool / `cluster_config.json`; selected clusters for this seed.
- **spawn_assignments**: One entry per location; `defender_template` = unit to spawn; `hp_mult`/`dmg_mult`/`veterancy_rank` = tier scaling (easy/medium/hard).
- Game client receives this (e.g. via file or IPC); `UnlockableCheckSpawner` uses it to spawn the correct unit at the correct waypoint with the correct stats.

## Tier scaling (reference)

| Tier   | hp_mult | dmg_mult | veterancy_rank |
|--------|---------|----------|----------------|
| easy   | 2.0     | 1.0      | 1              |
| medium | 3.0     | 1.5      | 2              |
| hard   | 4.0     | 2.0      | 3              |

(Values may be tuned in config.)
