# Archipelago Implementation - Context Index

**Purpose**: First-stop handoff document for the Generals Archipelago project.

**Last updated**: April 27, 2026

---

## 1. Quick Start for a New Agent

1. Read first: [Docs/Archipelago/Planning/Archipelago-Logic-Implementation-Guide.md](Docs/Archipelago/Planning/Archipelago-Logic-Implementation-Guide.md)
2. Read next: [Docs/Archipelago/Planning/Archipelago-Logic-Mapping-Draft.md](Docs/Archipelago/Planning/Archipelago-Logic-Mapping-Draft.md)
3. Then read: [Docs/Archipelago/Planning/Archipelago-Implementation-Todo.md](Docs/Archipelago/Planning/Archipelago-Implementation-Todo.md)
4. For new item/location families, read: [Docs/Archipelago/Planning/Item-Location-Framework.md](Docs/Archipelago/Planning/Item-Location-Framework.md)
5. Then read the runtime contract docs:
   - [Data/Archipelago/Slot-Data-Format.md](Data/Archipelago/Slot-Data-Format.md)
   - [Docs/Archipelago/Operations/Archipelago-State-Sync-Architecture.md](Docs/Archipelago/Operations/Archipelago-State-Sync-Architecture.md)
   - [Docs/Archipelago/Unlock-Group-Logic.md](Docs/Archipelago/Unlock-Group-Logic.md)
6. Then sanity-check current repo reality with:
   - [Data/Archipelago/README.md](Data/Archipelago/README.md)
   - [Docs/Archipelago/Planning/Archipelago-Code-Review.md](Docs/Archipelago/Planning/Archipelago-Code-Review.md)
   - [Docs/Archipelago/Manual-Review-And-Debug-Guide.md](Docs/Archipelago/Manual-Review-And-Debug-Guide.md)
   - [Docs/Archipelago/Operations/Player-Release-Architecture.md](Docs/Archipelago/Operations/Player-Release-Architecture.md)
   - [TESTING.md](TESTING.md)
7. If you are touching logic, world contracts, or tracker semantics, read Section 3 of this file before acting on older numeric-model files.
8. If you are working on cluster placement, use the web-app submodule in `tools/cluster-editor`. The old Python/Tk editor is gone.
9. Normal builds use committed generated Archipelago outputs and do not need Python asset extraction. Only maintainers regenerating data need `GENERALS_ASSET_ROOT`.

---

## 2. Canonical Document Stack

### Core decisions and implementation plan

| Document | Current role |
|----------|--------------|
| [Docs/Archipelago/Planning/Archipelago-Logic-Implementation-Guide.md](Docs/Archipelago/Planning/Archipelago-Logic-Implementation-Guide.md) | Canonical alpha design and approved decision-pass record |
| [Docs/Archipelago/Planning/Archipelago-Logic-Mapping-Draft.md](Docs/Archipelago/Planning/Archipelago-Logic-Mapping-Draft.md) | Canonical mapping sheet for cluster classes, unlock groups, and item classifications |
| [Docs/Archipelago/Planning/Archipelago-Implementation-Todo.md](Docs/Archipelago/Planning/Archipelago-Implementation-Todo.md) | Canonical implementation backlog and phasing after the decision pass |
| [Docs/Archipelago/Planning/Item-Location-Framework.md](Docs/Archipelago/Planning/Item-Location-Framework.md) | Framework for future item/location families, economy items, sphere-zero checks, and ID/runtime-key lanes |
| [Docs/Archipelago/Planning/Item-Location-Framework-Branch-Readiness.md](Docs/Archipelago/Planning/Item-Location-Framework-Branch-Readiness.md) | Current branch readiness, validation status, merge target warning, and known runtime build gap |
| [Data/Archipelago/Slot-Data-Format.md](Data/Archipelago/Slot-Data-Format.md) | Canonical immutable seed payload contract for mission and cluster locations |
| [Data/Archipelago/location_families/catalog.json](Data/Archipelago/location_families/catalog.json) | Disabled author catalog for future captured-building and supply-pile-threshold checks |

### Runtime, sync, and release operations

| Document | Current role |
|----------|--------------|
| [Docs/Archipelago/Operations/Archipelago-State-Sync-Architecture.md](Docs/Archipelago/Operations/Archipelago-State-Sync-Architecture.md) | Current bridge seam and runtime state-sync responsibilities |
| [Docs/Archipelago/Operations/Player-Release-Architecture.md](Docs/Archipelago/Operations/Player-Release-Architecture.md) | Current release/install model built around clone + `-userDataDir` |
| [Docs/Archipelago/Operations/WND-UI-Workbench.md](Docs/Archipelago/Operations/WND-UI-Workbench.md) | Canonical WND extraction, audit, and loose-override workflow for the AP menu shell |
| [Docs/Archipelago/Operations/SuperHackers-Upstream-Sync.md](Docs/Archipelago/Operations/SuperHackers-Upstream-Sync.md) | Upstream sync workflow for the game-code fork |
| [Docs/Archipelago/Operations/Archipelago-Vendor-Sync.md](Docs/Archipelago/Operations/Archipelago-Vendor-Sync.md) | Vendor-lane workflow for upstream Archipelago refreshes |

