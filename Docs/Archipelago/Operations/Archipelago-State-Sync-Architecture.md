# Archipelago State Sync Architecture

## Goal

Keep GeneralsAP synchronized with Archipelago without embedding full AP networking into `generalszh.exe`.

Best implementation for alpha:

- game runtime owns local progression state
- external bridge owns AP connectivity and ID translation
- immutable seed payload stays separate from mutable progression sync

---

## 1. Canonical File Set

Profile-local layout:

```text
UserData/
  Save/
    ArchipelagoState.json
  Archipelago/
    Bridge-Inbound.json
    Bridge-Outbound.json
    Seed-Slot-Data.json
    LocalBridgeSession.json    # fixture/local sidecar only
```

### File roles

| File | Writer | Reader | Role |
|------|--------|--------|------|
| `Save/ArchipelagoState.json` | game | game | persistent local progression |
| `Archipelago/Bridge-Inbound.json` | bridge | game | mutable inbound AP/session state |
| `Archipelago/Bridge-Outbound.json` | game | bridge | mutable outbound completion/state mirror |
| `Archipelago/Seed-Slot-Data.json` | bridge | game | immutable per-seed mission/cluster contract |
| `Archipelago/LocalBridgeSession.json` | local fixture tool | local fixture tool | local offline harness only |

---

## 2. Ownership Split

| Layer | Owns |
|------|------|
| AP world | item table, numeric location IDs, completion condition, seed slot-data content |
| Bridge sidecar | server connection, session binding, file materialization, duplicate submission protection, runtime-key to AP-ID translation |
| Game runtime | local unlock state, local check completion, save/load, tracker queries, spawned-object association |

Important rule:

- game must not recompute seed selection
- bridge must not decide gameplay logic
- AP world must not depend on live runtime state

---

## 3. Implemented Foundation

`ArchipelagoState` already persists and exports:

- `unlockedUnits`
- `unlockedBuildings`
- `unlockedGenerals`
- `startingGenerals`
- `completedLocations`
- `completedChecks`
- `startingCashBonus`
- `productionMultiplier`

Current code seams:

- `GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp`
- `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp`
- `scripts/archipelago_bridge_local.py`

Current reality:

- inbound merge is merge-only
- outbound mirrors full local state
- spawned checks still use `UnlockableChecksDemo.ini` fallback
- no real slot-data ingestion yet

---

## 4. Best Alpha Bridge Lifecycle

### Session start

1. Bridge connects to AP server.
2. Bridge receives items, slot data, and world settings.
3. Bridge writes `Seed-Slot-Data.json` atomically.
4. Bridge writes `Bridge-Inbound.json` with:
   - `seedId`
   - `slotName`
   - `sessionNonce`
   - `slotDataVersion`
   - `slotDataPath`
   - `slotDataHash`
   - current unlock state
   - current session options
5. Game loads inbound state and slot-data.

### During play

1. Game updates local progression.
2. Game rewrites `Bridge-Outbound.json`.
3. Bridge polls outbound state.
4. Bridge translates:
   - mission numeric IDs directly
   - cluster runtime keys via loaded slot-data
5. Bridge submits newly completed AP locations.
6. Bridge updates inbound state if new items/session options arrive.

### Resume/reconnect

1. Bridge reloads AP session.
2. Bridge keeps same `sessionNonce` if same local profile/session.
3. Bridge rewrites inbound only if hash/state changed.
4. Game merge-imports new state without destructive rollback.

---

## 5. Session Binding Rules

Best implementation rules:

- one local profile binds to one `seedId` + `slotName`
- `sessionNonce` identifies one active bridge/runtime pairing
- bridge should refuse silent reseed onto an existing progressed profile
- replacing a profile with another seed should require explicit reset or rebind

Recommended bridge checks:

- if `seedId` changed and local state non-empty: stop, require reset
- if `slotDataHash` changed under same `sessionNonce`: stop, require rewrite/restart path
- if `sessionNonce` changed with same seed and same slot-data: treat as bridge restart, safe to continue

---

## 6. Duplicate Submission Policy

Bridge should be idempotent.

Do this:

- treat outbound as current full state, not one-shot deltas
- maintain acknowledged location-ID set per session
- submit only newly seen IDs
- never infer cluster AP IDs without slot-data lookup

Runtime should stay simple:

- keep `completedLocations`
- keep `completedChecks`
- never track AP submission ack state

---

## 7. Slot-Data Integration Path

Bridge inbound should reference `Seed-Slot-Data.json`, not inline full seed payload.

Runtime load path:

1. read inbound metadata
2. resolve `slotDataPath`
3. verify `slotDataHash`
4. load `Seed-Slot-Data.json`
5. cache loaded hash and `sessionNonce`
6. rebuild selected mission/cluster contract from loaded payload

Fallback rule:

- if no valid slot-data reference exists, runtime may fall back to `UnlockableChecksDemo.ini`
- once real slot-data ingestion ships, fallback should be for demo/local recovery only

---

## 8. Local Fixture Harness

`scripts/archipelago_bridge_local.py` remains useful and should evolve with real bridge work.

Fixture lane should support:

- empty session
- mixed progression
- almost exhausted pool
- post exhaustion
- same seed reconnect
- bad hash / missing slot-data file
- explicit reset/rebind

Do not let fixture tool define production contract by accident.
It should follow canonical docs, not become them.

---

## 9. Next Implementation Targets

### Bridge lane

- real AP client/session loop
- seed slot-data materialization
- session binding checks
- duplicate submission cache
- error reporting for bad slot-data or mismatched profile

### Runtime lane

- slot-data loader
- selected-check registry
- runtime-key to spawned-object association
- tracker query API
- graceful fallback messaging when only demo INI exists

---

## 10. Acceptance

Architecture ready when:

- bridge can materialize `Seed-Slot-Data.json`
- inbound references slot-data by path + hash
- runtime loads slot-data and spawns only selected checks
- completed cluster runtime key round-trips to AP numeric location ID
- reconnect does not duplicate submissions
- same seed replay keeps stable state
- wrong-seed profile bind is detected and blocked
