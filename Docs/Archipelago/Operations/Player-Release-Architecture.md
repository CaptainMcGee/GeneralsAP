# Player Release Architecture

## Goals

- Ship GeneralsAP as a prebuilt player release. Players should not need Visual Studio, CMake, Python, or Archipelago development tooling.
- Avoid redistributing retail Zero Hour assets.
- Keep the base game install recoverable and easy to support.
- Keep the release model compatible with future SuperHackers upstream merges and Archipelago bridge updates.

## Recommended Player Flow

1. Install Command & Conquer Generals Zero Hour from a legal source.
2. Verify the clean base game launches and is a healthy Zero Hour 1.04-compatible runtime.
3. Clone that healthy install into a separate GeneralsAP folder outside `Program Files`.
4. Apply the GeneralsAP release package to the cloned folder only.
5. Launch GeneralsAP from that cloned folder with its own `-userDataDir`.

This avoids modifying the only base install and avoids requiring a launcher with elevated trust just to play.

## Base Game Policy

GeneralsAP does not require, invoke, detect, or assume any external base-game patcher.

Supported release baseline:

- legal Command & Conquer Generals Zero Hour install
- healthy 1.04-compatible runtime that can launch before GeneralsAP is applied
- dedicated GeneralsAP clone created from that healthy install
- GeneralsAP-owned overlay applied to the clone only

If a player's base game cannot launch, that is a base-install repair issue outside the GeneralsAP release contract. The GeneralsAP installer should fail with a clear health-check error instead of trying to repair unrelated base-game state.

## Why A Separate Clone

GeneralsAP is not a data-only mod. It changes game code, GUI behavior, Archipelago runtime state, and generated INI data. That makes the usual "drop a mod into the base game and hope the launcher stack agrees" path too fragile for first release.

A dedicated clone gives us:

- a single tested executable and data set
- no dependence on players matching a specific SuperHackers binary manually
- easier rollback and support
- room for per-profile user data and Archipelago bridge files

## `-userDataDir` Foundation

The engine now supports `-userDataDir <path>` through:

- `GeneralsMD/Code/GameEngine/Source/Common/CommandLine.cpp`
- `GeneralsMD/Code/GameEngine/Source/Common/GlobalData.cpp`

Use this for every packaged GeneralsAP shortcut or launcher entry. That keeps `Options.ini`, save data, and Archipelago bridge state out of the default Documents path and prevents one install copy from stomping another.

Recommended layout:

```text
C:\Games\GeneralsAP\
  generalszh.exe
  Data\...
  UserData\
    Options.ini
    Save\
    Archipelago\
      Bridge-Inbound.json
      Bridge-Outbound.json
```

Launch example:

```powershell
generalszh.exe -win -userDataDir ".\\UserData\\"
```

## Release Artifact Shape

The first supported player release should contain only Generals-owned files:

- the prebuilt GeneralsAP executable and DLLs we produce from this fork
- GeneralsAP data and UI files
- generated `Data/INI/Archipelago.ini`
- Archipelago helper assets used by the mod
- bundled bridge sidecar executable once the live AP network bridge exists
- `generalszh.apworld` or an equivalent APWorld payload for seed hosts/generators
- a release manifest that records:
  - GeneralsAP version
  - SuperHackers upstream commit/tag
  - Archipelago vendor release/version
  - required base game expectations

Do not ship retail `.big` archives or any other copyrighted base-game assets.

Current alpha packaging checkpoint:

- `scripts/package_generalsap_alpha.ps1` creates a manifest-backed overlay package from a prepared runtime directory.
- `scripts/build_generalsap_bridge_stub.ps1` creates a `GeneralsAPBridge.exe` staging stub for package wiring only.
- `scripts/build_generalsap_bridge.ps1` builds the packaged file-bridge executable from `tools/bridge/GeneralsAPBridge`.
- `scripts/archipelago_bridge_executable_smoke.py` verifies the bridge executable can materialize supplied slot data, write inbound metadata, reject unknown runtime keys, and merge duplicate completions idempotently.
- `scripts/archipelago_bridge_network_smoke.py` verifies the same bridge executable can speak the AP 0.6.7 websocket seam against a fake AP server, receive `slot_data` and items, write the same file contract, submit `LocationChecks`, and avoid duplicate submissions across reconnects.
- `scripts/archipelago_bridge_real_ap_server_smoke.py` verifies the same bridge executable against a real local Archipelago 0.6.7 `MultiServer.py` room generated from the GeneralsZH world: mission/cluster `LocationChecks`, fresh reconnect persistence, and duplicate completion idempotency.
- `scripts/smoke_generalsap_alpha_package.ps1` verifies package layout, manifest fields, no retail archives, clone overlay, and packaged bridge executable translation.
- The package uses an allowlist and scans output for forbidden retail archive types.
- It is not a complete public alpha until a hosted AP room smoke and clean-machine runtime smoke both pass.

