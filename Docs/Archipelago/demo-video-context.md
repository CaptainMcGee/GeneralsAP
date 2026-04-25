# C&C Generals: Zero Hour — Archipelago Mod Demo Context

## What Is This?

This document captures the goals, working features, and current progress of the **Generals Archipelago mod** — a project to integrate **Command & Conquer: Generals Zero Hour** with the **Archipelago multiworld randomizer framework**. It is organized as source material for a gameplay demonstration video that uses burned-in captions instead of voiceover.

---

## 1. The Big Picture

### What Is Archipelago?

Archipelago is an open-source multiworld randomizer framework. It connects multiple games together so that items found in one game unlock progress in another. Players connect to a shared server, and every time they complete a "check" in their game, it may send an item to another player in a completely different game — and vice versa.

### What Is This Mod?

This mod turns C&C Generals: Zero Hour into an Archipelago-compatible game. The core idea:

- **Items** = units, buildings, upgrades, and general powers. These are shuffled into the Archipelago item pool and received from other players (or found locally).
- **Checks** = enemy unit clusters spawned at fixed map locations. Defeat them to send checks back into the multiworld network.
- **Progression** = you start with almost nothing — basic infantry, dozers, and supply buildings. As items arrive, your army roster grows across all three factions (USA, China, GLA).

### The Vision

Play through Zero Hour's Generals Challenge mode (7 missions against enemy generals), but your available units depend on what the Archipelago network gives you. You might get GLA Scorpion tanks before you get USA War Factories. You might unlock Comanche helicopters but not Airfields. Every seed is different.

---

## 2. Core Gameplay Loop

### Starting Position

You begin each mission with only the essentials:
- **USA**: Ranger infantry, Dozer, Chinook, Command Center, Barracks, Supply Center, Power Plant
- **China**: Red Guard infantry, Dozer, Supply Truck, Mini Gunner (Infantry General), Command Center, Barracks, Supply Center, Power Plant
- **GLA**: Rebel infantry, Worker, Command Center, Barracks, Supply Stash

Everything else — tanks, aircraft, artillery, base defenses, upgrades — is locked until the Archipelago network delivers it.

### Receiving Items

When the Archipelago server sends you an item, an entire cross-faction group unlocks at once. For example, receiving the **"Shared_Tanks"** item unlocks:
- USA: Crusader, Paladin
- China: Battle Master, Overlord (3 variants)
- GLA: Scorpion, Marauder, Light Tank (Stealth General)

There are **29 unlock groups** covering approximately 90 base unit templates, 44 buildings, and multiple upgrade tiers — expanding to 300+ faction-variant templates when general sub-factions are included.

### Completing Checks

On each challenge map, enemy unit clusters are spawned at fixed waypoints. These are the "checks." Destroy a cluster to send its check back to the Archipelago network. That check might unlock something for you, or it might send an item to another player in a different game entirely.

---

## 3. The Spawned Unit System

This is the heart of the mod. Enemy units representing Archipelago checks are spawned at map load and behave as autonomous, self-managing packs.

### Cluster Organization

- Units spawn in **clusters** — coordinated groups positioned at map waypoints
- Each cluster gets its own **dedicated team** (e.g., `ArchipelagoCluster_0`)
- Units within a cluster fight together: when one is attacked, the entire cluster responds
- Clusters are assigned difficulty tiers: Easy, Medium, or Hard

### Placement Algorithm

Units are placed using a **golden-angle spiral pattern** around each cluster's center waypoint:
- Inner dead-zone prevents stacking on the center point
- Minimum separation of at least 54 units between spawned objects
- Expanding search phases handle terrain collisions and tight spaces
- Terrain height tolerance prevents spawning on cliffs or slopes

---

## 4. Spawned Unit AI

The spawned units use a custom AI behavior system built on top of the engine's native guard machine. This was the focus of 43 dedicated commits on the current development branch.

### Two-Tier Leashing

Every spawned unit has two distance boundaries measured from its guard position (spawn point):

1. **Defend Radius (soft leash)** — When a unit drifts past this distance with no live target, it gently walks back to its guard position. If actively engaged in combat, it can keep fighting.

2. **Max Chase Radius (hard leash)** — Beyond this distance, the unit **always** retreats, even mid-combat. No exceptions. This prevents players from kiting spawned units across the map.

### Retreat Mechanics

