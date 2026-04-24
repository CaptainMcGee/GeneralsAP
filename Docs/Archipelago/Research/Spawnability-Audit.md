# Archipelago UnlockGroups Spawnability Audit

Cross-reference of Archipelago.ini groups against game INI files (CommandSet.ini, CommandButton.ini, FactionUnit.ini, FactionBuilding.ini) to verify which items are actually spawnable/produceable.

---

## Summary

| Category | Count | Notes |
|----------|-------|-------|
| **Verified spawnable** | Most | Have Command_Construct in build menu |
| **Uncertain / needs verification** | 8 | See below |
| **Likely non-spawnable** | 2 | GLATunnelNetworkNoSpawn, possibly USA_FireBase |

---

## Uncertain / Needs Verification

### 1. **Shared_CaptureBuilding** – `Upgrade_InfantryCaptureBuilding`
- **Type:** Upgrade (not unit/building)
- **Spawnable?** Upgrades are purchased, not spawned. The Archipelago unlock system may treat this differently (unlocking the *ability* to capture buildings).
- **Question:** Does Archipelago need upgrades in UnlockGroups, or only units/buildings?

### 2. **Shared_Officer** – `AmericaInfantryOfficer`, `ChinaInfantryOfficer`
- **Construct command:** None found (`Command_ConstructAmericaInfantryOfficer` / `Command_ConstructChinaInfantryOfficer` do not exist)
- **How obtained:** In retail ZH, Officers come from Strategy Center (USA) / Propaganda Center (China) via an upgrade or special mechanism. Could not find the exact trigger in this mod's INI.
- **Question:** Are Officers obtainable in-game through any build menu or upgrade? If only via campaign/scripted spawns, they may not belong in Archipelago.

### 3. **USA_FireBase** – `AmericaFireBase`
- **Construct command:** None in `AmericaDozerCommandSet` (no `Command_ConstructAmericaFireBase`)
- **Object definition:** Not in this mod's `FactionBuilding.ini`; may exist only in retail INIZH.big
- **Wiki:** Retail ZH Fire Base is buildable from Dozer (hotkey I), requires Cold Fusion Reactor
- **Question:** Is Fire Base available in this mod? If it's only in retail big files, the ThingFactory dump would include it, but players might not be able to build it from this mod's CommandSet.

### 4. **USA_Checkpoint** – `AmericaCheckpoint`
- **Construct command:** None in `AmericaDozerCommandSet`
- **Object:** Exists in FactionBuilding.ini, has `KindOf = LINEBUILD CAPTURABLE`
- **Question:** LINEBUILD structures may use a different build flow (draw line, place). Is Checkpoint in any build menu or line-build UI in this mod?

### 5. **China_Moat** – `ChinaMoat`
- **Construct command:** None (`Command_ConstructChinaMoat` does not exist)
- **Object:** Exists, has `KindOf = LINEBUILD`
- **Question:** Same as Checkpoint – is Moat available via line-build or another mechanism?

### 6. **China_Agent**, **China_ParadeRedGuard**, **China_SecretPolice**
- **Construct commands:** None found for Agent, ParadeRedGuard, or SecretPolice
- **ChinaBarracksCommandSet:** Redguard, TankHunter, Hacker, BlackLotus only
- **ChinaPropagandaCenterCommandSet:** Upgrades (Nationalism, SubliminalMessaging, Mines) – no unit builds
- **Question:** In retail ZH, these may come from propaganda conversion (civilians → your side). Are they obtainable in this mod? If only from conversion/special powers, they might be edge cases for Archipelago.

### 7. **Shared_LightVehicle** – `GLAVehicleTechnicalChassisOne/Two/Three`
- **Spawnable?** These are `BuildVariations` of `GLAVehicleTechnical` – when you build a Technical, the game picks one chassis variant. You don't build ChassisOne/Two/Three directly.
- **Note:** Including them is likely fine for fallback (ThingFactory may iterate them), but they're not directly constructable.

### 8. **China_Overlord** – `ChinaTankOverlordBattleBunker`, `ChinaTankOverlordGattlingCannon`, `ChinaTankOverlordPropagandaTower`
- **Spawnable?** These are Overlord *upgrade modules* – you build `ChinaTankOverlord` and add modules. The module variants exist as separate templates for the upgraded states.
- **Note:** May be spawnable via ObjectCreationList or as transformed states of the base Overlord. Likely OK to include.

---

## Likely Non-Spawnable

### 1. **GLA_TunnelNetworkNoSpawn** – `GLATunnelNetworkNoSpawn`
- **Comment in FactionBuilding.ini:** "GLA Tunnel Network copy, without the spawn module"
- **Construct command:** `Command_ConstructGLATunnelNetwork` builds `GLATunnelNetwork`, not `GLATunnelNetworkNoSpawn`
- **Conclusion:** `GLATunnelNetworkNoSpawn` is not in the build menu. It may be for map placement or scripts only. **Consider removing from Archipelago** or confirming it's never used for player construction.

### 2. **USA_FireBase** (see above)
- If Fire Base is not in this mod's Dozer CommandSet, it's not buildable with this mod's INI.

---

## Verified Spawnable (Sample)

These have explicit `Command_Construct*` entries and are in the build menu:

- **Shared:** Barracks, CommandCenter, PowerPlant, Supply, WarFactory, Airfield, Wall, WallHub, Scout, Hero, LightVehicle, MainTank, HeavyTank, Dozer, CargoPlane, Worker
- **USA:** StrategyCenter, ParticleCannon, Patriot, DetentionCamp, Tomahawk, Ambulance, SentryDrone, Comanche, Raptor, StealthFighter, Aurora, A10, B52, Battleship, Chinook, Drones, Ranger, SecretService, Pilot
- **China:** PropagandaCenter, NukeSilo, GatlingCannon, Bunker, SpeakerTower, Inferno, Overlord, TroopCrawler, NukeCannon, MiG, Helix, NapalmStriker, SupplyTruck, Redguard, TankHunter
- **GLA:** ArmsDealer, Palace, ScudStorm, StingerSite, TunnelNetwork, DemoTrap, BlackMarket, BurningBarrier, Trap, Terrorist, Hijacker, AngryMob, QuadCannon, RocketBuggy, ToxinTractor, BombTruck, ScudLauncher, RadarVan

---

## Recommendations

1. **GLATunnelNetworkNoSpawn:** Remove from `GLA_TunnelNetworkNoSpawn` or confirm it's never player-constructable.
2. **USA_FireBase, USA_Checkpoint:** Verify whether these are in the build menu (including line-build). If not, consider removing or documenting as "retail-only / map-placed."
3. **Shared_Officer, China_Agent, China_ParadeRedGuard, China_SecretPolice:** Confirm how these are obtained in this mod. If they're not obtainable in normal play, consider removing from Archipelago.
4. **China_Moat:** Same as Checkpoint – verify line-build availability.
5. **Shared_CaptureBuilding:** Confirm Archipelago handles upgrades correctly; if it only cares about units/buildings, this may be intentional for a different unlock path.
