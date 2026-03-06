# Generals Archipelago Logic & Implementation Guide

**Purpose**: Master design document for cluster difficulty, defender/spawnable unit filtering, defense/objective logic, UI, items, traps, and AP integration. Use this to guide implementation phases.

---

## Part 1: Defender & Spawnable Unit Rules

### 1.1 Single Source of Truth

**The defender list IS the spawnable unit list.** The matchup graph's defender nodes define what can appear in clusters. No separate spawn pool—defenders = spawnable.

### 1.2 Units Completely Excluded from Medium & Hard Clusters

These units must **never** appear as defenders in medium or hard clusters (and thus never spawn there):

| Category | Templates / Patterns |
|----------|----------------------|
| Elite / Utility | Black Lotus, Super Black Lotus, Supply Outposts, Troop Crawler, Terrorist, Saboteur, Hacker |
| Utility-based | Dozer, Worker, Supply Truck, Chinook, Cargo Plane, Radar Van, Scout Drone, Spy Drone, Repair Drone, Hijacker, Pilot |
| Chinooks | All Chinooks (except fully-loaded Battle Chinook in hard—see §1.6) |

**Implementation**: Add `cluster_exclude_templates` and `cluster_exclude_regexes` to `unit_matchup_archetypes.json`. Script filters defenders per cluster tier.

### 1.3 Infantry Defenders – Restricted

**Remove from defender list entirely** (not spawnable in any cluster):

- Most infantry **except**: Pathfinder, MiniGunner, Angry Mob, Bomb Truck (suicide, not infantry but included)

**Keep as defenders**: Pathfinder, MiniGunner, Angry Mob, Bomb Truck (and any other explicitly allowed).

**Implementation**: Replace broad `infantry_rifle` / `infantry_rocket` / `infantry_elite` defender inclusion with an **explicit allowlist** for infantry. All other infantry excluded.

### 1.4 Base Defenses

- **Medium clusters only**: Patriot Battery, Gatling Cannon, Stinger Site, Tunnel Network, Fire Base, Bunker
- **Exclude from all clusters**: Demo Trap, Advanced Demo Trap
- **Hard clusters**: No base defenses

**Implementation**: Base defenses only in medium defender pool. Remove Demo Trap from `defender_base_defense_force_include_regexes`; add to exclude.

### 1.5 Cluster Tier Unit Pools (Summary)

| Tier | Allowed Defenders |
|------|-------------------|
| **Easy** | Pathfinder, MiniGunner, Angry Mob, Bomb Truck; weak vehicles (Technical, Humvee); passive/utility (Dozer, Worker, Supply Truck—weight 1/3 of combat). No Chinooks. |
| **Medium** | Non-elite vehicles, tanks, artillery, helicopters, base defenses (no Demo Trap). Excludes all from §1.2. |
| **Hard** | Heavy tanks, air (Comanche, Raptor, etc.), loaded compositions (Battle Bus + 7 elite Tunnel Defenders + Jarmen Kell; Helix + rocket troopers; Battle Chinook + 8 elite Missile Defenders). No base defenses. No Chinooks except Battle Chinook (fully loaded). |

### 1.6 Hard Cluster Compositions

Compositions are **single spawn units** (one check = destroy the transport):

- **Battle Bus**: 7 elite Tunnel Defenders + Jarmen Kell inside (elite = same stat buffs as transport)
- **Helix**: All slots filled with elite rocket troopers
- **Battle Chinook**: 8 elite Missile Defenders

**Logic**: Destroying the transport grants the check. Contents are not separate checks.

### 1.7 Easy Cluster Weighting

Non-combat units (Dozer, Worker, Supply Truck, etc.): combined weight = **1/3** of combat units in easy pool. Ensures combat units dominate but some passive spawns exist.

---

## Part 2: Matchup Graph Refinements

### 2.1 Defender List = Spawnable List