When a unit retreats, it gets survival bonuses:
- **2.5x movement speed** (vs. 1.5x base speed)
- **10% max HP healing per second**
- **67% damage reduction** (incoming damage multiplied by 0.33)
- Retreat completes when the unit is within 200 units of its guard position

### Post-Retreat Cooldown

After completing a retreat, each unit enters a **5-second cooldown**. During this window:
- The unit will **not** chase cluster retaliation targets
- If directly attacked, it fires back from its current position (defensive stance) instead of attack-moving toward the attacker
- This prevents the retreat-chase loop: retreat → arrive → immediately re-engage → chase → retreat again

### Guard-Without-Pursuit

Spawned units use the engine's `GUARDMODE_GUARD_WITHOUT_PURSUIT` setting. This means the vanilla guard AI will never chase targets outside the guard radius on its own. All offensive movement is controlled by the spawner's retaliation system instead.

### Command Authority

Spawned units **only** accept orders from the spawner system itself. They ignore:
- Map trigger scripts (which normally control enemy AI behavior)
- Player commands
- Team synchronization from other units
- Any AI command that doesn't originate from the spawner

This is enforced via a `spawnerCommandInProgress` flag — the spawner sets it before issuing commands and clears it after.

### Stealth Detection

Spawned units scan for stealthed enemies within their detection range at half-second intervals. When a stealthed unit is detected, it is revealed for one second, allowing the cluster to engage cloaked threats like Stealth Fighters or Jarmen Kell.

### No-Collision Ghosting

Spawned units have object-to-object collisions disabled (`OBJECT_STATUS_NO_COLLISIONS`). They ghost through each other and through enemy units, preventing pathing jams in tight cluster formations. They still collide with terrain and buildings.

---

## 5. Cluster Retaliation System

When any unit in a cluster takes damage, the entire cluster responds as a coordinated group.

### How It Works

1. **Damage Detection**: When a spawned unit takes damage, the system captures the attacker's identity directly in the damage pipeline (before the engine's ActiveBody can overwrite the damage info).

2. **Per-Unit Target**: The damaged unit gets a direct retaliation target — it attack-moves toward the attacker.

3. **Cluster Propagation**: The attacker's identity is broadcast to the entire cluster. All units in the cluster become aware of the threat.

4. **Role-Based Response**:
   - **Crusher units** (Overlord, Dragon Tank, Dozers): Prioritize nearby infantry for crush attacks, with a 3-second cooldown between pursuits
   - **Artillery** (Nuke Cannon, Inferno Cannon): Fire from their guard position, never chase. They have a fixed 500-unit vision and attack range, and spawn pre-deployed so they can fire immediately
   - **Support units** (ECM Tank): Maintain distance, use anti-kite rules
   - **Standard units**: Attack-move toward the threat location

5. **Alert Timer**: Cluster alerts expire after a set duration. When they expire, stale retaliation targets are cleared, preventing units from chasing ghosts.

### The Retreat-Chase Loop Problem (Solved)

The biggest technical challenge was eliminating infinite retreat-chase loops. Three independent sources were identified and fixed:

1. **Direct hits during cooldown**: Damage pipeline was setting retaliation targets that bypassed the post-retreat cooldown. Fix: during cooldown, units use defensive fire-from-position instead of attack-move.

2. **Guard radius drift**: Units arriving at exactly the guard radius boundary (e.g., 376 units from guard position when the radius is 375) would immediately trigger a full retreat. Fix: units at the boundary now get a soft re-guard command instead of a hard retreat.

3. **Chase/guard radius gap**: The gap between chase radius and guard radius created an oscillation zone. Fix: soft re-guard naturally walks units back without triggering the full retreat state machine.

---

## 6. Protection & Balance System

Spawned units would be trivially destroyed by late-game weapons without protection rules. The mod implements a **91-rule damage protection matrix** across 7 categories.

### Damage Reduction Categories

| Category | Damage Multiplier | Effect | Example Sources |
|----------|------------------|--------|-----------------|
| Superweapons | 0.00 (0%) | Full immunity | Particle Cannon, Nuclear Missile, SCUD Storm |
| General Powers | 0.02 (2%) | 98% reduction | Carpet Bomb, MOAB, Fuel Air Bomb, A-10 Strike, Artillery Barrage, Spectre Gunship, EMP Pulse |
| Fighter Aircraft | 0.10 (10%) | 90% reduction | Raptor, King Raptor, Aurora, Stealth Fighter, MiG variants |
| Artillery Projectiles | 0.10 (10%) | 90% reduction | Tomahawk, Inferno Cannon, Nuke Cannon, Crusader/Paladin shells |
| Helicopters | 0.25 (25%) | 75% reduction | Comanche, Helix |
| Ground Fields | 0.25 (25%) | 75% reduction | Anthrax toxin fields, Radiation fields |

