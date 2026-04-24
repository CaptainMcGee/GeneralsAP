# Archipelago Unlock Grouping Changes – Examples for Review

This document lists the adjustments made to group equivalent units/buildings across factions and associate general-prefixed templates with their vanilla faction.

## Summary

- **Cross-faction groups**: Same unit/building types from USA, China, and GLA now unlock together in Shared groups.
- **General-prefixed variants** (e.g. `Slth_`, `Chem_`, `AirF_`, `Infa_`) are handled at runtime via `expandUnlockAcrossFactionGenerals`; only base template names are listed in the INI.
- **UnlockRegistry** was updated to support groups that contain both Units and Buildings (e.g. GLA_StingerSite).

---

## 1. Cross-Faction Building Groups (Shared)

### Shared_Barracks
**Before:** USA_Barracks, China_Barracks, GLA_Barracks (3 separate groups)
**After:** One group with all three:
- `AmericaBarracks` (+ AirF_, Lazr_, SupW_ variants at runtime)
- `ChinaBarracks` (+ Tank_, Infa_, Nuke_ variants at runtime)
- `GLABarracks` (+ Demo_, Slth_, Chem_, Toxin_ variants at runtime)

### Shared_CommandCenter
**Before:** USA_CommandCenter, China_CommandCenter, GLA_CommandCenter (3 separate groups)
**After:** One group:
- `AmericaCommandCenter`, `ChinaCommandCenter`, `GLACommandCenter`

### Shared_PowerPlant
**Before:** USA_PowerPlant, China_PowerPlant (2 separate groups)
**After:** One group:
- `AmericaPowerPlant`, `ChinaPowerPlant`

### Shared_Supply
**Before:** USA_SupplyCenter, USA_SupplyDropZone, China_SupplyCenter, GLA_SupplyStash (4 separate groups)
**After:** One group:
- `AmericaSupplyCenter`, `AmericaSupplyDropZone`, `ChinaSupplyCenter`, `GLASupplyStash`

### Shared_WarFactory
**Before:** USA_WarFactory, China_WarFactory (2 separate groups)
**After:** One group:
- `AmericaWarFactory`, `ChinaWarFactory`

### Shared_Airfield
**Before:** USA_Airfield, China_Airfield (2 separate groups)
**After:** One group:
- `AmericaAirfield`, `ChinaAirfield`

### Shared_Wall
**Before:** USA_Wall, China_Wall, GLA_Wall (3 separate groups)
**After:** One group:
- `AmericaWall`, `ChinaWall`, `GLAWall`

### Shared_WallHub
**Before:** USA_WallHub, China_WallHub, GLA_WallHub (3 separate groups)
**After:** One group:
- `AmericaWallHub`, `ChinaWallHub`, `GLAWallHub`

---

## 2. Cross-Faction Unit Groups (Shared)

### Shared_Scout
**Before:** USA_Pathfinder, China_Hacker, GLA_Rebel (3 separate groups)
**After:** One group:
- `AmericaInfantryPathfinder`, `ChinaInfantryHacker`, `GLAInfantryRebel`

### Shared_Hero
**Before:** USA_ColonelBurton, China_BlackLotus, GLA_JarmenKell (3 separate groups)
**After:** One group:
- `AmericaInfantryColonelBurton`, `ChinaInfantryBlackLotus`, `GLAInfantryJarmenKell`

### Shared_LightVehicle
**Before:** USA_Humvee, GLA_Technical (2 separate groups)
**After:** One group:
- `AmericaVehicleHumvee`, `GLAVehicleTechnical`, `GLAVehicleTechnicalChassisOne`, `GLAVehicleTechnicalChassisTwo`, `GLAVehicleTechnicalChassisThree`

### Shared_MainTank
**Before:** USA_Crusader, China_Battlemaster, China_GatlingTank, GLA_Scorpion (4 separate groups)
**After:** One group:
- `AmericaTankCrusader`, `ChinaTankBattleMaster`, `ChinaTankGattling`, `GLATankScorpion`, `GLALightTank`

### Shared_HeavyTank
**Before:** USA_Paladin, China_DragonTank, GLA_Marauder (3 separate groups)
**After:** One group:
- `AmericaTankPaladin`, `ChinaTankDragon`, `GLATankMarauder`

### Shared_Dozer
**Before:** USA_Dozer, China_Dozer, GLA_Dozer (3 separate groups)
**After:** One group:
- `AmericaVehicleDozer`, `ChinaVehicleDozer`, `GLAVehicleDozer`

### Shared_CargoPlane
**Before:** USA_CargoPlane, China_CargoPlane, GLA_CargoPlane (3 separate groups)
**After:** One group:
- `AmericaJetCargoPlane`, `ChinaJetCargoPlane`, `GLAJetCargoPlane`

### Shared_Officer
**Before:** USA_Officer, China_Officer (2 separate groups)
**After:** One group:
- `AmericaInfantryOfficer`, `ChinaInfantryOfficer`

### Shared_Worker
**Before:** GLA_Worker (1 group)
**After:** Same group, kept as Shared for consistency:
- `GLAInfantryWorker`

---

## 3. General-Prefixed Templates (Vanilla Association)

