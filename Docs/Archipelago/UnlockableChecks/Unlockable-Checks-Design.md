# Unlockable Checks Design Document

**Purpose**: Define how units/buildings/upgrades are unlocked by completing challenge missions and defeating specific units/buildings within those missions.

**Requirements**:
- Unlock by finishing every combination of general × challenge mission
- Unlock by defeating certain units/buildings within each mission
- Highly flexible, modular, future-proof
- Easy to change without code edits where possible

---

## 1. Project Progress Reevaluation

### Completed
| Area | Status | Notes |
|------|--------|------|
| UnlockRegistry | Done | INI parsing, groups, AlwaysUnlocked, ArchipelagoSettings |
| ArchipelagoState | Done | Unlock sets, markLocationComplete, save/load |
| Production/Build hooks | Done | ProductionUpdate, BuildAssistant block locked templates |
| UI lock overlay | Done | ControlBarCommand, ArchipelagoLock image |
| Location completion | Done | ScoreScreen marks location on mission win |
| General selection | Done | ChallengeMenu restricts to unlocked generals |
| Dynamic config | Done | groups.json, presets.json, archipelago_generate_ini.py |
| Upstream sync | Done | ../Operations/SuperHackers-Upstream-Sync.md, sync scripts, workflow |

### Gaps (Addressed by This Design)
| Area | Status |
|------|--------|
| **Kill-based checks** | Not implemented – no tracking of "defeat X unit type in mission Y" |
| **Check→unlock mapping** | Not implemented – no config linking checks to groups |
| **Mission completion→unlock** | Partial – markLocationComplete exists but doesn't trigger unlocks |
| **Archipelago client** | Not implemented (external Python) |

---

## 2. Check Types (Two Axes)

### Axis A: Completion Triggers
1. **Mission complete** – Win the mission (general G, mission M)
2. **Kill check** – Defeat at least N instances of template T in mission (G, M)

### Axis B: What Gets Unlocked
1. **Group** – Unlock entire UnlockGroup (e.g. Shared_Tanks)
2. **General** – Unlock a general for selection
3. **Single template** – Unlock one unit/building/upgrade

---

## 3. Creative Solution Space

### Solution 1: Config-Driven Check Registry (Recommended)
**Idea**: `Data/Archipelago/checks.json` defines all checks. Game loads it, evaluates during play, unlocks on satisfaction.

```json
{
  "checks": [
    {
      "id": "usa_airforce_mission1",
      "type": "mission_complete",
      "general": 0,
      "mission": 1,
      "rewards": ["group:Shared_Barracks"]
    },
    {
      "id": "china_tank_mission2_kill_overlord",
      "type": "kill",
      "general": 3,
      "mission": 2,
      "template": "ChinaOverlord",
      "count": 1,
      "rewards": ["group:Shared_Tanks"]
    }
  ]
}
```

**Pros**: Fully data-driven, no code for new checks. **Cons**: Need parser, validation.

---

### Solution 2: INI Block Extension
**Idea**: Extend Archipelago.ini with `UnlockCheck` blocks.

```ini
UnlockCheck MissionComplete_USA_AirForce_01
    Type = MissionComplete
    General = 0
    Mission = 1
    RewardGroup = Shared_Barracks
End

UnlockCheck Kill_China_Tank_02_Overlord
    Type = Kill
    General = 3
    Mission = 2
    Template = ChinaOverlord
    Count = 1
    RewardGroup = Shared_Tanks
End
```

**Pros**: Consistent with existing INI style. **Cons**: Less flexible for complex conditions.

---

### Solution 3: Hybrid – Checks in JSON, Rewards Reference INI Groups
**Idea**: Checks defined in JSON; rewards reference existing UnlockGroup names. Single source of truth for groups.

---

### Solution 4: Script-Based (Map Scripts)
**Idea**: Map scripts (e.g. Map.ini or script actions) call `ArchipelagoCheckComplete(checkId)` when conditions are met.

**Pros**: Per-map control. **Cons**: Requires editing every map, not centralized.

---