### Complete Immunities (24 Rules)

Spawned units are **completely immune** to:
- **EMP** — cannot be disabled by EMP weapons or EMP Pulse general power
- **Hacker disable** — cannot be hacked or disabled by Black Lotus or Hackers
- **Hijack** — cannot be hijacked by the Hijacker unit
- **Vehicle snipe** — cannot be sniped by Jarmen Kell
- **Crew kill** — cannot be neutron-killed (Neutron Mines, Neutron Shells)
- **Conversion** — cannot be converted by the Defector unit
- **Leaflet Drop** — cannot be demoralized by the Leaflet Drop general power

These immunities are enforced via hardcoded `isSpawnedUnit()` checks in the engine, bypassing the protection registry entirely. They cover `Object::setDisabledUntil()`, `EMPUpdate`, `LeafletDropBehavior`, `SpecialAbilityUpdate`, and `ActionManager`.

### Stat Boosts

- **4x health** at spawn (max health quadrupled)
- **1.0x damage output** (full normal damage — spawned units hit as hard as regular units)
- **140% weapon range** via the engine's Search and Destroy bonus condition (same mechanism as the Strategy Center's battle plan)
- **1.5x base movement speed**

---

## 7. The Unlock & Progression System

### 29 Cross-Faction Unlock Groups

Units are organized into shared groups that unlock all three factions simultaneously:

**Auto-Unlocked (available from game start):**
- Shared_Barracks, Shared_CommandCenters, Shared_SupplyCenters, Shared_RifleInfantry

**Unit Groups (unlocked via Archipelago items):**
- **Shared_RocketInfantry** — Missile Defender, Tank Hunter, RPG Trooper, Tunnel Defender
- **Shared_InfantryVehicles** — 13 vehicles including Humvee, Technical, Battle Bus, Combat Bike
- **Shared_Tanks** — 10 tanks: Crusader, Paladin, Battle Master, Overlord (3 variants), Scorpion, Marauder, Light Tank
- **Shared_Artillery** — Tomahawk, Inferno Cannon, Nuke Launcher, Rocket Buggy, SCUD Launcher
- **Shared_PlaneTypeAircraft** — Aurora, Raptor, Stealth Fighter, MiG, Napalm Striker
- **Shared_ComanchesHelixes** — Comanche, Helix (4 sub-variants)
- **Shared_MachineGunVehicles** — Gattling Tank, Quad Cannon
- **Shared_MiscVehicles** — 13 specialized units including Avenger, Microwave Tank, ECM Tank, Dragon Tank, Bomb Trucks
- **Shared_MiscInfantry** — 19 special units: Colonel Burton, Pathfinder, Black Lotus, Jarmen Kell, Angry Mob, Hijacker, and more
- **Shared_Drones** — Battle, Guardian, Repair, Scout, and Spy drones
- **Shared_MiscUnits** — A-10, B-52, Cargo Planes, Battleship

**Building Groups:**
- **Shared_BaseDefenses** — 16 buildings: Patriot Battery, Gattling Cannon, Stinger Site, Tunnel Network, Bunker, Firebase, Walls, Demo Traps
- **Shared_AirFields** — USA and China Airfields
- **Shared_WarFactoriesArmsDealers** — War Factory, Arms Dealer, GLA Hole variants
- **Shared_StrategyBuildings** — Strategy Center, Palace
- **Shared_AltMoneyBuildings** — Supply Drop Zone, Internet Center, Black Market
- **Shared_Superweapons** — Particle Cannon, Nuclear Missile Launcher, SCUD Storm
- **Shared_MiscBuildings** — Detention Camp, Power Plants, Speaker Tower

**Upgrade Groups (7):**
- CaptureBuilding, Radar, Weapons, Infantry, Vehicles (14 upgrades), Aircraft, Mines

### Enemy Generals

Seven challenge generals serve as missions, each with defined threat profiles:

| General | Faction | Key Threats |
|---------|---------|-------------|
| Tank General | China | Overlord, Gattling Tank, Battle Master, Inferno Cannon |
| Air Force General | USA | Raptor, Aurora, Comanche, Pathfinder |
| Laser General | USA | Paladin, Avenger, Missile Defender |
| Superweapon General | USA | Tomahawk, Patriot Battery, Colonel Burton |
| Nuke General | China | Nuke Launcher, Overlord, Inferno Cannon |
| Stealth General | GLA | Stealth Fighter, Pathfinder, Jarmen Kell |
| Toxin General | GLA | Toxin Truck, Marauder, Rocket Buggy |

### Configurable Options

The mod supports Archipelago YAML seed options:
- **Game difficulty**: Easy / Medium / Hard
- **Clusters per map**: 1–12 (default 3)
- **Slots per cluster**: 1–8 (default 2)
- **Starting general**: Random or specific (per faction)
- **Include superweapons in logic**: Toggle
- **Unlock preset**: Default / Minimal / Chaos

---

## 8. Technical Foundation

### Engine Modifications

The mod builds on the **SuperHackers community source port** of C&C Generals: Zero Hour, modernized from the original Visual Studio 6 / C++98 codebase to **Visual Studio 2022 / C++20**. Key C++ modifications:

- **UnlockableCheckSpawner** (~4,400 lines) — The central spawned unit manager. Handles spawning, AI behavior, retreat mechanics, cluster retaliation, damage protection, and stealth detection.
- **ArchipelagoState** — Persistent progression state across missions. Tracks unlocked units, buildings, generals, completed checks, and bonus modifiers.
- **UnlockRegistry** — Loads and indexes all 29 unlock groups from INI configuration.
- **AIUpdate** — Modified to enforce command authority and guard mode overrides for spawned units.
- **Object** — Extended with spawned-unit damage tracing, kill tracking, and immunity enforcement.
- **EMPUpdate, LeafletDropBehavior, SpecialAbilityUpdate, ActionManager** — Hardcoded immunity bypasses for spawned units.

### Tooling

- **Data generation**: `archipelago_generate_ini.py`, `archipelago_generate_matchup_graph.py`
- **Name pipeline**: `archipelago_build_localized_name_map.py`, `archipelago_build_template_name_map.py`
- **Validation**: `archipelago_validate_ini.py`, `archipelago_run_checks.py`, `archipelago_audit_groups.py`
- **Bridge**: `archipelago_bridge_local.py` — Local sidecar for demo progression fixtures
- **Cluster tools**: `tools/cluster-editor` web-app submodule, `archipelago_cluster_selection.py`
- **Vendor management**: Sync with upstream Archipelago framework and SuperHackers source

### Runtime Profiles

Multiple validated runtime configurations for different testing scenarios:
- **reference-clean** — Known-good baseline, startup-safe
- **demo-playable** — Validated gameplay profile
- **demo-ai-stress** — AI stress testing profile
- **archipelago-bisect** — Controlled feature reintroduction
- **archipelago-current** — Current development candidate

### CI/CD

GitHub Actions workflows for:
- Continuous integration builds
- Archipelago data validation
- Pull request checks
- Replay verification
- Upstream sync automation

---

## 9. Current Status

### Working Now (Demonstrable)

- Full unlock registry with 29 cross-faction groups
- Spawned unit clusters at map waypoints with coordinated AI
- Two-tier leashing (defend radius + max chase radius)
- Retreat mechanics with speed boost, healing, and damage reduction
- Post-retreat cooldown preventing chase loops
- Cluster-wide coordinated retaliation
- 91-rule damage protection matrix with 7 categories
- Complete immunity to EMP, hacker, hijack, snipe, conversion, leaflet drop
- 4x HP, 140% weapon range, 1.5x movement speed for spawned units
- Stealth detection scanning
- No-collision ghosting between spawned units
- Command authority enforcement (spawned units ignore map scripts)
- Guard-without-pursuit preventing vanilla AI exploitation
- Artillery pre-deployment and fixed-range behavior
- Role-specific targeting (crushers, artillery, support)
- State persistence (completed checks saved across missions)
- Local demo mode with bridge fixtures for testing progression
- Runtime profile system for validated testing configurations

### In Progress

- AI behavior tuning (current branch — 43 commits of iterative fixes)
- Spawned unit combat balance refinement
- Protection matrix coverage expansion

### Not Yet Implemented

