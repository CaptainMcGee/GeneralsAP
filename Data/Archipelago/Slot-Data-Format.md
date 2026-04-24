# Slot Data Format

**Canonical status**: This document defines the future per-seed spawned-check payload contract for Archipelago alpha. It replaces the older generic-slot draft.

Related docs:

- [Archipelago-State-Sync-Architecture.md](../../Docs/Archipelago/Operations/Archipelago-State-Sync-Architecture.md)
- [Archipelago-Logic-Implementation-Guide.md](../../Docs/Archipelago/Planning/Archipelago-Logic-Implementation-Guide.md)
- [Archipelago-Implementation-Todo.md](../../Docs/Archipelago/Planning/Archipelago-Implementation-Todo.md)

---

## 1. Purpose

`Seed-Slot-Data.json` is immutable per seed/slot.

It exists to answer:

- which mission-victory locations exist for this seed
- which cluster-unit locations exist for this seed
- which AP numeric IDs map to which runtime keys
- which cluster class and tier each selected cluster uses
- which mission-gate schema applies to each map

It does **not** replace progression-state sync.

Keep these separate:

- `Bridge-Inbound.json` / `Bridge-Outbound.json`: mutable session state
- `Seed-Slot-Data.json`: immutable seed contract

Reason:

- smaller per-frame bridge churn
- easier save/load stability
- easier duplicate-submission protection
- easier profile/session validation

---

## 2. Transport Model

### File location

Recommended profile-local path:

```text
UserData/
  Archipelago/
    Bridge-Inbound.json
    Bridge-Outbound.json
    Seed-Slot-Data.json
```

### Ownership

| Layer | Owns |
|------|------|
| AP world | selected locations, numeric IDs, seed-facing options, grouped item model, completion condition |
| Bridge sidecar | writes `Seed-Slot-Data.json`, writes inbound reference metadata, translates runtime keys to AP location IDs |
| Game runtime | consumes `Seed-Slot-Data.json`, spawns selected checks, tracks local completion by runtime key |

### Inbound reference metadata

`Bridge-Inbound.json` should reference, not inline, the seed payload:

```json
{
  "bridgeVersion": 1,
  "sessionVersion": 1,
  "seedId": "example-seed",
  "slotName": "Player 1",
  "sessionNonce": "run-001",
  "slotDataVersion": 2,
  "slotDataPath": "Seed-Slot-Data.json",
  "slotDataHash": "sha256:example",
  "sessionOptions": {
    "startingCashBonus": 0,
    "productionMultiplier": 1.0,
    "disableZoomLimit": false,
    "starterGenerals": []
  }
}
```

Rules:

- bridge writes slot-data atomically
- bridge writes inbound metadata only after slot-data file is complete
- runtime reloads slot-data only when `sessionNonce` or `slotDataHash` changes
- bridge should refuse silent reseed of a live profile unless reset/rebind is explicit

---

## 3. Top-Level JSON Shape

```json
{
  "version": 2,
  "logicModel": "generalszh-alpha-grouped-v1",
  "seedId": "example-seed",
  "slotName": "Player 1",
  "sessionNonce": "run-001",
  "unlockPreset": "default",
  "locationNamespaceBase": 270000000,
  "maps": {
    "tank": {
      "mapSlot": 3,
      "missionVictory": {
        "runtimeKey": "mission.tank.victory",
        "apLocationId": 270000003
      },
      "missionGate": {
        "statusModel": "hold_win_v1",
        "hold": {
          "requirements": [],
          "startingMoneyFloor": "none",
          "productionFloor": "none"
        },
        "win": {
          "requirements": [],
          "startingMoneyFloor": "none",
          "productionFloor": "none"
        }
      },
      "clusters": [
        {
          "clusterKey": "c03",
          "tier": "medium",
          "clusterClass": "armor",
          "primaryRequirement": "anti_vehicle",
          "requiredWeaknesses": ["anti_vehicle"],
          "yellowRequirement": "siege_units",
          "requiredMissionGate": "hold",
          "center": {
            "x": 1042.0,
            "y": 2210.0,
            "radius": 180.0
          },
          "tierScaling": {
            "hpMult": 3.0,
            "dmgMult": 1.5,
            "veterancyRank": 2
          },
          "units": [
            {
              "unitKey": "u01",
              "runtimeKey": "cluster.tank.c03.u01",
              "apLocationId": 270040301,
              "defenderTemplate": "ChinaTankOverlord"
            },
            {
              "unitKey": "u02",
              "runtimeKey": "cluster.tank.c03.u02",
              "apLocationId": 270040302,
              "defenderTemplate": "ChinaTankOverlordGattlingCannon"
            }
          ]
        }
      ]
    }
  }
}
```

---

## 4. Required Fields

### Top level

| Field | Type | Meaning |
|------|------|---------|
| `version` | int | payload schema version; start with `2` for this contract |
| `logicModel` | string | logic contract name; lets bridge/runtime reject incompatible seeds |
| `seedId` | string | stable AP seed identifier |
| `slotName` | string | human-facing AP slot name |
| `sessionNonce` | string | bridge-run instance guard for profile/session binding |
| `unlockPreset` | string | `default` or `minimal` |
| `locationNamespaceBase` | int | reserved Generals location namespace base |
| `maps` | object | per-map selected content keyed by canonical map key |

### Per map

