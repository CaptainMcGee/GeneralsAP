# Generals Archipelago Logic & Implementation Guide

**Purpose**: Canonical alpha design for Archipelago goal logic, cluster logic, mission gates, item classifications, and the world/bridge/game contract.

**Canonical status**: This document supersedes the older numeric-strength-first planning language for alpha logic.

**Historical note**: The following files still exist in the repo, but they are no longer the design authority for alpha logic:

- `Data/Archipelago/enemy_general_profiles.json`
- `scripts/archipelago_logic_prerequisites.py`
- `Data/Archipelago/Slot-Data-Format.md`
- `Data/Archipelago/options_schema.yaml`

They should be treated as implementation scaffolding or historical drafts until they are rewritten to match this guide.

**External AP patterns this guide follows**:

- AP dev FAQ: soft logic, restrictive starts, repeatable reachability
- StarCraft II world: separate tactical-logic difficulty and optional location categories
- Kingdom Hearts II world: separate goal logic from fight logic

---

## 1. Canonical Alpha Decisions

The alpha Archipelago contract is now locked around ten decisions:

1. **World goal and reachability** are replay-friendly and use `full` accessibility.
2. **Cluster logic** is discrete unit-type coverage, not numeric matchup scoring.
3. **Mission logic** is separate from cluster logic and uses `Hold` and `Win`.
4. **Alpha locations** are mission victories plus cluster-unit kills only.
5. **AP numeric IDs** are owned by the world; the game keeps local string check IDs for cluster-unit kills.
6. **Grouped-only alpha** is the official first-release item-pool model.
7. **Easy / Medium / Hard cluster rules** are explicit: Easy uses one explicit weakness and no `Hold`; Medium uses one or two explicit weaknesses plus `Hold`; Hard uses two explicit weaknesses plus `Win`.
8. **Economy and buffs** are separate from combat weakness tags. They primarily support cluster difficulty floors and mission `Hold` / `Win`, and they do not replace missing cluster weaknesses.
9. **Capability satisfaction** is concrete: a weakness is satisfied by usable unit/item unlocks plus required production facilities, not by unlocking an abstract weakness category.
10. **Planning docs** in this folder are the design authority; stale numeric-model docs are historical only.

---

## 2. Thread 1: World Goal and Reachability Rules

### Approved decision

- The world completion condition is:
  - collect the seven shuffled main challenge victory medals
  - then beat the boss map
- Each main challenge general has one progression medal item shuffled into the AP item pool:
  - `Air Force General Medal`
  - `Laser General Medal`
  - `Superweapons General Medal`
  - `Tank General Medal`
  - `Nuke General Medal`
  - `Stealth General Medal`
  - `Toxin General Medal`
- These medals denote that the corresponding general has been defeated for world-goal progression.
- The boss map is logically locked behind all seven medal items, not behind free event items or mere mission-region access.
- The China Boss general has its own clusters and future `Hold` / `Win` conditions.
- Defeating the boss map is total victory.
- `Mission Victory - Boss General` carries the locked final `Victory` item as an AP event location. It is not a shuffled item location and is not submitted through normal `LocationChecks`.
- Mission replayability is a core design assumption for Archipelago logic.
- Medium and hard clusters assume replay access.
- Alpha uses **`full` accessibility**, not `minimal`.
- Missable or one-time-only location families are banned from alpha logic.

### Rationale

- Archipelago assumes reachability is monotonic. Replayable challenge maps fit that model; missable mission-only checks do not.
- A replay assumption makes medium and hard cluster logic honest instead of forcing everything into one first-clear path.
- `full` accessibility is the right target because the alpha location pool is intentionally repeatable and deterministic.

### Downstream impacts

- The AP world should define boss access as all seven main victory medals, then completion as boss victory.
- The future mission `Win` implementation must control when the runtime completes `mission.boss.victory`; medal collection only unlocks access to the boss map.
- Mission select / replay support is not optional UI polish; it is part of the logic model.
- Time-limited, one-shot, or missable location families must stay out of the alpha item/location pool.
- Optional future location families must be repeatable or stay disabled by default.

---

## 3. Thread 2: Core Logic Semantics

### Approved decision