These templates use general-specific prefixes in the code but are treated as vanilla faction unlocks. Only base names are in the INI; the runtime expands them.

| Base Template       | General Variants (auto-expanded at runtime) | Group          |
|---------------------|---------------------------------------------|----------------|
| `GLABarracks`       | Chem_, Demo_, Slth_, Toxin_GLABarracks      | Shared_Barracks |
| `GLAScudStorm`      | Chem_, Demo_, Slth_GLAScudStorm              | GLA_ScudStorm  |
| `AmericaParticleCannonUplink` | AirF_, Lazr_, SupW_AmericaParticleCannonUplink | USA_ParticleCannon |
| `ChinaNuclearMissileLauncher` | Infa_, Nuke_, Tank_ChinaNuclearMissileLauncher | China_NukeSilo |
| `AmericaBarracks`   | AirF_, Lazr_, SupW_AmericaBarracks          | Shared_Barracks |
| `ChinaBarracks`     | Infa_, Nuke_, Tank_ChinaBarracks            | Shared_Barracks |
| `GLACommandCenter`  | Chem_, Demo_, Slth_, Toxin_GLACommandCenter  | Shared_CommandCenter |
| `AmericaVehicleDozer` | AirF_, Lazr_, SupW_AmericaVehicleDozer   | Shared_Dozer   |
| `GLAVehicleDozer`   | Chem_, Demo_, Slth_, Toxin_GLAVehicleDozer  | Shared_Dozer   |
| `ChinaVehicleDozer` | Infa_, Nuke_, Tank_ChinaVehicleDozer        | Shared_Dozer   |
| `GLAInfantryWorker` | Chem_, Demo_, Slth_, Toxin_GLAInfantryWorker | Shared_Worker  |
| `GLATankScorpion`   | Chem_, Demo_, Slth_, Toxin_GLATankScorpion   | Shared_MainTank |
| `AmericaTankCrusader` | AirF_, Lazr_, SupW_AmericaTankCrusader    | Shared_MainTank |
| `ChinaTankGattling` | Infa_, Nuke_, Tank_ChinaTankGattling         | Shared_MainTank |
| `GLAVehicleTechnical` | Chem_, Demo_, Slth_, Toxin_GLAVehicleTechnical* | Shared_LightVehicle |
| `AmericaInfantryPathfinder` | AirF_, Lazr_, SupW_AmericaInfantryPathfinder | Shared_Scout |
| `GLAInfantryRebel`  | Chem_, Demo_, Slth_, Toxin_GLAInfantryRebel  | Shared_Scout  |

---

## 4. Mixed Units + Buildings Groups

### GLA_StingerSite
**Before:** Buildings only (GLAStingerSite); GLAInfantryStingerSoldier was effectively unassigned.
**After:** Both unit and building in one group:
- **Units:** `GLAInfantryStingerSoldier`
- **Buildings:** `GLAStingerSite`

### GLA_TunnelNetwork
**Before:** Buildings only (GLATunnelNetwork); GLAInfantryTunnelDefender was in a separate group.
**After:** Both in one group:
- **Units:** `GLAInfantryTunnelDefender`
- **Buildings:** `GLATunnelNetwork`

---

## 5. Faction-Specific Groups (Unchanged Concept)

These remain faction-specific because they have no direct cross-faction equivalent:

- **USA:** Strategy Center, Particle Cannon, Patriot, Fire Base, Checkpoint, Detention Camp, Tomahawk, Ambulance, Sentry Drone, Comanche, Raptor, Stealth Fighter, Aurora, A-10, B-52, Battleship, Chinook, Guardian/Repair/Scout/Spy Drone, Ranger, Secret Service, Pilot
- **China:** Propaganda Center, Nuke Silo, Gatling Cannon (building), Bunker, Speaker Tower, Moat, Inferno, Overlord, Troop Crawler, Nuke Cannon, MiG, Helix, Napalm Striker, Supply Truck, Agent, Parade Red Guard, Red Guard, Secret Police, Tank Hunter
- **GLA:** Arms Dealer, Palace, Scud Storm, Stinger Site, Tunnel Network, Demo Trap, Black Market, Burning Barrier, Trap, TunnelNetworkNoSpawn, Terrorist, Hijacker, Angry Mob, Quad Cannon, Rocket Buggy, Toxin Tractor, Bomb Truck, Scud Launcher, Radar Van

---

## 6. Code Changes

### UnlockRegistry.cpp
- Parser now supports both `Units` and `Buildings` in the same group (append instead of overwrite).
- `UnlockGroup::buildingTemplateNames` added to distinguish unit vs building templates in mixed groups.
- `addGroup()` uses `buildingTemplateNames` when present to classify each template correctly.

### UnlockRegistry.h
- `struct UnlockGroup` extended with `std::set<AsciiString> buildingTemplateNames`.

---

## 7. Group Count Summary

| Category        | Before | After |
|----------------|--------|-------|
| Shared groups   | 1      | 19    |
| USA-specific    | 35     | 24    |
| China-specific  | 24     | 17    |
| GLA-specific   | 25     | 18    |
| **Total groups**| **~85** | **~78** |