### Solution 5: Event Listener Architecture
**Idea**: `ArchipelagoCheckEvaluator` subscribes to events: `onMissionComplete`, `onObjectDestroyed`. Evaluates all checks, grants rewards.

**Pros**: Decoupled, extensible. **Cons**: More moving parts.

---

### Solution 6: ScoreKeeper Integration
**Idea**: Hook into `ScoreKeeper::addObjectDestroyed`. When local player destroys object, notify ArchipelagoCheckEvaluator with (templateName, missionContext).

**Pros**: Reuses existing kill tracking. **Cons**: ScoreKeeper is per-player; need mission context.

---

### Solution 7: Object::scoreTheKill Hook
**Idea**: In `Object::scoreTheKill`, after `addObjectDestroyed`, call `TheArchipelagoCheckEvaluator->onKill(controller, victim)`.

**Pros**: Single choke point for all kills. **Cons**: Adds dependency in hot path.

---

### Solution 8: Per-Mission Check Definitions
**Idea**: Each mission (or campaign) has an optional `ArchipelagoChecks.ini` in its map folder listing which kills matter for that mission.

**Pros**: Map authors control checks. **Cons**: Scattered config, harder to audit.

---

### Solution 9: Template Tags / KindOf
**Idea**: Mark templates with `ArchipelagoCheck = OverlordKill` in INI. When any such unit is killed, check fires.

**Pros**: No separate check list. **Cons**: Pollutes game INI, less explicit.

---

### Solution 10: Layered Unlock Modes
**Idea**: Support multiple "modes": `mission_only` (current), `mission_and_kills`, `kills_only`. Preset selects mode.

**Pros**: Backward compatible, optional complexity.

---

### Solution 11: Weighted / Progressive Unlocks
**Idea**: Each check has a "weight" or "tier". Completing N checks of tier T unlocks tier T rewards. Allows "defeat any 5 enemy tanks across all missions" style goals.

**Pros**: Flexible, encourages variety. **Cons**: More complex to configure.

---

### Solution 12: Map Script Callbacks
**Idea**: Map scripts can call `ScriptAction` like `ArchipelagoGrantCheck("kill_overlord_china_02")` when a script detects an Overlord death. Map author controls trigger.

**Pros**: Full control per map. **Cons**: Requires script engine support, map edits.

---

### Solution 13: Event Sink / Observer Pattern
**Idea**: `ArchipelagoEventSink` interface. Any system can `TheArchipelagoEvents->fire("kill", victimTemplate, killerPlayer)`. Evaluator subscribes.

**Pros**: Maximum decoupling. **Cons**: Indirection, debugging harder.

---

### Solution 14: Template Inheritance for Kill Matching
**Idea**: When matching victim, use `ThingTemplate::isEquivalentTo()` or `isKindOf()` so killing "ChinaOverlord" also counts "Tank_ChinaOverlord", "Nuke_ChinaOverlord".

**Pros**: Fewer template entries in config. **Cons**: May over-match (e.g. civilian variant).

---

### Solution 15: Check Dependencies (Prerequisites)
**Idea**: Checks can have `requires: ["mission_0_1"]`. Kill check only active after mission 1 complete.

**Pros**: Logical ordering (e.g. "kill in mission 2" implies mission 1 done). **Cons**: More config complexity.

---

### Comparison Matrix

| Solution | Config-driven | No code for new checks | Kill tracking | Mission context | Complexity |
|----------|---------------|------------------------|---------------|-----------------|------------|
| 1 Check Registry | ✓ | ✓ | ✓ | ✓ | Medium |
| 2 INI blocks | ✓ | ✓ | ✓ | ✓ | Low |
| 4 Map scripts | Partial | ✗ | ✓ | ✓ | High |
| 7 scoreTheKill hook | - | - | ✓ | ✓ | Low |
| 11 Weighted | ✓ | ✓ | ✓ | ✓ | High |
| 14 Template inheritance | ✓ | ✓ | ✓ | ✓ | Medium |

---

## 4. Recommended Architecture (Modular & Future-Proof)

