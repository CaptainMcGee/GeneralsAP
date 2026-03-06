# Archipelago Configuration

This directory is the source of truth for Archipelago generation data. `Data/INI/Archipelago.ini` is generated from the files here, and human-readable script output must resolve names through the game’s real localization data instead of guessed code labels.

## Core Rules

- `groups.json` defines unlock groups. Use base template names unless a group intentionally targets a specific variant.
- `display_names.json` stores `DisplayName key -> template list` mappings. It is not a localized string file.
- `ingame_names.json` stores `DisplayName key -> exact localized string` mappings and is generated from `Data/English/generals.csf` by `scripts/archipelago_build_localized_name_map.py`.
- `name_overrides.json` is for deliberate player-facing aliases and explicit fallback names when a `DisplayName` key is missing from `generals.csf`.
- `template_ingame_names.json` stores `template -> exact player-facing localized string` mappings. It is generated from object `DisplayName`, parent/build-variation inheritance, and build-button `TextLabel` fallback for wrapper templates like `GLAVehicleTechnical`, and carries `_unresolved_notes` for templates that still need review-only naming context.
- `non_spawnable_templates.json` is the denylist. Templates in that file must not survive into generated INI, audits, or matchup graph outputs.
- `Slot-Data-Format.md` is the target contract for future Archipelago world integration. The current runtime fallback is still `Data/INI/UnlockableChecksDemo.ini`.

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

`default`, `minimal`, and `chaos` currently exist, but they are still close to placeholder presets and are not materially different enough yet. Treat them as ordering/config scaffolds until the backend phases add real slot-data and cluster integration.

## Name Pipeline

1. Template name from INI or script input.
2. `template_ingame_names.json` resolves the template to the exact player-facing string.
3. That template map is generated from object `DisplayName`, parent/build-variation inheritance, and build-button `TextLabel` fallback when a template has no direct `DisplayName`.
4. `ingame_names.json` remains the authoritative `DisplayName -> localized text` map generated from `generals.csf`.
5. `name_overrides.json` may optionally replace a player-facing string or supply a curated fallback when CSF is missing the key.

If a matchup graph name cannot be resolved through this pipeline, generation should fail. Do not add camel-case guessing back as a fallback. Unresolved templates must also carry a review note in `reference/unresolved_template_name_notes.json` so future agents know the suspected in-game tie even when the template is non-player-facing.

## Generation Commands

```bash
python scripts/archipelago_build_localized_name_map.py
python scripts/archipelago_build_template_name_map.py
python scripts/archipelago_generate_ini.py --preset default
python scripts/archipelago_generate_matchup_graph.py
python scripts/archipelago_run_checks.py
```

## Build Integration

CMake now regenerates `Data/Archipelago/ingame_names.json` and the build-directory `Archipelago.ini` through the `archipelago_config` target:

```bash
cmake --build build/win32-vcpkg-debug --target archipelago_config --config Debug
```

## Current Runtime Reality

- `UnlockableChecksDemo.ini` is still the active in-game fallback source for check spawning.
- `Slot-Data-Format.md` documents the intended future data exchange with the Archipelago world/client.
- The localized name map and matchup outputs are generation artifacts and should be refreshed after upstream merges or naming/data changes.
- Transient audit and expansion outputs belong under `build/archipelago` rather than the repo root.