- Ensure every potentially spawnable unit is a defender in the graph.
- Remove any defender that is not spawnable in any cluster tier.
- Add `cluster_tier` to defender metadata (easy / medium / hard) so the graph knows which tier each defender belongs to.
- **Not a script flag**—defender list is the canonical spawnable list.

### 2.2 Veterancy in Graph

Veterancy (Rank 1/2/3) must be **baked into the graph ratings**:

- Easy: Rank 1 → factor into existing weights
- Medium: Rank 2 → factor into weights
- Hard: Rank 3 → factor into weights

If not already present, add veterancy scaling to the weight calculation. No script flag—hardcoded in the rating logic. **Priority: sooner rather than later.**

### 2.3 Technical Soundness

- Refine graph relationships to be more technically sound and easier to consume for logic.
- Ensure weights account for: base stats, armor modifiers, veterancy, cluster stat scaling (HP/dmg mult).

---

## Part 3: Cluster Configuration & Tooling

### 3.1 Cluster Definition Tool

**Create a tool** for defining cluster positions:

- **Input**: Bitmap of the map + coordinate-based positioning
- **Output**: Developer-defined waypoints exportable into code/game
- **Use case**: Place cluster points on the map image; export waypoint names and coordinates for `UnlockableCheckSpawner` and slot data

**Suggested format**: JSON or INI with `{ "cluster_id": "Cluster_Near_1", "x": 123, "y": 456, "tier": "easy" }`

### 3.2 Configurable Units Per Cluster

- **YAML option**: `clusters_per_map` or `slots_per_cluster` (or both)
- **Defines**: Number of locations per mission = number of clusters × slots per cluster
- **Total locations** = 7 missions × (clusters × slots) + 7 mission completions + boss/victory

### 3.3 Random Cluster Selection

- Per map: N cluster positions defined (from tool)
- YAML option: how many clusters to use per map (e.g. 3 of 5)
- At seed gen: randomly select which clusters are active
- Active clusters define locations; inactive ones are not used
- Cluster positions from tool → hardcoded or baked into config

---

## Part 4: Defense & Objective Logic

### 4.1 Two Separate Concerns

1. **Defense**: Can the player survive several minutes to reach medium clusters?
2. **Objective (beat mission)**: Can the player defeat the enemy general and win? (Harder than just defending.)

### 4.2 Enemy General Threat Profiles (A1)

- **Hardcoded** per enemy general
- **Depends on game difficulty** (Easy / Medium / Hard) from Archipelago YAML
- Each general has a **static strength value** for defense and for objective
- Player has a **dynamic strength value** from unlocks
- Logic: `player_strength >= enemy_defense_strength` (for defense) and `player_strength >= enemy_objective_strength` (for mission win)

### 4.3 Explicit Unit Lists (D9)

Use **explicit unit lists** for defense requirements, not archetypes:

- Each enemy general → list of unit types they send
- Defense requirement: player must have counters for **all** threat types (D10)

### 4.4 Excluded from Logic (D10)

Do **not** count toward defense/objective strength:

- Upgrades
- Strategy buildings
- Money-making buildings (Black Market, Landing Drop Zone from USA, Internet Center)
- Super weapons (unless YAML option enabled)

**YAML option**: `include_superweapons_in_logic` — Include super weapons in "can beat mission" logic (default: false).

### 4.5 Super Weapon Limit

- **Player limit**: 1 super weapon (except Superweapon General → 2)
- Enforce in production/build logic and in item pool

---

## Part 5: Game Client Changes

### 5.1 Spawned Unit Detection Radius

- **Increase** detection radius of spawned units to be **higher than Nuke Cannon range**
- Prevents players from exploiting range to avoid aggro

### 5.2 Spawned Unit AI

- Fix AI of spawned units to reduce exploitable behavior
- Minimize strange pathing, idle behavior, or easy kiting

### 5.3 UnlockableChecksDemo.ini Fallback (F14)

- Keep as fallback until project nears completion
- When fallback is used: **log console message** (e.g. "Using UnlockableChecksDemo.ini fallback—no slot data")

