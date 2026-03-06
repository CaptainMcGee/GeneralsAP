# Testing

## Prerequisite Asset Root

The GitHub-safe repo does not track retail Zero Hour assets. If this checkout does not already contain `Data/English/generals.csf` and the retail `Data/INI` files, point the scripts/build to your local game install first:

```powershell
$env:GENERALS_ASSET_ROOT = "C:\Path\To\Generals Zero Hour"
```

`GENERALS_ASSET_ROOT` may point either to the game root or directly to its `Data` directory.

## Lightweight Archipelago Checks

Run the script suite from the repo root:

```bash
python scripts/archipelago_run_checks.py
```

This now runs, in order:

1. `scripts/archipelago_build_localized_name_map.py`
2. `scripts/archipelago_build_template_name_map.py`
3. `scripts/archipelago_generate_ini.py`
4. `scripts/archipelago_validate_ini.py`
5. `scripts/archipelago_generate_matchup_graph.py`
6. `scripts/archipelago_audit_groups.py`
7. `scripts/tests/test_archipelago_data_pipeline.py`

## CMake Regeneration

To regenerate the localized name maps and build-directory `Archipelago.ini` through CMake:

```bash
cmake --list-presets
cmake -S . -B build/win32-vcpkg-debug -DGENERALS_ASSET_ROOT="C:/Path/To/Generals Zero Hour"
cmake --build build/win32-vcpkg-debug --target archipelago_config --config Debug
```

## Archipelago Vendor Checks

To verify the managed Archipelago vendor lane:

```bash
python scripts/archipelago_vendor_materialize.py
python scripts/archipelago_vendor_capture.py
```

`archipelago_vendor_materialize.py` rebuilds `build/archipelago/archipelago-worktree` from `vendor/archipelago/upstream` plus any overlay files and ordered patches.

`archipelago_vendor_capture.py` round-trips edits from that disposable worktree back into `vendor/archipelago/overlay` and `vendor/archipelago/patches` so future Archipelago release syncs can replay Generals-owned changes instead of keeping a hand-edited fork.

## CI

- `.github/workflows/validate-archipelago-data.yml`
  - runs the full lightweight Archipelago generation/validation suite on every push and PR to `main`
- `.github/workflows/ci.yml`
  - runs build and replay verification for game code changes, including `codex/upstream-sync-*` branches
- `.github/workflows/sync-superhackers-upstream.yml`
- `.github/workflows/sync-archipelago-vendor.yml`
  - creates an Archipelago release-sync branch, refreshes the managed vendor snapshot, materializes the disposable worktree, and opens a PR

## Manual In-Game Checks

After engine-side changes, verify these in game:

- save/load a mission with spawned check units and confirm kills still complete checks exactly once
- destroy the final required spawned or tagged object and confirm the all-unlocked bonus triggers once
- beat the same enemy challenge mission with different player generals and confirm the same Archipelago location is marked complete
- confirm denylisted templates are absent from generated data and no longer appear in graph or audit outputs

## Replay Tests

The replay compatibility workflow remains the same as the broader project flow. For local replay checks, use the repo’s existing replay maps and build guidance after the Archipelago-specific suite passes.


