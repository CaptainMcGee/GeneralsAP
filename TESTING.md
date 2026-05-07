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

For the packaged bridge executable file path:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_generalsap_bridge.ps1
python scripts\archipelago_bridge_executable_smoke.py --bridge-exe .\build\release-tools\GeneralsAPBridge.exe
python scripts\archipelago_bridge_network_smoke.py --bridge-exe .\build\release-tools\GeneralsAPBridge.exe
python scripts\archipelago_bridge_real_ap_server_smoke.py --bridge-exe .\build\release-tools\GeneralsAPBridge.exe
python scripts\archipelago_bridge_real_ap_server_smoke.py --bridge-exe .\build\release-tools\GeneralsAPBridge.exe --full-world-simulation
```

This proves the packaged bridge binary can materialize `Seed-Slot-Data.json`, write `Bridge-Inbound.json`, reject unknown runtime keys/AP IDs, reject reused session files when seed/slot/session nonce changes without `--reset-session`, accept valid numeric `completedLocations`, merge duplicate outbound completions idempotently, preserve future capture/supply state arrays without completing checks, translate selected future-family fixture keys (`capture.tank.b001`, `supply.tank.p02.t02`) without enabling production capture/supply gameplay, speak the AP 0.6.7 websocket packet seam against a fake AP server, map incremental received AP items into runtime unlock/session options, submit selected runtime checks as AP numeric location IDs, submit selected future-family fixture checks over network mode, keep Boss victory as `StatusUpdate` only instead of `LocationChecks`, and then repeat the same mission/cluster submission path against a real local Archipelago 0.6.7 `MultiServer.py` generated from the GeneralsZH world. The real-server smoke also verifies fresh reconnect persistence and duplicate-safe replay, serializes shared AP smoke venv/worktree setup, and retries local server startup on fresh ports. An external hosted-room smoke can still be useful before public alpha, but the local real-server smoke is the stronger automated gate because it owns generation, server startup, connection, submission, and reconnect in one repeatable command.

The `--full-world-simulation` variant completes every selected main mission/cluster runtime key through the bridge, verifies the AP server delivers all seven shuffled medals, submits Boss cluster checks only after medals, submits Boss victory through the goal status path, and replays duplicate completion input as a no-op. This is a bridge/AP simulation, not final weakness or mission-gate proof.

Location-family validation is still planning/scaffold validation, not gameplay proof. `archipelago_location_catalog_validate.py` proves disabled catalog shape, authoring metadata, future persistence contract, and enable criteria. `archipelago_logic_contract_validate.py` proves disabled future capability-source and mission-gate handoff contracts align with current map keys, requirement tags, floors, medal/Boss policy, and item-specific production-prerequisite policy. `archipelago_item_location_capacity_report.py` proves current location pressure: active presets remain `minimal=35` and `default=51`, with `3992` reserved captured-building IDs and `3528` reserved supply-threshold IDs. Production catalog count remains `0`; example candidates are test fixtures only.

For the ordered non-human release gate, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_generalsap_nonhuman_release_checks.ps1
```

Use `-FastRealApSmoke` only when `build\archipelago\ap-smoke-venv` and `build\archipelago\archipelago-worktree` already exist. This runner executes PR scope audit, required checkout for `tools/cluster-editor` and `tools/logic-foundry`, bridge build, AP data/world suite, generated-output cleanliness, file bridge smoke, fake AP network smoke, real local AP server smoke, package fixture smoke, clean-runtime fixture harness smoke, and the clean-runtime legal-runtime guard in release-check order. Generated-output cleanliness checks unstaged, staged, and untracked generated drift. Package fixture smoke builds and validates both package root and zip output, rejects zip siblings outside the selected package root, rejects transient APWorld artifacts, requires the full APWorld module set, rejects bundled `bridgeKind=staging_stub`, and runs bridge translation against the produced `payload\Bridge\GeneralsAPBridge.exe`. It writes reports under `build\archipelago\nonhuman-release-checks`. GitHub framework-contract CI stages retained package, bridge executable, and AP-smoke temp directories from the Python temp root into `build\archipelago\ci-framework-smoke-artifacts`, fails if those proof directories are missing after successful smokes, and uploads that staged folder for failure inspection. It does not replace legal-runtime launch proof. The guard intentionally verifies that `smoke_generalsap_clean_runtime.ps1` fails unless a real `-BaseRuntimeDir` or explicit `-UseFixtureRuntime` is supplied.

When a legal Zero Hour runtime is available, include the fast automatic runtime completion proof in the same ordered gate:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_generalsap_nonhuman_release_checks.ps1 `
  -BaseRuntimeDir "C:\Games\ZeroHourCleanClone"
```

