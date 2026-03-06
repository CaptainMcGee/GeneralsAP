# Archipelago Feature Code Review

**Date:** January 2025
**Scope:** All implemented Archipelago features in GeneralsAP (C&C Generals: Zero Hour)
**Review Type:** Deep dive, investigative, feature-completeness verification

---

## Executive Summary

The Archipelago integration is **well-implemented** with clear separation between state management, unlock definitions, and production/build hooks. The dynamic config system (Data/Archipelago) with `groups.json`, `presets.json`, `always_unlocked.json`, and `display_names.json` is fully integrated. **One gap**: the `ArchipelagoSettings` block (StartingGeneralUSA/China/GLA) is generated but **not read by the game**—starting generals remain random.

---

## Architecture Overview

| Component | Location | Purpose |
|-----------|----------|---------|
| **ArchipelagoState** | `GeneralsMD/.../ArchipelagoState.cpp` | Persisted unlock state, JSON save/load, always-unlocked rules |
| **UnlockRegistry** | `GeneralsMD/.../UnlockRegistry.cpp` | Loads `Archipelago.ini`, parses AlwaysUnlocked + UnlockGroups, maps templates to groups |
| **ProductionUpdate** | `.../ProductionUpdate.cpp` | Blocks unit creation if template not unlocked (`canQueueCreateUnit`) |
| **BuildAssistant** | `.../BuildAssistant.cpp` | Blocks building placement if template not unlocked |
| **ControlBarCommand** | `.../ControlBarCommand.cpp` | Greys out locked commands, shows ArchipelagoLock overlay |
| **ControlBarPopupDescription** | `.../ControlBarPopupDescription.cpp` | Shows "Locked - Requires Archipelago Item" in tooltips |
| **CommandXlat** | `.../CommandXlat.cpp` | Debug hotkeys (unlock next group/general, status, dump) |
| **InGameChat** | `.../InGameChat.cpp` | Chat commands (`ap_unlock_next_group`, `ap_status`, etc.) |
| **ScoreScreen** | `.../ScoreScreen.cpp` | Marks locations complete on Challenge campaign mission win |
| **ChallengeMenu** | `.../ChallengeMenu.cpp` | Restricts general selection to unlocked generals |

---

## Feature Verification

### 1. Unlock Groups (UnlockRegistry)

- **INI parsing**: UnlockGroup blocks with Units, Buildings, Faction, DisplayName, Importance
- **AlwaysUnlocked block**: Parsed; templates added to `m_alwaysUnlockedUnits` / `m_alwaysUnlockedBuildings`
- **isAlwaysUnlockedTemplate()**: Checked by ArchipelagoState before hardcoded fallbacks
- **Template→group mapping**: `m_templateToGroupIndex`; `getGroupTemplates()` returns all templates in a group
- **Mixed groups**: Units and Buildings in same group; `buildingTemplateNames` tracks which are buildings
- **Init order**: UnlockRegistry init before ArchipelagoState (GameLogic.cpp:384–390)

### 2. Always-Unlocked Logic (ArchipelagoState)

- **Registry first**: `isAlwaysUnlocked()` checks `TheUnlockRegistry->isAlwaysUnlockedTemplate()` before hardcoded lists
- **Hardcoded fallback**: Explicit lists (Dozer, Worker, Chinook, Ranger, etc.) + pattern fallbacks (endsWith "Barracks", "CommandCenter", etc.)
- **Config source**: `Data/Archipelago/always_unlocked.json` → generator → AlwaysUnlocked block in INI

### 3. Unlock Expansion

- **unlockUnit / unlockBuilding**: When template is in a group, iterates group and calls `expandUnlockAcrossFactionGenerals` for each member
- **expandUnlockAcrossFactionGenerals**: Iterates ThingFactory, matches faction + core name, adds all general variants
- **unlockGroup**: Inserts templates directly (no expansion); INI has explicit general-prefixed names
- **Legacy aliases**: `resolveLegacyTemplateName()` maps e.g. GLASaboteur → GLAInfantryHijacker

### 4. Production / Build Hooks

- **ProductionUpdate::canQueueCreateUnit()**: Returns `CANMAKE_ARCHIPELAGO_LOCKED` if `!isTemplateUnlocked(unitType)`
- **BuildAssistant**: Returns `CANMAKE_ARCHIPELAGO_LOCKED` if `!isTemplateUnlocked(whatToBuild)`
- **ControlBarCommand**: `isArchipelagoLocked` = `!isTemplateUnlocked(thingTemplate)`; `isArchipelagoDefaultLockedCommand` for Capture, CombatDrop, Barracks upgrades

### 5. UI Lock Overlay

- **ArchipelagoLock image**: Loaded from MappedImageCollection; fallback created if missing
- **Barracks check**: `producer.endsWithNoCase("Barracks")` covers all general variants (AirF_AmericaBarracks, etc.)

### 6. Chat Commands (RTS_DEBUG)

| Command | Action |
|---------|--------|
| `ap_help` / `ap_commands` | Lists all ap_ commands |
| `ap_unlock_all` | Unlock all groups + generals |
| `ap_unlock_capture` | Unlock Upgrade_InfantryCaptureBuilding |
| `ap_reset` | Wipe progress, reset indices |
| `ap_unlock_next_general` | Unlock next locked general |
| `ap_unlock_next_group` | Calls `debugUnlockNextGroup()` (sequential) |
| `ap_status` | Shows generals/units/buildings counts |
| `ap_save_path` | Shows ArchipelagoState.json path |

### 7. Debug Hotkeys (CommandXlat)

