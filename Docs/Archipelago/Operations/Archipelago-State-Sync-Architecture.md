# Archipelago State Sync Architecture

## Goal

Keep the local GeneralsAP runtime state synchronized with Archipelago multiworld state without embedding the full Archipelago networking stack directly into `generalszh.exe` yet.

## Why A Sidecar Bridge Fits GeneralsAP

GeneralsAP is unusual compared with many Archipelago integrations:

- the game logic is a native C++ fork, not a script-friendly runtime
- check completion is tied to kill flow, unlock groups, and challenge mission completion
- the current spawned-check runtime still has an in-game fallback path via `UnlockableChecksDemo.ini`
- save/load persistence already matters for local progression

Because of that, the safest foundation is a file-based bridge seam:

- the game owns authoritative local runtime state
- an external Archipelago bridge process owns server connectivity
- both sides exchange normalized JSON in the profile user-data directory

## Implemented Foundation

`ArchipelagoState` now supports a merge-only bridge under the active user-data directory:

- persistent local save: `Save\ArchipelagoState.json`
- bridge inbound: `Archipelago\Bridge-Inbound.json`
- bridge outbound: `Archipelago\Bridge-Outbound.json`

Relevant code paths:

- `GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp`
- `GeneralsMD/Code/GameEngine/Include/GameLogic/ArchipelagoState.h`
- `GeneralsMD/Code/GameEngine/Source/Common/GlobalData.cpp`
- `GeneralsMD/Code/GameEngine/Source/Common/CommandLine.cpp`

## Current Local State Model

The local game now persists and exports:

- `unlockedUnits`
- `unlockedBuildings`
- `unlockedGenerals`
- `startingGenerals`
- `completedLocations`
- `completedChecks`

`completedChecks` is important here because GeneralsAP has local kill-check semantics beyond raw Archipelago location IDs.

## Inbound Merge Rules

`Bridge-Inbound.json` is polled by `ArchipelagoState::update()`.

Current behavior:

- merge-only, never destructive
- hash-based change detection to avoid reparsing identical content every frame
- imported `startingGenerals` also unlock those generals locally
- imported templates resolve through the same legacy-name and faction-variant expansion logic as local unlocks
- imported changes are persisted back into `ArchipelagoState.json` and mirrored to `Bridge-Outbound.json`

This keeps the game tolerant of bridge restarts and allows the external bridge to be updated independently.

## Outbound State

`Bridge-Outbound.json` is regenerated whenever local Archipelago state is saved.

It currently includes:

- bridge metadata
- save-file path
- all unlock/general/location/check sets

That gives an external bridge enough state to:

- submit new location checks to the AP server
- confirm local unlock application
- rebuild its own session cache after reconnects

## Example Files

Minimal inbound example:

```json
{
  "unlockedUnits": ["AmericaInfantryPathfinder"],
  "unlockedBuildings": ["AmericaFireBase"],
  "unlockedGenerals": [1],
  "startingGenerals": [1, 4, 8],
  "completedLocations": [1001],
  "completedChecks": ["MapA:Cluster_2:Slot_0"]
}
```

Representative outbound example:

```json
{
  "bridgeVersion": 1,
  "stateVersion": 2,
  "syncMode": "merge-only",
  "runtimeSpawnSource": "UnlockableChecksDemo.ini fallback",
  "saveFilePath": ".../Save/ArchipelagoState.json",
  "unlockedUnits": [],
  "unlockedBuildings": [],
  "unlockedGenerals": [],
  "startingGenerals": [],
  "completedLocations": [],
  "completedChecks": []
}
```

## Expected Future Bridge Responsibilities

The external Archipelago bridge process should eventually:

1. Connect to the Archipelago server.
2. Translate received items, slot data, and world settings into `Bridge-Inbound.json`.
3. Watch `Bridge-Outbound.json` for new completed locations and local state changes.
4. Submit location checks and keep the multiworld session in sync.
5. Manage per-seed/per-slot metadata so the local profile can be tied to one AP session cleanly.

## What Is Still Missing

- direct AP server client implementation for GeneralsAP
- real slot-data ingestion by `UnlockableCheckSpawner`
- mission/map-specific spawn assignment loading from bridge data
- items, traps, and DeathLink-style cross-session effects
- conflict rules for replacing or re-seeding an existing local profile

## Why This Is Future-Proof

This split keeps three change streams decoupled:

- SuperHackers upstream game-code merges
- Archipelago upstream client/library changes
- GeneralsAP-specific gameplay logic and release packaging

That is the right tradeoff for a long-lived C++ fork that still needs to track both upstreams.
