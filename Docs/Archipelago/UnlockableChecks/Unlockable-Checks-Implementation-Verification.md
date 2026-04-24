# Unlockable Checks: Implementation Verification & Demo Guide

**Purpose**: Verify the chosen approach (dynamic spawn at load, identifier on selection, check ID format) is sound, feasible, future-proof, and expandable. Provide a concrete guide for building a self-contained randomizer demo without Archipelago.

---

## 1. Design Decisions (Confirmed)

| Decision | Specification | Rationale |
|----------|---------------|-----------|
| **Identifier display** | Only when unit is selected (unit name / tooltip) | No floating numbers, no particles. Minimal UI change. |
| **Check ID format** | No suffix when only one check of that type | `kill_china_tank_2_overlord` not `kill_china_tank_2_overlord_1` when there's only one. Suffix only when multiple checks share the same type. |
| **Units** | Spawn at static waypoints; waypoint = `hash(seed, targetIndex) % numWaypoints` | Deterministic; same seed → same targets. |
| **Buildings** | Use existing map buildings; pick one with `hash(seed, checkIndex) % count`; set `ArchipelagoCheckId` on that object | No spawning; tag at load. |
| **Seed** | All choices derived from Archipelago seed | Same seed → same targets and locations. |

---

## 2. Code Deep Dive: Identifier Display

### 2.1 Where the Unit Name Is Shown When Selected

**Location**: `GeneralsMD/Code/GameEngine/Source/GameClient/InGameUI.cpp` ~2654–2727

When the mouse hovers over a drawable (unit/building), the game builds a tooltip:

```cpp
UnicodeString str = thingTemplate->getDisplayName();
if( str.isEmpty() )
{
    AsciiString txtTemp;
    txtTemp.format("ThingTemplate:%s", obj->getTemplate()->getName().str());
    str = TheGameText->fetch(txtTemp);
}
// ... warehouse feedback, etc. ...
tooltip.format(L"%s\n%s", str.str(), ((Player *)player)->getPlayerDisplayName().str());
TheMouse->setCursorTooltip(tooltip, -1, &rgb);
```

**Conclusion**: The tooltip is the place where the unit name is shown. This is effectively “when unit is selected” in the sense that hovering shows the name. If the user means “when the unit is in the selection ring,” the same tooltip path is used when hovering over selected units.

### 2.2 How to Add the Check ID to the Display

**Approach**: Add an `ArchipelagoCheckId` field to `Object`. When building the tooltip, if `obj->getArchipelagoCheckId().isNotEmpty()`, append it to the tooltip.

**Code changes**:
1. `Object.h`: Add `AsciiString m_archipelagoCheckId;` and `getArchipelagoCheckId()`, `setArchipelagoCheckId()`.
2. `InGameUI.cpp` (tooltip block ~2724): After building `tooltip`, if `obj->getArchipelagoCheckId().isNotEmpty()`, append `\nCheck: <id>` (or similar).

**Feasibility**: ✅ Straightforward. Single hook, no new UI windows.

---

## 3. Code Deep Dive: Object Properties & Map Load

### 3.1 Map Object Properties Flow

**Location**: `GameLogic.cpp` ~1889–1904

```cpp
Object *obj = TheThingFactory->newObject( thingTemplate, team );
if( obj )
{
    obj->setOrientation(angle);
    obj->setPosition( &pos );
    obj->updateObjValuesFromMapProperties( pMapObj->getProperties() );
    // ...
}
```

**`Object::updateObjValuesFromMapProperties`** (`Object.cpp` ~3488): Reads `Dict* properties` and applies values. Existing keys include `TheKey_objectName`, `TheKey_objectMaxHPs`, etc.

### 3.2 Adding ArchipelagoCheckId

**Option A – From map properties**: Add `TheKey_archipelagoCheckId` in `WellKnownKeys.h`. In `updateObjValuesFromMapProperties`, read it and call `setArchipelagoCheckId(valStr)`. Map authors would set this in WorldBuilder.

**Option B – Set in code at load**: For the dynamic approach, we do **not** rely on map properties. Instead:
- **Buildings**: After the main object load loop, iterate objects by template, pick targets with `hash(seed, index) % count`, then call `obj->setArchipelagoCheckId(checkId)`.
- **Units**: We spawn them ourselves and call `setArchipelagoCheckId` at creation.

**Conclusion**: Option B matches the dynamic spawn design. No WorldBuilder changes needed.

---

## 4. Code Deep Dive: Spawning Units at Waypoints

### 4.1 Existing Spawn Logic

**Location**: `ScriptActions.cpp` ~1171–1226, `createUnitOnTeamAt`