That optional path rebuilds `build\win32-vcpkg-playtest\GeneralsMD\Release\generalszh.exe`, packages the overlay, launches the cloned legal runtime, injects `mission.tank.victory` and `cluster.tank.c02.u01` through the guarded runtime-smoke file, fails if `generalszh.exe` exits immediately after producing the proof, then verifies AP numeric ID translation. The runner defaults to 20 seconds of startup wait and 180 seconds of runtime-key wait because the real Zero Hour startup path can be slow on cloned legal installs. You can also set `GENERALSAP_BASE_RUNTIME_DIR` instead of passing `-BaseRuntimeDir`.

For the strongest non-human release-flow proof, add `-RunIntegratedRealApRuntimeSmoke` to the same command. That starts a real local AP 0.6.7 server, seeds the clean installed runtime through the packaged bridge's live `--connect` path, launches the game, injects the guarded mission/cluster runtime keys, submits them back to the AP server through the network bridge, and fresh-reconnects to verify server-persisted checked locations. This still does not prove natural score-screen or spawned-kill gameplay events.

Add `-RunSpawnedMaterializationSmoke` only when a legal runtime is available and you need non-human proof that the Tank challenge can launch directly and materialize selected spawned check object `cluster.tank.c02.u01`. This reads `ArchipelagoSpawnedUnitState.json` after the runtime writes `Runtime-Smoke-DumpSpawned.flag`; it proves selected spawned-object materialization, not kill completion, save/load replay, pathing, combat fairness, or natural player interaction.

For the most human-like automated demo proof, run the demo director against a legal healthy Zero Hour install or clone:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_generalsap_demo_director.ps1 `
  -BaseRuntimeDir "C:\Games\ZeroHourCleanClone"
```

This uses `human_demo_tank`, builds the packaged bridge, verifies fixture slot-data and inbound unlock state, launches `Maps\GC_TankGeneral.map`, waits for selected spawned check object `cluster.tank.c02.u01`, injects guarded completions for `mission.tank.victory` and `cluster.tank.c02.u01`, and then runs the live local AP 0.6.7 network loop unless `-SkipNetworkProof` is passed. It writes `build\archipelago\demo\Demo-Proof.json`. This is stronger than a hand demo for bridge/seed plumbing, but it still does not prove natural 45-minute mission victory, player combat fairness, or final mission-gate design.

Use `Docs\Archipelago\Operations\Demo-Proof-Review.md` when interpreting `Demo-Proof.json` for PR review. That doc records the exact pass criteria and the caveats that must not be overclaimed.

Before PR review, also run the branch-scope audit against the intended base branch:

```powershell
python scripts\archipelago_pr_scope_audit.py --base origin/codex/ap-world-skeleton-checkpoint --head HEAD
```

This rejects unexpected changed-file lanes, obvious forbidden-scope filenames, and forbidden implementation matches in `GeneralsMD`, `tools/bridge`, `scripts`, and APWorld overlay implementation files. The ordered non-human runner calls it automatically by default. Use `-SkipScopeAudit` only outside this branch context or when the intended base branch is unavailable.

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

`/ap_unlock_capture` unlocks the vanilla `Upgrade_InfantryCaptureBuilding` ability. It is not captured-building AP location gameplay.

## Bridge Fixtures

The sidecar can seed `LocalBridgeSession.json` from curated fixtures under `Data/Archipelago/bridge_fixtures`:

- `minimal_progression`
- `mixed_progression`
- `human_demo_tank`
- `almost_exhausted_pool`
- `post_exhaustion_pool`

Example:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_demo_run.ps1 -Fixture almost_exhausted_pool -ResetSession
powershell -ExecutionPolicy Bypass -File .\scripts\windows_demo_run.ps1 -Fixture human_demo_tank -ResetSession -NoZoomLimit
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
python scripts/archipelago_bridge_real_ap_server_smoke.py --bridge-exe build/release-tools/GeneralsAPBridge.exe --skip-install --skip-materialize
powershell -ExecutionPolicy Bypass -File scripts/run_generalsap_nonhuman_release_checks.ps1 -FastRealApSmoke
python scripts/archipelago_vendor_capture.py
```

Current expected vendor-lane shape: materialize/capture should report 14 GeneralsZH overlay files and `Patch written: none`. `archipelago_vendor_capture.py` must not capture transient AP runtime output such as root `host.yaml`, `logs/`, `__pycache__/`, or `.pyc` files. If those appear in `git status`, treat the vendor lane as polluted and fix the capture guard before committing.

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
2. clean base install launches as a healthy Zero Hour 1.04-compatible runtime
3. clone into a separate GeneralsAP folder
4. GeneralsAP overlay/package applied to the clone only
5. launch with `-userDataDir`
6. no Python, CMake, or dev tooling required for the player path
7. package manifest sets `requiresExternalBasePatcher` to `false`
8. no retail `.big` archives or other base-game assets are present in the GeneralsAP package
9. the package applies the canonical Super Patch runtime overlay instead of raw patch-source files
10. `bridgeKind` is `real` for public AP alpha; `file_bridge` is allowed only for local release-staging smoke

Release-staging package smoke:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_generalsap_alpha_package.ps1 -RuntimeDir .\build\win32-vcpkg-playtest\GeneralsMD\Release
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_generalsap_release_externality.ps1 -BaseRuntimeDir "C:\Games\ZeroHourCleanClone" -RunRuntimeLaunchSmoke -RunSpawnedMaterializationSmoke
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_generalsap_clean_runtime.ps1 -UseFixtureRuntime
```

