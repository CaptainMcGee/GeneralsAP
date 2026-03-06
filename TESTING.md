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

## Maintainer CMake Regeneration

To force regeneration of the localized name maps and build-directory `Archipelago.ini` through CMake:

```bash
cmake --list-presets
cmake -S . -B build/win32-vcpkg-debug -DARCHIPELAGO_REGENERATE_DATA=ON -DGENERALS_ASSET_ROOT="C:/Path/To/Generals Zero Hour"
cmake --build build/win32-vcpkg-debug --target archipelago_config --config Debug
```

## Archipelago Vendor Checks

To verify the managed Archipelago vendor lane:

```bash
python scripts/archipelago_vendor_materialize.py
python scripts/archipelago_vendor_capture.py
```

## Manual Runtime Checks

After engine-side changes, verify these in game:

- launch from an isolated profile with `-userDataDir` and confirm the game writes into that local `UserData` tree instead of the default Documents profile
- confirm `UserData\Archipelago\Bridge-Outbound.json` is created after local Archipelago state initializes
- place a small `Bridge-Inbound.json` containing new generals or unlocks and confirm the game imports them once and persists the result
- save/load a mission with spawned check units and confirm kills still complete checks exactly once
- destroy the final required spawned or tagged object and confirm the all-unlocked bonus triggers once
- beat the same enemy challenge mission with different player generals and confirm the same Archipelago location is marked complete
- confirm denylisted templates are absent from generated data and no longer appear in graph or audit outputs

## Player Release Smoke Test

Before shipping a player build, verify:

1. legal base install
2. GenPatcher on the clean base install
3. clone into a separate GeneralsAP folder
4. GeneralsAP overlay/package applied to the clone only
5. launch with `-userDataDir`
6. no Python, CMake, or dev tooling required for the player path

## CI

- `.github/workflows/validate-archipelago-data.yml`
  - runs the Archipelago generation/validation suite on pushes and PRs
- `.github/workflows/ci.yml`
  - runs build and replay verification for game code changes
- `.github/workflows/sync-superhackers-upstream.yml`
- `.github/workflows/sync-archipelago-vendor.yml`
  - creates an Archipelago release-sync branch, refreshes the managed vendor snapshot, materializes the disposable worktree, and opens a PR