- Unlock All, Reset, Status, Unlock Next General, Unlock Next Group, Dump Templates
- Chat and hotkeys share logic via `debugUnlockNextGroup()`, `debugResetArchipelagoIndices()`

### 8. Location Completion (ScoreScreen)

- On Challenge campaign victory: `markLocationComplete(locationId)` where `locationId = calculateLocationId(generalIndex, missionNumber)`
- `calculateLocationId`: `(playerGeneralIndex * 10) + missionNumber`

### 9. General Selection (ChallengeMenu)

- `mapChallengeIndexToGeneralIndex()` maps template names to ArchipelagoState::GeneralIndex
- Random general option disabled if `!isGeneralUnlocked(generalIndex)`

---

## Gaps and Issues

### 1. ArchipelagoSettings Not Read

**Issue**: The `ArchipelagoSettings` block (StartingGeneralUSA, StartingGeneralChina, StartingGeneralGLA) is generated in Archipelago.ini but **never parsed by the game**. Starting generals are always random (`ensureDefaultStartingGenerals()`).

**Impact**: Preset settings for starting generals are cosmetic only.

**Recommendation**: Add parsing in UnlockRegistry or a dedicated loader; pass to ArchipelagoState for `ensureDefaultStartingGenerals()` to use.

### 2. Init Order Dependency

**Observation**: ArchipelagoState::isAlwaysUnlocked checks TheUnlockRegistry. If UnlockRegistry init fails or is delayed, the registry check is skipped (NULL check). Init order in GameLogic is correct.

### 3. unlockGroup Does Not Expand

**Observation**: `unlockGroup()` inserts templates from the INI directly. The INI from our generator has explicit general-prefixed names (AirF_, Lazr_, etc.), so expansion is unnecessary. Correct.

---

## Dynamic Config Pipeline

| File | Purpose |
|------|---------|
| `Data/Archipelago/groups.json` | Group definitions (units, buildings, by_display_name, include) |
| `Data/Archipelago/presets.json` | Preset group_order + settings |
| `Data/Archipelago/always_unlocked.json` | Templates unlocked from start |
| `Data/Archipelago/display_names.json` | Display name → templates (built by archipelago_build_display_name_map.py) |
| `scripts/archipelago_generate_ini.py` | Generates Data/INI/Archipelago.ini from config |
| `scripts/archipelago_extract_ini_config.py` | Migrates existing INI → groups.json, presets.json |
| `scripts/archipelago_build_display_name_map.py` | Builds display_names.json from Data/Archipelago/reference/archipelago_template_display_names.json |

**Build integration**: CMake runs generator before z_generals build; output copied to exe dir. `ARCHIPELAGO_PRESET` CMake option selects preset.

---

## Scripts and Validation

| Script | Purpose |
|--------|---------|
| `archipelago_validate_ini.py` | Validates all templates exist in game INI or allowlist |
| `archipelago_audit_groups.py` | Cross-references groups with spawnable units/buildings |
| `archipelago_expand_group_templates.py` | Expands base names to general variants (used by generator) |
| `archipelago_extract_template_display_names.py` | Extracts template→DisplayName from INI |
| `archipelago_run_checks.py` | Runs validate + audit |

**CI**: `.github/workflows/validate-archipelago-data.yml` runs validate + audit on every push/PR. **Recommendation**: Add a step to run `archipelago_generate_ini.py` before validation so CI validates the generated output.

---

## Data Files

| File | Purpose |
|------|---------|
| `Data/INI/Archipelago.ini` | Generated; AlwaysUnlocked + ArchipelagoSettings + UnlockGroups |
| `Data/INI/CommandMapDebug/Archipelago.ini` | Debug hotkey bindings |
| `ArchipelagoState.json` | Persisted state (Save directory) |
| `Data/Archipelago/reference/archipelago_template_display_names.json` | Template→DisplayName reference input for display_names.json generation |
| `Data/Archipelago/reference/ArchipelagoThingFactoryTemplates_filtered.txt` | Optional; from in-game DEMO_AP_DUMP_TEMPLATES |

---

## Audit Findings (../Research/Spawnability-Audit.md)

- GLATunnelNetworkNoSpawn: May be non-spawnable; consider removing if not buildable
- Officers, Agent, ParadeRedGuard, SecretPolice: Confirm obtainability in this mod

---

## IMPLEMENTATION_GUIDE.md Alignment

| Todo | Status |
|------|--------|
| Todo 4 (State Management) | Done |
| Todo 7 (Unlock Registry) | Done |
| Todo 8 (Hook Unit Creation) | Done |
| Todo 9 (Objective-Location Mapping) | Done |
| Todo 12 (Offline State) | Done |
| Todo 3 (Python client + IPC) | Not implemented |
| Todo 5–6 (Menu restrictions, General/Level selection) | Partial (ChallengeMenu restricts generals) |
| Todo 10 (Buff system) | Not implemented |
| Todo 11 (Progress Tracker UI) | Not implemented |
| Todo 13 (Full integration testing) | Partial (validate + audit + replay) |

---

## Recommendations

1. **Parse ArchipelagoSettings**: Add UnlockRegistry or ArchipelagoState support for StartingGeneralUSA/China/GLA from INI.
2. **CI**: Run `archipelago_generate_ini.py` before validation so CI validates generated output.
3. **Verify spawnability**: GLATunnelNetworkNoSpawn, Officers, Agent, ParadeRedGuard, SecretPolice.
4. **Workspace cleanup**: Add `build/archipelago/archipelago_expanded.ini` to .gitignore (build artifact from archipelago_expand_group_templates.py).