- Cluster logic uses explicit unit-type coverage, not numeric power.
- `Yellow` is **tracker-only information**. It never grants AP logical access.
- `Hold` and `Win` are mission gates, not cluster-local requirements.
- Final cluster status is the **worst-of**:
  - cluster-local result
  - mission-gate result
- Cluster tooltips/tracker output should still explain the local rule and the mission gate separately.
- Alpha mission gates are **green/red only**. `Hold` and `Win` do not use yellow in alpha.

### Player-facing vocabulary

| UI name | Internal key | Meaning | Used by |
|---------|--------------|---------|---------|
| `Anti-Infantry` | `anti_infantry` | Reliable answer to infantry and mob swarms | clusters, missions |
| `Anti-Vehicle` | `anti_vehicle` | Reliable answer to ground vehicles and tanks | clusters, missions |
| `Siege Units` | `siege_units` | Reliable answer to static defenses and entrenched positions | clusters, missions |
| `Frontline Units` | `frontline_units` | Durable push units that can advance under fire | clusters, missions |
| `Detectors` | `detectors` | Reliable stealth reveal | missions only in alpha |
| `Anti-Air` | `anti_air` | Reliable answer to air pressure | missions only in alpha |
| `Starting Money` | `starting_money` | Mission-start economy floor | missions only |
| `Production` | `production` | Build-speed / rebuild-speed floor | missions only |

`Starting Money` and `Production` are progression dimensions, not combat weakness tags. They may be required by cluster difficulty floors and mission `Hold` / `Win`, but they should not act as an alternative route around a missing required cluster weakness.

### Capability satisfaction semantics

- Player unlocks are concrete units/items/powers, not abstract weakness grants.
- A unit can satisfy one or more weaknesses, though most units should satisfy only one primary weakness.
- A unit only counts if the player also has the production facility required to build it.
- Multiple weak/support unlocks do not combine into one formal green weakness unless a later design pass explicitly adds a combo rule.
- Upgrades, economy, and buffs do not turn a yellow cluster route into green.
- Non-unit items and general powers can still be formal requirements for mission-specific `Hold` / `Win` logic when a route truly depends on them.
- Logic must respect the player's actual faction/general route and YAML granularity setting. A general-specific route cannot borrow unrelated faction/general unlocks that the player cannot actually field.

### Cluster color semantics

| Color | Meaning | Logic effect |
|-------|---------|--------------|
| `Green` | intended route exists | grants AP access if mission gate also green |
| `Yellow` | only an explicitly blessed glitch / attrition / cheese route exists | tracker-only, never grants AP access |
| `Red` | no approved route exists | no AP access |

### Cluster classes

| Cluster class | Green if player has | Yellow if player only has | Notes |
|---------------|---------------------|---------------------------|-------|
| `Infantry Swarm` | `Anti-Infantry` | `Frontline Units` | yellow means brute-force crush route |
| `Vehicle Pack` | `Anti-Vehicle` | `Frontline Units` | light-to-mid vehicle pressure |
| `Armor` | `Anti-Vehicle` | `Siege Units` | yellow means kite / attrition route |
| `Fort` | `Siege Units` | `Frontline Units` | yellow means brute-force breach |
| `Artillery` | `Frontline Units` | `Siege Units` | yellow means counter-battery / cheese route |

Tier interpretation:

- Easy clusters require one explicit weakness that is consistent across the cluster's core units and do not require `Hold`.
- Medium clusters require `Hold` plus one or two explicit weaknesses.
- Hard clusters require `Win` plus two explicit weaknesses.
- `Yellow` remains tracker emphasis / notes only for alpha. It does not grant AP access.

### Mission-gate definitions

- **`Hold`**:
  - survive the opening pressure
  - stabilize enough to leave base
  - reach medium clusters on a repeat visit if needed
- **`Win`**:
  - close the map
  - defeat the general
  - reach hard clusters that sit on the full-clear route

### Exact per-general mission table

- The `Hold` / `Win` framework is locked.
- The exact per-general requirement table is intentionally deferred.
- Do not treat any earlier example map table as canonical.
- A later dedicated mission pass should author:
  - per-map `Hold` requirements
  - per-map `Win` requirements
  - per-map `Starting Money` / `Production` floors
