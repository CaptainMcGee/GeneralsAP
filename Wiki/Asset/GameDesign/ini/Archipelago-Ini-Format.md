# Archipelago.ini Format

`Data/INI/Archipelago.ini` configures unlock groups for the Archipelago randomizer integration. Each group defines which units, buildings, or upgrades unlock together when the player receives an item.

## File Location

```
Data/INI/Archipelago.ini
```

## Structure

### AlwaysUnlocked Block (Optional)

```ini
AlwaysUnlocked
    Units = AmericaDozer AmericaInfantryRanger ...
    Buildings = AmericaCommandCenter AmericaBarracks ...
End
```

- **Units**: Space-separated template names unlocked from the start (no Archipelago item required).
- **Buildings**: Same for buildings.

Templates in this block are available immediately. Generated from `Data/Archipelago/always_unlocked.json`. If absent, the game falls back to hardcoded defaults (Dozers, Workers, Command Centers, Barracks, etc.).

### ArchipelagoSettings Block (Optional)

```ini
ArchipelagoSettings
    StartingGeneralUSA = RANDOM
    StartingGeneralChina = RANDOM
    StartingGeneralGLA = RANDOM
End
```

- **StartingGeneralUSA / China / GLA**: `RANDOM` or a general index (0–8). If `RANDOM`, one general per faction is chosen at init.

### UnlockGroup Blocks

```ini
UnlockGroup GroupName
    Faction = Shared
    DisplayName = "Human-Readable Name"
    Units = Template1 Template2 Template3
    Buildings = Building1 Building2
    Importance = 0
End
```

| Key | Required | Description |
|-----|----------|-------------|
| **Faction** | No | `USA`, `China`, `GLA`, or `Shared` for cross-faction groups |
| **DisplayName** | No | Shown when the group is unlocked (e.g. in chat) |
| **Units** | No* | Space- or comma-separated template names (units, upgrades) |
| **Buildings** | No* | Space- or comma-separated template names |
| **Importance** | No | Sort order: 0 = buildings first, 1 = units, 2 = misc last |

\* At least one of `Units` or `Buildings` must be present.

### Template Names

- Use exact names from `FactionUnit.ini`, `FactionBuilding.ini`, or `Upgrade.ini`.
- General-prefixed variants (e.g. `AirF_AmericaInfantryRanger`, `Slth_GLAScudStorm`) are supported.
- Upgrades use `Upgrade_` prefix (e.g. `Upgrade_AmericaRadar`).
- Commands use `Command_` prefix (e.g. `Command_CombatDrop`).

### General Prefixes

| Faction | Prefixes |
|---------|----------|
| USA | `AirF_`, `Lazr_`, `SupW_` |
| China | `Tank_`, `Infa_`, `Nuke_` |
| GLA | `Demo_`, `Slth_`, `Toxin_`, `Chem_` |

## Mixed Groups

A group can have both `Units` and `Buildings`:

```ini
UnlockGroup Shared_StrategyBuildings
    Faction = Shared
    DisplayName = "Strategy Buildings"
    Buildings = AmericaStrategyCenter ChinaPropagandaCenter GLAPalace ...
    Units = Upgrade_AmericaAdvancedTraining Upgrade_ChinaSubliminalMessaging ...
End
```

## Validation

Run the validation script to ensure all templates exist:

```bash
python scripts/archipelago_validate_ini.py
```

Run the audit to compare groups against spawnable units/buildings:

```bash
python scripts/archipelago_audit_groups.py
```

Output: `build/archipelago/archipelago_audit_report.md`, `build/archipelago/archipelago_leftovers.txt`.

## See Also

- `Docs/Archipelago/Planning/Archipelago-Code-Review.md` – Implementation overview
- `Docs/Archipelago/Research/Spawnability-Audit.md` – Spawnability notes