### 4.1 Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    ArchipelagoCheckRegistry                       │
│  - Loads checks from Data/Archipelago/checks.json                 │
│  - Maps check IDs to conditions + rewards                         │
│  - Validates against UnlockRegistry (reward groups exist)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ArchipelagoCheckEvaluator                       │
│  - Tracks: completed checks, kills-per-mission (in-memory)       │
│  - Subscribes: onMissionComplete, onKill                          │
│  - Evaluates checks, calls ArchipelagoState::unlockGroup()        │
│  - Persists completed check IDs in ArchipelagoState.json          │
└─────────────────────────────────────────────────────────────────┘
                              ▲
         ┌────────────────────┼────────────────────┐
         │                    │                    │
┌────────┴────────┐  ┌────────┴────────┐  ┌────────┴────────┐
│  ScoreScreen    │  │ Object::       │  │  (Future)       │
│  on mission win │  │ scoreTheKill   │  │  Script actions │
└─────────────────┘  └────────────────┘  └────────────────┘
```

### 4.2 Data Model: checks.json

```json
{
  "version": 1,
  "checks": [
    {
      "id": "mission_usa_af_1",
      "type": "mission_complete",
      "general": 0,
      "mission": 1,
      "rewards": ["group:Shared_Barracks"]
    },
    {
      "id": "kill_usa_af_1_ranger",
      "type": "kill",
      "general": 0,
      "mission": 1,
      "templates": ["AmericaInfantryRanger", "AirF_AmericaInfantryRanger"],
      "count": 3,
      "rewards": ["group:Shared_RifleInfantry"]
    },
    {
      "id": "kill_china_tank_2_overlord",
      "type": "kill",
      "general": 3,
      "mission": 2,
      "templates": ["ChinaOverlord", "Tank_ChinaOverlord"],
      "count": 1,
      "rewards": ["template:ChinaOverlordGattlingCannon"]
    }
  ],
  "presets": {
    "default": { "enabled_checks": ["mission_*", "kill_*"] },
    "mission_only": { "enabled_checks": ["mission_*"] },
    "kills_only": { "enabled_checks": ["kill_*"] }
  }
}
```

**Design choices**:
- `templates`: List to support base + general-prefixed names (e.g. AmericaInfantryRanger, AirF_AmericaInfantryRanger)
- `count`: Minimum kills required (1 = "defeat at least one")
- `rewards`: `group:X` or `template:X` or `general:N`
- `presets`: Allow disabling check types without editing checks

### 4.3 Kill Matching Logic

When `scoreTheKill(victim)` is called:
1. Get victim template name: `victim->getTemplate()->getName()`
2. Resolve to base name (strip general prefix) for matching
3. Get current mission context: `TheCampaignManager->getCurrentMissionNumber()`, `mapPlayerTemplateToGeneralIndex()`
4. For each active kill check with matching (general, mission):
   - If victim template matches (exact or base), increment kill count
   - If count >= required, mark check complete, grant rewards

### 4.4 Mission Context

- **Challenge campaign**: `TheCampaignManager->getCurrentCampaign()`, `getCurrentMissionNumber()`, `TheChallengeGenerals->getCurrentPlayerTemplateNum()` → general index
- **locationId** = `generalIndex * 10 + missionNumber` (existing formula)
- **Kill checks** use same (general, mission) to scope

### 4.5 Persistence

- **ArchipelagoState** extends: `m_completedChecks: set<string>` (check IDs)
- On check complete: add to set, unlock rewards, save
- On load: completed checks stay completed; no re-evaluation

---

## 5. Implementation Phases

### Phase 1: Foundation (No New Unlocks)
- [ ] Add `ArchipelagoCheckRegistry` – load checks.json, validate
- [ ] Add `ArchipelagoCheckEvaluator` – stub, no hooks yet
- [ ] Extend ArchipelagoState with `m_completedChecks`, `markCheckComplete(id)`, `isCheckComplete(id)`
- [ ] Script: `archipelago_validate_checks.py` – validate checks.json against groups.json

### Phase 2: Mission-Complete Checks
- [ ] In ScoreScreen (on victory): call `Evaluator->evaluateMissionComplete(generalIndex, missionNumber)`
- [ ] Evaluator finds matching checks, grants rewards, marks complete
- [ ] Wire mission_complete checks to unlock groups

### Phase 3: Kill Checks
- [ ] In `Object::scoreTheKill`: call `Evaluator->onKill(killerPlayer, victim)` when in challenge campaign
- [ ] Evaluator: get victim template, current (general, mission), increment per-check counters
- [ ] When count reached: mark complete, grant rewards
- [ ] In-memory kill counts reset on mission load (not persisted across missions)

### Phase 4: Config & Tooling
- [ ] `checks.json` schema + validation
- [ ] Generator: optional `--checks` to merge checks into build
- [ ] Docs: how to add new checks, template naming

### Phase 5: Polish
- [ ] In-game UI: show "Check complete: Defeated 3 Rangers" toast
- [ ] Debug commands: `ap_check_status`, `ap_complete_check <id>`
- [ ] Preset support: mission_only vs mission_and_kills

---

## 6. Robustness & Edge Cases

| Case | Handling |
|------|----------|
| checks.json missing | No checks, no crashes |
| Invalid check (bad group ref) | Validation script fails; game logs warning, skips |
| Kill in skirmish/multiplayer | Evaluator checks `isChallengeCampaign()` before processing |
| Mission number 0 | Treat as invalid or training; document convention |
| Template name with general prefix | Match against `templates` list; support `*_AmericaInfantryRanger` pattern |
| Same check satisfied twice | `isCheckComplete` guards; no double unlock |
| Save/load mid-mission | Kill counts in-memory only; completed checks persisted |

---

## 7. Flexibility Hooks

### 7.1 Adding New Check Types
- Evaluator uses `type` field: `mission_complete`, `kill`, (future: `capture`, `survive_duration`)
- New type = new handler in Evaluator, no changes to core

### 7.2 Adding New Reward Types
- `group:X`, `template:X`, `general:N` – extend reward parser
- Future: `money_bonus`, `starting_unit`, etc.

### 7.3 Per-Preset Check Sets
- `presets.default.enabled_checks`: `["mission_*", "kill_*"]` – wildcard support
- Or explicit list: `["mission_usa_af_1", "kill_china_tank_2_overlord"]`

### 7.4 Map-Specific Overrides
- Optional: `Maps/CHI02/ArchipelagoChecks.ini` appends checks for that map only
- Merged at load; allows map authors to add checks without editing central config

---

## 8. File Layout

```
Data/Archipelago/
  checks.json           # Check definitions (new)
  checks_schema.json    # Optional JSON schema
  groups.json           # (existing)
  presets.json          # (existing) + optional check preset
  always_unlocked.json  # (existing)

