# Archipelago Logic Mapping Draft

**Purpose**: Approved alpha mapping sheet for cluster classes, unit templates, unlock groups, and AP item classifications.

**Status note**: The file name still says `Draft`, but the alpha decisions in this file are now locked unless a later design change explicitly reopens them.

---

## 1. Short Verdict

### 1.1 Locked alpha conclusions

- Cluster logic uses explicit unit-type coverage, not numeric power.
- Easy clusters require one explicit weakness shared consistently across the cluster's core units, with no `Hold` gate.
- Medium clusters may require one or two explicit weaknesses. The number is flexible so world generation can produce varied but still readable logic.
- Hard clusters require `Win` and two explicit weaknesses covered by the player.
- Each cluster unit stays its own AP location.
- Each cluster shares one cluster-level access rule.
- `Yellow` is tracker-only and never grants AP access.
- Medium clusters require `Hold`.
- Hard clusters require `Win`.
- Alpha is grouped-only.
- The exact per-general `Hold` / `Win` table is intentionally deferred to a later mission-design pass.

### 1.1.1 April 24, 2026 design decision record

The following decisions supersede any older cluster-tier language that implied a fixed one-class truth table for every cluster:

| Question | Recorded answer |
|----------|-----------------|
| What can Easy require? | One explicit weakness consistent across all core cluster units. Easy clusters do not require `Hold`. |
| Can Medium require one or two weaknesses? | Yes. Medium clusters can require one or two explicit weaknesses. Flexibility is intentional to make world generation less brittle. |
| What gates Hard? | Hard clusters require the mission `Win` / `Defeat` gate plus two explicit weaknesses covered by the player. |
| How many capability tags? | Use a middle-sized tag list, roughly 6-8 tags. Do not collapse to only five broad tags, but avoid a large matchup taxonomy. |
| Is economy a weakness tag? | No. Economy should be separate from combat weakness tags. Economy requirements belong primarily to cluster difficulty floors and mission `Hold` / `Win` logic. |
| What unlock counts for a weakness? | The player needs both the unit item and the relevant production-facility item/state needed to build that unit. Individual units/items satisfy weaknesses; the player does not unlock an entire weakness category at once. |
| Can weak/support unlocks combine into a formal weakness? | Tentatively no. Multiple weak/support unlocks should not combine into one formal green weakness unless a later design pass explicitly adds such a combo rule. |
| Can upgrades or buffs turn yellow into green? | No for cluster requirements. Upgrades and buffs do not upgrade a yellow route into a green cluster weakness answer. |
| Can non-unit items satisfy requirements? | Yes, but mostly for mission-specific cases. General powers or special items can be required by `Hold` / `Win` rows, such as GLA Ambush for a GLA route against Superweapons General. |
| Are buffs or micro formal logic? | For alpha, micro-heavy and non-perfect routes are yellow / notes only. Buffs may be required for harder clusters, but buffs and economy should not be an `OR` replacement for required cluster weaknesses. |
| How should `Hold` / `Win` relate to cluster tags? | Economy and buffs should primarily drive `Hold` / `Win`, but combat tags still matter. `Hold` requirements do not need to match Medium-cluster requirements. Medium clusters require `Hold`; `Hold` does not require Medium-cluster coverage. `Hold` should align with Easy-cluster expectations enough to avoid generation quirks. |
| What proves mission completion? | Use a hybrid mission-specific `Win` table. Author exact rows manually after the final tag list and formal logic are locked. |
| When is detection required? | Per mission plus explicit cluster stealth tags. |
| Should micro-heavy routes be supported? | Overall logic should lean lenient. World difficulty should eventually be a YAML option, with the framework open to stricter difficulty without artificial requirements. |
| How are explicit weaknesses authored? | Start mechanically derived from selected spawnable cluster units, then allow author edits. The author-edited requirements are the source of truth for AP logic after validation. |
| What tool support is required? | Expand the cluster web app into a visual logic-authoring tool for associating player units/items with weaknesses and spawnable enemy units/clusters with required weaknesses. It should use pictures/icons and make grouping, editing, validation, and review easy. |

Open design items:

- Finalize the 6-8 combat capability tags.
- Resolve the exact `Hold` definition: survival-only, access-to-checks, or access-and-clear assumptions.

### 1.1.2 Capability satisfaction semantics

Cluster requirements are satisfied by concrete owned capability sources, not by owning a weakness category directly.

- A unit can satisfy one or more weaknesses, though most units should satisfy only one primary weakness.
- The player must have the unit item and the production facility required to build that unit.
- Unit/item granularity may vary by YAML option:
  - shared faction item, such as `Shared_RocketInfantry`
  - faction-specific item
  - general-specific item
