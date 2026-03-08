# Archipelago Implementation - Context Index

**Purpose**: First-stop handoff document for the Generals Archipelago project.

**Last updated**: March 8, 2026

---

## 1. Quick Start for New Agent

1. Read first: [Archipelago-Logic-Implementation-Guide.md](Docs/Archipelago/Planning/Archipelago-Logic-Implementation-Guide.md)
2. Read next: [Archipelago-Implementation-Todo.md](Docs/Archipelago/Planning/Archipelago-Implementation-Todo.md)
3. Then read: [Docs/Archipelago/Unlock-Group-Logic.md](Docs/Archipelago/Unlock-Group-Logic.md)
4. Sanity-check current repo reality with:
   - [Archipelago-Code-Review.md](Docs/Archipelago/Planning/Archipelago-Code-Review.md)
   - [Spawnability-Audit.md](Docs/Archipelago/Research/Spawnability-Audit.md)
   - [Data/Archipelago/README.md](Data/Archipelago/README.md)
   - [Wiki/Asset/GameDesign/ini/Archipelago-Template-Name-Pipeline.md](Wiki/Asset/GameDesign/ini/Archipelago-Template-Name-Pipeline.md)
   - [Player-Release-Architecture.md](Docs/Archipelago/Operations/Player-Release-Architecture.md)
   - [Archipelago-State-Sync-Architecture.md](Docs/Archipelago/Operations/Archipelago-State-Sync-Architecture.md)
   - `vendor/vendor-lock.json`
   - `vendor/generals-game-patch/vendor.json`
   - [SuperHackers-Upstream-Sync.md](Docs/Archipelago/Operations/SuperHackers-Upstream-Sync.md)
   - [Archipelago-Vendor-Sync.md](Docs/Archipelago/Operations/Archipelago-Vendor-Sync.md)
   - [TESTING.md](TESTING.md)
