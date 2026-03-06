# Unlock Group Logic (Archipelago Spawned Units)

## Intended Behavior

When a player kills a spawned unit with an Archipelago check ID:

1. **Check completion**: The check ID (e.g. `kill_supw_vs_tank_1_overlord`) is marked complete in ArchipelagoState.
2. **Group lookup**: The **victim's template name** (e.g. `Tank_ChinaTankBattleMaster`) is used to find the corresponding UnlockGroup in Archipelago.ini via `UnlockRegistry::findGroupForTemplate()`.
3. **Group unlock**: If a group contains that template, the entire group is unlocked (all units/buildings in that group).
4. **Display message**: The in-game message shows the **group DisplayName** (e.g. "Tanks" or "Machine Gun Vehicles"), not the raw check ID. Format: `"[UNLOCKED] <DisplayName> (+$5000)"`.
5. **Direct unlock**: If the victim template is not in any group, the template itself is unlocked directly.
6. **Cash**: $5000 is granted per kill (handled by UnlockableCheckSpawner).
7. **All-unlocked bonus**: When all check IDs for the current map are complete, an additional $10,000 is granted and "All groups unlocked! +$10,000" is shown.

## Execution Order (Critical)

For each kill, the order MUST be:

1. **ArchipelagoState::grantCheckForKill** (first)
   - Mark check complete
   - Find group via victim template
   - Unlock group (or direct template)
   - Show in-game message: `[UNLOCKED] <DisplayName> (+$5000)`

2. **UnlockableCheckSpawner::onSpawnedUnitKilled** (second)
   - Grant $5000
   - Update local m_unlockedCheckIds
   - Check "all unlocked" → if so, grant $10,000 and show "All groups unlocked! +$10,000"
   - Do NOT show per-check message (ArchipelagoState already did)

This order ensures the group DisplayName message appears before the "All groups unlocked" message when the last kill completes the set.

## Message Rules

- **One message per kill**: ArchipelagoState shows the group DisplayName (or template name for direct unlock). UnlockableCheckSpawner does NOT show a per-check message.
- **Always show on grant**: Even if the group was already unlocked (e.g. from sync or unlock-all), we show the message so the player gets feedback that the check completed.
- **All-unlocked**: Shown only once per map when the last required check is completed.

## Data Flow

```
Kill spawned unit
  → Object::scoreTheKill()
    1. ArchipelagoState::grantCheckForKill(checkId, victimTemplateName, TRUE)
       - If checkId already complete → return (no message)
       - Mark checkId complete
       - group = findGroupForTemplate(victimTemplateName)
       - If group: unlockGroup(group, " (+$5000)") → notifyUnlock(displayName + " (+$5000)")
       - Else: unlockUnit/Building(victimTemplateName) → notifyUnlock(templateName)
    2. UnlockableCheckSpawner::onSpawnedUnitKilled(victim)
       - Grant $5000
       - Add checkId to m_unlockedCheckIds
       - Check all required IDs complete → grant $10,000, show "All groups unlocked! +$10,000"
```

## Requirements for Correct Display

1. **Archipelago.ini** must define UnlockGroups that contain the spawned unit templates (e.g. `Tank_ChinaTankBattleMaster` in `Shared_Tanks`, `Tank_ChinaTankGattling` in `Shared_MachineGunVehicles`).
2. Each group should have a `DisplayName` for readable messages.
3. UnlockableCheckSpawner must not display its own per-check message when ArchipelagoState is present.
