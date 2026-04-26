# Archipelago Configuration

This directory is the source of truth for Archipelago generation data. Human-readable script output must resolve names through the game's real localization data instead of guessed code labels.

The live runtime no longer stages loose Archipelago INIs straight from `Data/INI`. Instead, the validated runtime copies live under `Data/Archipelago/runtime_profiles/*`, and the debug/recovery scripts stage exactly one named profile at a time:

- `reference-clean`
  - known-good old `Archipelago.ini` + `UnlockableChecksDemo.ini`
- `demo-playable`
  - validated gameplay/demo profile layered on top of `reference-clean`
- `demo-ai-stress`
  - widened spawned-unit leash/chase profile for AI behavior testing
- `archipelago-bisect`
  - working profile for controlled reintroduction of runtime INI changes
- `archipelago-current`
  - current candidate loose Archipelago runtime files, including command-map overlays

The GitHub-safe repo intentionally does not vendor retail Zero Hour assets. Normal game builds use the committed Archipelago outputs already in the repo. Maintainers only need `GENERALS_ASSET_ROOT` when regenerating naming, validation, or graph data from source scripts.

## Core Rules

- `groups.json` defines unlock groups. Use base template names unless a group intentionally targets a specific variant.
- `display_names.json` stores `DisplayName key -> template list` mappings. It is not a localized string file.
- `ingame_names.json` stores `DisplayName key -> exact localized string` mappings and is generated from `generals.csf` by `scripts/archipelago_build_localized_name_map.py`.
- `name_overrides.json` is for deliberate player-facing aliases and explicit fallback names when a `DisplayName` key is missing from `generals.csf`.
- `template_ingame_names.json` stores `template -> exact player-facing localized string` mappings. It is generated from object `DisplayName`, parent/build-variation inheritance, and build-button `TextLabel` fallback for wrapper templates like `GLAVehicleTechnical`, and carries `_unresolved_notes` for templates that still need review-only naming context.
- `non_spawnable_templates.json` is the denylist. Templates in that file must not survive into generated INI, audits, or matchup graph outputs.
- `Slot-Data-Format.md` is the canonical immutable seed payload contract for mission and cluster locations. Mutable session-state sync is documented separately in `Docs/Archipelago/Operations/Archipelago-State-Sync-Architecture.md`.
- `location_families/catalog.json` is the disabled author-facing catalog for future captured-building and supply-pile-threshold checks. It validates IDs/runtime keys now, but must not feed AP generation until runtime support exists.
- `wnd_working_set.json` defines the generated-only WND extraction set for the Archipelago menu-shell workbench. Raw extracted WNDs stay under `build/archipelago/wnd-work`, not in the repo.
- `UnlockableChecksDemo.ini` is now explicit fallback/recovery content. Seeded runs should use selected checks from verified `Seed-Slot-Data.json`.
- `Data/INI/Archipelago.ini` should be treated as a generated/runtime-candidate artifact, not the authoritative editing surface.

## Key Files

| File | Purpose |
|------|---------|
| `groups.json` | Unlock-group definitions for units, buildings, includes, and `by_display_name` expansion. |
| `presets.json` | Group ordering and settings presets for `archipelago_generate_ini.py`. |
| `always_unlocked.json` | Templates unlocked from the start without Archipelago items. |
| `display_names.json` | `DisplayName` localization keys to template names. Generated from INI data. |
| `ingame_names.json` | Exact localized strings from `generals.csf` for each `DisplayName` key. |
| `template_ingame_names.json` | Exact player-facing names for templates, including wrapper-template fallback via build buttons/build variations, plus `_unresolved_notes` metadata. |
| `name_overrides.json` | Explicit player-facing aliases when intentional. Keep this small. |
| `reference/unresolved_template_name_notes.json` | Curated review notes for templates that still do not resolve to trustworthy player-facing names. |
| `non_spawnable_templates.json` | Templates that are unusable for Archipelago and must be removed from scripts/output. |
| `location_families/catalog.json` | Disabled author catalog for future captured-building and supply-pile-threshold locations. |
| `wnd_working_set.json` | Generated-only WND working set for Archipelago UI extraction, manifesting, and loose-override iteration. |
| `reference/` | Extracted reference inputs such as template->DisplayName dumps and filtered template dumps. |
| `unit_matchup_archetypes.json` | Matchup graph archetypes, defender filters, and tier rules. |
| `generated_unit_matchup_graph.json` | Generated directed graph for logic and review. |
| `generated_unit_matchup_graph_readable.txt` | Human-readable graph output using localized names plus `[TemplateName]` for verification. |

## Editing `groups.json`

Each group can contain:

- `display_name`: player-facing group label used in-game
- `faction`: usually `Shared` for cross-faction groups
- `units`: base template names or exact templates
- `buildings`: base template names or exact templates
- `include`: group IDs to merge into this group
- `by_display_name`: `DisplayName` keys such as `OBJECT:Ranger`