5. Normal builds use committed Archipelago outputs and do not need Python. Only maintainers regenerating data need `GENERALS_ASSET_ROOT`.
6. For current in-game testing, use the direct debug wrapper flow instead of the experimental staged localtest path:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_prepare.ps1`
   - `python scripts\archipelago_bridge_local.py --archipelago-dir ".\build\win32-vcpkg-debug\GeneralsMD\Debug\UserData\Archipelago"`
   - `powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_launch.ps1`
   - Or just run `powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_run.ps1`
   - Default runtime profile is `reference-clean`, which stages the known-good old `Archipelago.ini` + `UnlockableChecksDemo.ini` pair on top of the known-good root debug runtime assets from `C:\Users\Matt\Desktop\GeneralsAP\build\win32-vcpkg-debug\GeneralsMD\Debug`.
   - Use `-RuntimeProfile archipelago-bisect` or `-RuntimeProfile archipelago-current` only when intentionally validating newer runtime INI changes.
7. Build generated Archipelago config with:
   - `cmake --build build/win32-vcpkg-debug --target archipelago_config --config Debug`
   - For data regeneration, configure with `-DARCHIPELAGO_REGENERATE_DATA=ON -DGENERALS_ASSET_ROOT=...`.
8. Run script validation with:
   - `python scripts/archipelago_run_checks.py`
   - `python scripts/archipelago_vendor_materialize.py`

---

## 2. Document Index

### Core Design & Plan

| Document | Purpose |
|----------|---------|
| [Archipelago-Logic-Implementation-Guide.md](Docs/Archipelago/Planning/Archipelago-Logic-Implementation-Guide.md) | Master design for cluster rules, logic, UI, items, traps, and phased work |
| [Archipelago-Implementation-Todo.md](Docs/Archipelago/Planning/Archipelago-Implementation-Todo.md) | Current status, open phases, and ownership boundaries |
| [Docs/Archipelago/Unlock-Group-Logic.md](Docs/Archipelago/Unlock-Group-Logic.md) | Kill -> unlock -> message execution order and group-display-name rules |

### Operations / Release / Sync

| Document | Purpose |
|----------|---------|
| [Player-Release-Architecture.md](Docs/Archipelago/Operations/Player-Release-Architecture.md) | Supported player install/release model built around clone + `-userDataDir` |
| [Archipelago-State-Sync-Architecture.md](Docs/Archipelago/Operations/Archipelago-State-Sync-Architecture.md) | Inbound/outbound bridge-state contract, local fixture bridge, and external AP bridge responsibilities |
| [SuperHackers-Upstream-Sync.md](Docs/Archipelago/Operations/SuperHackers-Upstream-Sync.md) | Fork remote model and merge-based upstream sync workflow |
| [Archipelago-Vendor-Sync.md](Docs/Archipelago/Operations/Archipelago-Vendor-Sync.md) | Managed Archipelago release-vendor workflow, overlay, patch, and capture policy |
| `vendor/vendor-lock.json` | Pinned GeneralsAP upstream refs, including the canonical Super Patch runtime artifact |
| `vendor/generals-game-patch/vendor.json` | Managed Super Patch vendor-lane metadata and runtime overlay contract |

### Data / Naming / Validation

| Document | Purpose |
|----------|---------|
| [Data/Archipelago/README.md](Data/Archipelago/README.md) | Current data conventions, denylist rules, naming pipeline, and runtime data split |
| [Data/Archipelago/Slot-Data-Format.md](Data/Archipelago/Slot-Data-Format.md) | Planned spawned-check slot-data payload contract |
| [Wiki/Asset/GameDesign/ini/Archipelago-Template-Name-Pipeline.md](Wiki/Asset/GameDesign/ini/Archipelago-Template-Name-Pipeline.md) | Template -> DisplayName -> localized-name lookup reference |
| `Data/Archipelago/reference/unresolved_template_name_notes.json` | Curated suspected ties for unresolved non-player-facing templates |
| [Spawnability-Audit.md](Docs/Archipelago/Research/Spawnability-Audit.md) | Historical spawnability review notes for template cleanup |
| [TESTING.md](TESTING.md) | Current build/test commands and manual verification targets |

### Engine / Gameplay Notes

| Document | Purpose |
|----------|---------|
| [Docs/Archipelago/Spawned-Unit-AI.md](Docs/Archipelago/Spawned-Unit-AI.md) | Current spawned-unit AI status and remaining tuning work |
| [Docs/Archipelago/Manual-Review-And-Debug-Guide.md](Docs/Archipelago/Manual-Review-And-Debug-Guide.md) | Manual validation guide and debug search hints |
| [Archipelago-Code-Review.md](Docs/Archipelago/Planning/Archipelago-Code-Review.md) | Prior findings and code review notes |

---

## 3. Key Code Paths

### C++

| Path | Responsibility |
|------|----------------|
| `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp` | Map load, spawn/tag setup, save-load rebuild, leash state, kill bonus/all-unlocked bonus bookkeeping |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp` | Unlock state persistence, bridge inbound/outbound sync, completed check/location state, notifications |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Object.cpp` | `scoreTheKill` ordering and `m_archipelagoCheckId` save/load serialization |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/AIUpdate.cpp` | Spawned-unit retarget restrictions outside defend radius |
| `GeneralsMD/Code/GameEngine/Source/Common/RTS/Team.cpp` | Spawned-unit exclusion from mission/team command control |
| `GeneralsMD/Code/GameEngine/Source/GameClient/GUI/GUICallbacks/Menus/ScoreScreen.cpp` | Challenge mission completion location marking by enemy mission/general |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockRegistry.cpp` | Archipelago.ini loading, location IDs, group lookup, settings parsing |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/System/GameLogic.cpp` | Archipelago-related challenge superweapon limit |
| `GeneralsMD/Code/GameEngine/Source/Common/GlobalData.cpp` | User-data directory ownership and `-userDataDir` path normalization |
| `GeneralsMD/Code/GameEngine/Source/Common/CommandLine.cpp` | `-userDataDir`, `-mod`, and startup command-line parsing |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/ProductionUpdate.cpp` | Unit-production lock enforcement |
| `GeneralsMD/Code/GameEngine/Source/Common/System/BuildAssistant.cpp` | Building-placement lock enforcement |
| `GeneralsMD/Code/GameEngine/Source/GameClient/GUI/ControlBar/ControlBarCommand.cpp` | Lock overlays in the command bar |
| `GeneralsMD/Code/GameEngine/Source/GameClient/GUI/GUICallbacks/ControlBarPopupDescription.cpp` | Locked tooltip messaging |
| `GeneralsMD/Code/Main/CMakeLists.txt` | Build-time generation/validation of localized name maps and Archipelago.ini |

### Python

| Path | Responsibility |
|------|----------------|
| `scripts/archipelago_build_localized_name_map.py` | Generate `ingame_names.json` from `display_names.json` + `generals.csf` |
| `scripts/archipelago_build_template_name_map.py` | Generate `template_ingame_names.json` from object `DisplayName`, build variations, and build-button localization |
| `scripts/archipelago_generate_ini.py` | Generate `Data/INI/Archipelago.ini` with denylist enforcement |
| `Data/Archipelago/runtime_profiles/profiles.json` | Explicit runtime-profile manifest for `reference-clean`, `archipelago-bisect`, and `archipelago-current` |
| `Data/Archipelago/runtime_profiles/archipelago-bisect/batches.json` | Ordered reintroduction batches for strict Archipelago runtime-file bisecting |
| `scripts/archipelago_validate_ini.py` | Validate generated INI templates and reject denylisted entries |
| `scripts/archipelago_audit_groups.py` | Audit remaining spawnable units/buildings after applying the denylist |
| `scripts/archipelago_generate_matchup_graph.py` | Generate localized matchup graph outputs with denylist enforcement |
| `scripts/archipelago_logic_prerequisites.py` | Logic prerequisites; `compute_player_strength()` is still a stub |
| `scripts/archipelago_cluster_editor.py` | Cluster point editing/export tool |
| `scripts/archipelago_cluster_selection.py` | Cluster selection logic |
| `scripts/archipelago_run_checks.py` | Lightweight Archipelago generation + validation suite |
| `scripts/archipelago_bridge_local.py` | Fixture-driven local bridge sidecar for `LocalBridgeSession.json` <-> bridge JSON round-trip |
| `scripts/windows_debug_prepare.ps1` | Imports the VS x86 environment, builds `win32-vcpkg-debug`, and ensures the direct debug runtime is ready |
| `scripts/windows_debug_launch.ps1` | Launches the direct debug runtime with `-userDataDir .\UserData\` |
| `scripts/windows_debug_run.ps1` | One-command direct debug build + sidecar + launch flow |
| `scripts/windows_debug_smoketest.ps1` | Startup regression gate for runtime profiles; fails on asset/assert signatures before menu |
| `scripts/windows_localtest_prepare.ps1` | Older staged localtest flow retained for reference only; not the recommended path for current in-game testing |
| `scripts/windows_localtest_launch.ps1` | Older staged localtest launcher retained for reference only |
| `scripts/gamepatch_runtime_materialize.py` | Build the canonical runtime-safe Super Patch overlay from the pinned `Patch104pZH` checkout |
| `scripts/gamepatch_runtime_audit.py` | Reject blocked source-only files in the canonical Super Patch runtime overlay |
| `scripts/gamepatch_asset_parity_scan.py` | Reject blocked source artifacts and missing expected overlay files in the final staged runtime |
| `scripts/archipelago_vendor_materialize.py` | Build a disposable Archipelago worktree from upstream + overlay + patches |
| `scripts/archipelago_vendor_capture.py` | Capture worktree edits back into `vendor/archipelago/overlay` and `vendor/archipelago/patches` |
| `scripts/archipelago_vendor_sync.py` | Import an official Archipelago release into the managed vendor lane |
| `scripts/archipelago_vendor_sync.ps1` / `scripts/archipelago_vendor_sync.sh` | Create `codex/archipelago-sync-*` branches for Archipelago release refreshes |
| `scripts/superhackers_upstream_sync.ps1` / `scripts/superhackers_upstream_sync.sh` | Merge-based upstream sync branch workflow |
| `scripts/repo_configure_remotes.ps1` / `scripts/repo_configure_remotes.sh` | Normalize `origin`/`upstream` remotes for a fork setup |

---

## 4. Conventions

- `display_names.json` stores localization keys, not final player-facing text.
- Human-readable script output should use `template_ingame_names.json` first, backed by `DisplayName -> generals.csf`, with optional explicit overrides only from `name_overrides.json`.
- Retail Zero Hour assets are intentionally external to the GitHub-safe repo. Normal builds use committed generated Archipelago files; only regeneration flows resolve retail assets from the checkout or `GENERALS_ASSET_ROOT`.
- `non_spawnable_templates.json` is authoritative. Denylisted templates must not appear in generated INI, matchup outputs, or audits.
- `reference/unresolved_template_name_notes.json` is authoritative for unresolved template review metadata; `template_ingame_names.json` mirrors it in `_unresolved_notes`, and generation should fail if any unresolved template lacks a note.
- `Data/Archipelago/*` is the editable source layer. Runtime-safe loose INI files are staged from `Data/Archipelago/runtime_profiles/*`, not directly from the evolving source files.
- `UnlockableChecksDemo.ini` is still the active in-game fallback source for spawned checks, but the validated runtime copy now comes from the selected runtime profile.
- Unlock group IDs from `groups.json` / `Archipelago.ini` are the stable Archipelago item IDs. Use `item_pool=false` for baseline groups that should never be chosen as randomized unlock items.
- `Bridge-Inbound.json` / `Bridge-Outbound.json` are the implemented local state-sync seam; `LocalBridgeSession.json` is the fixture-driven local harness input; real inbound unlocks are explicit `receivedItems`, while `Slot-Data-Format.md` remains the separate future spawned-check seed payload contract.
- Launch isolated installs with `-userDataDir` so saves, options, and bridge files remain profile-local.
- Use the direct debug runtime under `build/win32-vcpkg-debug/GeneralsMD/Debug` for current in-game testing.
- Default debug/recovery testing must use the `reference-clean` runtime profile until newer runtime INI batches pass the startup smoke gate.
- The staged localtest flow is now secondary and should not be used as the default path while re-establishing the zero-asset-error baseline.
- Super Patch source content is not stageable as-is. Localtest and release prep must consume the canonical runtime overlay built by `scripts/gamepatch_runtime_materialize.py`, not raw `Patch104pZH/GameFilesEdited`.
- Reference-only extracted inputs live under `Data/Archipelago/reference`.
- Transient audit, expansion, and materialized vendor outputs belong under `build/archipelago`, not the repo root.
- Use `[Archipelago]` in DEBUG_LOG output for Archipelago-specific logging.
- Preserve kill ordering: `grantCheckForKill()` must run before spawner post-kill handling.
- Project Git model: `origin` = your GeneralsAP repo, `upstream` = TheSuperHackers/GeneralsGameCode.
- Archipelago vendor model: `vendor/archipelago/upstream` is the imported release snapshot, `vendor/archipelago/overlay` is Generals-owned additive content, `vendor/archipelago/patches` stores ordered edits to upstream-managed files, and `scripts/archipelago_vendor_capture.py` is the round-trip tool for preserving materialized worktree edits.

---

## 5. Agent Assignments

| Agent | Domain | Current Priority |
|-------|--------|------------------|
| Agent A | Data/scripts/AP-world prep | Real cluster data, `compute_player_strength()`, AP bridge process, slot-data schema |
| Agent B | C++ game logic | Slot-data ingestion, compositions, items/traps, bridge-aware runtime behavior |
| Agent C | UI / release shell | Phase E UI and first-player release workflow after A/B contracts stabilize |

---

## 6. Open Phases (Summary)

- `P1` data hygiene
  - keep naming CSF-backed and verified
  - keep non-spawnable templates out of all script paths
- `P2` backend
  - external AP bridge process
  - real slot-data ingestion
  - real cluster data for challenge maps
  - meaningful presets
  - `compute_player_strength()` implementation
- `P3` release foundation
  - standalone clone/install flow
  - release manifest + staging pipeline
  - clean player package that always uses `-userDataDir`
- `P4` feature work
  - Phase E UI
  - Phase F items/traps
  - C7 compositions

---

## 7. Build & Test Commands

```bash
cmake --list-presets
cmake -S . -B build/win32-vcpkg-debug -DARCHIPELAGO_REGENERATE_DATA=ON -DGENERALS_ASSET_ROOT="C:/Path/To/Generals Zero Hour" -DRTS_BUILD_ZEROHOUR=ON -DRTS_BUILD_GENERALS=OFF
cmake --build build/win32-vcpkg-debug --target archipelago_config --config Debug
python scripts/archipelago_run_checks.py
python scripts/archipelago_generate_matchup_graph.py
python scripts/archipelago_bridge_local.py --archipelago-dir build/win32-vcpkg-debug/GeneralsMD/Debug/UserData/Archipelago --once
python scripts/gamepatch_runtime_materialize.py
python scripts/gamepatch_runtime_audit.py
python scripts/gamepatch_asset_parity_scan.py --stage-root build/localtest-install --overlay-manifest build/gamepatch-runtime/runtime-overlay-manifest.json
python scripts/archipelago_vendor_materialize.py
python scripts/archipelago_vendor_capture.py
```

For isolated local runtime testing, launch the built game with a dedicated profile path:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_prepare.ps1
python scripts\archipelago_bridge_local.py --archipelago-dir ".\build\win32-vcpkg-debug\GeneralsMD\Debug\UserData\Archipelago"
powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_launch.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\windows_debug_smoketest.ps1
```

---

Use this file as the first document to load when resuming or transferring Archipelago work.