- Boss tracking should still expose only `Hold` and `Win` as the main alpha statuses. More detailed boss sub-phases can be added later as tracker-only explanation.

### Downstream impacts

- The discrete evaluator should return:
  - cluster-local result
  - mission-gate result
  - merged final result
  - explicit missing-type text
- AP access rules should use only green states.
- `Yellow` should remain visible in the in-game tracker to help players, but never influence the seed's formal logic.
- The machine-readable mission-gate source is blocked on the later per-general mission pass.

---

## 4. Thread 3: Location Model

### Approved decision

- Alpha location families are **only**:
  - mission victories
  - cluster-unit kills
- Every cluster unit remains its own AP location.
- Units inside a cluster share one cluster-level access rule.
- Extra location families are deferred and may only return as optional categories later.
- The old generic `slots_per_cluster` model is no longer the canonical design target.

### Alpha location taxonomy

| Family | Alpha status | Notes |
|--------|--------------|-------|
| Mission victory | in | one location per challenge map, plus boss |
| Cluster-unit kill | in | one location per authored unit in a selected cluster |
| Capture building | out | future optional category only |
| Destroy marked structure | out | future optional category only |
| Build first landmark structure | out | future optional category only |
| Supply pile / depletion | out | future optional category only |
| Generic kill counts | out | not suitable for alpha |
| Generic build counts | out | not suitable for alpha |

### Rules for future optional families

- Must be repeatable or logically monotonic.
- Must be singular and readable.
- Must not be chore-like.
- Must default to disabled until fully tested.

### Downstream impacts

- Seed payloads should describe **selected cluster units**, not generic slot counts.
- Location-count balancing should be solved by the AP world and item pool, not by reviving abstract slot placeholders.
- `clusters_per_map` and `slots_per_cluster` can remain as temporary scaffolding in old files, but they are not the future contract.

---

## 5. Thread 4: AP Addressing and World / Bridge / Game Contract

### Approved decision

- The AP world owns the canonical numeric location table.
- The game owns local runtime check IDs for cluster-unit kills.
- The bridge owns translation between the two.
- The game should not recompute seed selection, cluster classification, or AP numeric IDs.

### Canonical map keys

| Map key | Canonical slot |
|---------|----------------|
| `air_force` | `0` |
| `laser` | `1` |
| `superweapon` | `2` |
| `tank` | `3` |
| `nuke` | `4` |
| `stealth` | `5` |
| `toxin` | `6` |
| `boss` | `7` |

### Canonical numeric ID scheme

Reserve a GeneralsAP location namespace and keep the formula stable.

```text
AP namespace base:     270000000
Mission victory base:  270000000
Cluster unit base:     270010000
```

Use these formulas:

```text
mission victory location id
= 270000000 + map_slot

cluster unit location id
= 270010000 + (map_slot * 10000) + (cluster_index * 100) + unit_index
```

Rules:

- `cluster_index` is the canonical authored cluster index within that map's static catalog.
- `unit_index` is the canonical authored unit index within that cluster.
- IDs are assigned from the full authored superset, not from the per-seed selected subset.

### Runtime key grammar

Use stable string keys in the game and bridge:

```text
mission.<map_key>.victory
cluster.<map_key>.cXX.uYY
```

Examples:

```text
mission.tank.victory
cluster.superweapon.c03.u01
```

### Ownership split

**Static repo-side authored data** owns:

- canonical map keys
- canonical cluster catalog
- canonical cluster class and tier
- canonical mission-gate schema and, later, the authored per-map `Hold` / `Win` table
- unlock-group coverage and item classifications

**AP world** owns:

- numeric AP location IDs
- item table
- per-seed location subset selection
- per-seed item placement

**Bridge payload** owns:

- selected mission victory locations for the seed
- selected cluster-unit locations for the seed
- runtime string keys
- AP numeric IDs for those selected locations
- resolved cluster class / tier / requirement labels
- resolved map `Hold` / `Win` requirements and buff floors once the per-map mission table exists

**Game runtime** owns:

- local completion of mission victories
- local completion of cluster runtime checks
- rendering the tracker using the seed payload plus local progression state

### Seed payload scope

The future bridge payload must be per-seed and per-unit, not slot-count based. At minimum it should contain:

- map key
- mission victory location ID
- selected cluster key
- selected cluster tier
- cluster class
- primary requirement
- optional yellow requirement
- per-unit runtime check key
- per-unit AP numeric location ID
- per-unit defender template
- per-map mission-gate data when authored:
  - `Hold` requirements
  - `Win` requirements
  - `Starting Money` / `Production` floors

### Downstream impacts

- `completedChecks` should stay the game's local source of truth for cluster-unit kills.
- The bridge should map completed cluster runtime keys to AP numeric IDs before server submission.
- `Slot-Data-Format.md` must eventually be rewritten around this per-unit payload model.

---

## 6. Thread 5: Item Pool and Classification

### Approved decision

- Alpha uses explicit AP item classifications:
  - `progression`
  - `useful`
  - `filler`
  - `trap`
- Any item referenced by logic must be `progression`.
- Mission buffs are both:
  - AP progression items
  - bridge/session-option transport values
- Alpha uses normal AP local/non-local behavior. No custom local-item rules are added beyond standard AP options.
- Early pacing should be handled by AP progression balancing and configuration, not by a bespoke Generals-side early-item guarantee rule.

### Classification table

| Bucket | Entries | AP classification | Notes |
|--------|---------|-------------------|-------|
| Core logic groups | `Shared_MachineGunVehicles`, `Shared_RocketInfantry`, `Shared_Tanks`, `Shared_Artillery`, `Upgrade_Radar` | `progression` | all are referenced by cluster or mission logic |
| Mission buff items | `Progressive Starting Money`, `Progressive Production` | `progression` | logic-relevant mission gates |
| Mixed combat support | `Shared_InfantryVehicles`, `Shared_MiscVehicles`, `Shared_MiscInfantry` | `useful` | support-only in alpha |
| Mission support / late tech | `Shared_BaseDefenses`, `Shared_WarFactoriesArmsDealers`, `Shared_AirFields`, `Shared_ComanchesHelixes`, `Shared_PlaneTypeAircraft`, `Shared_MiscUnits`, `Shared_AltMoneyBuildings`, `Shared_StrategyBuildings`, `Shared_Superweapons` | `useful` | never required by alpha core logic |
| Ignored-by-logic helper items | `Shared_Drones` | `useful` | real item, but never counted by alpha logic |
| Non-logic upgrades | `Upgrade_Weapons`, `Upgrade_Infantry`, `Upgrade_Vehicles`, `Upgrade_Aircraft`, `Upgrade_Mines` | `useful` | strong power, not logic proofs |
| Conditional future logic item | `Upgrade_CaptureBuilding` | `useful` by default, `progression` only if capture-building locations are enabled later | conditional promotion only |
| Cash / resource relief | `Temporary Cash` and similar | `filler` or low-tier `useful` | never logic-relevant |
| Harmful effects | `Money Drain`, `Airshow Trap`, `Random Voice Trap` | `trap` | future-only content, not part of current alpha presets |
| Baseline auto-unlocks | `Shared_RifleInfantry`, `Shared_Barracks`, `Shared_CommandCenters`, `Shared_SupplyCenters`, `Shared_DroneUnits`, `Shared_AutoUpgradeVariants`, `Shared_AngryMobMembers` | not in pool | baseline or implementation-detail content |

### Mission buff semantics

Use four named floors for tracker and design purposes:

| Tier | `Starting Money` | `Production` |
|------|------------------|--------------|
| `none` | `0` | `1.00x` |
| `low` | `+2000` | `1.25x` |
| `medium` | `+4000` | `1.50x` |
| `high` | `+6000` | `1.75x` |

Alpha AP-item model:

- Seven main challenge victory medals are real progression items and must appear exactly once each.
- Boss access requires all seven medal items.
- Boss mission victory remains the locked final `Victory` event item, not an eighth shuffled medal item.
- The named floors above are the current tracker and logic vocabulary.
- Pool sizing is configuration-driven and intentionally not locked yet.
- Do not hardcode a global copy count for either progressive buff item in the canonical docs.
- The AP world can decide how many copies exist and how they map to the named floors, as long as the bridge can still resolve the final effective floor for tracker and logic use.

Bridge transport rule:

- world options may set a baseline floor
- AP progression items add tiers on top
- bridge resolves the final effective floor and emits the corresponding numeric value
- bridge writes the final numeric value to session options:
  - `startingCashBonus`
  - `productionMultiplier`

### Downstream impacts

- The AP world should itemize mission buffs as normal progression items.
- The bridge should own tier-to-numeric conversion.
- Temporary cash and similar economy relief must stay out of logic evaluation.

---

## 7. Thread 6: Unlock Group Mapping Policy

### Approved decision

- Grouped-only alpha is the official first-release target.
- Mixed groups stay support-only in alpha.
- No mixed group is required to be split before the first AP world implementation.
- Granularity options that imply per-unit, per-building, or per-upgrade itemization are deferred.

### Primary progression logic groups

| Group | Grants |
|-------|--------|
| `Shared_MachineGunVehicles` | `Anti-Infantry`, strong `Anti-Air` support |
| `Shared_RocketInfantry` | `Anti-Vehicle`, strong `Anti-Air` support |
| `Shared_Tanks` | `Anti-Vehicle`, `Frontline Units` |
| `Shared_Artillery` | `Siege Units` |
| `Upgrade_Radar` | `Detectors` |

### Support-only groups in alpha

| Group | Alpha rule |
|-------|------------|
| `Shared_InfantryVehicles` | support only; no standalone green |
| `Shared_MiscVehicles` | support only; no standalone green |
| `Shared_MiscInfantry` | support only; no standalone green |
| `Shared_BaseDefenses` | mission-only support; no off-base cluster credit |
| `Shared_WarFactoriesArmsDealers` | useful throughput support only |
| `Shared_AirFields` | useful route support only |
| `Shared_ComanchesHelixes` | useful mission support only |
| `Shared_PlaneTypeAircraft` | useful mission support only |
| `Shared_Drones` | item exists, but ignore it for alpha logic |

### Baseline starter content

| Group | Alpha rule |
|-------|------------|
| `Shared_RifleInfantry` | always granted at start; not in the randomized alpha item pool; never used as a primary logic proof |

### Deferred split candidates

- `Shared_InfantryVehicles`
- `Shared_MiscVehicles`
- `Shared_MiscInfantry`
- `Shared_BaseDefenses` if optional location families later need fortifications, walls, and traps separated

### Granularity policy

These remain deferred and should not be treated as alpha-supported:

- per-unit itemization
- per-building itemization
- per-upgrade itemization
- presets whose only purpose is smaller or noisier group granularity

### Downstream impacts

- `groups.json` remains the item-pool source of truth for alpha.
- The first AP world should target grouped items only.
- Old granularity options should be documented as deferred rather than treated as current implementation targets.

---

## 8. Thread 7: Alpha Options, Presets, and Phasing

### Approved decision

Alpha-facing options and presets are narrowed to match the grouped, replayable, per-unit location model.

### Supported alpha-facing options

| Option | Status | Notes |
|--------|--------|-------|
| `unlock_preset` | supported | semantic ruleset selector, not granularity selector |
| `starting_generals_usa` | supported | valid seed-facing option |
| `starting_generals_china` | supported | valid seed-facing option |
| `starting_generals_gla` | supported | valid seed-facing option |

### Experimental / deferred options

| Option | Status | Why |
|--------|--------|-----|
| `game_difficulty` | experimental only | gameplay may vary, but alpha logic tables are not yet authored per difficulty |
| `clusters_per_map` | deferred | generic slot-count model is no longer canonical |
| `slots_per_cluster` | deferred | replaced by authored per-unit locations |
| `include_superweapons_in_logic` | deferred | superweapons are not alpha logic requirements |
| `unit_granularity` | deferred | grouped-only alpha target |
| `building_granularity` | deferred | grouped-only alpha target |
| `upgrade_granularity` | deferred | grouped-only alpha target |

### Preset semantics

| Preset | Meaning |
|--------|---------|
| `default` | canonical alpha ruleset: grouped-only pool, mission victories plus selected cluster-unit kills, no experimental location families, no superweapon logic |
| `minimal` | shorter grouped-only ruleset: mission victories plus easy/medium cluster-unit kills, no experimental families, no traps |

Additional alpha preset rule:

- `chaos` is not part of the current plan.
- Trap content is future-only and is not part of `default` or `minimal`.

