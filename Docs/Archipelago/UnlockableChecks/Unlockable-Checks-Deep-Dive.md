# Unlockable Checks: Deep Dive on Each Approach

**Purpose**: Detailed implementation analysis, pros/cons, and manual requirements for each of the 15 approaches to implementing unlockable checks (mission completion + kill-based unlocks).

---

## Table of Contents
1. [Solution 1: Config-Driven Check Registry](#solution-1-config-driven-check-registry)
2. [Solution 2: INI Block Extension](#solution-2-ini-block-extension)
3. [Solution 3: Hybrid (JSON Checks, INI Rewards)](#solution-3-hybrid-json-checks-ini-rewards)
4. [Solution 4: Script-Based (Map Scripts)](#solution-4-script-based-map-scripts)
5. [Solution 5: Event Listener Architecture](#solution-5-event-listener-architecture)
6. [Solution 6: ScoreKeeper Integration](#solution-6-scorekeeper-integration)
7. [Solution 7: Object::scoreTheKill Hook](#solution-7-objectscorethekill-hook)
8. [Solution 8: Per-Mission Check Definitions](#solution-8-per-mission-check-definitions)
9. [Solution 9: Template Tags / KindOf](#solution-9-template-tags--kindof)
10. [Solution 10: Layered Unlock Modes](#solution-10-layered-unlock-modes)
11. [Solution 11: Weighted / Progressive Unlocks](#solution-11-weighted--progressive-unlocks)
12. [Solution 12: Map Script Callbacks](#solution-12-map-script-callbacks)
13. [Solution 13: Event Sink / Observer Pattern](#solution-13-event-sink--observer-pattern)
14. [Solution 14: Template Inheritance for Kill Matching](#solution-14-template-inheritance-for-kill-matching)
15. [Solution 15: Check Dependencies (Prerequisites)](#solution-15-check-dependencies-prerequisites)
16. [Summary Comparison Table](#summary-comparison-table)

---

## Solution 1: Config-Driven Check Registry

### Exact Implementation

**1. New files**
- `Data/Archipelago/checks.json` – JSON schema with `checks`, `checks[].id`, `checks[].type`, `checks[].general`, `checks[].mission`, `checks[].templates`, `checks[].count`, `checks[].rewards`
- `GeneralsMD/Code/GameEngine/Include/GameLogic/ArchipelagoCheckRegistry.h` – class with `loadFromFile()`, `getChecksForMission(general, mission)`, `getCheckById(id)`
- `GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoCheckRegistry.cpp` – JSON parsing (manual or use a lightweight JSON lib; game may already have one in Dependencies)

**2. JSON parsing**
- Game uses `FileSystem` to read files. Check if `vcpkg.json` or `Dependencies` includes `nlohmann/json` or similar. If not: hand-roll a minimal parser for the known schema (avoid heavy deps) or use a header-only JSON lib.
- Parse path: `Data/Archipelago/checks.json` or `Data/INI/ArchipelagoChecks.json` (if you want INI dir). Load in `ArchipelagoCheckRegistry::init()` or `UnlockRegistry::init()`.

**3. Registry logic**
```cpp
struct ArchipelagoCheck {
  AsciiString id;
  std::string type;  // "mission_complete", "kill"
  Int general, mission;
  std::vector<AsciiString> templates;  // for kill type
  Int count;
  std::vector<AsciiString> rewards;    // "group:X", "template:X", "general:N"
};
std::vector<ArchipelagoCheck> m_checks;
std::map<std::pair<Int,Int>, std::vector<ArchipelagoCheck*>> m_checksByMission;
```

**4. Integration**
- `ArchipelagoCheckEvaluator` (new class) holds `ArchipelagoCheckRegistry*`, `ArchipelagoState*`, `UnlockRegistry*`
- On mission win: `Evaluator->evaluateMissionComplete(generalIndex, missionNumber)`
- On kill: `Evaluator->onKill(killerPlayer, victim)` – called from `Object::scoreTheKill`
- Evaluator: for each matching check, if not complete, increment (kill) or grant (mission complete), then `ArchipelagoState->markCheckComplete(id)`, `unlockGroup()` etc.

**5. Persistence**
- `ArchipelagoState::m_completedChecks` (std::set<AsciiString>) – add to JSON save/load

### Pros
- Fully data-driven; add new checks by editing JSON only
- No recompile for new checks
- Easy to validate with Python script
- Fits existing Data/Archipelago pattern

### Cons
- Requires JSON parsing in C++ (no built-in in game)
- Validation script must stay in sync with schema
- Schema changes require code + schema update

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Create checks.json** | Write `Data/Archipelago/checks.json` with all your check definitions. Use the schema from Unlockable-Checks-Design.md. Example: `{"id":"mission_0_1","type":"mission_complete","general":0,"mission":1,"rewards":["group:Shared_Barracks"]}` |
| **Add JSON dependency** | If game has no JSON lib: add `nlohmann/json` via vcpkg (`vcpkg.json`) or use a minimal single-header parser. See [vcpkg.json](vcpkg.json) for existing deps. |
| **Populate check matrix** | Design which units/buildings to require per mission. Reference `Data/Archipelago/reference/archipelago_template_display_names.json` and `archipelago_audit_groups.py` output for template names. |
| **Validate schema** | Run `archipelago_validate_checks.py` (you create this) before each merge to catch typos or invalid group refs. |
| **Document check IDs** | Maintain a list of check IDs for debug commands (`ap_complete_check <id>`) and for players who want to know what they've done. |

**Wiki/External Research**: [GeneralsWiki Asset/GameDesign](https://github.com/TheSuperHackers/GeneralsWiki/tree/main/Asset/GameDesign) – INI and game data docs. For JSON: no Generals-specific docs; use standard JSON schema.

---

## Solution 2: INI Block Extension

### Exact Implementation

**1. Extend Archipelago.ini**
- Add `UnlockCheck` block parsing in `UnlockRegistry::loadFromStream()` (same pattern as `UnlockGroup`, `AlwaysUnlocked`, `ArchipelagoSettings`).
- Parse: `UnlockCheck <id>`, `Type = MissionComplete`, `General = 0`, `Mission = 1`, `RewardGroup = Shared_Barracks`, `End`
- For kill: `Type = Kill`, `Template = ChinaOverlord`, `Count = 1`, `RewardGroup = Shared_Tanks`

**2. Data structure**
```cpp
struct UnlockCheck {
  AsciiString id;
  AsciiString type;
  Int general, mission;
  std::vector<AsciiString> templates;
  Int count;
  std::vector<AsciiString> rewards;
};
std::vector<UnlockCheck> m_unlockChecks;
```

**3. Generator integration**
- Extend `archipelago_generate_ini.py` to read `checks.json` (or a new `checks.ini`) and emit `UnlockCheck` blocks into `Archipelago.ini`. So source of truth stays JSON; INI is generated.

**4. Evaluator**
- Same as Solution 1: `ArchipelagoCheckEvaluator` subscribes to mission complete + kill.

### Pros
- Consistent with existing UnlockGroup/AlwaysUnlocked format
- No new file format; everything in one INI
- Generator can produce INI from JSON; best of both worlds

### Cons
- INI is less flexible for nested structures (e.g. multiple rewards, template lists)
- Multi-template kill checks need `Template = A B C` or repeated `Template` lines – parser must support

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Define checks in config** | Either: (a) Edit `checks.json` and let generator produce INI, or (b) Edit `Archipelago.ini` directly if you skip generator. Prefer (a) for consistency. |
| **Generator changes** | Add `--checks` to `archipelago_generate_ini.py` to read `Data/Archipelago/checks.json` and append `UnlockCheck` blocks. Ensure `scripts/archipelago_run_checks.py` validates generated output. |
| **INI format** | If you use repeated `Template = X` lines, ensure UnlockRegistry parser handles it (e.g. append to `templates` vector). |
| **CMake** | Ensure generator runs before build so `Archipelago.ini` includes checks. |

**Wiki/External Research**: [GeneralsWiki Asset/GameDesign/ini](https://github.com/TheSuperHackers/GeneralsWiki/tree/main/Asset/GameDesign) – INI structure. [ini-linter.md](Wiki/Asset/GameDesign/ini/ini-linter.md) – ZeroSyntax VSCode extension for INI validation.

---

## Solution 3: Hybrid (JSON Checks, INI Rewards)

### Exact Implementation

- Same as Solution 1, but rewards *only* reference existing `UnlockGroup` names from `Archipelago.ini`. No `template:X` or `general:N` in rewards – only `group:X`.
- Validator: `archipelago_validate_checks.py` ensures every `rewards` entry matches a group in `groups.json` / `UnlockRegistry`.

### Pros
- Single source of truth for groups (INI)
- Checks stay flexible (JSON)
- Simpler reward handling

### Cons
- Cannot reward a single template or general without adding a group

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Create groups for single rewards** | If you want to reward "unlock ChinaOverlordGattlingCannon only", add a group like `Upgrade_OverlordGattling` with that one template. |
| **Keep groups.json in sync** | Any new reward target must exist as a group. Run `archipelago_validate_checks.py` in CI. |

---

## Solution 4: Script-Based (Map Scripts)

### Exact Implementation

**1. Scripts location**
- Scripts are embedded in the .map file (binary DataChunk format), not in map.ini. They are created in WorldBuilder and saved with the map.
- `ScriptList` is parsed from `PlayerScriptsList` when the map loads.

**2. New ScriptAction**
- Add `ARCHIPELAGO_GRANT_CHECK` to `ScriptAction` enum in `Scripts.h`.
- In `ScriptEngine.cpp`: add template for `ARCHIPELAGO_GRANT_CHECK` with `m_internalName = "ARCHIPELAGO_GRANT_CHECK"`, 1 parameter (check ID string).
- In `ScriptActions.cpp`: add `doArchipelagoGrantCheck(const AsciiString& checkId)` which calls `TheArchipelagoCheckEvaluator->grantCheck(checkId)`.
- In `ScriptActions::executeAction` switch: add case for `ARCHIPELAGO_GRANT_CHECK`.

**3. New ScriptCondition**
- Add `ARCHIPELAGO_CHECK_COMPLETE` – condition that checks if a check is done. Useful for "IF check X complete THEN do Y".
- In `ScriptConditions.cpp`: `evaluateArchipelagoCheckComplete(Parameter *pCheckIdParm)` → `TheArchipelagoState->isCheckComplete(pCheckIdParm->getString())`.

**4. Map author workflow**
- In WorldBuilder: Condition = `NAMED_DESTROYED` (unit "Overlord01") → Action = `ARCHIPELAGO_GRANT_CHECK` (parameter "kill_china_tank_2_overlord").
- Problem: `NAMED_DESTROYED` requires a *named* unit. You must place a specific Overlord in the map with a script name. You cannot say "when ANY Overlord is destroyed".

**5. Alternative: polling**
- Script: `Condition = PLAYER_DESTROYED_N_BUILDINGS_PLAYER` – but this evaluates "player destroyed N buildings of opponent" and is **not implemented** (returns FALSE in `evaluatePlayerDestroyedNOrMoreBuildings`). Also it's buildings only, not units.
- No existing condition for "player destroyed N units of type X". You would need to add `PLAYER_DESTROYED_N_UNITS_OF_TYPE` – new condition, new evaluation logic using ScoreKeeper's `m_objectsDestroyed`.

### Pros
- Per-map control; map author decides when check fires
- Can tie to specific named units (e.g. boss Overlord)

### Cons
- Scripts are in .map binary; must use WorldBuilder to edit
- No "any Overlord" – only named units
- `PLAYER_DESTROYED_N_BUILDINGS_PLAYER` is unimplemented
- Requires editing every challenge map (9 generals × 3 missions = 27+ maps)
- High manual effort per map

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Install WorldBuilder** | Use WorldBuilder from the game or [CCGWBpcMAN.pdf](https://github.com/TheSuperHackers/GeneralsWiki/blob/main/Asset/Maps/worldbuilder/) – see [worldbuilder_links.md](Wiki/Asset/Maps/worldbuilder/worldbuilder_links.md). |
| **Edit each map** | Open each challenge map (USA01, USA02, etc. for challenge campaigns) in WorldBuilder. Add script: Condition = `NAMED_DESTROYED` for a specific named unit, Action = `ARCHIPELAGO_GRANT_CHECK` with check ID. |
| **Name units** | Place or identify units that must be killed for the check. Give them script names (e.g. "OverlordBoss"). |
| **Implement PLAYER_DESTROYED_N_* if needed** | If you want "kill any 3 Overlords" – implement `evaluatePlayerDestroyedNOrMoreBuildings` (it's stubbed) or add `PLAYER_DESTROYED_N_UNITS_OF_TYPE`. Requires C++ changes. |
| **Document script IDs** | Maintain mapping: map script name → Archipelago check ID. |

**Wiki/External Research**: [C&C Labs – Modifying Scripts in Zero Hour World Builder](https://www.cnclabs.com/forums/cnc_postst17755_Help--Modifying-Scripts-in-Zero-Hour-World-Builder.aspx), [WorldBuilder Tutorials](https://www.youtube.com/watch?v=MvjIL5ARZBk&list=PLY4PfZWEnYtVad853LHjILA1Z5nB5hlim). Script condition list: `ScriptEngine.cpp` lines 4180–4900+ (enum values and templates).

---

## Solution 5: Event Listener Architecture

### Exact Implementation

**1. Event interface**
```cpp
class ArchipelagoEventListener {
public:
  virtual void onMissionComplete(Int general, Int mission) = 0;
  virtual void onObjectDestroyed(Player* killer, const Object* victim) = 0;
};
```

**2. Event bus**
```cpp
class ArchipelagoEventBus {
  std::vector<ArchipelagoEventListener*> m_listeners;
public:
  void subscribe(ArchipelagoEventListener* l);
  void fireMissionComplete(Int g, Int m);
  void fireObjectDestroyed(Player* k, const Object* v);
};
extern ArchipelagoEventBus* TheArchipelagoEvents;
```

**3. Firing**
- `ScoreScreen` (on victory): `TheArchipelagoEvents->fireMissionComplete(generalIndex, missionNumber)`
- `Object::scoreTheKill`: `TheArchipelagoEvents->fireObjectDestroyed(controller, victim)`

**4. Evaluator**
- `ArchipelagoCheckEvaluator` implements `ArchipelagoEventListener`, subscribes to `TheArchipelagoEvents`. In `onMissionComplete` / `onObjectDestroyed`, evaluates checks and grants rewards.

**5. Extensibility**
- Future: `ArchipelagoProgressTracker` (another listener) for UI. `ArchipelagoAnalytics` (another listener) for logging. No changes to core.

### Pros
- Decoupled; multiple systems can react to same events
- Easy to add new listeners
- Testable (mock events)

### Cons
- More indirection; harder to trace "who unlocked this"
- Slightly more code for simple case

### What You Must Do Manually

| Task | Details |
|------|---------|
| **None** | This is an architectural choice. Once implemented, you add checks via config (Solution 1/2). No manual steps beyond normal check authoring. |

---

## Solution 6: ScoreKeeper Integration

### Exact Implementation

**1. ScoreKeeper**
- `ScoreKeeper::addObjectDestroyed(const Object *o)` is called from `Object::scoreTheKill`. It stores `m_objectsDestroyed[playerIdx][template]` – count per victim-owner and per template.

**2. Hook point**
- Option A: Add a callback in `ScoreKeeper::addObjectDestroyed` – `if (TheArchipelagoCheckEvaluator) TheArchipelagoCheckEvaluator->onKill(...)`. But: `addObjectDestroyed` receives `victim` only; killer is implicit (the ScoreKeeper belongs to the player who did the action). Actually the ScoreKeeper is per *player* – each player has one. So when we call `pPlayer->getScoreKeeper()->addObjectDestroyed(victim)`, we're adding to *that player's* ScoreKeeper. The caller is `controller->getScoreKeeper()` where controller is the killer. So we have the killer.

**3. Problem**
- `addObjectDestroyed` is called with `victim`; the killer is the player whose ScoreKeeper we're updating. So we can infer: `TheArchipelagoCheckEvaluator->onKill(/* need to find player whose ScoreKeeper this is */, victim)`. ScoreKeeper doesn't have a back-pointer to Player. We'd need to pass `player` or get it from the caller.

**4. Change**
- Add `ScoreKeeper::addObjectDestroyed(Player* killer, const Object* victim)` – but that changes the signature. Or: in `Object::scoreTheKill`, after `controller->getScoreKeeper()->addObjectDestroyed(victim)`, call `TheArchipelagoCheckEvaluator->onKill(controller, victim)`. So we're not really "integrating" with ScoreKeeper – we're just calling Evaluator from the same place (Object::scoreTheKill). That's Solution 7.

**5. True integration**
- If we want to *read* from ScoreKeeper: e.g. `Evaluator->evaluateKillChecks()` which polls `ThePlayerList->getLocalPlayer()->getScoreKeeper()->getObjectsDestroyedCount(template)`. But ScoreKeeper doesn't expose per-template counts easily – it has `m_objectsDestroyed[playerIdx]` as `ObjectCountMap` (template -> count). We'd need `getObjectDestroyedCount(const ThingTemplate*, Int victimOwnerIdx)` or similar. And we need mission context – ScoreKeeper doesn't know which mission we're in.

### Pros
- Reuses existing kill tracking
- No duplicate logic

### Cons
- ScoreKeeper is per-player, not per-mission; need to reset or scope by mission
- ScoreKeeper doesn't expose per-template counts in a clean API
- Mission context must come from elsewhere

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Expose ScoreKeeper API** | Add `Int ScoreKeeper::getObjectDestroyedCount(const ThingTemplate* tmpl, Int victimPlayerIdx)` if you want to poll. |
| **Reset on mission load** | ScoreKeeper is reset on map load. So kills in mission 1 don't persist to mission 2. For in-mission kill checks, we're fine. For "cross-mission" (e.g. kill 5 Overlords across any mission), you'd need to persist. |
| **Mission scoping** | Evaluator must only run in challenge campaign and must know current (general, mission). Get from CampaignManager + ChallengeGenerals. |

---

## Solution 7: Object::scoreTheKill Hook

### Exact Implementation

**1. Single change**
```cpp
// In Object.cpp, Object::scoreTheKill, after:
if (controller)
{
    controller->getScoreKeeper()->addObjectDestroyed(victim);
    controller->addSkillPointsForKill(this, victim);
    controller->doBountyForKill(this, victim);
    // ADD:
    if (TheArchipelagoCheckEvaluator)
        TheArchipelagoCheckEvaluator->onKill(controller, victim);
}
```

**2. Evaluator**
- `ArchipelagoCheckEvaluator::onKill(Player* killer, const Object* victim)`:
  - If `!TheCampaignManager || !TheCampaignManager->getCurrentCampaign()->isChallengeCampaign()` return;
  - Get general index from `TheChallengeGenerals->getCurrentPlayerTemplateNum()` → `mapPlayerTemplateToGeneralIndex`
  - Get mission from `TheCampaignManager->getCurrentMissionNumber()`
  - Get victim template: `victim->getTemplate()->getName()`
  - For each kill check with matching (general, mission): if victim matches templates, increment count; if count >= required, mark complete, grant rewards

**3. Init order**
- `TheArchipelagoCheckEvaluator` must be created before `Object::scoreTheKill` can be called. Create in `GameLogic::init()` after `TheArchipelagoState` and `TheUnlockRegistry`.

### Pros
- Single choke point; all kills go through here
- Minimal code change
- No polling; immediate reaction

### Cons
- Adds a call in hot path (every kill); negligible cost
- Tight coupling to Object (but Object already calls many systems)

### What You Must Do Manually

| Task | Details |
|------|---------|
| **None** | This is the implementation. You configure checks via checks.json or INI. |

---

## Solution 8: Per-Mission Check Definitions

### Exact Implementation

**1. File layout**
- `Maps/USA01/ArchipelagoChecks.ini` – optional; if present, load for this map.
- `Maps/CHI02/ArchipelagoChecks.ini` – same for China mission 2.

**2. Load order**
- Map name comes from `TheCampaignManager->getCurrentMap()` or `MapCache`. When map loads, `GameLogic::loadMapINI` loads `map.ini` and `solo.ini` from the map folder. Add: `ArchipelagoChecks.ini` – if exists, parse and merge into `ArchipelagoCheckRegistry` for this session only.

**3. Registry**
- `ArchipelagoCheckRegistry` has `m_sessionChecks` – checks loaded from map folder. `loadFromMapFolder(const AsciiString& mapPath)` – construct path `mapPath/ArchipelagoChecks.ini`, parse, merge into active checks.

**4. Map path**
- Map path format: `Maps/USA01/USA01.map` → folder is `Maps/USA01`. `TheMapCache` or `TheGameState` can provide map directory. `loadMapINI` uses `pristineMapName` – strip `.map`, get dir, append `ArchipelagoChecks.ini`.

### Pros
- Map authors control checks without touching central config
- Per-map customization

### Cons
- Scattered config; 27+ maps = 27+ potential files
- Harder to audit "all checks"
- Map folder must be writable (for user maps)

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Create ArchipelagoChecks.ini per map** | For each challenge map you want kill checks: create `Maps/<MapName>/ArchipelagoChecks.ini` with UnlockCheck blocks. |
| **Map name convention** | Challenge campaigns use maps like USA01, CHI02, GLA03. Map folder = `Maps/USA01` for `USA01.map`. |
| **Ensure map load** | `loadMapINI` is called from `GameLogic::startNewGame` or similar. Verify `ArchipelagoChecks.ini` is loaded at the right time (before mission starts). |

**Wiki/External Research**: [GameLogic::loadMapINI](GeneralsMD/Code/GameEngine/Source/GameLogic/System/GameLogic.cpp) – loads `map.ini` and `solo.ini` from map folder. Path: `filename` + `\map.ini` where filename is map name without extension.

---

## Solution 9: Template Tags / KindOf

### Exact Implementation

**1. ThingTemplate field**
- Add `ArchipelagoCheck = OverlordKill` to `ThingTemplate` field parse table. `s_objectFieldParseTable` in `ThingTemplate.cpp` – add entry for `ArchipelagoCheck` that sets a string member.
- In `FactionUnit.ini` or `FactionBuilding.ini`: `Object ChinaOverlord` ... `ArchipelagoCheck = OverlordKill` `End`

**2. On kill**
- Evaluator: when victim is killed, get `victim->getTemplate()->getArchipelagoCheck()`. If non-empty, look up check by that tag. Problem: "OverlordKill" maps to which check? We need a registry: tag -> check ID. So we still need `checks.json` or similar: `{"OverlordKill": "kill_china_tank_2_overlord"}`.

**3. Flow**
- Template has tag `OverlordKill`. Registry maps `OverlordKill` -> check ID `kill_china_tank_2_overlord`. On kill: get tag, get check ID, evaluate that check (mission context must match).

**4. FieldParse**
- `ThingTemplate` field parse: `ThingTemplate.cpp` has `s_objectFieldParseTable`. Add `{"ArchipelagoCheck", &ThingTemplate::parseArchipelagoCheck}`. Parse function stores in `m_archipelagoCheckTag` (AsciiString).

### Pros
- Check defined at template level; no separate list of templates per check
- Map authors don't need to know template names

### Cons
- Pollutes game INI (FactionUnit, FactionBuilding) with Archipelago-specific fields
- May conflict with GeneralsPatch or other mods that edit same INI
- One tag per template; multiple checks for same template need multiple tags or tags with comma-sep IDs – messy

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Edit FactionUnit.ini / FactionBuilding.ini** | Add `ArchipelagoCheck = <tag>` to every relevant Object. Example: `Object ChinaOverlord` ... `ArchipelagoCheck = OverlordKill` `End` |
| **Maintain tag→check mapping** | In `checks.json` or `Archipelago.ini`: map tag -> check ID. E.g. `{"tag_to_check": {"OverlordKill": "kill_china_tank_2_overlord"}}` |
| **Avoid conflicts** | If using GeneralsPatch or other mods, ensure your INI overrides don't break. Use `Data/INI` override approach. |
| **Merge with upstream** | SuperHackers may change FactionUnit.ini. Your `ArchipelagoCheck` fields will need to be merged on upstream sync. |

**Wiki/External Research**: [GeneralsWiki Asset/GameDesign/ini](https://github.com/TheSuperHackers/GeneralsWiki/tree/main/Asset/GameDesign) – INI structure. [ThingTemplate field parse](GeneralsMD/Code/GameEngine/Source/Common/ThingTemplate.cpp) – search for `s_objectFieldParseTable`.

---

## Solution 10: Layered Unlock Modes

### Exact Implementation

**1. Mode enum**
```cpp
enum ArchipelagoUnlockMode {
  UNLOCK_MODE_MISSION_ONLY,
  UNLOCK_MODE_MISSION_AND_KILLS,
  UNLOCK_MODE_KILLS_ONLY
};
```

**2. Config**
- In `presets.json` or `Archipelago.ini`: `UnlockMode = MissionAndKills`. Parser in UnlockRegistry or ArchipelagoState.

**3. Evaluator**
- `ArchipelagoCheckEvaluator::evaluateMissionComplete`: if mode is `MISSION_ONLY` or `MISSION_AND_KILLS`, process mission_complete checks. If `KILLS_ONLY`, skip.
- `onKill`: if mode is `KILLS_ONLY` or `MISSION_AND_KILLS`, process kill checks.

**4. Default**
- `MissionAndKills` for full experience; `MissionOnly` for players who want simpler unlocks.

### Pros
- Backward compatible
- Player/moder choice

### Cons
- Requires preset support

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Set mode in preset** | `presets.json`: `"default": {"unlock_mode": "mission_and_kills", ...}`. Or `Archipelago.ini`: `UnlockMode = MissionAndKills`. |
| **Document modes** | In README or docs: explain what each mode does. |

---

## Solution 11: Weighted / Progressive Unlocks

### Exact Implementation

**1. Check schema**
```json
{
  "id": "kill_5_overlords",
  "type": "kill",
  "tier": 2,
  "templates": ["ChinaOverlord", "Tank_ChinaOverlord"],
  "count": 5,
  "rewards": ["group:Shared_Tanks"]
}
```
- No `general` or `mission` – counts across all missions.

**2. Tier system**
- `Tier 1`: mission complete checks. `Tier 2`: kill N of type X across any mission. Completing 5 tier-2 checks unlocks tier-2 rewards.

**3. Evaluator**
- `m_tierProgress[tier]` – count of completed checks in tier. When `m_tierProgress[2] >= 5`, unlock tier-2 rewards. Rewards defined in config: `"tier_rewards": {"2": ["group:Shared_Tanks"]}`.

**4. Persistence**
- `m_tierProgress` persisted in ArchipelagoState.json.

### Pros
- Flexible goals ("kill 5 Overlords across any mission")
- Encourages variety

### Cons
- More complex config
- Tier rewards need separate definition

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Design tier structure** | Define tiers (1=mission, 2=cross-mission kills, etc.). Define rewards per tier. |
| **Populate tier checks** | For each tier, list checks and their tier. Define `tier_rewards` in config. |
| **Balance** | Tune counts and thresholds so progression feels right. |

---

## Solution 12: Map Script Callbacks

### Exact Implementation

**1. New ScriptAction**
- `ARCHIPELAGO_GRANT_CHECK` – same as Solution 4. Parameter: check ID string.

**2. Map author**
- In WorldBuilder: Condition = `NAMED_DESTROYED` (unit "Overlord01") → Action = `ARCHIPELAGO_GRANT_CHECK` ("kill_china_tank_2_overlord").

**3. Evaluator**
- `ArchipelagoCheckEvaluator::grantCheck(const AsciiString& checkId)` – called from ScriptAction. If check exists and not complete, mark complete, grant rewards. No mission context validation – script author is responsible.

**4. Security**
- Scripts are in map; map author controls. If playing a custom map, they could grant any check. For official challenge maps, you control the scripts.

### Pros
- Full control per map
- Can tie to specific named units (e.g. boss)

### Cons
- Requires WorldBuilder editing
- Only works for named units
- 27+ maps to edit

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Create ScriptAction** | Add `ARCHIPELAGO_GRANT_CHECK` to Scripts.h enum, ScriptEngine.cpp template, ScriptActions.cpp handler. |
| **Edit each map in WorldBuilder** | Open each challenge map. Add script: Condition = `NAMED_DESTROYED` for named unit, Action = `ARCHIPELAGO_GRANT_CHECK`. |
| **Name units** | Place units with script names. Or use existing named units in map. |
| **Save maps** | Ensure .map files are saved and included in build/distribution. |

**Wiki/External Research**: [Adding a Script Action](GeneralsMD/Code/GameEngine/Source/GameLogic/ScriptEngine/ScriptEngine.cpp) – comment at line 566: "1. In Scripts.h, add enum element. 2. Create template. 3. Add protected method in ScriptActions.h. 4. Add case in executeAction switch."

---

## Solution 13: Event Sink / Observer Pattern

### Exact Implementation

- Same as Solution 5 (Event Listener). More formal name: Observer pattern. `ArchipelagoEventBus` = Subject; `ArchipelagoCheckEvaluator` = Observer.

### Pros / Cons
- Same as Solution 5.

### What You Must Do Manually
- Same as Solution 5.

---

## Solution 14: Template Inheritance for Kill Matching

### Exact Implementation

**1. Matching logic**
- Instead of exact match: `victim->getTemplate()->getName() == "ChinaOverlord"`, use `victim->getTemplate()->isEquivalentTo(baseTemplate)` or `victim->getTemplate()->isKindOf(KINDOF_*)`.
- Base template: `TheThingFactory->findTemplate("ChinaOverlord")`. For each victim, check `victim->getTemplate()->isEquivalentTo(baseTemplate)`.

**2. Config**
- In checks: `"templates": ["ChinaOverlord"]` – match any template equivalent to ChinaOverlord (includes Tank_ChinaOverlord, Nuke_ChinaOverlord if they're equivalent).

**3. Caveat**
- `isEquivalentTo` – need to check API. `isKindOf` – checks KindOf flags, not template hierarchy. May need to walk parent chain.

**4. Implementation**
```cpp
Bool matchesTemplate(const ThingTemplate* victim, const AsciiString& baseName) {
  const ThingTemplate* base = TheThingFactory->findTemplate(baseName);
  if (!base) return false;
  return victim->isEquivalentTo(base);  // or appropriate API
}
```

### Pros
- Fewer template entries in config
- One entry covers all general variants

### Cons
- May over-match (e.g. civilian Overlord)
- Need to verify `isEquivalentTo` semantics

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Verify ThingTemplate API** | Check `ThingTemplate::isEquivalentTo`, `getParent`, etc. in `ThingTemplate.h` and `ThingFactory.h`. |
| **Simplify config** | Use base names only: `["ChinaOverlord"]` instead of `["ChinaOverlord","Tank_ChinaOverlord","Nuke_ChinaOverlord"]`. |
| **Test edge cases** | Ensure no false positives (e.g. tech buildings that inherit from Overlord). |

---

## Solution 15: Check Dependencies (Prerequisites)

### Exact Implementation

**1. Schema**
```json
{
  "id": "kill_china_tank_2_overlord",
  "type": "kill",
  "requires": ["mission_3_2"],
  "general": 3,
  "mission": 2,
  ...
}
```

**2. Evaluator**
- Before evaluating a check: `if (!check.requires.empty()) { for (id : check.requires) if (!isCheckComplete(id)) return; }`. Only evaluate if all prerequisites are complete.

**3. Mission complete**
- `mission_3_2` = mission complete for general 3, mission 2. So "kill Overlord in China Tank mission 2" requires "complete China Tank mission 2" first. That's redundant – you can't kill in mission 2 without being in mission 2, and mission complete is evaluated after the mission. So the kill would have already happened. Unless: "kill in mission 2" means during the mission, and "mission complete" is evaluated at victory. So kill checks can complete during mission; mission complete checks at end. For "kill in mission 2" we don't need mission 2 complete first – we're already in mission 2. For "kill in mission 3" we need mission 2 complete to get to mission 3. So `requires` is for ordering: e.g. "kill in mission 3" requires "mission_3_3" complete? No – mission complete is the victory. So we'd require "mission_3_2" to mean "we've completed mission 2 and are now in mission 3". So `requires` = "mission_3_2" means "we must have completed mission 2 of general 3 before this check is active". That makes sense for mission 3 kill checks.

**4. Implementation**
- `ArchipelagoCheckEvaluator::isCheckActive(check)`: if `check.requires` empty, true. Else, all required checks must be in `m_completedChecks`.

### Pros
- Logical ordering
- Prevents sequence breaks

### Cons
- More config
- Circular dependency risk if not careful

### What You Must Do Manually

| Task | Details |
|------|---------|
| **Define prerequisites** | For each check that depends on another, add `requires: ["check_id"]`. |
| **Validate DAG** | `archipelago_validate_checks.py` should detect circular dependencies (A requires B, B requires A). |
| **Document** | Explain when to use `requires`. |

---

## Summary Comparison Table

| Solution | Pros | Cons | Complexity | Your Manual Work |
|----------|------|------|------------|------------------|
| **1 Config Registry** | Data-driven, flexible | JSON parsing in C++ | Medium | Create checks.json, add JSON dep, validate schema |
| **2 INI Block** | Consistent format | Less flexible for lists | Low | Define checks in config, extend generator |
| **3 Hybrid** | Best of 1+2 | Single-template rewards need groups | Low | Create groups for single rewards |
| **4 Map Scripts** | Per-map control | WorldBuilder, named units only | High | Edit 27+ maps in WorldBuilder, name units |
| **5 Event Listener** | Decoupled | Indirection | Medium | None (architecture) |
| **6 ScoreKeeper** | Reuses tracking | API not exposed, mission context | Medium | Expose API, handle mission scope |
| **7 scoreTheKill hook** | Single choke point | Hot path | Low | None |
| **8 Per-Mission INI** | Map author control | Scattered config | Medium | Create ArchipelagoChecks.ini per map |
| **9 Template Tags** | No separate list | Pollutes game INI | Medium | Edit FactionUnit/Building.ini, tag→check map |
| **10 Layered Modes** | Backward compatible | Preset support | Low | Set mode in preset |
| **11 Weighted** | Cross-mission goals | Complex config | High | Design tiers, populate |
| **12 Script Callbacks** | Map control | WorldBuilder, named units | High | Add ScriptAction, edit maps |
| **13 Event Sink** | Same as 5 | Same as 5 | Medium | None |
| **14 Template Inheritance** | Fewer config entries | Over-match risk | Medium | Verify API, test |
| **15 Dependencies** | Ordering | Config complexity | Medium | Define requires, validate DAG |

---

## Recommended Combination

| Component | Use |
|-----------|-----|
| **Check definition** | Solution 1 (JSON) or 2 (INI) |
| **Kill hook** | Solution 7 (scoreTheKill) |
| **Mission hook** | ScoreScreen on victory |
| **Architecture** | Solution 5 (Event Listener) for flexibility |
| **Kill matching** | Solution 14 (Template inheritance) for fewer config entries |
| **Modes** | Solution 10 (Layered) for optional complexity |
| **Dependencies** | Solution 15 (optional) for mission ordering |

**Implementation order**: 7 → 1 → 5 → 14 → 10 → 15 (optional).

---

## External Resources & Wiki References

### GeneralsWiki (TheSuperHackers)
- **Home**: https://github.com/TheSuperHackers/GeneralsWiki
- **Asset/GameDesign**: INI structure, game data
- **Asset/Maps/worldbuilder**: WorldBuilder tutorials, map editing
- **SourceCode/Builds**: Build guides

### C&C Labs (Community)
- **Modifying Scripts in World Builder**: https://www.cnclabs.com/forums/cnc_postst17755_Help--Modifying-Scripts-in-Zero-Hour-World-Builder.aspx
- **Map.ini basics**: http://www.cnclabs.com/forums/cnc_postst10478_Map-ini-basics.aspx
- **Script conditions with markers**: https://www.cnclabs.com/maps/generals/worldbuilder/tutorials/using-markers-as-script-conditions.aspx

### WorldBuilder
- **YouTube tutorials**: https://www.youtube.com/watch?v=MvjIL5ARZBk&list=PLY4PfZWEnYtVad853LHjILA1Z5nB5hlim
- **CCGWBpcMAN.pdf**: WorldBuilder manual (in repo if present)

### Codebase References
- **ScriptAction enum**: `GeneralsMD/Code/GameEngine/Include/GameLogic/Scripts.h` (enum ScriptActionType)
- **Adding a Script Action**: `ScriptEngine.cpp` ~line 566 (comment with 4-step process)
- **ScriptCondition**: `ScriptConditions.cpp` – evaluateNamedUnitDestroyed, evaluatePlayerDestroyedNOrMoreBuildings
- **Object::scoreTheKill**: `GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Object.cpp` ~2945
- **ScoreKeeper**: `GeneralsMD/Code/GameEngine/Include/Common/ScoreKeeper.h`, `m_objectsDestroyed`
- **ThingTemplate FieldParse**: `GeneralsMD/Code/GameEngine/Source/Common/ThingTemplate.cpp` – `s_objectFieldParseTable`
- **GameLogic::loadMapINI**: `GameLogic.cpp` ~2419 – loads map.ini, solo.ini from map folder
