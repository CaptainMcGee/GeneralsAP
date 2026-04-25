# Testing

## Maintainer Asset Root

Normal source builds do not need Python or retail asset roots; they use the committed Archipelago outputs already in the repo. The GitHub-safe repo does not track retail Zero Hour assets, so maintainers only need this when regenerating Archipelago data from source scripts:

```powershell
$env:GENERALS_ASSET_ROOT = "C:\Path\To\Generals Zero Hour"
```

`GENERALS_ASSET_ROOT` may point either to the game root or directly to its `Data` directory.

## Maintainer Validation

Run the script suite from the repo root:

```bash
python scripts/archipelago_run_checks.py
```

This runs the lightweight Archipelago generation/validation suite.

For the real Archipelago 0.6.7 world-generation smoke, run:

```bash
python scripts/archipelago_run_real_ap_smoke.py
```

That command materializes `build/archipelago/archipelago-worktree`, creates `build/archipelago/ap-smoke-venv`, installs the minimal AP smoke dependencies from `scripts/requirements-archipelago-smoke.txt`, and verifies the GeneralsZH world can generate/fill with shuffled medals and locked Boss victory. Once the venv exists, `python scripts/archipelago_run_checks.py` automatically uses it for the optional real AP generation smoke instead of skipping on missing global Python dependencies.

For the Phase 1 seed-runtime contract, this suite currently covers:

- bridge materializes `Seed-Slot-Data.json`
- inbound carries `slotDataPath`, file-byte `slotDataHash`, `slotDataVersion`, `seedId`, `slotName`, and `sessionNonce`
- mission and cluster runtime keys translate back to AP numeric location IDs
- unknown runtime keys are rejected
- duplicate outbound completions are idempotent
- minimal slot data does not accept unselected hard-cluster checks
- runtime fallback boundaries stay explicit:
  - no slot-data reference permits demo fallback
  - bad slot-data reference rejects seeded mode
  - seeded mode does not mix selected checks with demo rewards/checks

## Canonical Demo-Ready Playtest Loop

For gameplay/demo validation, use the playtest build. Do not use the strict debug build as the default gameplay path.
The runtime profiles now split into:

- `reference-clean`
  - known-good old `Archipelago.ini` + `UnlockableChecksDemo.ini`
  - startup-safety control only
- `demo-playable`
  - validated gameplay/demo profile built on the reference-clean baseline
- `demo-ai-stress`
  - AI leash/chase/pathing profile built on the same safe baseline
- `archipelago-bisect`
  - working profile for reintroducing runtime INI changes in controlled batches
- `archipelago-current`
  - current candidate loose Archipelago runtime files, including command-map overlays

For normal playable testing, use `demo-playable`. `reference-clean` stays untouched as the control profile.

From plain PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_demo_run.ps1
```

That command:

- builds `win32-vcpkg-playtest`
- prepares the `demo-playable` runtime profile
- starts the local bridge sidecar
- launches `build\win32-vcpkg-playtest\GeneralsMD\Release\generalszh.exe` with `-userDataDir .\UserData\`

Optional variants:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_demo_run.ps1 -RuntimeProfile demo-ai-stress
powershell -ExecutionPolicy Bypass -File .\scripts\windows_demo_run.ps1 -Fixture mixed_progression -ResetSession
```

Double-click:

```text
Run-GeneralsAP-Demo.cmd
```

## Playtest Debug Controls

The safe playtest path no longer uses `CommandMap.ini` overlays. Archipelago demo controls are code-side and available in mission:

- `Shift+Alt+Ctrl+9` status
- `Shift+Alt+Ctrl+6` unlock next group
- `Shift+Alt+Ctrl+0` unlock next general
- `Shift+Alt+Ctrl+7` unlock all
- `Shift+Alt+Ctrl+8` reset
- `Shift+Alt+Ctrl+5` dump state/templates

Slash-chat mirrors the same actions in mission:

- `/ap_help`
- `/ap_status`
- `/ap_unlock_next_group`
- `/ap_unlock_next_general`
- `/ap_unlock_all`
- `/ap_reset`
- `/ap_unlock_capture`
- `/ap_dump`

