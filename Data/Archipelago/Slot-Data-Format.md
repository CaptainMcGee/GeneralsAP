# Slot Data Format (Future Bridge Payload)

`UnlockableCheckSpawner` still falls back to `Data/INI/UnlockableChecksDemo.ini` at runtime. The implemented bridge foundation now covers unlock/general/location/check state through `Bridge-Inbound.json` and `Bridge-Outbound.json`; this document remains the target payload for future spawned-check seed data.

Related docs:

- `Docs/Archipelago/Operations/Archipelago-State-Sync-Architecture.md`
- `Docs/Archipelago/Operations/Player-Release-Architecture.md`

## Intended Role

The Archipelago bridge process will eventually deliver seed-specific spawned-check data to the game client, either inline in bridge state or via a separate referenced JSON file. `UnlockableCheckSpawner` should consume that data when available and only use `UnlockableChecksDemo.ini` as a fallback.

## JSON Structure (Per Seed)

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

## Separation From State Sync

The state bridge and the future slot-data payload solve different problems:

- `Bridge-Inbound.json` / `Bridge-Outbound.json`: sync local Archipelago progression state
- slot data JSON: tell the spawner which challenge checks exist for this seed and where to place them

That separation matters because GeneralsAP has save/load-sensitive local progression even before the real seed payload is available.

## Tier Scaling Reference

| Tier | hp_mult | dmg_mult | veterancy_rank |
|------|---------|----------|----------------|
| easy | 2.0 | 1.0 | 1 |
| medium | 3.0 | 1.5 | 2 |
| hard | 4.0 | 2.0 | 3 |

Values remain tunable.

## Next Implementation Step

The next backend step is to make `UnlockableCheckSpawner` accept real slot data from the bridge path instead of only `UnlockableChecksDemo.ini`.