| Field | Type | Meaning |
|------|------|---------|
| `mapSlot` | int | canonical slot index from guide |
| `missionVictory` | object | mission-victory runtime key and AP ID |
| `missionGate` | object | gate schema and, later, authored `Hold` / `Win` data |
| `clusters` | array | selected clusters for this map |

### Mission gate object

Use this structure now, even though exact per-general rows are deferred:

| Field | Type | Meaning |
|------|------|---------|
| `statusModel` | string | `hold_win_v1` |
| `hold.requirements` | array[string] | unit-type requirements; may be empty until authored |
| `hold.startingMoneyFloor` | string | `none` / `low` / `medium` / `high` |
| `hold.productionFloor` | string | `none` / `low` / `medium` / `high` |
| `win.requirements` | array[string] | unit-type requirements; may be empty until authored |
| `win.startingMoneyFloor` | string | `none` / `low` / `medium` / `high` |
| `win.productionFloor` | string | `none` / `low` / `medium` / `high` |

Rule:

- per-map gate objects may carry empty requirement arrays until the dedicated mission pass is finished
- schema must still be present so bridge/runtime/UI can stabilize around one shape

### Per cluster

| Field | Type | Meaning |
|------|------|---------|
| `clusterKey` | string | stable local cluster identifier like `c03` |
| `tier` | string | `easy`, `medium`, `hard` |
| `clusterClass` | string | `infantry_swarm`, `vehicle_pack`, `armor`, `fort`, `artillery` |
| `primaryRequirement` | string | cluster green requirement |
| `requiredWeaknesses` | array[string] | one or two explicit green requirements derived from the author-edited cluster rule |
| `yellowRequirement` | string or null | tracker-only yellow route |
| `requiredMissionGate` | string | `none` for easy, `hold` for medium, `win` for hard |
| `center` | object | cluster placement anchor |
| `tierScaling` | object | hp/dmg/veterancy defaults used by runtime |
| `units` | array | ordered per-unit AP locations |

### Per unit

| Field | Type | Meaning |
|------|------|---------|
| `unitKey` | string | stable unit key like `u01` |
| `runtimeKey` | string | game-local completion key |
| `apLocationId` | int | canonical AP numeric location ID |
| `defenderTemplate` | string | ThingTemplate name to spawn |

Optional future fields:

- `displayName`
- per-unit override scaling
- support-role hinting
- explicit placement override if runtime placement algorithm ever needs escaping

---

## 5. Runtime-Key and ID Rules

### Runtime keys

Mission:

```text
mission.<map_key>.victory
```

Cluster unit:

```text
cluster.<map_key>.cXX.uYY
```

### Numeric IDs

Follow guide formulas exactly:

```text
mission victory id = 270000000 + map_slot
cluster unit id    = 270010000 + (map_slot * 10000) + (cluster_index * 100) + unit_index
```

Rules:

- IDs must be deterministic from seed selection
- runtime keys must be deterministic from selected cluster/unit keys
- bridge owns translation between numeric IDs and runtime keys
- runtime stores only runtime completion keys for cluster checks

---

## 6. Placement and Scaling Rules

Best implementation split:

- slot-data carries cluster center, tier, scaling, ordered units
- runtime keeps placement algorithm
- runtime does **not** choose which clusters or units exist

Reason:

- payload stays compact
- runtime placement behavior remains in one code path
- seed selection remains deterministic
- save/load rebuild stays tied to runtime order and stable unit keys

Required runtime behavior:

- spawn units in listed order
- use cluster center plus stable local placement algorithm
- assign listed runtime key to each spawned object
- apply cluster-level tier scaling unless unit override exists later

---

## 7. Validation Rules

Reject payload if any of these fail:

- unknown `logicModel`
- duplicate `apLocationId`
- duplicate `runtimeKey`
- map key outside canonical set
- `mapSlot` mismatch for canonical map key
- cluster missing `primaryRequirement`
- cluster unit missing `defenderTemplate`
- cluster unit count zero
- mission-victory runtime key mismatch
- payload hash mismatch with inbound metadata

Soft-warning only for now:

- empty `missionGate` requirement arrays

Hard-fail later when per-general mission table is authored:

- missing mission-gate data for any enabled map

---

## 8. Bridge and Runtime Responsibilities

### Bridge sidecar

- receive slot data from AP world
- materialize `Seed-Slot-Data.json`
- write inbound reference metadata
- translate outbound runtime keys back to AP numeric location IDs
- dedupe submissions by `sessionNonce` and location ID

### Game runtime

- load slot-data once per `sessionNonce` / `slotDataHash`
- keep local mission and cluster completion state
- expose tracker queries against slot-data + progression state
- use `UnlockableChecksDemo.ini` only when no slot-data reference exists

---

## 9. Migration From Old Draft

Remove these old assumptions:

- generic `location_id` strings as server authority
- generic `slots_per_cluster`
- per-map `spawn_assignments` without AP numeric IDs
- slot-data as a vague future add-on separate from world contract

Keep only:

- tier scaling idea
- map-keyed organization
- clear split between mutable state sync and immutable seed content

---

## 10. Acceptance

Contract ready when:

- AP world can emit this shape from `fill_slot_data`
- bridge can materialize `Seed-Slot-Data.json`
- runtime can load it without recomputing seed choices
- one completed cluster unit can round-trip:
  - spawned object -> runtime key -> outbound -> bridge translation -> AP numeric location ID
- mission victory and cluster-unit IDs stay stable across reloads