---

## Part 6: Archipelago Menu & UI

### 6.1 New Single-Player Menu

Add a new menu under Single Player for the Archipelago version:

- **Archipelago** submenu or main entry
- Contains all Archipelago-specific UI

### 6.2 Menu Contents

| Section | Purpose |
|---------|---------|
| **Connect** | Connect to Archipelago server (address, slot, password) |
| **Item Tracker** | Per-general view of items (unlocks). Categorized by buildings and the units/upgrades they spawn. **Icons instead of text** when possible. |
| **Logic Tracker** | Per mission: map bitmap with hoverable cluster markers. Shows which clusters are reachable and whether the mission is beatable. **Icons over text** when applicable. |
| **Mission Select** | Pick which general mission to fight + pick your own general. Optional: integrate logic tracker (hover mission → show bitmap + logic overlay). |

### 6.3 Logic Tracker Map Display

- Use map bitmap as background
- Overlay hoverable objects at cluster positions
- Show reachable (green?) vs unreachable (red/gray?)
- Show "mission beatable" indicator

---

## Part 7: New Items & Traps

### 7.1 Unlockable Items

| Item | Effect |
|------|--------|
| Production bonus upgrade | Faster build/production |
| Increased starting cash | More money at mission start |
| Temporary bonus cash | One-time cash grant on mission start OR at moment of receiving (if in mission) |

### 7.2 Traps (Negative/Fun Items)

| Trap | Effect |
|------|--------|
| **Airshow** | Several King Raptors fly over map, no damage. Repeating "Let's give them an airshow" voice line. Slightly annoying. |
| **Money subtract** | One-time money reduction at mission start or when received (if in mission). Voice line confirmation. |
| **Random voice line sequence** | Funny random voice line sequence with slight overlap. |

---

## Part 8: Archipelago YAML Options

### 8.1 Options to Implement

| Option | Type | Description |
|--------|------|-------------|
| `game_difficulty` | Choice | Easy / Medium / Hard. Affects enemy general strength, wave composition. |
| `clusters_per_map` | Range | Number of clusters per mission (or number to randomly select). |
| `slots_per_cluster` | Range | Units/locations per cluster. |
| `starting_general` | Choice | Random or specific. USA, China, GLA. (B5: provision for both) |
| `include_superweapons_in_logic` | Toggle | Whether super weapons count toward "can beat mission". Default: false. |
| `unlock_preset` | Choice | default / minimal / chaos (existing). |

### 8.2 YAML Template

Create `options.yaml` or extend `options_schema.yaml` for full AP world implementation.

---

## Part 9: Generals & Missions (B4, B5)

### 9.1 Seven Missions

- One mission per **enemy** general
- Excluded as enemies: Demolition, Infantry (no challenge missions in vanilla—SuperHackers may add later; **keep provisions**)
- **Boss general** is separate (8th encounter, after 7 mission completions)

### 9.2 Player General

- **YAML**: Allow random or specific general selection
- **Code**: Support both modes (B5)
- Each general has a **defined unit/building set** (for item tracker and logic)
- Reference: PlayerTemplate / FactionUnit / FactionBuilding per general

---

## Part 10: Implementation Phases (F13)

### Phase A: Graph & Defender Overhaul

1. Update `unit_matchup_archetypes.json`:
   - `cluster_exclude_templates`, `cluster_exclude_regexes`
   - Infantry allowlist (Pathfinder, MiniGunner, Angry Mob, Bomb Truck only)
   - Base defense: medium only, exclude Demo Trap
   - Per-tier defender pools (easy / medium / hard)
2. Ensure defender list = spawnable list; add cluster tier to defenders.
3. Bake veterancy into graph ratings.
4. Refine graph for logic consumption.

### Phase B: Cluster Tool & Config

1. Build cluster definition tool (bitmap + coordinates → waypoints).
2. Add `clusters_per_map`, `slots_per_cluster` to config.
3. Implement random cluster selection at seed gen.

