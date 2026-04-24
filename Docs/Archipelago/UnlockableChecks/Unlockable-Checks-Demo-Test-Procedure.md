# Unlockable Checks Demo – Test Procedure

This document describes how to test the self-contained unlockable checks demo.

---

## Prerequisites

1. **Build the project** using your usual method (e.g. `cmake --preset win32-vcpkg-debug` then `cmake --build build/win32-vcpkg-debug`).
2. **Config file**: `Data/INI/UnlockableChecksDemo.ini` must exist (it is in the repo).
3. **Run Generals Challenge** (not Skirmish, not Campaign).

---

## Quick Test (USA01 – USA Super Weapons General Mission 1)

1. **Start the game** and go to **Generals Challenge**.
2. **Select USA** → **Super Weapons General** → **Mission 1** (first mission).
3. **Start the mission**.
4. **On mission start**, you should see an in-game message:
   ```
   Unlockable Checks Demo: 1 unit, 0 buildings tagged. Hover units to see check IDs.
   ```
5. **Find the spawned unit**: An enemy China Tank unit (Overlord, Gattling Tank, or Battle Master, depending on seed) is spawned near the player start (Player_1_Start). It should be visible near where you begin the mission.
6. **Hover over the unit**: Move the mouse over the spawned enemy unit. The tooltip should show:
   - Unit name (e.g. "Overlord Tank")
   - Player name
   - **Check ID**: `kill_usa_superweapon_1_overlord`
7. **Verify**: The check ID appears on a new line in the tooltip when hovering over the unit.

---

## Extended Test (CHI02 – China Tank Mission 2)

1. **Start** Generals Challenge → China → Tank General → **Mission 2**.
2. **On mission start**, you should see:
   ```
   Unlockable Checks Demo: 2 units, 1 buildings tagged. Hover units to see check IDs.
   ```
3. **Spawned units**: Two enemy units (Overlord and/or Gattling Tank) at the enemy base.
4. **Tagged building**: One of the enemy Barracks or War Factories is tagged. Hover over enemy buildings to find one showing a check ID (e.g. `kill_china_tank_2_barracks`).
5. **Hover over spawned units** to see `kill_china_tank_2_overlord` or `kill_china_tank_2_gattling`.

---

## If the Demo Does Not Run

| Symptom | Check |
|--------|--------|
| No in-game message | Ensure you're in **Generals Challenge** (not Skirmish/Campaign). |
| No message, correct mode | Verify `Data/INI/UnlockableChecksDemo.ini` exists next to the executable. Path may be `Data\INI\` from the game's working directory. |
| Message shows "0 units, 0 buildings" | The map (e.g. USA01, CHI02) may not be in the config, or waypoints/templates are wrong. Check `UnlockableChecksDemo.ini`. |
| Can't find spawned units | They spawn at `Player_1_Start` (near your start). Campaign maps may only have this waypoint. |
| No check ID in tooltip | Ensure you're hovering over the **unit/building** (not the ground). The tooltip appears when the cursor is over the object. |

---

## Config Customization

Edit `Data/INI/UnlockableChecksDemo.ini`:

```ini
[USA01]
Seed = 42
UnitWaypoints = Player_1_Start
UnitTemplates = Tank_ChinaTankOverlord,Tank_ChinaTankGattling,Tank_ChinaTankBattleMaster
UnitCheckIds = kill_usa_superweapon_1_overlord
EnemyTeam = player2
```

- **Seed**: Change to get different unit types (e.g. 12345 vs 42).
- **UnitWaypoints**: Must match waypoints in the map. Use `Player_2_Start` for enemy base.
- **UnitTemplates**: Valid template names from the game (e.g. `ChinaOverlord`, `ChinaGattlingTank`).
- **UnitCheckIds**: Check IDs shown in the tooltip. No suffix when there is only one check of that type.

---

## Adding More Maps

Add a new section:

```ini
[USA01]
Seed = 999
UnitWaypoints = Player_1_Start
UnitTemplates = AmericaRanger,AmericaVehicleHumVee
UnitCheckIds = kill_usa_airforce_1_ranger
EnemyTeam = player2
```

Use the map leaf name (e.g. CHI01, USA02, GLA03) as the section name.

---

## Verification Checklist

- [ ] In-game message appears at mission start
- [ ] Spawned unit(s) visible at enemy base
- [ ] Hovering over spawned unit shows check ID in tooltip
- [ ] (CHI02) Hovering over tagged building shows check ID
- [ ] Same seed produces same unit type and positions
- [ ] Different seed produces different unit type

---

## Files Changed

| File | Purpose |
|------|---------|
| `Object.h` | Added `m_archipelagoCheckId`, `getArchipelagoCheckId()`, `setArchipelagoCheckId()` |
| `InGameUI.cpp` | Appends check ID to tooltip when hovering over units with `ArchipelagoCheckId` |
| `UnlockableCheckSpawner.h/cpp` | New module: loads config, spawns units, tags buildings |
| `GameLogic.cpp` | Creates spawner, calls `runAfterMapLoad` after object load |
| `Data/INI/UnlockableChecksDemo.ini` | Demo config for USA01, CHI02 |