- **Archipelago network connection** — The bridge to the actual Archipelago server is not yet built. Current demo mode uses local fixture files.
- **Real cluster map data** — The web cluster editor exists, but committed coordinate/layout data still needs to be authored for all 8 maps
- **UI systems** — Archipelago menu, item tracker, logic tracker, mission select screen
- **Items & traps** — Production bonuses, cash items, airshow trap, money drain trap
- **AP world definition** — No `vendor/archipelago/overlay/worlds/generalszh` files are committed yet
- **`compute_player_strength()`** — Logic function to determine if the player has enough unlocked units to tackle a mission
- **Kill-based checks** — Currently only cluster defeat triggers checks; individual kill tracking is designed but not implemented
- **Matchup graph integration** — Unit effectiveness graph exists as data but isn't yet used in logic

---

## 10. Key Visual Moments for Demo Footage

These are the features that would look most impressive in gameplay footage:

1. **The Locked Roster** — Show the build menu with most units/buildings grayed out and locked. Only Rangers, Dozers, and basic buildings available.

2. **Item Arrival** — Show an unlock group being received and the build menu expanding. Suddenly tanks or aircraft become available.

3. **Cluster Discovery** — Pan to a map location where spawned enemy units are guarding a position. They sit idle at their guard positions until the player approaches.

4. **Cluster Retaliation** — Attack one unit in a cluster and watch the entire group respond. All units coordinate their attack on the aggressor.

5. **The Leash in Action** — Kite a spawned unit away from its guard position. Watch it hit the max chase radius and snap back into retreat — moving fast, healing, taking reduced damage.

6. **Post-Retreat Behavior** — After a unit retreats, approach it again. It fires defensively from position during the cooldown window instead of charging.

7. **Superweapon Immunity** — Fire a Particle Cannon or Nuclear Missile at a spawned cluster. Watch them survive with zero damage.

8. **EMP Immunity** — Drop an EMP on spawned units. They don't get disabled — they keep fighting.

9. **Artillery Behavior** — Show spawned Nuke Cannons or Inferno Cannons firing from their fixed positions. They never chase — they just bombard from range.

10. **Stealth Detection** — Approach a cluster with a stealthed unit (Jarmen Kell, Stealth Fighter). Watch the cluster detect and engage the cloaked unit.

11. **Cluster Kill → Check Complete** — Destroy an entire cluster and show the check being registered in the progression system.

12. **Cross-Faction Unlocks** — Show that receiving one item unlocks the equivalent units across all three factions simultaneously.

---

## 11. Development Journey Highlights

The current development branch (`fix/ai-behavior-and-item-changes`) represents 43 commits of intensive AI behavior work. Key milestones:

- **Root Cause #1**: Damage detection system was broken at spawn — the engine's body module returned `UINT_MAX` as a sentinel value for "no damage timestamp," causing all subsequent damage frames to be undetectable. Every spawned unit was effectively deaf to damage from frame 1.

- **Root Cause #2**: The vanilla guard AI's pursuit behavior created infinite loops. Units would chase targets out of guard radius, get pulled back, arrive at guard position, immediately re-acquire the target, and chase again forever. Fixed by switching to guard-without-pursuit mode and letting the spawner's retaliation system handle all offensive movement.

- **Root Cause #3**: Three independent retreat-chase loop sources were discovered in a single debugging session and fixed simultaneously. The final commit message title: *"eliminate all three retreat-chase loop sources."*

- **Protection Evolution**: The protection matrix grew from a few basic rules to 91 entries across 7 categories, driven by playtesting discoveries (e.g., Comanche helicopters could shred clusters, Spectre Gunships were not covered, MOAB needed protection).

- **Immunity Hardening**: Immunities evolved from protection-registry rules to hardcoded engine bypasses after discovering that some disable effects (EMP, hacker, leaflet drop) used code paths that skipped the protection system entirely.

---

*Historical note, updated April 25, 2026: this demo context still describes the AI-behavior milestone. Since then, the old Python cluster editor has been replaced by the `tools/cluster-editor` web-app submodule, the AP world skeleton and fixture slot-data path exist, the local bridge can round-trip mission/cluster runtime keys to AP numeric IDs, and runtime seeded mode can consume verified `Seed-Slot-Data.json`. `UnlockableChecksDemo.ini` is now explicit no-reference fallback/recovery content, not the seeded alpha path. Real AP network session integration and in-game seeded playtest smoke are still pending.*