### Data, naming, and validation

| Document | Current role |
|----------|--------------|
| [Data/Archipelago/README.md](Data/Archipelago/README.md) | Source-data conventions, denylist rules, naming pipeline, and runtime-data split |
| [Wiki/Asset/GameDesign/ini/Archipelago-Template-Name-Pipeline.md](Wiki/Asset/GameDesign/ini/Archipelago-Template-Name-Pipeline.md) | Template-to-localized-name reference path |
| [Docs/Archipelago/Manual-Review-And-Debug-Guide.md](Docs/Archipelago/Manual-Review-And-Debug-Guide.md) | Manual validation path and debug search hints |
| [TESTING.md](TESTING.md) | Current build/test commands and manual verification targets |

---

## 3. Historical or Non-Canonical Files for Alpha Design

These files still exist and may still matter for migration work, but they are **not** the canonical design authority for the current alpha model.

| Path | Current status |
|------|----------------|
| [Data/Archipelago/enemy_general_profiles.json](Data/Archipelago/enemy_general_profiles.json) | Historical numeric mission-logic scaffold; superseded conceptually by discrete `Hold` / `Win` mission gates |
| [scripts/archipelago_logic_prerequisites.py](scripts/archipelago_logic_prerequisites.py) | Historical numeric prerequisite evaluator; `compute_player_strength()` should be replaced or isolated, not expanded blindly |
| [Data/Archipelago/options_schema.yaml](Data/Archipelago/options_schema.yaml) | Contains older or placeholder option surface that is broader than the locked alpha-facing design |
| [Docs/Archipelago/Planning/Archipelago-Code-Review.md](Docs/Archipelago/Planning/Archipelago-Code-Review.md) | Historical repo audit and code-path inventory; useful, but not a design source of truth |

Use those files when migrating or deleting old paths, not when deciding what the alpha model should be.

---

## 4. External AP Reference Points

These references informed the approved design choices in the guide and are worth checking when changing the world contract or logic philosophy:

- [Archipelago apworld dev FAQ](https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/apworld_dev_faq.md)
  - replay-safe logic, restrictive-start avoidance, monotonic reachability