### Phase C: Defense & Objective Logic

1. Define enemy general threat profiles (explicit unit lists).
2. Assign static strength values per difficulty.
3. Implement `can_defend` and `can_beat_mission` with dynamic player strength.
4. Add super weapon logic option.

### Phase D: Game Client

1. Increase spawned unit detection radius (> Nuke Cannon).
2. Fix spawned unit AI.
3. Super weapon limit (1 default, 2 for Superweapon General).
4. Fallback console message for UnlockableChecksDemo.ini.

### Phase E: Menu & UI

1. Archipelago submenu under Single Player.
2. Connect UI.
3. Item tracker (per general, icons, building/unit categorization).
4. Logic tracker (map bitmap, cluster overlay, reachability).
5. Mission select with optional logic hover.

### Phase F: Items & Traps

1. Production bonus, starting cash, temporary cash items.
2. Airshow trap.
3. Money subtract trap.
4. Random voice line trap.

### Phase G: AP World & YAML

1. Full YAML options template.
2. Python world implementation.
3. Slot data format for spawn assignments.

---

## Part 11: Additional Suggestions

### Not Yet Considered

- **Death link** support (if desired for multiworld).
- **Hint system** for locations (optional).
- **Seed hash display** in menu for verification.
- **Reconnect** handling when connection drops.
- **Item link** (receive items for other games).
- **Accessibility** options (e.g. larger UI, colorblind modes).
- **Save sync** with Archipelago (ensure location checks persist across sessions).
- **Map-specific cluster presets** (some maps may have different cluster layouts).
- **Validation script** that checks: defender list ⊆ spawnable, all spawnable in graph, no excluded units in wrong tiers.

---

## Quick Reference: Exclusions

| Excluded From | Units |
|---------------|-------|
| **All clusters** | Black Lotus, Super Black Lotus, Supply Outposts, Troop Crawler, Terrorist, Saboteur, Hacker, Chinook (except Battle Chinook in hard), Demo Trap, Advanced Demo Trap |
| **Defender list (not spawnable)** | Most infantry except Pathfinder, MiniGunner, Angry Mob, Bomb Truck |
| **Medium & Hard** | All of above + utility (Dozer, Worker, Supply Truck, etc.) |
| **Hard** | Base defenses |
| **Easy** | Chinooks |

---

## Agent Guide Answers Summary

| ID | Answer |
|----|--------|
| A1 | Hardcoded threat profiles; difficulty (Easy/Medium/Hard) from YAML; static strength per general; dynamic player strength |
| A2 | Defense = survive to reach medium clusters; Objective = beat enemy general (harder than defending) |
| A3 | Cluster positions from tool → hardcoded; random cluster selection; YAML defines # clusters → # locations |
| B4 | Demo/Infantry not in 7; SuperHackers may add—keep provisions; Boss separate |
| B5 | Provision for random or specific general; each general has defined unit/building set |
| C6 | No Chinooks except Battle Chinook (hard); non-combat weight = 1/3 of combat in easy |
| C7 | Compositions = destroy transport; elite = same stat buffs as transport |
| C8 | No base defenses on hard |
| D9 | Explicit unit lists |
| D10 | Counters for all; exclude upgrades, strategy, money buildings, super weapons (unless YAML) |
| E11 | Veterancy hardcoded in graph; sooner rather than later |
| E12 | Defender list = spawnable; not a script flag |
| F13 | Phase A (graph) first |
| F14 | Keep fallback; console message when used |

---

## Implementation TODO

For a consolidated checklist of prompt requirements and Agent Guide answers (including Phase E/F and open items), see **[Archipelago-Implementation-Todo.md](Archipelago-Implementation-Todo.md)**.

For context transfer and agent assignments, see **[ARCHIPELAGO_CONTEXT_INDEX.md](ARCHIPELAGO_CONTEXT_INDEX.md)**.

---

*Document version: 1.0. Update as implementation progresses.*
