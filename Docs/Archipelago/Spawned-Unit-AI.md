# Spawned Unit AI (Archipelago)

**Status**: Partial implementation in code; tuning and validation still open.

## Current Behavior

Spawned or tagged Archipelago check objects already have several behavior restrictions in the engine:

- `UnlockableCheckSpawner.cpp`
  - spawned units get minimum vision above Nuke Cannon range
  - defend-radius and max-chase-radius leash logic are enforced
  - save/load runtime state is rebuilt for spawned check units
- `AIUpdate.cpp`
  - spawned units refuse certain retargeting outside their defend radius
- `Team.cpp`
  - spawned units ignore team-script command control so mission scripting does not repurpose them

This is no longer a placeholder-only area. The remaining work is on tuning, coverage, and verifying the behavior in live challenge missions.

## Remaining Goals

- Reduce exploitable idle or pullback behavior without making units look broken.
- Keep spawned defenders aggressive inside their intended leash while preventing map-wide kiting.
- Validate that transport/composition work in later phases will respect the same leash and team-script exclusions.

## Expected Direction

Prefer incremental behavior rules over a full custom AI system:

- keep the current leash model as the baseline
- tighten edge cases in `AIUpdate.cpp`
- preserve the `UnlockableCheckSpawner` guard/chase data as the single source of truth
- avoid reintroducing mission team control for spawned Archipelago defenders

## References

- `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp`
- `GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/AIUpdate.cpp`
- `GeneralsMD/Code/GameEngine/Source/Common/RTS/Team.cpp`