Use `-UseFixtureRuntime` only for package/installer harness mechanics when no legal cloned runtime is available. It does not prove launch. `smoke_generalsap_release_externality.ps1` is the stronger release artifact check: it packages from the prepared runtime, validates the package root and zip, extracts the zip in a path with spaces, rejects local path leakage and retail `.big` archives, runs bridge translation from the extracted `payload\Bridge\GeneralsAPBridge.exe`, and can run clean-runtime launch/materialization smokes from work directories with spaces when `-BaseRuntimeDir` is available.

Clean cloned-runtime proof, when a legal healthy Zero Hour runtime is available:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_generalsap_clean_runtime.ps1 `
  -BaseRuntimeDir "C:\Games\ZeroHourCleanClone" `
  -PreparedRuntimeDir ".\build\win32-vcpkg-playtest\GeneralsMD\Release" `
  -StartupWaitSeconds 20
```

Automatic runtime completion smoke, after the game launches, can inject guarded seeded completions without playing a full mission:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_generalsap_clean_runtime.ps1 `
  -BaseRuntimeDir "C:\Games\ZeroHourCleanClone" `
  -PreparedRuntimeDir ".\build\win32-vcpkg-playtest\GeneralsMD\Release" `
  -SmokeCompleteRuntimeKey mission.tank.victory,cluster.tank.c02.u01 `
  -CompletionTimeoutSeconds 90
```

That command packages the current GeneralsAP overlay, clones the legal runtime into a temporary install, applies `payload\Game`, seeds `UserData\Archipelago` through the packaged bridge, launches with `-userDataDir`, writes `Enable-Runtime-Smoke.flag` plus `Runtime-Smoke-Complete.json`, waits for the runtime keys to appear in `Bridge-Outbound.json`, then runs the packaged bridge again and verifies those keys translate to AP numeric location IDs. The game only processes the smoke file when the explicit flag exists, and normal seeded mode still accepts only selected keys from verified `Seed-Slot-Data.json`.

Source-wiring contract tests also verify that the natural callback paths use the same selected runtime-key pipeline: score-screen victory must call `markRuntimeCheckComplete` with the selected canonical mission runtime key, and spawned seeded cluster-unit kills must call `grantCheckForKill(..., TRUE)` with runtime keys assigned from slot data. These tests do not replace a slow natural-event playtest; they make sure the code path being playtested is the expected one.

Manual natural-event proof can still use `-WaitForRuntimeKey` instead of `-SmokeCompleteRuntimeKey` if you want to prove the score-screen mission-victory event or a real spawned-unit kill:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_generalsap_clean_runtime.ps1 `
  -BaseRuntimeDir "C:\Games\ZeroHourCleanClone" `
  -PreparedRuntimeDir ".\build\win32-vcpkg-playtest\GeneralsMD\Release" `
  -WaitForRuntimeKey mission.tank.victory,cluster.tank.c02.u01 `
  -CompletionTimeoutSeconds 900
```

Steam/TUC installs may expose `Generals.exe` instead of `generalszh.exe` in the legal base directory. That is valid for the base-runtime clone, but after the GeneralsAP payload is applied the installed clone must contain `generalszh.exe`. The package also carries `zlib1.dll` from the prepared GeneralsAP runtime; omitting it can produce Windows loader error `0xc000007b` if another incompatible zlib is found.

## CI

- `.github/workflows/validate-archipelago-data.yml`
  - runs the Archipelago generation/validation suite on pushes and PRs
  - rejects generated-output drift after the AP data suite
  - includes the AP framework contract gate on Windows: data pipeline tests, AP world contract tests, package fixture smoke with packaged bridge translation, bridge file-mode smoke, fake AP network smoke, real local AP server smoke, and PR branch-scope audit
  - includes a narrow `GeneralsMD` `win32-vcpkg-playtest` runtime compile smoke so C++ runtime changes are not covered only by source-string assertions
  - is intentionally GitHub-safe and non-human: it does not require retail assets, a legal runtime launch, AP hosted-room access, or natural gameplay events
- `.github/workflows/ci.yml`
  - runs build and replay verification for game code changes
- `.github/workflows/sync-superhackers-upstream.yml`
- `.github/workflows/sync-archipelago-vendor.yml`
  - creates an Archipelago release-sync branch, refreshes the managed vendor snapshot, materializes the disposable worktree, and opens a PR