```cpp
void ScriptActions::createUnitOnTeamAt(const AsciiString& unitName, const AsciiString& objType,
    const AsciiString& teamName, const AsciiString& waypoint)
{
    // ...
    const ThingTemplate *thingTemplate = TheThingFactory->findTemplate(objType);
    Object *obj = TheThingFactory->newObject( thingTemplate, theTeam );
    if( obj )
    {
        if (unitName != m_unnamedUnit) {
            obj->setName(unitName);
            TheScriptEngine->addObjectToCache(obj);  // or transferObjectName
        }
        Waypoint *way = TheTerrainLogic->getWaypointByName( waypoint );
        if (way) {
            Coord3D destination = *way->getLocation();
            obj->setPosition(&destination);
        }
    }
}
```

**Waypoint lookup**: `TheTerrainLogic->getWaypointByName(AsciiString name)` – iterates waypoints by name.

### 4.2 Integration Point for Our Spawner

**When to spawn**: After map objects are loaded, before or during script execution. A good place is a new `GameLogic` hook or a module that runs once after `loadMapINI` / object creation.

**Flow**:
1. Check if we're in a challenge mission (e.g. `TheCampaignManager`, `TheChallengeGenerals`).
2. Load config for current map (e.g. `CHI02`).
3. Get seed (from Archipelago or demo RNG).
4. For each unit check: `waypointIndex = hash(seed, checkIndex) % waypoints.size()`, `unitType = groundUnits[hash(seed, checkIndex) % groundUnits.size()]`, spawn at `waypoints[waypointIndex]`.
5. Call `obj->setArchipelagoCheckId(checkId)`.

**Feasibility**: ✅ `createUnitOnTeamAt` and `TheTerrainLogic->getWaypointByName` are sufficient. We can either call `ScriptActions::createUnitOnTeamAt` or inline equivalent logic.

---

## 5. Code Deep Dive: Tagging Buildings

### 5.1 Iterating Objects by Template

**Location**: `GameLogic::getFirstObject()` / `Object::getNextObject()` – global object list.

We need: “all objects with template X owned by team Y.” Options:
- Iterate `TheGameLogic->getFirstObject()` and filter by `obj->getTemplate()->getName() == templateName` and team.
- Or use `Player::iterateObjects` if we know the owner.

**Building selection**: Config lists templates (e.g. `ChinaBarracks`, `ChinaWarFactory`). At load, collect all matching objects. Pick index `hash(seed, checkIndex) % count`, set `ArchipelagoCheckId` on that object.

**Feasibility**: ✅ Simple iteration and filtering.

---

## 6. Code Deep Dive: Check ID Format (No Suffix When Single)

**Rule**: `kill_china_tank_2_overlord` when there is only one such check; `kill_china_tank_2_overlord_1`, `kill_china_tank_2_overlord_2` when there are multiple.

**Where to enforce**: In the config generator or check registry, when emitting check IDs:

```python
# Pseudocode for check ID generation
def get_check_id(base_id, index, total_of_type):
    if total_of_type == 1:
        return base_id  # e.g. "kill_china_tank_2_overlord"
    return f"{base_id}_{index + 1}"  # e.g. "kill_china_tank_2_overlord_1"
```

**Conclusion**: Purely a data/config concern. No engine changes needed.

---

## 7. Soundness, Feasibility, Future-Proofing, Expandability

| Criterion | Assessment |
|----------|------------|
| **Soundness** | ✅ Deterministic seed → deterministic spawns and tagging. Kill detection via `Object::scoreTheKill` is a single choke point. Tooltip hook is localized. |
| **Feasibility** | ✅ All required APIs exist: `TheThingFactory->newObject`, `TheTerrainLogic->getWaypointByName`, `Object::updateObjValuesFromMapProperties`, `Object::setName`, tooltip in `InGameUI.cpp`. |
| **Future-proof** | ✅ Config-driven; new maps/checks = config only. `ArchipelagoCheckId` on `Object` is generic. Event listener pattern (Solution 5) allows more listeners without touching core. |
| **Expandability** | ✅ Add checks by config. Add new identifier display (e.g. minimap) by reading `getArchipelagoCheckId()`. Add particles later if desired. |

### Risks

| Risk | Mitigation |
|------|------------|
| Waypoints missing on some maps | Config must list waypoints that exist. Validator script can check map vs config. |
| Replay/CRC | Spawned units and tagged buildings change game state. Replays may need to record seed and check config, or disable checks in replay mode. |
| Multiplayer | Kill checks are per-player. Ensure `scoreTheKill` caller has correct killer. |

---

## 8. Self-Contained Randomizer Demo (No Archipelago)

A demo that proves the mechanics without Archipelago: spawn units, tag buildings, show identifiers, use a seed.

### 8.1 What the User Must Do

#### Step 1: Config File

Create `Data/INI/UnlockableChecksDemo.json` (or `Data/Archipelago/checks_demo.json`):