- [Archipelago generic advanced settings guide](https://github.com/ArchipelagoMW/Archipelago/blob/main/worlds/generic/docs/advanced_settings_en.md)
  - option-surface discipline and accessibility defaults
- [Archipelago BaseClasses item classifications](https://github.com/ArchipelagoMW/Archipelago/blob/main/BaseClasses.py)
  - `progression`, `useful`, `filler`, `trap`
- [StarCraft II world options](https://github.com/ArchipelagoMW/Archipelago/blob/main/worlds/sc2/options.py)
  - tactical-logic difficulty versus optional location-category structure
- [Kingdom Hearts II world options](https://github.com/ArchipelagoMW/Archipelago/blob/main/worlds/kh2/Options.py)
  - separation between world goal logic and combat/fight logic

---

## 5. Key Code Paths

### C++

| Path | Responsibility |
|------|----------------|
| `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp` | Spawn setup, check tagging, save/load rebuild, kill bookkeeping, current fallback content path |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp` | State persistence, bridge JSON import/export, completed checks/locations |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoSlotData.cpp` | Runtime loader for verified `Seed-Slot-Data.json`, selected runtime keys, and seeded cluster spawn data |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Object.cpp` | Kill-order handling and `m_archipelagoCheckId` serialization |
| `GeneralsMD/Code/GameEngine/Source/GameClient/GUI/GUICallbacks/Menus/ScoreScreen.cpp` | Mission-victory location marking |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockRegistry.cpp` | `Archipelago.ini` parsing, group lookup, starting-general settings parsing |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/ProductionUpdate.cpp` | Unit-production lock enforcement |
| `GeneralsMD/Code/GameEngine/Source/Common/System/BuildAssistant.cpp` | Building-placement lock enforcement |
| `GeneralsMD/Code/GameEngine/Source/GameClient/GUI/ControlBar/ControlBarCommand.cpp` | Lock overlays in the command bar |
| `GeneralsMD/Code/GameEngine/Source/GameClient/GUI/GUICallbacks/ControlBarPopupDescription.cpp` | Locked tooltip messaging |

### Python and data tooling

| Path | Responsibility |
|------|----------------|
| `scripts/archipelago_generate_ini.py` | Generate `Data/INI/Archipelago.ini` from the data layer |
| `scripts/archipelago_validate_ini.py` | Validate generated INI templates and denylist rules |
| `scripts/archipelago_audit_groups.py` | Audit remaining spawnable units/buildings after denylist filtering |
| `scripts/archipelago_generate_matchup_graph.py` | Historical matchup output generation; no longer the primary design oracle |
| `scripts/archipelago_logic_prerequisites.py` | Historical numeric logic scaffold still present in repo |
| `scripts/archipelago_bridge_local.py` | Fixture-driven local bridge sidecar |
| `scripts/archipelago_seeded_bridge_loop_smoke.py` | Checkpoint smoke for fixture slot-data -> inbound -> runtime outbound -> AP numeric IDs |
| `tools/bridge/GeneralsAPBridge` | Packaged bridge executable source for release-staging file mode and live AP network mode |
| `scripts/build_generalsap_bridge.ps1` | Builds `GeneralsAPBridge.exe` from the .NET bridge project |
| `scripts/archipelago_bridge_executable_smoke.py` | Verifies packaged bridge executable slot-data materialization, runtime-key translation, unknown-key rejection, and duplicate idempotency |
| `scripts/archipelago_bridge_network_smoke.py` | Verifies packaged bridge AP 0.6.7 websocket seam with fake AP server, received item mapping, `LocationChecks`, and duplicate-safe reconnects |
| `scripts/archipelago_runtime_fallback_contract_check.py` | Checkpoint smoke for no-reference fallback, bad-hash rejection, and seeded/no-demo-mix guardrails |
| `scripts/archipelago_run_checks.py` | Lightweight script/data validation suite |
| `tools/cluster-editor` | Web-app cluster authoring tool submodule |

---

## 6. Active Phases and Lane Ownership

| Phase | Scope |
|-------|-------|
| `P1` | Align static contract docs and machine-readable logic/data sources with the approved alpha model |
| `P2` | Implement `worlds/generalszh`, grouped alpha item tables, stable numeric IDs, and slot-data generation |
| `P3` | Implement bridge translation and game-side seed payload ingestion. Current branch covers local fixture materialization, packaged file-bridge executable validation, packaged AP network bridge fake-server validation, file-byte hash verification, selected seeded cluster spawning, canonical mission/cluster runtime keys, bridge runtime-key translation, and fallback-boundary smoke checks. Hosted AP room smoke is still pending. |
| `P4` | Implement discrete evaluator and tracker query APIs in the runtime |
| `P5` | Build UI, mission select, connect flow, release packaging, and later optional extras |

| Lane | Scope |
|------|-------|
| `L1` | Contract + seed schema |
| `L2` | AP world skeleton |
| `L3` | Bridge sidecar |
| `L4` | Runtime ingestion + evaluator |
| `L5` | UI / tracker / mission select |
| `L6` | Packaging + fixtures + playtest |

Recommended reading by lane:

- `L1`: guide -> slot-data format -> state sync architecture
- `L2`: guide -> mapping draft -> slot-data format -> overlay README
- `L3`: state sync architecture -> slot-data format -> bridge local script
- `L4`: guide -> slot-data format -> `UnlockableCheckSpawner.cpp` -> `ArchipelagoState.cpp`
- `L5`: guide -> todo -> state sync architecture -> fixture docs
- `L5` UI shell work: guide -> todo -> [Docs/Archipelago/Operations/WND-UI-Workbench.md](Docs/Archipelago/Operations/WND-UI-Workbench.md) -> state sync architecture
- `L6`: player release architecture -> state sync architecture -> testing docs

---

## 7. Build and Validation Commands

```bash
cmake --list-presets
cmake -S . -B build/win32-vcpkg-debug -DARCHIPELAGO_REGENERATE_DATA=ON -DGENERALS_ASSET_ROOT="C:/Path/To/Generals Zero Hour" -DRTS_BUILD_ZEROHOUR=ON -DRTS_BUILD_GENERALS=OFF
cmake --build build/win32-vcpkg-debug --target archipelago_config --config Debug
python scripts/archipelago_run_checks.py
python scripts/archipelago_location_catalog_validate.py
python scripts/tests/test_archipelago_data_pipeline.py
python scripts/archipelago_seeded_bridge_loop_smoke.py
python scripts/archipelago_runtime_fallback_contract_check.py
python scripts/archipelago_bridge_network_smoke.py --bridge-exe build/release-tools/GeneralsAPBridge.exe
python scripts/archipelago_bridge_local.py --archipelago-dir build/win32-vcpkg-playtest/GeneralsMD/Release/UserData/Archipelago --once
python scripts/archipelago_vendor_materialize.py
python scripts/archipelago_vendor_capture.py
cd tools/cluster-editor && npm install && npm run dev
```

For the demo-ready playable path:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_demo_run.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\windows_demo_run.ps1 -Fixture mixed_progression -ResetSession
```

---

Use this file as the first document to load when resuming or transferring Archipelago work.
