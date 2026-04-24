# Archipelago Mod AI Debug — Agent Context Transfer

## Task
Fix problems with the Archipelago mod for Command & Conquer Generals Zero Hour. The mod spawns AI that act like clustered guard groups that stick to one spot with mechanics that prevent players from easily exploiting them. Debug AI issues by reviewing the source code for inconsistencies and behaviors that don't match the spec below.

## Source Files to Find and Review
- **UnlockableCheckSpawner.cpp/.h** — All spawning, AI leashing, protection, damage tracing
- **UnlockableChecksDemo.ini** — Per-map config (radii, damage scalar, etc.)
- **ArchipelagoChallengeUnitProtection.ini** — 73 protection rules

These files need to be built using CMake as part of the project.

---

## Complete AI Behavior Spec

### Per-Map Configurable Parameters
| Parameter | Default | Example (TankGeneral) | Purpose |
|-----------|---------|----------------------|---------|
| DefendRadius | 350 | 375 | Soft leash — pull back when idle and outside this |
| MaxChaseRadius | 500 | 500 | Hard leash — ALWAYS pull back, even mid-combat |
| SpawnOffset | 600 | 700 | Inner ring distance from waypoint |
| SpawnOffsetSpread | 200 | 225 | Outer ring delta for radial placement |
| DamageOutputScalar | 1.0 | 0.1 | Damage multiplier (0.1 = spawned units deal 10% damage) |

### Two-Tier Leashing System

**Defend Radius (soft):** Units outside this radius retreat ONLY if they have no live target. They can still fight in place if engaged.

**MaxChase Radius (hard):** Units ALWAYS retreat when beyond this, even if actively attacking. Triggers hard-pull assistance after 1 second delay.

```
Retreat logic:
  if distance > MaxChaseRadius → hard pull (always retreat)
  else if distance > DefendRadius AND no live target → soft pull
```

**During retreat:**
- Speed boost: 2.0x normal
- Healing: 5% max HP per second
- Movement assist: 1.05x scalar, minimum 20 units/sec
- Ultra-accurate pathfinding enabled
- After 1 second delay, hard-pull drag kicks in (requires facing guard pos within ~37 degrees)
- Retreat complete when within 150 world units of guard position

### Threat Response (Anti-Kite Vision)

When a spawned unit takes damage:
- Vision and acquire radius temporarily elevated to **max(base, 500.0)** world units
- Duration: **0.5 seconds** per hit (extends with repeated damage)
- During retreat: reverts to base vision (prevents chase outside leash)

### Unit Placement Within Cluster

Units are placed using a **golden angle spiral** pattern:
- Inner dead-zone: spread * 0.12 (nothing spawns here)
- Outer boundary: spread * 0.70
- Angle per unit: golden angle (137.5 degrees) * slot index + random jitter (22%)
- Radial distance: sqrt distribution (more units near outer edge)

**Minimum unit separation:** max(54, spread * 0.20)

**Search phases** if placement fails (expanding radius):
- Phase 0: spread * 1.0 (1.30 for hard tier)
- Phase 1: spread * 1.15 (1.45 for hard)
- Phase 2: spread * 1.30 (1.65 for hard)
- Phase 3: spread * 1.45 (1.85 for hard)

### Combat Targeting

**Crushers** (tanks): Find nearest enemy infantry within acquire radius, attack-move. 3-second cooldown between commands.

**Support/Artillery**: Find nearest enemy combat unit within acquire radius. Special cases:
- ECM Tank: move-only command (no attack)
- Troop Crawler: direct attack command
- Inferno Cannons: 90 unit friendly-fire safety radius
- Nuke Cannons: 150 unit friendly-fire safety radius

### Team Assignment

Each cluster gets a dedicated team named `ArchipelagoCluster_{clusterId}`. All units in a cluster share one team, controlled by the enemy player.

### Protection Matrix (73 rules)

| Category | Multiplier | What it covers |
|----------|-----------|----------------|
| Superweapons | 0.0 (immune) | SCUD Storm, Particle Cannon, Neutron Missile |
| Fighters | 0.05 (95% reduction) | Raptor, Stealth Fighter, Aurora, MiG |
| Ground fields | 0.25 (75% reduction) | Toxin fields, Radiation fields |
| General powers | 0.02 (98% reduction) | Daisy Cutter, MOAB, EMP, Anthrax Bomb, Carpet Bomb, A-10 Strike, Artillery Barrage, Spectre Gunship, etc. |
| Special actions | Full immunity | Hijack, pilot snipe (Jarmen Kell), neutron crew kill, EMP disable, leaflet drop, Black Lotus hack, Defector conversion |

### Damage Trace System

Records every damage event on spawned units through a 4-stage pipeline:
1. **Begin** — captures source, weapon, special power, incoming damage
2. **Protection** — records which rule matched, multiplier applied, damage after scaling
3. **Finalize** — records actual damage dealt, HP before/after, max HP
4. **Bypass trace** — for damage applied outside normal `attemptDamage` path

Ring buffer of 64 most recent events for runtime inspection.

### Baseline HP Tracking

Each spawned unit's max HP is cached at spawn time for comparison in damage trace events and post-game analysis.

---

## Goals & Priorities

### P0: Core Identity — "Territorial Pack"
- Units anchor to a fixed guard point and always return
- Fight as a cluster (shared team), not as individuals
- Spawn in golden-angle spiral pattern
- Deal reduced damage via DamageOutputScalar — threat through numbers/durability, not burst DPS

### P1: Two-Tier Leash — "Sticky But Not Stupid"
- Soft leash (DefendRadius): retreat when no target, fight in place if engaged
- Hard leash (MaxChaseRadius): always retreat beyond this, even mid-combat, non-negotiable
- Retreat feels purposeful: speed boost, healing, movement assist, 1s delay before hard-pull drag, facing check

### P2: Anti-Exploit — "You Can't Cheese This"
- Anti-kite vision: damaged units get 500-range vision (0.5s per hit, extends)
- Vision reverts during retreat (prevents re-aggro outside leash)
- Protection matrix: superweapons immune, fighters 95% reduced, powers 98% reduced
- Special action immunity: hijack, snipe, hack, conversion, EMP all blocked
- Hard leash is unconditional

### P3: Combat Behavior — "Role-Appropriate Targeting"
- Crushers/tanks: prioritize infantry, attack-move, 3s cooldown
- Support/artillery: type-specific logic (ECM move-only, Troop Crawler direct attack)
- Friendly-fire safety radii (Inferno 90, Nuke Cannon 150)

### P4: Diagnostics — "Know What Happened"
- 4-stage damage trace pipeline with 64-event ring buffer
- Baseline HP caching at spawn time

---

## What To Do

1. Find and read UnlockableCheckSpawner.cpp/.h, UnlockableChecksDemo.ini, and ArchipelagoChallengeUnitProtection.ini
2. Review the code against this spec for inconsistencies
3. Identify any logic bugs that would cause:
   - Units not returning to guard position (leash failures)
   - Units chasing too far or not engaging at all
   - Protection rules not applying correctly
   - Cluster groups splitting apart or not fighting as a pack
   - Placement collisions or units spawning outside intended area
   - Targeting logic picking wrong targets or causing friendly fire
   - Damage trace events missing or recording incorrect data
4. Produce a prioritized list of issues found with code references