Recommended alpha artifact layout:

```text
GeneralsAP-0.1.0-alpha.zip
  GeneralsAP-Release-Manifest.json
  README-PACKAGE.txt
  payload/
    Game/
      Run-GeneralsAP.cmd
      generalszh.exe
      Game.dat
      Data/INI/Archipelago.ini
      Data/INI/ArchipelagoChallengeUnitProtection.ini
      Data/INI/UnlockableChecksDemo.ini
      MappedImages/...
    Bridge/
      GeneralsAPBridge.exe
    APWorld/
      generalszh.apworld
    Docs/
      README-Alpha.md
```

## Current Release Readiness

Current repo state is not a player-portable release yet.

Implemented foundation:

- game supports profile-local `-userDataDir`
- local bridge file contract exists
- runtime can consume verified `Seed-Slot-Data.json`
- AP world skeleton can generate/fill under Archipelago 0.6.7
- packaged bridge network mode can connect to AP protocol, receive slot data/items, write the runtime file contract, and submit selected location IDs in fake-server smoke
- packaged bridge network mode can complete the same selected mission/cluster submission path against a real local AP 0.6.7 `MultiServer.py` room
- package manifest schema exists
- alpha overlay package script exists and rejects retail archive packaging

Missing before public alpha:

- clean C++ runtime build plus legal base-runtime asset staging
- clean-machine install/package smoke
- bundled APWorld package produced by release tooling
- launcher or script that starts bridge then game
- support log/error path for seed, hash, and version mismatch
- optional external hosted-room smoke if the first alpha uses hosted AP rooms instead of local AP servers

Latest checkpoint status, April 27, 2026:

- `windows_debug_prepare.ps1 -Preset win32-vcpkg-playtest -RuntimeConfiguration Release -RuntimeProfile demo-playable` compiled and linked `GeneralsMD\Release\generalszh.exe`.
- The same prepare step failed after linking because the build runtime did not contain retail Zero Hour runtime assets such as `.big` archives, `MSS`, `MappedImages`, and `ZH_Generals`.
- That failure is expected in this GitHub-safe worktree and does not mean the GeneralsAP executable failed to build.
- Packaging can still create an overlay package from the built executable and GeneralsAP-owned INI files.
- A packaged `file_bridge` executable now proves the seed file/inbound/outbound/ID-translation loop without requiring Python on the staged player path.
- The same bridge executable now has `--connect` network mode and a fake AP server smoke for `DataPackage`, `Connected` + `slot_data`, `ReceivedItems`, `LocationChecks`, and duplicate-safe reconnects.
- The same bridge executable now passes real local AP 0.6.7 `MultiServer.py` smoke: a real generated GeneralsZH multidata zip, AP server startup, mission/cluster location submission, fresh reconnect persistence, and duplicate-safe replay.
- Public alpha still needs a clean cloned legal runtime to prove launch.

## Bridge Distribution Decision

The bridge should be a separate process, but bundled with the GeneralsAP release.

Do this:

- ship `GeneralsAPBridge.exe` beside the game overlay
- version-lock bridge, APWorld, game runtime, slot-data schema, and logic model through `GeneralsAP-Release-Manifest.json`
- also publish `generalszh.apworld` separately for AP hosts/generators that do not need the game files
- record bridge type in the manifest as `bridgeKind`: `none`, `staging_stub`, `file_bridge`, or `real`

Do not do this:

- embed AP networking inside `generalszh.exe`
- require players to manually assemble unrelated bridge/APWorld/game versions
- silently fall back to demo mode when seeded AP data is present but invalid
- ship `bridgeKind=staging_stub` or `bridgeKind=file_bridge` as a public AP alpha

Reason:

- sidecar bridge isolates networking failures from the game
- file contract is easier to debug and support
- bundled version lock prevents seed/runtime mismatch

## Alpha Release Plan

Alpha release should be conservative and supportable:

1. Build release runtime in known-good environment.
2. Build live AP network `GeneralsAPBridge.exe`; validate file-bridge smoke, fake-server AP network smoke, and real local AP server smoke. `file_bridge` remains acceptable only for release-staging smoke.
3. Build/package `generalszh.apworld`.
4. Run `scripts/package_generalsap_alpha.ps1` against prepared runtime and bridge.
5. Install package onto a cloned healthy Zero Hour runtime.
6. Launch bridge and game through `Run-GeneralsAP.cmd` or a thin launcher.
7. Smoke one mission victory and one cluster-unit check through AP numeric location submission.

Alpha can still have manual setup steps, but it must not require Python, CMake, Visual Studio, vcpkg, or repo checkout on the player's machine.

Alpha should not enable:

- captured-building checks
- supply-pile-threshold checks
- final weakness evaluator
- final mission `Hold` / `Win` table
- tracker UI as a release blocker
- YAML difficulty modes

## 1.0 Release Plan

Version 1.0 should replace manual alpha setup with a first-party installer/launcher.

1. Detect legal Zero Hour install.
2. Validate healthy 1.04-compatible runtime.
3. Clone install to a GeneralsAP-owned target directory.
4. Apply overlay package.
5. Install/update bundled bridge.
6. Install/update `generalszh.apworld`.
7. Create isolated `UserData`.
8. Create launcher shortcut with `-userDataDir`.
9. Validate release manifest before launch.
10. Start bridge, then game.
11. Show bridge/server/slot/version status.
12. Support repair, upgrade, uninstall, and support-log export.

1.0 acceptance:

- wrong seed/profile reuse is blocked unless user explicitly resets
- bridge duplicate submissions are idempotent
- APWorld/game/bridge version mismatch is blocked before play
- no retail assets are included in release package
- two separate GeneralsAP installs do not share profile state
- upgrade preserves AP profile state unless user resets it

## Tooling Position

- GenLauncher: optional future distribution path, not the required path for the first stable GeneralsAP release.
- Custom installer/launcher: recommended for GeneralsAP because we need controlled clone creation, package overlay, and `-userDataDir` shortcuts.

## What The Future Installer Should Do

A first-party GeneralsAP setup tool should:

1. Detect a legal Zero Hour install.
2. Confirm the base install is a healthy 1.04-compatible runtime and not a random repack or already-modded directory.
3. Clone the base install into a GeneralsAP target directory.
4. Create a dedicated `UserData` directory.
5. Apply the GeneralsAP package.
6. Create a shortcut that always passes `-userDataDir`.
7. Record a local manifest so upgrades know which SuperHackers/GeneralsAP baseline is installed.

## Release Prep Checklist

Before calling a build "player-ready":

- verify a healthy legal Zero Hour install + clone + GeneralsAP overlay path
- verify `Bridge-Outbound.json` is created under the profile user-data directory
- verify Archipelago save/load still works from the cloned install
- verify the package does not require Python or CMake at install time
- verify no retail assets are being distributed from this repo or release bundle

## Release Manifest

Best implementation: every packaged release writes a manifest beside the executable.

Recommended file:

```text
GeneralsAP-Release-Manifest.json
```

Recommended fields:

```json
{
  "packageVersion": "0.1.0-alpha",
  "releaseChannel": "alpha",
  "generalsApCommit": "abc123",
  "superHackersRef": "commit-or-tag",
  "archipelagoVersion": "0.6.7",
  "apworldName": "generalszh.apworld",
  "apworldVersion": "0.1.0",
  "bridgeVersion": 1,
  "bridgeBundled": true,
  "bridgeKind": "real",
  "slotDataVersion": 2,
  "logicModel": "generalszh-alpha-grouped-v1",
  "requiresExternalBasePatcher": false,
  "requiredBaseGame": "Command & Conquer Generals Zero Hour 1.04-compatible healthy install",
  "retailAssetsIncluded": false,
  "userDataDirRequired": true,
  "launchArgs": ["-win", "-userDataDir", ".\\UserData\\"]
}
```

Reason:

- support can identify install lineage quickly
- bridge/runtime compatibility can be checked before launch
- upgrade tooling has one stable machine-readable source
- release tooling can reject accidental retail-asset packaging

Schema:

```text
Data/Archipelago/release_manifest_schema.json
```

This schema is the release contract. It intentionally sets `requiresExternalBasePatcher` to `false` and `retailAssetsIncluded` to `false`.

Package smoke:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_generalsap_alpha_package.ps1 -RuntimeDir .\build\win32-vcpkg-playtest\GeneralsMD\Release
```

Use `-UseFixtureRuntime` when only testing package mechanics without a built runtime.

## Fixture and Validation Lane

Packaging lane should own repeatable validation fixtures, not only installer output.

Minimum fixture matrix:

| Scenario | Expected result |
|---------|-----------------|
| clean clone + first launch | profile-local `UserData` created, no default-documents bleed |
| bridge absent | game launches, fallback/demo messaging is clear |
| bridge present + valid seed | bridge files created under profile and game loads slot-data |
| save/load mid-run | local Archipelago state persists cleanly |
| replay same mission | no duplicate location completion corruption |
| install upgrade over same clone | manifest and bridge compatibility remain correct |
| second install copy | profile isolation still holds |

## Lane 6 Deliverables

Release/test lane is done when it can hand other lanes:

- reproducible package shape
- manifest schema
- shortcut/launcher args with `-userDataDir`
- fixture matrix for bridge + runtime + UI smoke tests
- upgrade/reinstall checklist
