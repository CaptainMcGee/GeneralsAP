# Archipelago Implementation - Context Index

**Purpose**: First-stop handoff document for the Generals Archipelago project.

**Last updated**: March 6, 2026

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
   - [SuperHackers-Upstream-Sync.md](Docs/Archipelago/Operations/SuperHackers-Upstream-Sync.md)
   - [Archipelago-Vendor-Sync.md](Docs/Archipelago/Operations/Archipelago-Vendor-Sync.md)
   - [TESTING.md](TESTING.md)
5. Build generated Archipelago config with:
   - `cmake --build build/win32-vcpkg-debug --target archipelago_config --config Debug`
6. Run script validation with:
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

### Data / Naming / Validation

| Document | Purpose |
|----------|---------|
| [Data/Archipelago/README.md](Data/Archipelago/README.md) | Current data conventions, denylist rules, naming pipeline, runtime fallback |
| [Data/Archipelago/Slot-Data-Format.md](Data/Archipelago/Slot-Data-Format.md) | Planned slot-data contract for future AP integration |
| [Wiki/Asset/GameDesign/ini/Archipelago-Template-Name-Pipeline.md](Wiki/Asset/GameDesign/ini/Archipelago-Template-Name-Pipeline.md) | Template -> DisplayName -> localized-name lookup reference |
| `Data/Archipelago/reference/unresolved_template_name_notes.json` | Curated suspected ties for unresolved non-player-facing templates |
| [Spawnability-Audit.md](Docs/Archipelago/Research/Spawnability-Audit.md) | Historical spawnability review notes for template cleanup |
| [TESTING.md](TESTING.md) | Current build/test commands and manual verification targets |
| [Archipelago-Vendor-Sync.md](Docs/Archipelago/Operations/Archipelago-Vendor-Sync.md) | Managed Archipelago release-vendor workflow, overlay, patch, and capture policy |

### Engine / Gameplay Notes

| Document | Purpose |
|----------|---------|
| [Docs/Archipelago/Spawned-Unit-AI.md](Docs/Archipelago/Spawned-Unit-AI.md) | Current spawned-unit AI status and remaining tuning work |
| [Docs/Archipelago/Manual-Review-And-Debug-Guide.md](Docs/Archipelago/Manual-Review-And-Debug-Guide.md) | Manual validation guide and debug search hints |
| [Archipelago-Code-Review.md](Docs/Archipelago/Planning/Archipelago-Code-Review.md) | Prior findings and code review notes |
| [SuperHackers-Upstream-Sync.md](Docs/Archipelago/Operations/SuperHackers-Upstream-Sync.md) | Fork remote model and merge-based upstream sync workflow |

---

## 3. Key Code Paths

### C++

| Path | Responsibility |
|------|----------------|
| `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp` | Map load, spawn/tag setup, save-load rebuild, leash state, kill bonus/all-unlocked bonus bookkeeping |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp` | Check completion, group unlock flow, notifications, unlock state persistence |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Object.cpp` | `scoreTheKill` ordering and `m_archipelagoCheckId` save/load serialization |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/AIUpdate.cpp` | Spawned-unit retarget restrictions outside defend radius |
| `GeneralsMD/Code/GameEngine/Source/Common/RTS/Team.cpp` | Spawned-unit exclusion from mission/team command control |
| `GeneralsMD/Code/GameEngine/Source/GameClient/GUI/GUICallbacks/Menus/ScoreScreen.cpp` | Challenge mission completion location marking by enemy mission/general |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockRegistry.cpp` | Archipelago.ini loading, location IDs, group lookup, settings parsing |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/System/GameLogic.cpp` | Archipelago-related challenge superweapon limit |
| `GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/ProductionUpdate.cpp` | Unit-production lock enforcement |
| `GeneralsMD/Code/GameEngine/Source/Common/System/BuildAssistant.cpp` | Building-placement lock enforcement |
| `GeneralsMD/Code/GameEngine/Source/GameClient/GUI/ControlBar/ControlBarCommand.cpp` | Lock overlays in the command bar |
| `GeneralsMD/Code/GameEngine/Source/GameClient/GUI/GUICallbacks/ControlBarPopupDescription.cpp` | Locked tooltip messaging |
| `GeneralsMD/Code/Main/CMakeLists.txt` | Build-time generation of localized name maps and Archipelago.ini |

### Python

| Path | Responsibility |
|------|----------------|
| `scripts/archipelago_build_localized_name_map.py` | Generate `ingame_names.json` from `display_names.json` + `generals.csf` |
| `scripts/archipelago_build_template_name_map.py` | Generate `template_ingame_names.json` from object `DisplayName`, build variations, and build-button localization |
| `scripts/archipelago_generate_ini.py` | Generate `Data/INI/Archipelago.ini` with denylist enforcement |
| `scripts/archipelago_validate_ini.py` | Validate generated INI templates and reject denylisted entries |
| `scripts/archipelago_audit_groups.py` | Audit remaining spawnable units/buildings after applying the denylist |
| `scripts/archipelago_generate_matchup_graph.py` | Generate localized matchup graph outputs with denylist enforcement |
| `scripts/archipelago_logic_prerequisites.py` | Logic prerequisites; `compute_player_strength()` is still a stub |
| `scripts/archipelago_cluster_editor.py` | Cluster point editing/export tool |
| `scripts/archipelago_cluster_selection.py` | Cluster selection logic |
| `scripts/archipelago_run_checks.py` | Lightweight Archipelago generation + validation suite |
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
- `non_spawnable_templates.json` is authoritative. Denylisted templates must not appear in generated INI, matchup outputs, or audits.
- `reference/unresolved_template_name_notes.json` is authoritative for unresolved template review metadata; `template_ingame_names.json` mirrors it in `_unresolved_notes`, and generation should fail if any unresolved template lacks a note.
- `UnlockableChecksDemo.ini` is still the active in-game fallback source; `Slot-Data-Format.md` is the target contract for future AP-world integration.
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
| Agent A | Data/scripts/AP-world prep | Remove stale data assumptions, finish real cluster data, implement `compute_player_strength()` |
| Agent B | C++ game logic | Save/load correctness, slot-data ingestion, compositions, items, traps |
| Agent C | UI | Phase E only after A/B contracts stabilize |

---

## 6. Open Phases (Summary)

- `P0` stability
  - Save/load persistence for spawned/tagged checks
  - Mission-completion location semantics
  - Building-check completion bookkeeping
- `P1` data hygiene
  - Remove non-spawnable templates from all script paths
  - Keep naming CSF-backed and verified
  - Normalize Git/upstream workflow
- `P2` backend
  - Real slot-data ingestion
  - Real cluster data for challenge maps
  - Meaningful presets
  - `compute_player_strength()` implementation
- `P3` feature work
  - Phase E UI
  - Phase F items/traps
  - C7 compositions

---

## 7. Build & Test Commands

```bash
cmake --list-presets
cmake --build build/win32-vcpkg-debug --target archipelago_config --config Debug
python scripts/archipelago_run_checks.py
python scripts/archipelago_generate_matchup_graph.py
python scripts/archipelago_vendor_materialize.py
python scripts/archipelago_vendor_capture.py
```

---

Use this file as the first document to load when resuming or transferring Archipelago work.