- Logic must evaluate the actual selected player setup. A Toxin General route should not borrow unrelated USA or China unlocks unless the player's chosen/general-enabled route can actually use them.
- Upgrades, economy, and buffs do not replace missing cluster weaknesses.
- General powers and other non-traditional items can be mission-specific `Hold` / `Win` requirements when the route truly depends on them.

### 1.1.3 Explicit weakness authoring process

The intended workflow is:

1. mechanically derive initial weaknesses from selected spawnable cluster units
2. show the derivation visually to the author
3. allow manual grouping and edits
4. validate that the edited explicit requirements are satisfiable by real player items plus production facilities
5. treat the author-edited requirements as the AP source of truth

This should be supported by a dedicated web app workflow, preferably by expanding `tools/cluster-editor`, with icon/picture-driven views for:

- player units/items and the weaknesses they satisfy
- production-facility prerequisites
- spawnable enemy units and their default derived weaknesses
- selected clusters and their explicit edited requirements
- mission-specific special requirements and notes
- validation warnings for unsatisfied, contradictory, or overly broad requirements

### 1.2 Primary progression logic groups

- `Shared_MachineGunVehicles`
- `Shared_RocketInfantry`
- `Shared_Tanks`
- `Shared_Artillery`
- `Upgrade_Radar`
- `Progressive Starting Money`
- `Progressive Production`

### 1.3 Support-only groups

- `Shared_InfantryVehicles`
- `Shared_MiscVehicles`
- `Shared_MiscInfantry`
- `Shared_BaseDefenses`
- `Shared_WarFactoriesArmsDealers`
- `Shared_AirFields`
- `Shared_ComanchesHelixes`
- `Shared_PlaneTypeAircraft`
- `Shared_Drones`

### 1.4 Baseline starter groups

- `Shared_RifleInfantry`

---

## 2. Cluster Truth Table

| Cluster class | Typical core units | Green if player has | Yellow if player only has | Final AP access |
|---------------|--------------------|---------------------|---------------------------|-----------------|
| `Infantry Swarm` | Rangers, Tank Hunters, Angry Mob, MiniGunners | `Anti-Infantry` | `Frontline Units` | green only |
| `Vehicle Pack` | Technicals, Humvees, Gatts, Quads, Dragon Tanks | `Anti-Vehicle` | `Frontline Units` | green only |
| `Armor` | Crusaders, Paladins, BattleMasters, Overlords, Marauders, Battle Bus | `Anti-Vehicle` | `Siege Units` | green only |
| `Fort` | Patriots, Bunkers, Fire Bases, Tunnels, Stingers | `Siege Units` | `Frontline Units` | green only |
| `Artillery` | Tomahawks, Infernos, Nuke Launchers, Buggies, SCUDs | `Frontline Units` | `Siege Units` | green only |

### 2.1 Alpha notes

- `Stealth / Marksman` is cut from alpha progression clusters.
- `Anti-Air` and `Detectors` stay mission-only in alpha.
- `Vehicle Pack` and `Armor` both use `Anti-Vehicle`, but keeping separate authoring labels still helps cluster readability.

---

## 3. Per-Template Cluster Classification

This section classifies current likely cluster-capable templates into core, support-only, or excluded buckets.

### 3.1 `Infantry Swarm` core

- `AmericaInfantryRanger`
- `AmericaInfantryMissileDefender`
- `ChinaInfantryRedguard`
- `ChinaInfantryTankHunter`
- `ChinaInfantryMiniGunner`
- `GLAInfantryRebel`
- `GLAInfantryStingerSoldier`
- `GLAInfantryTunnelDefender`
- `GLAInfantryAngryMobNexus`
- `GLAInfantryAngryMobMolotov02`
- `GLAInfantryAngryMobPistol01`
- `GLAInfantryAngryMobPistol03`
- `GLAInfantryAngryMobPistol05`
- `GLAInfantryAngryMobRock02`
- `GLAInfantryAngryMobRock04`

### 3.2 `Vehicle Pack` core

- `AmericaVehicleHumvee`
- `ChinaVehicleListeningOutpost`
- `ChinaVehicleTroopCrawler`
- `ChinaTankGattling`
- `ChinaTankDragon`
- `GLAVehicleCombatBike`
- `GLAVehicleTechnical`
- `GLAVehicleQuadCannon`
- `GLAVehicleBombTruck`
- `GLAVehicleToxinTruck`

### 3.3 `Armor` core