scripts/
  archipelago_validate_checks.py   # Validate checks.json
  archipelago_generate_ini.py      # (existing) optionally embed check metadata
```

---

## 9. Example checks.json (Starter Set)

```json
{
  "version": 1,
  "checks": [
    {
      "id": "mission_0_1",
      "type": "mission_complete",
      "general": 0,
      "mission": 1,
      "rewards": ["group:Shared_Barracks"]
    },
    {
      "id": "mission_0_2",
      "type": "mission_complete",
      "general": 0,
      "mission": 2,
      "rewards": ["group:Shared_CommandCenters"]
    },
    {
      "id": "kill_0_1_ranger",
      "type": "kill",
      "general": 0,
      "mission": 1,
      "templates": ["AmericaInfantryRanger"],
      "count": 1,
      "rewards": ["group:Shared_RifleInfantry"]
    }
  ]
}
```

---

## 10. Summary

| Aspect | Approach |
|--------|----------|
| **Config** | JSON (checks.json) – flexible, toolable |
| **Kill hook** | Object::scoreTheKill → Evaluator::onKill |
| **Mission hook** | ScoreScreen (victory) → Evaluator::evaluateMissionComplete |
| **Rewards** | Reference UnlockRegistry groups; ArchipelagoState::unlockGroup |
| **Persistence** | Completed check IDs in ArchipelagoState.json |
| **Modularity** | Check types + reward types extensible without core changes |
| **Validation** | Script validates checks against groups before use |
