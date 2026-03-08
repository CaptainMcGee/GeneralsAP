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

## Canonical Windows Debug Test Loop

For in-game testing, use the direct debug build again. Do not stage a separate clone-backed runtime.

From plain PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_prepare.ps1
python scripts\archipelago_bridge_local.py --archipelago-dir ".\build\win32-vcpkg-debug\GeneralsMD\Debug\UserData\Archipelago"
powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_launch.ps1
```

For the simplest repeatable loop, use the one-command runner instead:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_run.ps1
```

To force a clean rebuild first:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_run.ps1 -Rebuild
```

Or double-click:

```text
Run-GeneralsAP-Debug.cmd
```

That runner builds `win32-vcpkg-debug`, starts the local bridge sidecar against the debug runtime `UserData\Archipelago` folder, and launches `build\win32-vcpkg-debug\GeneralsMD\Debug\generalszh.exe` with `-userDataDir .\UserData\`.

## Cursor / VS Code Debugging

The clean worktree now includes ready-to-run debugger profiles in `.vscode\launch.json` and tasks in `.vscode\tasks.json`.

Recommended flow in Cursor:

1. Open this clean worktree as the workspace.
2. Run the task `GeneralsAP: Run Local Bridge Sidecar` in one terminal if you want bridge sync active during the test.
3. Start the launch configuration `GeneralsAP Debug (Cursor/VS Code)`.

That launch config rebuilds the direct debug output first, then starts `build\win32-vcpkg-debug\GeneralsMD\Debug\generalszh.exe` with `-userDataDir .\UserData\`.

Use `GeneralsAP Debug (No Rebuild)` only when you know the debug output is already current.

`windows_debug_prepare.ps1` will:

- import the Visual Studio x86 build environment into the current PowerShell session
- validate `VCPKG_ROOT`
- configure/build the `win32-vcpkg-debug` preset
- generate `Archipelago.ini` through `archipelago_config`
- sync the known-good root debug runtime `Data`, `MappedImages`, `MSS`, `ZH_Generals`, `.big`, and DLL files from `C:\Users\Matt\Desktop\GeneralsAP\build\win32-vcpkg-debug\GeneralsMD\Debug`
- preserve the recovery build's Archipelago-only overrides such as `Archipelago.ini`, `UnlockableChecksDemo.ini`, and debug command maps
- ensure the direct debug runtime has a local `UserData\Archipelago` folder ready for the bridge
- fail immediately if the debug runtime is missing the traditional run-directory essentials such as `Data`, `MSS`, `ZH_Generals`, `BINKW32.DLL`, `mss32.dll`, and the required `.big` archives

The local bridge sidecar mirrors `LocalBridgeSession.json` into `Bridge-Inbound.json`, including explicit `receivedItems`, watches `Bridge-Outbound.json`, and merges completed checks/locations plus unlocked group IDs back into the session file for repeatable in-game testing without a live AP server.

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
python scripts/archipelago_vendor_capture.py
```

## Manual Runtime Checks

After engine-side changes, verify these in game:

- run the direct debug output from `build\win32-vcpkg-debug\GeneralsMD\Debug`
- launch from an isolated profile with `-userDataDir` and confirm the game writes into that local `UserData` tree instead of the default Documents profile
- confirm `UserData\Archipelago\LocalBridgeSession.json` is created by the bridge sidecar and `Bridge-Inbound.json` is written
- confirm `UserData\Archipelago\Bridge-Outbound.json` is created after local Archipelago state initializes
- the current fallback demo in `Data\INI\UnlockableChecksDemo.ini` targets `GC_TankGeneral`
- save/load a mission with spawned check units and confirm kills still complete checks exactly once
- confirm each new fallback check grants either one unlock group + `$2000` or, when the item pool is exhausted, `$10000`
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