- `AmericaTankCrusader`
- `AmericaTankPaladin`
- `ChinaTankBattleMaster`
- `ChinaTankOverlord`
- `ChinaTankOverlordBattleBunker`
- `ChinaTankOverlordGattlingCannon`
- `ChinaTankOverlordPropagandaTower`
- `GLALightTank`
- `GLATankMarauder`
- `GLATankScorpion`
- `GLAVehicleBattleBus`

`GLAVehicleBattleBus` stays in `Armor` for alpha logic.

Reason:

- it is not a rifles-only check
- rockets and tanks are the cleanest answer
- it behaves much closer to armor-breaking logic than to a light-vehicle cleanup check

### 3.4 `Fort` core

- `AmericaFireBase`
- `AmericaPatriotBattery`
- `ChinaBunker`
- `ChinaGattlingCannon`
- `GLAStingerSite`
- `GLATunnelNetwork`

### 3.5 `Artillery` core

- `AmericaVehicleTomahawk`
- `ChinaVehicleInfernoCannon`
- `ChinaVehicleNukeLauncher`
- `GLAVehicleRocketBuggy`
- `GLAVehicleScudLauncher`

### 3.6 Support-only templates

These may appear inside a cluster, but they do not define the cluster's logic color.

- `AmericaVehicleMedic`
- `AmericaTankAvenger`
- `AmericaTankAvengerLaserTurret`
- `AmericaTankMicrowave`
- `ChinaTankECM`

### 3.7 Excluded from alpha progression clusters

- `AmericaVehicleChinook`
- `AmericaVehicleDozer`
- `ChinaVehicleDozer`
- `ChinaVehicleSupplyTruck`
- `GLAVehicleDozer`
- `ChinaInfantryHacker`
- `GLAInfantryHijacker`
- `GLAInfantrySaboteur`
- `GLAInfantryTerrorist`
- `GLAInfantryWorker`
- `AmericaWall`
- `AmericaWallHub`
- `ChinaPropagandaCenter`
- `ChinaWall`
- `ChinaWallHub`
- `GLABurningBarrier`
- `GLADemoTrap`
- `GLATrap`
- `GLAWall`
- `GLAWallHub`
- `AmericaInfantryPathfinder`
- `GLAInfantryJarmenKell`
- `AmericaInfantryColonelBurton`
- `ChinaInfantryBlackLotus`

### 3.8 Air templates excluded from current cluster logic

Current alpha assumption: no air units in cluster units.

- `AmericaVehicleComanche`
- `ChinaVehicleHelix`
- `ChinaHelixBattleBunker`
- `ChinaHelixGattlingCannon`
- `ChinaHelixPropagandaTower`
- `AmericaJetAurora`
- `AmericaJetRaptor`
- `AmericaJetStealthFighter`
- `ChinaJetMIG`
- `ChinaJetMIGNapalmStriker`

---

## 4. Unlock Group Mapping

### 4.1 Progression groups

| Group | Coverage / role | AP class | Alpha rule | Notes |
|-------|------------------|----------|------------|-------|
| `Shared_MachineGunVehicles` | `Anti-Infantry`, strong `Anti-Air` support | `progression` | in | clean infantry-swarm answer |
| `Shared_RocketInfantry` | `Anti-Vehicle`, strong `Anti-Air` support | `progression` | in | clean low-tech anti-vehicle answer |
| `Shared_Tanks` | `Anti-Vehicle`, `Frontline Units` | `progression` | in | cleanest dual-role combat group |
| `Shared_Artillery` | `Siege Units` | `progression` | in | long-range break tool |
| `Upgrade_Radar` | `Detectors` | `progression` | in | mission-only logic in alpha |

### 4.2 Mixed combat support groups

| Group | Coverage / role | AP class | Alpha rule | Notes |
|-------|------------------|----------|------------|-------|
| `Shared_InfantryVehicles` | mixed `Anti-Infantry` / light push support | `useful` | support-only | defer split |
| `Shared_MiscVehicles` | mixed utility support | `useful` | support-only | defer split |
| `Shared_MiscInfantry` | mixed hero / special support | `useful` | support-only | defer split |

### 4.3 Mission support / route support groups

| Group | Coverage / role | AP class | Alpha rule | Notes |
|-------|------------------|----------|------------|-------|
| `Shared_BaseDefenses` | `Hold` support only | `useful` | mission-only support | never a cluster-local answer |
| `Shared_WarFactoriesArmsDealers` | route / throughput support | `useful` | mission-only support | separate from progressive `Production` |
| `Shared_AirFields` | air-route enablement | `useful` | mission-only support | required before planes matter |
| `Shared_ComanchesHelixes` | air route and anti-air support | `useful` | mission-only support | not a cluster logic item |
| `Shared_PlaneTypeAircraft` | strike support | `useful` | mission-only support | not a cluster logic item |
| `Shared_Drones` | USA-only detector helper | `useful` | ignored by logic | real item, but do not count it for alpha logic |

