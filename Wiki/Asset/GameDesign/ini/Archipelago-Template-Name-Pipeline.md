# Archipelago Template Names → In-Game Names

This document maps technical template names (used in `Archipelago.ini`) to human-readable in-game names, and lists resources for looking them up.

---

## How the Game Resolves Names

1. **Template name** (e.g. `AmericaInfantryRanger`) – defined in `FactionUnit.ini` / `FactionBuilding.ini` as `Object` or `ObjectReskin`.
2. **DisplayName** – e.g. `OBJECT:Ranger` or `UPGRADE:FlashBangGrenade`. This is a localization key.
3. **Localization** – the key is looked up in CSF files (e.g. `generals.csf`, `generals.str`) to get the text shown in-game (e.g. "Ranger").
4. **Wrapper-template fallback** – if a buildable template has no direct `DisplayName` (for example `GLAVehicleTechnical`), resolve the player-facing name from its build variations or the build button `TextLabel`.

---

## Online Resources

| Resource | URL | Description |
|----------|-----|-------------|
| **CNCNZ GLA Units** | https://cncnz.com/games/zero-hour/gla-units/ | GLA units with in-game names (Worker, Rebel, RPG Trooper, Terrorist, Saboteur, Angry Mob, Hijacker, Jarmen Kell, Radar Van, Technical, Scorpion Tank, Quad Cannon, Toxin Tractor, Combat Cycle, Marauder Tank, Rocket Buggy, Battle Bus, Bomb Truck, Scud Launcher) |
| **CNCNZ USA Units** | https://cncnz.com/games/zero-hour/usa-units/ | USA unit catalog with in-game names |
| **CNCNZ China Units** | https://cncnz.com/games/zero-hour/kwais-units/ | China unit catalog (e.g. Red Guard, Tank Hunter, Hacker) |
| **C&C Fandom Wiki** | https://cnc.fandom.com/wiki/Category:Zero_Hour_units | Zero Hour units by category |
| **C&C Fandom Buildings** | https://cnc.fandom.com/wiki/Category:Zero_Hour_buildings | Zero Hour buildings |
| **GeneralsWiki** | https://github.com/TheSuperHackers/GeneralsWiki | Technical wiki; asset and INI docs |
| **FreemanZY INI Repo** | https://github.com/FreemanZY/Command_And_Conquer_INI | Extracted Zero Hour INI files |
| **ModDB Tutorial** | https://www.moddb.com/games/cc-generals-zero-hour/tutorials/coding-basics-2 | INI structure and DisplayName |

---

## Mapping: Template → DisplayName Key → In-Game Name (Examples)

Extracted from `Data/INI/Object/FactionUnit.ini`, `FactionBuilding.ini`, `Upgrade.ini`:

| Template | DisplayName Key | Typical In-Game Name |
|----------|-----------------|----------------------|
| AmericaInfantryRanger | OBJECT:Ranger | Ranger |
| AmericaInfantryColonelBurton | OBJECT:ColonelBurton | Colonel Burton |
| AmericaVehicleHumvee | OBJECT:Humvee | Humvee |
| AmericaVehicleTomahawk | OBJECT:Tomahawk | Tomahawk |
| AmericaJetRaptor | OBJECT:Raptor | Raptor |
| AmericaJetB52 | OBJECT:B52 | B-52 |
| AmericaJetAurora | OBJECT:Aurora | Aurora Bomber |
| AmericaJetStealthFighter | OBJECT:StealthFighter | Stealth Fighter |
| AmericaVehicleComanche | OBJECT:Comanche | Comanche |
| AmericaInfantryPathfinder | OBJECT:Pathfinder | Pathfinder |
| GLAInfantryRebel | OBJECT:Rebel | Rebel |
| GLAInfantryJarmenKell | OBJECT:JarmenKell | Jarmen Kell |
| GLAVehicleTechnical | Build-variation/button fallback -> `OBJECT:Technical` | Technical |
| GLAVehicleQuadCannon | OBJECT:QuadCannon | Quad Cannon |
| GLAVehicleRocketBuggy | OBJECT:RocketBuggy | Rocket Buggy |
| GLAVehicleBattleBus | (Battle Bus) | Battle Bus |
| GLAVehicleBombTruck | OBJECT:BombTruck | Bomb Truck |
| GLAVehicleScudLauncher | OBJECT:ScudLauncher | Scud Launcher |
| ChinaInfantryRedguard | OBJECT:Redguard | Red Guard |
| ChinaInfantryTankHunter | OBJECT:TankHunter | Tank Hunter |
| ChinaInfantryHacker | OBJECT:Hacker | Hacker |
| ChinaInfantryBlackLotus | OBJECT:BlackLotus | Black Lotus |
| ChinaTankOverlord | OBJECT:Overlord | Overlord Tank |
| ChinaVehicleHelix | OBJECT:Helix | Helix |
| Upgrade_AmericaRangerFlashBangGrenade | UPGRADE:RangerFlashBangGrenade | Flash Bang Grenades |
| Upgrade_AmericaRadar | UPGRADE:Radar | Radar |
| Upgrade_InfantryCaptureBuilding | UPGRADE:RangerCaptureBuilding | Capture Building |

---

## Extracting the Full Mapping

Run the extraction and template-name scripts:

```bash
python scripts/archipelago_extract_template_display_names.py
python scripts/archipelago_build_display_name_map.py
python scripts/archipelago_build_localized_name_map.py
python scripts/archipelago_build_template_name_map.py
```

This produces `Data/Archipelago/reference/archipelago_template_display_names.json`, `Data/Archipelago/display_names.json`, `Data/Archipelago/ingame_names.json`, and `Data/Archipelago/template_ingame_names.json`. Review-only notes for unresolved templates live in `Data/Archipelago/reference/unresolved_template_name_notes.json` and are mirrored into `template_ingame_names.json::_unresolved_notes`.

To get the final in-game text:

1. **Units/Buildings** – Parse `Data/INI/Object/FactionUnit.ini` and `FactionBuilding.ini` for each `Object` / `ObjectReskin` block; read `DisplayName = OBJECT:X`.
2. **Upgrades** – Parse `Data/INI/Upgrade.ini` for `DisplayName = UPGRADE:X`.
3. **Localization** – Use a CSF editor or the format in `Wiki/Asset/Localization/csf/csf_format.md` to resolve `OBJECT:X`, `UPGRADE:X`, and relevant `CONTROLBAR:X` keys to the actual strings (from `generals.csf` or equivalent in the game data).
4. **Wrapper fallback** – For templates without a direct `DisplayName`, inherit from parent/build variations or the build-button `TextLabel`.

---

## General-Prefixed Variants

Templates like `AirF_AmericaInfantryRanger` and `Slth_GLAVehicleTechnical` are general-specific variants. They usually share the same `DisplayName` as the base template (e.g. `AmericaInfantryRanger` → `OBJECT:Ranger`), so the in-game name is the same: "Ranger", "Technical", etc.

---

## See Also

- [Archipelago.ini format](Archipelago-Ini-Format.md)
- [CSF format](Localization/csf/csf_format.md)
- [Unit quotes](Localization/unit_quotes.txt) – voice file naming (e.g. `vhum` = Humvee)