```json
{
  "seed": 12345,
  "maps": {
    "CHI02": {
      "enemy_faction": "China",
      "enemy_general": "Tank",
      "unit_waypoints": ["EnemyBase", "Flank1", "Flank2"],
      "unit_target_count": 2,
      "unit_check_ids": ["kill_china_tank_2_overlord", "kill_china_tank_2_gattling"],
      "building_templates": ["ChinaBarracks", "ChinaWarFactory"],
      "building_target_count": 1,
      "building_check_ids": ["kill_china_tank_2_barracks"]
    }
  },
  "ground_units_by_general": {
    "China_Tank": ["ChinaOverlord", "ChinaGattlingTank", "ChinaDragonTank"]
  }
}
```

#### Step 2: New C++ Module – `UnlockableCheckSpawner`

**Files**:
- `GeneralsMD/Code/GameEngine/Include/GameLogic/UnlockableCheckSpawner.h`
- `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp`

**Responsibilities**:
1. Load JSON config (reuse existing JSON lib or minimal parser).
2. Expose `runAfterMapLoad(const AsciiString& mapName)`.
3. If map is in config:
   - Get seed from config.
   - Spawn units: for each unit check, compute waypoint and unit type via hash, call `TheThingFactory->newObject`, set position from waypoint, `setArchipelagoCheckId`, add to ScriptEngine cache if using names.
   - Tag buildings: iterate objects by template, pick with hash, `setArchipelagoCheckId`.

**Hash function** (deterministic):

```cpp
static UInt32 demoHash(UInt32 seed, UInt32 index) {
    // Simple deterministic hash
    return (seed * 31 + index) * 2654435761u;
}
```

#### Step 3: Hook Into Map Load

In `GameLogic.cpp`, after the main object load loop (e.g. after ~1918, before scripts run), add:

```cpp
if (TheUnlockableCheckSpawner)
    TheUnlockableCheckSpawner->runAfterMapLoad(pristineMapName);
```

Create `TheUnlockableCheckSpawner` in `GameLogic::init()` (or similar), and only run when in challenge campaign (or always for demo).

#### Step 4: Add `ArchipelagoCheckId` to Object

- `Object.h`: `AsciiString m_archipelagoCheckId;` plus getter/setter.
- `Object.cpp`: Implement getter/setter. Optionally add to `updateObjValuesFromMapProperties` for future map-based use.
- `WellKnownKeys.h`: `DEFINE_KEY(archipelagoCheckId)` if using map properties.

#### Step 5: Tooltip Display

In `InGameUI.cpp`, in the tooltip block (~2724), before `TheMouse->setCursorTooltip`:

```cpp
if (obj->getArchipelagoCheckId().isNotEmpty()) {
    tooltip.concat(L"\n");
    tooltip.concat(UnicodeString(obj->getArchipelagoCheckId().str()));
}
```

#### Step 6: Build and Run

1. Build the project.
2. Copy `UnlockableChecksDemo.json` to `Data/INI/` or `Data/Archipelago/`.
3. Start a challenge mission (e.g. China Tank, Mission 2 – CHI02).
4. Verify: spawned units at waypoints, one building tagged, tooltip shows check ID when hovering.

### 8.2 What to Avoid in the Demo

- No Archipelago client or network.
- No `ArchipelagoState` or `UnlockRegistry` dependency for the spawner (can be optional).
- No kill-completion logic (optional for demo; can add `scoreTheKill` hook later).
- No persistence of completed checks.

### 8.3 Minimal Demo Scope

For the smallest proof-of-concept:

1. **Config**: Hardcode one map (e.g. CHI02), one waypoint name, one unit type, seed = 42.
2. **Spawner**: Spawn 1 unit at that waypoint, set `ArchipelagoCheckId = "kill_china_tank_2_overlord"`.
3. **Tooltip**: Show the ID when hovering.
4. **No buildings**: Skip building tagging initially.

This validates: spawn at waypoint, `ArchipelagoCheckId` on object, tooltip display.

---

## 9. Summary

| Component | Status | Notes |
|-----------|--------|------|
| Identifier on selection | ✅ Verified | Tooltip in `InGameUI.cpp`; append `ArchipelagoCheckId` |
| Check ID format | ✅ Config-only | No suffix when single; suffix when multiple |
| Unit spawning | ✅ Verified | `createUnitOnTeamAt` / `TheTerrainLogic->getWaypointByName` |
| Building tagging | ✅ Verified | Iterate objects, hash-pick, `setArchipelagoCheckId` |
| Map load hook | ✅ Verified | After object loop in `GameLogic.cpp` |
| Demo without Archipelago | ✅ Documented | Config + `UnlockableCheckSpawner` + 4 code hooks |

The approach is **sound, feasible, future-proof, and expandable**. The demo can be implemented with the steps above.