### 4.4 Late-tech / economy / non-logic upgrade groups

| Group | Coverage / role | AP class | Alpha rule | Notes |
|-------|------------------|----------|------------|-------|
| `Shared_AltMoneyBuildings` | economy support | `useful` | not in core logic | never required in alpha |
| `Shared_StrategyBuildings` | tech support | `useful` | not in core logic | strong power, no logic credit |
| `Shared_Superweapons` | late-game power | `useful` | not in core logic | never required in alpha |
| `Upgrade_Weapons` | power increase | `useful` | not in core logic | never required in alpha |
| `Upgrade_Infantry` | power increase | `useful` | not in core logic | never required in alpha |
| `Upgrade_Vehicles` | power increase | `useful` | not in core logic | never required in alpha |
| `Upgrade_Aircraft` | power increase | `useful` | not in core logic | never required in alpha |
| `Upgrade_Mines` | defensive modifier | `useful` | not in core logic | never required in alpha |
| `Upgrade_CaptureBuilding` | future optional-location enablement | `useful` by default | conditional | only becomes `progression` if capture locations are enabled later |

### 4.5 Auto / baseline / non-pool groups

| Group | Alpha role | Pool status | Notes |
|-------|------------|-------------|-------|
| `Shared_RifleInfantry` | baseline starter combat package | not in pool | always granted at start; never a primary logic proof |
| `Shared_Barracks` | baseline only | not in pool | auto-unlocked |
| `Shared_CommandCenters` | baseline only | not in pool | auto-unlocked |
| `Shared_SupplyCenters` | baseline only | not in pool | auto-unlocked |
| `Shared_DroneUnits` | baseline helper only | not in pool | auto-unlocked |
| `Shared_MiscUnits` | useful flavor / late power only | optional useful | never logic-relevant in alpha |
| `Shared_AutoUpgradeVariants` | implementation detail | not in pool | never player-facing |
| `Shared_AngryMobMembers` | implementation detail | not in pool | tied to `GLAInfantryAngryMobNexus` |

---

## 5. Progressive Mission Buffs

These are not `groups.json` entries yet, but they are part of the alpha item model.

| Item | Tiers | AP class | Logic use |
|------|-------|----------|-----------|
| `Progressive Starting Money` | `none`, `low`, `medium`, `high` | `progression` | mission `Hold` and `Win` only |
| `Progressive Production` | `none`, `low`, `medium`, `high` | `progression` | mission `Hold` and `Win` only |
| `Temporary Cash` | numeric one-shot relief | `filler` or low-tier `useful` | never logic-relevant |

### 5.1 Numeric bridge values

| Tier | `Starting Money` | `Production` |
|------|------------------|--------------|
| `none` | `0` | `1.00x` |
| `low` | `+2000` | `1.25x` |
| `medium` | `+4000` | `1.50x` |
| `high` | `+6000` | `1.75x` |

### 5.2 Bridge rule

- The AP world should treat these as progression items.
- Pool sizing is configuration-driven and intentionally not frozen in the canonical docs.
- The bridge should combine:
  - baseline option tiers
  - received progression-item tiers
- The bridge should resolve the final effective floor and emit final numeric session options:
  - `startingCashBonus`
  - `productionMultiplier`

---

## 6. Deferred Splits and Deferred Options

### 6.1 Deferred splits

These are explicitly deferred, not blockers for the first AP world implementation:

- `Shared_InfantryVehicles`
- `Shared_MiscVehicles`
- `Shared_MiscInfantry`
- `Shared_BaseDefenses` if later optional categories need forts, traps, and walls separated

### 6.2 Deferred options

These should not be treated as alpha-supported implementation targets:

- `clusters_per_map`
- `slots_per_cluster`
- `include_superweapons_in_logic`
- `unit_granularity`
- `building_granularity`
- `upgrade_granularity`

Grouped-only alpha is the official first-release target.

---

## 7. Implementation Notes

If implementation begins from this mapping, the next work should be:

1. represent player progression as boolean coverage of unit types and mission buff tiers
2. evaluate cluster-local status from the truth table above
3. evaluate `Hold` and `Win` separately
4. merge cluster-local and mission-gate results into one final tracker status
5. keep `Yellow` tracker-only and exclude it from AP access rules
6. treat mixed groups as support-only unless they are explicitly split later