## Bridge Fixtures

The sidecar can seed `LocalBridgeSession.json` from curated fixtures under `Data/Archipelago/bridge_fixtures`:

- `minimal_progression`
- `mixed_progression`
- `almost_exhausted_pool`
- `post_exhaustion_pool`

Example:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_demo_run.ps1 -Fixture almost_exhausted_pool -ResetSession
```

## Phase 1 Seeded Runtime Smoke

Use this before expanding logic beyond the runtime seed loop:

1. Run `python scripts/archipelago_seeded_bridge_loop_smoke.py`.
2. Run `python scripts/archipelago_runtime_fallback_contract_check.py`.
3. Run `python scripts/archipelago_run_checks.py`.
4. Start the local bridge with slot-data emission through the demo wrapper or directly through `scripts/archipelago_bridge_local.py`.
5. Confirm `UserData\Archipelago\Seed-Slot-Data.json` exists.
6. Confirm `Bridge-Inbound.json` includes `slotDataPath`, `slotDataHash`, `slotDataVersion`, `seedId`, `slotName`, and `sessionNonce`.
7. Start a challenge map covered by the fixture slot data.
8. Confirm logs show `Loaded verified slot data` and `Using Seed-Slot-Data.json spawn config`.
9. Kill one spawned seeded cluster unit and confirm `Bridge-Outbound.json` records its canonical runtime key, e.g. `cluster.tank.c02.u01`.
10. Complete one covered mission and confirm outbound records its canonical runtime key, e.g. `mission.tank.victory`.
11. Re-run the bridge cycle and confirm those runtime keys map to AP numeric location IDs with no duplicate changes.
12. Corrupt `Seed-Slot-Data.json` or its inbound hash and confirm seeded spawning is rejected instead of falling back to demo checks.

## Secondary Strict-Debug Loop

Use the strict debug path only for targeted stepping/call stacks, not for routine gameplay validation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_run.ps1
```

The strict debug runner still supports the same runtime profile names, but the startup-safe default remains `reference-clean`.

## Cursor / VS Code Debugging

The clean worktree now includes ready-to-run debugger profiles in `.vscode\launch.json` and tasks in `.vscode\tasks.json`.

Recommended flow in Cursor for gameplay/demo checks:

1. Open this clean worktree as the workspace.
2. Run the sidecar manually with a fixture if needed.
3. Start the playtest/runtime launch configuration or use `windows_demo_run.ps1`.

That launch config rebuilds the direct debug output first, then starts `build\win32-vcpkg-debug\GeneralsMD\Debug\generalszh.exe` with `-userDataDir .\UserData\`.

Use the strict debug launch configs only when you need call stacks or step-debugging.

`windows_debug_prepare.ps1` will:

- import the Visual Studio x86 build environment into the current PowerShell session
- validate `VCPKG_ROOT`
- configure/build the `win32-vcpkg-debug` preset
- generate a legacy-safe `Archipelago.ini` through `archipelago_config`
- sync the known-good root debug runtime `Data`, `MappedImages`, `MSS`, `ZH_Generals`, `.big`, and DLL files from `build\win32-vcpkg-debug\GeneralsMD\Debug`
- by default, also sync the known-good `generalszh.exe` and `Game.dat` from that reference runtime
- clear any previously staged Archipelago loose overrides
- apply exactly one runtime profile from `Data/Archipelago/runtime_profiles`
- ensure the direct debug runtime has a local `UserData\Archipelago` folder ready for the bridge
- fail immediately if the debug runtime is missing the traditional run-directory essentials such as `Data`, `MSS`, `ZH_Generals`, `BINKW32.DLL`, `mss32.dll`, and the required `.big` archives

The local bridge sidecar mirrors `LocalBridgeSession.json` into `Bridge-Inbound.json`, including explicit `receivedItems`, watches `Bridge-Outbound.json`, and merges completed checks/locations plus unlocked group IDs back into the session file for repeatable in-game testing without a live AP server. It now supports `--fixture` and `--reset-session` so demo sessions can be replayed consistently.

## Runtime Smoke Gate

Use the startup smoke gate before accepting any Archipelago runtime-file change:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_smoketest.ps1
```

