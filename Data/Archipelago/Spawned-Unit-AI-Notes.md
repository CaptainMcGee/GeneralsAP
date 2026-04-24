# Spawned Unit AI – Design Notes

Spawned Archipelago check units should minimize exploitable behavior so that killing them reflects real capability, not AI quirks.

## Current behavior

- **DefendRadius / MaxChaseRadius** (INI): Units are pulled back to guard position when beyond MaxChaseRadius; between DefendRadius and MaxChaseRadius they are only pulled when idle.
- **Vision range**: Set to at least 400 for all spawned units (above Nuke Cannon range) so they cannot be outranged without engagement.

## Desired improvements (placeholder)

- **Pathing**: Avoid obvious pathing stalls or getting stuck; consider simple direct move or short repath.
- **Idle**: Reduce idle wander; prefer holding position or short patrol near guard point.
- **Kiting**: If units can be kited (player moves in/out of range), consider attack-move toward last known threat or slightly increased aggression range.
- **Detection**: Vision range is already raised; no change needed unless other exploits appear.

## Implementation hook

Use `TheUnlockableCheckSpawner->isSpawnedUnit(obj)` in:

- `AIUpdate.cpp` (or equivalent AI tick) to branch behavior for spawned units only.
- Optionally a dedicated behavior module for “Archipelago spawn” with its own state.

No code changes required for Phase D2; this file and the comment in `UnlockableCheckSpawner.cpp` serve as the placeholder.
