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
    BridgeSession.json         # live AP sidecar session cache
```

### File roles

| File | Writer | Reader | Role |
|------|--------|--------|------|
| `Save/ArchipelagoState.json` | game | game | persistent local progression |
| `Archipelago/Bridge-Inbound.json` | bridge | game | mutable inbound AP/session state |
| `Archipelago/Bridge-Outbound.json` | game | bridge | mutable outbound completion/state mirror |
| `Archipelago/Seed-Slot-Data.json` | bridge | game | immutable per-seed mission/cluster contract, plus disabled future location-family sections |
| `Archipelago/LocalBridgeSession.json` | local fixture tool | local fixture tool | local offline harness only |
| `Archipelago/BridgeSession.json` | live bridge | live bridge | AP-backed session cache for completed checks, received items, and duplicate submission protection |

---

## 2. Ownership Split

| Layer | Owns |
|------|------|
| AP world | item table, seven shuffled victory medal items, numeric location IDs, boss access/completion condition, seed slot-data content |
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
- disabled future `capturedBuildingState` / `supplyPileState` arrays for save/outbound compatibility only

Current code seams:

- `GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp`
- `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp`
- `scripts/archipelago_bridge_local.py`
- `tools/bridge/GeneralsAPBridge`
- `scripts/build_generalsap_bridge.ps1`
- `scripts/archipelago_bridge_executable_smoke.py`
- `scripts/archipelago_bridge_network_smoke.py`
- `scripts/archipelago_bridge_real_ap_server_smoke.py`

Current reality:

- inbound merge is merge-only
- outbound mirrors full local state
- runtime can load and hash-verify `Seed-Slot-Data.json` when inbound references it
- seeded spawned checks come from selected cluster-unit entries in slot data
- `capturedBuildings` and `supplyPileThresholds` sections exist in slot data and are parsed read-only if present, but runtime completion/persistence for those families is not implemented yet
- production `fill_slot_data` rejects selected future-family checks today; non-empty sections are allowed only in targeted translation/parser tests
- mission victory can complete canonical runtime keys such as `mission.tank.victory`
- the AP item pool includes one shuffled victory medal per main challenge general; all seven medals gate Boss General access
- `UnlockableChecksDemo.ini` is fallback only when no slot-data reference exists
- bad or mismatched slot-data disables seeded spawning instead of silently mixing demo checks
- future capture/supply replay and idempotency rules are now captured in `Data/Archipelago/location_families/runtime_persistence_contract.json`, but runtime support is not implemented yet
- `ArchipelagoState` can write and preserve future capture/supply state arrays, but no capture event or supply collection tracker produces entries
- local fixture bridge mirrors `capturedBuildingState` and `supplyPileState` through session/inbound/outbound as opaque arrays; it does not translate those arrays to AP location IDs
- packaged `GeneralsAPBridge.exe` file-bridge mode can materialize a supplied `Seed-Slot-Data.json`, write inbound metadata, merge outbound mission/cluster runtime keys into AP numeric IDs, reject unknown keys, and keep duplicate cycles idempotent
- packaged `GeneralsAPBridge.exe` network mode can connect to an AP 0.6.7 websocket endpoint, request `DataPackage`, authenticate with `slot_data`, materialize `Seed-Slot-Data.json`, map received AP items into runtime unlock/session options, submit selected runtime checks through `LocationChecks`, and avoid duplicate submits across reconnects
- packaged `GeneralsAPBridge.exe` has passed an automated real local AP 0.6.7 `MultiServer.py` smoke generated from the GeneralsZH world: one mission victory and one cluster-unit check submit as AP numeric locations, a fresh bridge profile sees those checks persisted by the server, and duplicate completion replay is harmless
- Boss mission victory is a locked AP event. It may exist as runtime key `mission.boss.victory` in slot data for runtime goal tracking, but the bridge must not submit its marker ID as a `LocationChecks` location. Completing Boss sends AP goal `StatusUpdate` instead.
- external hosted-room AP validation is still useful before public AP alpha, but the local real-server smoke is the repeatable automated protocol/generation gate

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
   - mission runtime keys via loaded slot-data
   - cluster runtime keys via loaded slot-data
   - legacy numeric mission IDs only for demo/fallback paths
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

Future captured-building and supply-pile checks must follow the same rule. Runtime emits completed runtime keys, bridge translates only selected keys from verified slot data, and duplicate capture/threshold events are no-ops.

For future families, persistent state must also survive mission replay:

- captured-building checks: completed `capture.<map>.bXXX` keys stay complete after restart/replay
- supply-pile checks: persistent collected amount and completed `supply.<map>.pXX.tYY` thresholds stay complete after restart/replay
- wrong-seed or changed-slot-data imports reject instead of merging state from another seed

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

- if no slot-data reference exists, runtime may fall back to `UnlockableChecksDemo.ini`
- if a slot-data reference exists but hash/version/session validation fails, runtime must reject seeded mode and not mix in demo checks
- fallback is now demo/local recovery only, not the seeded alpha path

---

## 8. Local Fixture Harness

`scripts/archipelago_bridge_local.py` remains useful for fixture generation and Python-side validation.
`tools/bridge/GeneralsAPBridge` is the packaged player-path bridge. It supports file-bridge mode for release-staging smoke and network mode for the live AP websocket path.

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

File-bridge mode should also stay honest:

- accepted for release-staging smoke and clean local seed-file loop testing
- not accepted as public AP alpha networking
- must reject unknown runtime keys rather than guessing IDs
- must preserve duplicate completion idempotency across bridge restarts

Network mode should stay on the same contract:

- AP `slot_data` is the source for selected mission/cluster locations
- AP item placements are not written into `Seed-Slot-Data.json`
- received AP items update runtime unlock/session state through `Bridge-Inbound.json`
- `LocationChecks` submits only IDs selected by verified slot data
- `LocationChecks` also submits only IDs the AP server reports as known missing/checked locations; this prevents runtime-only event markers such as Boss victory from being guessed as normal locations
- Boss victory sends `StatusUpdate` after the runtime marks `mission.boss.victory` complete
- medals remain AP progression items only; they do not become runtime unlock groups

---

## 9. Next Implementation Targets

### Bridge lane

- optional external hosted AP room smoke against Archipelago 0.6.7 release flow
- session binding checks
- error reporting for bad slot-data or mismatched profile
- launcher handoff from live AP connection into the same file contract proven by file-bridge mode

### Runtime lane

- finish build/playtest validation for slot-data loader
- finish build/playtest validation for selected-check registry
- runtime-key to spawned-object association
- tracker query API
- graceful fallback messaging when only demo INI exists

### Release/runtime lane

- use `scripts/smoke_generalsap_clean_runtime.ps1` with a legal cloned Zero Hour runtime to prove the packaged overlay launches from an isolated `UserData`
- run the same harness with `-WaitForRuntimeKey mission.tank.victory -WaitForRuntimeKey cluster.tank.c02.u01` during manual play to prove one mission victory and one seeded cluster check reach `Bridge-Outbound.json` and merge through the packaged bridge
- keep `-UseFixtureRuntime` as harness-only validation; it does not prove launch or retail runtime compatibility

---

## 10. Acceptance

Architecture ready when:

- bridge can materialize `Seed-Slot-Data.json`
- inbound references slot-data by path + hash
- runtime loads slot-data and spawns only selected checks
- completed mission and cluster runtime keys round-trip to AP numeric location IDs
- no slot-data reference falls back to demo INI explicitly
- bad slot-data reference rejects seeded mode without demo fallback
- seeded mode does not mix in demo check selection or local fallback rewards
- reconnect does not duplicate submissions
- same seed replay keeps stable state
- wrong-seed profile bind is detected and blocked

Current local checkpoint commands:

```bash
python scripts/archipelago_seeded_bridge_loop_smoke.py
python scripts/archipelago_runtime_fallback_contract_check.py
python scripts/archipelago_bridge_executable_smoke.py --bridge-exe build/release-tools/GeneralsAPBridge.exe
python scripts/archipelago_bridge_network_smoke.py --bridge-exe build/release-tools/GeneralsAPBridge.exe
python scripts/archipelago_bridge_real_ap_server_smoke.py --bridge-exe build/release-tools/GeneralsAPBridge.exe --skip-install --skip-materialize
```