Base faction templates expand to their legal general variants automatically. For example, `AmericaInfantryRanger` expands to the base USA ranger plus `AirF_`, `Lazr_`, and `SupW_` variants. `Upgrade_*` and non-faction templates are kept as-is.

`by_display_name` is resolved through `display_names.json`, then filtered through the denylist. If a template is denylisted, generation now fails instead of quietly leaving unusable entries in the output.

## Presets

`default` and `minimal` are the current alpha-facing presets.

- `default`: canonical grouped alpha ruleset
- `minimal`: shorter grouped alpha ruleset

`chaos` is not part of the current alpha plan and should be treated as future-only content, not an active target.

## Name Pipeline

1. Template name from INI or script input.
2. `template_ingame_names.json` resolves the template to the exact player-facing string.
3. That template map is generated from object `DisplayName`, parent/build-variation inheritance, and build-button `TextLabel` fallback when a template has no direct `DisplayName`.
4. `ingame_names.json` remains the authoritative `DisplayName -> localized text` map generated from `generals.csf`.
5. `name_overrides.json` may optionally replace a player-facing string or supply a curated fallback when CSF is missing the key.

If a matchup graph name cannot be resolved through this pipeline, generation should fail. Do not add camel-case guessing back as a fallback. Unresolved templates must also carry a review note in `reference/unresolved_template_name_notes.json` so future agents know the suspected in-game tie even when the template is non-player-facing.

## Runtime Reality

There are now three separate runtime data concerns:

- local progression state, synchronized through `ArchipelagoState.json` plus `Archipelago\Bridge-Inbound.json` / `Archipelago\Bridge-Outbound.json`
- immutable seed payloads in `Archipelago\Seed-Slot-Data.json`, documented in `Slot-Data-Format.md`
- runtime fallback content in `UnlockableChecksDemo.ini` for demo/recovery only

That split is intentional. Mutable state, immutable seed content, and fallback demo content should not be conflated.

`Seed-Slot-Data.json` now emits empty `capturedBuildings` and `supplyPileThresholds` arrays per map. Runtime parses those sections read-only if present, but production seeds must leave them empty until the game can complete and persist those checks. The AP slot-data builder has a production guard for this: selected future-family checks may be used only by tests/translation fixtures, not by `fill_slot_data`.

## Runtime Profiles

`Data/Archipelago/runtime_profiles/profiles.json` is the runtime contract for debug/recovery staging.

- `reference-clean` is the startup-safe control and should remain the default.
- `demo-playable` and `demo-ai-stress` inherit from `reference-clean` so the safe baseline stays untouched.
- `archipelago-bisect` starts from the same validated pair and is the only profile that should be edited while reintroducing runtime INI changes.
- `archipelago-current` is the checked-in known-bad/current candidate capture for diffing and opt-in testing.
- Playtest controls are code-side. Do not reintroduce `CommandMap.ini`, `CommandMapDebug`, or `CommandMapDemo` overlays into the safe playtest path.

`runtime_profiles/archipelago-bisect/batches.json` defines the intended order for reintroducing `Archipelago.ini` and `UnlockableChecksDemo.ini` changes.

## Demo Fixtures

`Data/Archipelago/bridge_fixtures` contains curated `LocalBridgeSession.json` seeds for the local bridge sidecar:

- `minimal_progression.json`
- `mixed_progression.json`
- `almost_exhausted_pool.json`
- `post_exhaustion_pool.json`

Use them with:

```bash
python scripts/archipelago_bridge_local.py --archipelago-dir build/win32-vcpkg-playtest/GeneralsMD/Release/UserData/Archipelago --fixture mixed_progression --reset-session
```

Or via the demo wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_demo_run.ps1 -Fixture mixed_progression -ResetSession
```

## Generation Commands

```bash
python scripts/archipelago_build_localized_name_map.py
python scripts/archipelago_build_template_name_map.py
python scripts/archipelago_generate_ini.py --preset default
python scripts/archipelago_location_catalog_validate.py
python scripts/archipelago_item_location_capacity_report.py
python scripts/archipelago_generate_matchup_graph.py
python scripts/archipelago_run_checks.py
```

## Build Integration

By default, the runtime generator now emits a legacy-safe `Archipelago.ini` shape for build output. That keeps newer source-of-truth data in JSON/code while avoiding unvalidated runtime-only schema changes in the default build artifact. Maintainers can force regeneration through the `archipelago_config` target by enabling `ARCHIPELAGO_REGENERATE_DATA` and pointing CMake at local game assets:

```bash
cmake -S . -B build/win32-vcpkg-debug -DARCHIPELAGO_REGENERATE_DATA=ON -DGENERALS_ASSET_ROOT="C:/Path/To/Generals Zero Hour"
cmake --build build/win32-vcpkg-debug --target archipelago_config --config Debug
```