Implementation priority:

1. `default`
2. `minimal`

### Project phasing after the decision pass

| Phase | Goal |
|-------|------|
| `P1` | align docs and static data contracts with this guide |
| `P2` | implement AP world static IDs, item table, per-unit selected location payload, and preset semantics |
| `P3` | implement bridge translation and game-side seed payload ingestion |
| `P4` | implement discrete evaluator and tracker query APIs in the game runtime |
| `P5` | build UI, mission select, connect flow, and later optional location families / future trap content / compositions |

### Research-backed implementation lanes

| Lane | Owner | Depends on | Main outputs |
|------|-------|------------|--------------|
| `L1` Contract + seed schema | data/contract engineer | none | `Seed-Slot-Data.json` contract, stable runtime keys, numeric ID contract |
| `L2` AP world skeleton | AP-world engineer | `L1` | `worlds/generalszh` scaffold, item table, location table, `fill_slot_data` output |
| `L3` Bridge sidecar | bridge engineer | `L1`, partial `L2` | AP session bridge, slot-data materialization, ID translation, duplicate protection |
| `L4` Runtime ingestion + evaluator | C++ gameplay engineer | `L1`, `L3` | slot-data loader, selected-check registry, tracker query API, discrete evaluator |
| `L5` UI / tracker / mission select | UI engineer | `L1` mock payload, `L4` query surface | menu shell, tracker screens, fixture-driven UI flow |
| `L6` Packaging + fixtures + playtest | release/test engineer | none | package layout, manifest, fixture matrix, profile-isolation validation |

#### `L1` Contract + seed schema

Primary repo touchpoints:

- [Slot-Data-Format.md](../../../Data/Archipelago/Slot-Data-Format.md)
- [Archipelago-State-Sync-Architecture.md](../Operations/Archipelago-State-Sync-Architecture.md)
- `Data/Archipelago/*` machine-readable logic sources when added

Deliverables:

- immutable `Seed-Slot-Data.json` contract
- inbound reference metadata: path + hash + session nonce
- stable runtime-key grammar
- stable numeric ID formulas
- map/cluster/unit payload shape with reserved mission-gate fields

Acceptance:

- no generic `slots_per_cluster`
- no runtime recomputation of selected checks
- unique numeric IDs and runtime keys
- mission-gate schema present even before per-map rows are authored

#### `L2` AP world skeleton

Primary repo touchpoints:

- `vendor/archipelago/overlay/worlds/generalszh/*`
- alpha option surface in this guide
- grouped mapping in [Archipelago-Logic-Mapping-Draft.md](Archipelago-Logic-Mapping-Draft.md)

Best implementation shape:

- standard world flow built around:
  - `create_item`
  - `create_regions`
  - `create_items`
  - `set_rules`
  - `fill_slot_data`
- option surface stays narrow: `unlock_preset`, starting generals, future-safe experimental options only when they do not mislead

Deliverables:

- world package skeleton
- grouped item table using AP item classifications
- mission-victory + cluster-unit location table
- completion condition: seven main victories then boss
- `fill_slot_data` matching `L1`

Acceptance:

- seed generation works with grouped-only alpha items
- `default` and `minimal` are materially defined
- no `chaos` requirement in current alpha

#### `L3` Bridge sidecar

Primary repo touchpoints:

- [Archipelago-State-Sync-Architecture.md](../Operations/Archipelago-State-Sync-Architecture.md)
- `scripts/archipelago_bridge_local.py`
- future external AP bridge implementation

Deliverables:

- real AP connectivity outside game runtime
- `Seed-Slot-Data.json` materialization
- session binding rules
- runtime-key to AP-location-ID translation
- duplicate submission protection

Acceptance:

- reconnect safe
- reseed mismatch detected
- outbound state submission idempotent
- no cluster check submitted without slot-data lookup

#### `L4` Runtime ingestion + evaluator

Primary repo touchpoints:

- `UnlockableCheckSpawner.cpp`
- `ArchipelagoState.cpp`
- future runtime tracker query code

Deliverables:

- slot-data loader
- selected-check runtime registry
- discrete evaluator using cluster class + mission gate model
- tracker query surface for cluster color, `Hold`, `Win`, and missing types

Acceptance:

- medium clusters read `Hold`
- hard clusters read `Win`
- `Yellow` stays tracker-only
- no numeric player-strength oracle remains on critical path

#### `L5` UI / tracker / mission select

Primary repo touchpoints:

- main-menu AP flow
- logic/check tracker UI
- mission-select shell

Best implementation rule:

- fixture-first
- no live AP networking dependency for first UI pass
- consume mock payload matching `L1` / `L4`

Deliverables:

- connect screen shell
- mission select shell
- cluster tracker presentation
- mission `Hold` / `Win` presentation

Acceptance:

- UI can run against fixtures before bridge/runtime finish
- cluster rule and mission-gate rule shown separately
- boss still shown as `Hold` / `Win` at main status layer

#### `L6` Packaging + fixtures + playtest

Primary repo touchpoints:

- [Player-Release-Architecture.md](../Operations/Player-Release-Architecture.md)
- runtime profiles
- bridge fixtures

Deliverables:

- release manifest schema
- package/clone/install flow
- profile-local bridge/save layout
- fixture matrix for bridge/runtime/UI smoke tests

Acceptance:

- isolated installs do not share state
- fixture matrix covers reconnect, replay, save/load, fallback, upgrade
- package does not require developer tooling

---

## 9. Immediate Implementation Order

The planning docs and context index were aligned with this guide on April 12, 2026. Best execution order now is wave-based:

### Wave 1: freeze interfaces

1. Finish `L1` contract work:
   - rewrite slot-data contract
   - lock runtime-key and numeric-ID contract
   - add machine-readable item-classification source
2. Start `L2` AP world scaffold against that contract.
3. Expand `L3` bridge lifecycle and session-binding implementation notes.
4. Expand `L6` manifest and fixture matrix.

### Wave 2: consume frozen contract

5. Implement runtime slot-data ingestion and selected-check registry in `L4`.
6. Replace numeric prerequisite path with discrete evaluator APIs in `L4`.
7. Build bridge-side translation and duplicate-submission logic in `L3`.

### Wave 3: consume runtime query surface

8. Build fixture-driven UI shell in `L5`.
9. Wire live bridge/runtime data into UI only after `L4` query surface is stable.

### Still deferred

- exact per-general mission `Hold` / `Win` rows
- optional location families
- trap content

---

## 10. External AP Reference Points

These references informed the approved alpha design, especially around monotonic reachability, item classification, and separating tactical fight logic from world-goal logic.

- [Archipelago apworld dev FAQ](https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/apworld_dev_faq.md)
  - reinforces replay-safe, monotonic access rules and avoiding missable assumptions in the default ruleset
- [Archipelago generic advanced settings guide](https://github.com/ArchipelagoMW/Archipelago/blob/main/worlds/generic/docs/advanced_settings_en.md)
  - informed the decision to keep the alpha-facing option surface small and defer misleading knobs
- [Archipelago BaseClasses item classifications](https://github.com/ArchipelagoMW/Archipelago/blob/main/BaseClasses.py)
  - informs the `progression`, `useful`, `filler`, and `trap` split used in the grouped alpha item table
- [StarCraft II world options](https://github.com/ArchipelagoMW/Archipelago/blob/main/worlds/sc2/options.py)
  - informed the split between core logical access and optional or softer location categories
- [Kingdom Hearts II world options](https://github.com/ArchipelagoMW/Archipelago/blob/main/worlds/kh2/Options.py)
  - informed the separation between world goal logic and combat / encounter logic

---

## 11. Related Documents

- [Archipelago-Logic-Mapping-Draft.md](Archipelago-Logic-Mapping-Draft.md)
- [Archipelago-Implementation-Todo.md](Archipelago-Implementation-Todo.md)
- [Slot-Data-Format.md](../../../Data/Archipelago/Slot-Data-Format.md)
- [Archipelago-State-Sync-Architecture.md](../Operations/Archipelago-State-Sync-Architecture.md)
- [Player-Release-Architecture.md](../Operations/Player-Release-Architecture.md)
- [Docs/Archipelago/Unlock-Group-Logic.md](../Unlock-Group-Logic.md)
- [ARCHIPELAGO_CONTEXT_INDEX.md](../../../ARCHIPELAGO_CONTEXT_INDEX.md)