That test is still useful for `reference-clean` / `archipelago-bisect` startup regression work, but the playable demo gate is now the playtest loop above plus the manual checks below.

- stages the selected runtime profile on top of the known-good reference runtime
- launches through the normal debug path
- waits briefly for intro/menu startup
- scans the debug log for asset/assert signatures
- fails if startup asset errors reappear

## Maintainer CMake Regeneration

To force regeneration of the localized name maps and build-directory `Archipelago.ini` through CMake:

```bash
cmake --list-presets
cmake -S . -B build/win32-vcpkg-debug -DARCHIPELAGO_REGENERATE_DATA=ON -DGENERALS_ASSET_ROOT="C:/Path/To/Generals Zero Hour" -DRTS_BUILD_ZEROHOUR=ON -DRTS_BUILD_GENERALS=OFF
cmake --build build/win32-vcpkg-debug --target archipelago_config --config Debug
```

## Super Patch Runtime Overlay Checks

The canonical Super Patch runtime overlay is built from the patch repo's core bundle metadata, audited, and then verified again against the staged install:

```bash
python scripts/gamepatch_runtime_materialize.py
python scripts/gamepatch_runtime_audit.py
python scripts/gamepatch_asset_parity_scan.py --stage-root build/localtest-install --overlay-manifest build/gamepatch-runtime/runtime-overlay-manifest.json
```

## Archipelago Vendor Checks

To verify the managed Archipelago vendor lane:

```bash
python scripts/archipelago_vendor_materialize.py
python scripts/archipelago_run_real_ap_smoke.py --skip-install
python scripts/archipelago_vendor_capture.py
```

## Manual Demo Checks

After engine-side changes, verify these in game:

- run the playtest output from `build\win32-vcpkg-playtest\GeneralsMD\Release`
- launch from an isolated profile with `-userDataDir` and confirm the game writes into that local `UserData` tree instead of the default Documents profile
- confirm `UserData\Archipelago\LocalBridgeSession.json` is created by the bridge sidecar and `Bridge-Inbound.json` is written
- confirm `UserData\Archipelago\Bridge-Outbound.json` is created after local Archipelago state initializes
- when slot data is referenced, confirm spawned checks come only from `Seed-Slot-Data.json`
- when no slot data is referenced, confirm `UnlockableChecksDemo.ini` fallback still works explicitly
- the `demo-playable` and `demo-ai-stress` profiles both target `GC_TankGeneral`
- save/load a mission with spawned check units and confirm kills still complete checks exactly once
- in fallback mode only, confirm each new fallback check grants either one unlock group + `$2000` or, when the item pool is exhausted, `$10000`
- in seeded mode, confirm local fallback rewards do not fire because AP bridge owns rewards
- confirm playtest hotkeys and slash-chat controls work in mission
- confirm bridge fixtures can inject mixed group unlocks and general unlocks without crashes
- beat the same enemy challenge mission with different player generals and confirm the same Archipelago location is marked complete

## Player Release Smoke Test

Before shipping a player build, verify:

1. legal base install
2. GenPatcher on the clean base install
3. clone into a separate GeneralsAP folder
4. GeneralsAP overlay/package applied to the clone only
5. launch with `-userDataDir`
6. no Python, CMake, or dev tooling required for the player path
7. the package applies the canonical Super Patch runtime overlay instead of raw patch-source files

## CI

- `.github/workflows/validate-archipelago-data.yml`
  - runs the Archipelago generation/validation suite on pushes and PRs
- `.github/workflows/ci.yml`
  - runs build and replay verification for game code changes
- `.github/workflows/sync-superhackers-upstream.yml`
- `.github/workflows/sync-archipelago-vendor.yml`
  - creates an Archipelago release-sync branch, refreshes the managed vendor snapshot, materializes the disposable worktree, and opens a PR
