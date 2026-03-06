# Archipelago Implementation TODO

**Source**: [Archipelago-Logic-Implementation-Guide.md](Archipelago-Logic-Implementation-Guide.md) plus the current repo state.

---

## Top Priority Stabilization

| Item | Status | Notes |
|------|--------|-------|
| Serialize `m_archipelagoCheckId` and rebuild spawned-check runtime state on save/load | Done | `Object.cpp` now serializes the check ID; `UnlockableCheckSpawner.cpp` rebuilds runtime state on save load |
| Include building-tagged checks in current-map completion bookkeeping | Done | Spawner now tracks unit + building check IDs/templates for all-unlocked handling |
| Mark challenge mission completion by enemy mission/general, not player general | Done | `ScoreScreen.cpp` now resolves the opponent general from the current mission |
| Remove known non-spawnable templates from Archipelago data/scripts | Done | Denylist is enforced across generate/validate/audit/graph scripts and the refreshed outputs now validate cleanly |
| Normalize fork/upstream Git workflow | Done | `origin` now targets the GeneralsAP GitHub repo, `upstream` targets TheSuperHackers, and the sync scripts/workflows use explicit names |

---

## Backend / Data Status

| Item | Status | Notes |
|------|--------|-------|
| Tool to define cluster points | Done | `scripts/archipelago_cluster_editor.py` |
| Configurable units per cluster / locations per multiworld | Done | `cluster_config.json`, `options_schema.yaml` |
| YAML option template for AP | Done | `Data/Archipelago/options_schema.yaml` |
| Superweapon limit logic | Done | `GameLogic.cpp` |
| Spawned unit AI restrictions | Partial | Real leash/team-control logic exists in code; tuning and validation remain |
| Real matchup graph naming pipeline | Done | Graph now resolves names through `template_ingame_names.json`; unresolved templates must carry review notes in `reference/unresolved_template_name_notes.json` |
| Denylist enforcement in generate/validate/audit/graph scripts | Done | `non_spawnable_templates.json` is now enforced across the pipeline |
| `compute_player_strength()` | Stub | Still a stub in `scripts/archipelago_logic_prerequisites.py` |
| Real cluster data for challenge maps | Stub | Tooling exists; actual production map data is not complete |
| AP world slot-data hookup | Stub | `Slot-Data-Format.md` is still a target contract |
| Meaningful presets | Stub | `default`, `minimal`, and `chaos` remain close placeholders |

---

## Guide Answers / Repo Reality

| ID | Requirement | Repo Reality |
|----|-------------|--------------|
| A1 | Dynamic player strength for logic | Partial: prerequisite scaffolding exists, but `compute_player_strength()` is still a stub |
| A2 | Separate defend vs beat checks | Done |
| A3 | Cluster positions from tool + random map selection | Partial: tools/config exist, but real challenge-map data is still incomplete |
| B4 | 7 missions (no Demo/Infantry) | Done |
| B5 | YAML options and per-general tracker data | Partial: options/schema exist, item-tracker UI does not |
| C6 | Chinook/base-defense cluster restrictions | Done |
| C7 | Transport compositions | Todo |
| C8 | No base defenses on hard clusters | Done |
| D9 | Explicit unit lists | Done |
| D10 | Counter-based player strength, no upgrade/money/super dependence by default | Stub |
| E11 | Hardcoded graph ratings/overrides | Done |
| E12 | Defender list equals spawnable list | Done |
| F13 | Phased implementation | Done |
| F14 | INI fallback with explicit messaging | Done |

---

## Open Work

### P1 Data Hygiene

- [ ] Confirm localized names for edge cases such as Fire Base, Checkpoint, and Moat match the actual game strings and add overrides only if community naming should differ intentionally.
- [ ] Review obviously non-player-facing but currently resolved templates (dead hulls, debris, helper beams, projectiles) and decide whether to keep their inferred labels or move more of them into `_unresolved_notes`.
- [ ] Keep `reference/unresolved_template_name_notes.json` in sync with any future template-name-map changes.

### P2 Backend

- [ ] Implement real slot-data ingestion instead of relying on `UnlockableChecksDemo.ini` fallback.
- [ ] Populate real cluster definitions for the challenge maps.
- [ ] Implement `compute_player_strength()` with explicit counter logic.
- [ ] Make presets materially different once slot-data and logic are real.

### P3 Features

- [ ] Phase E: Archipelago menu, connect flow, item tracker, logic tracker, mission select.
- [ ] Phase F: items (production bonus, starting cash, temporary cash) and traps (airshow, money subtract, random voice).
- [ ] C7 compositions: Battle Bus, Helix, Battle Chinook, and transport-destruction check handling.

---

## Agent Assignments

| Agent | Scope |
|-------|-------|
| Agent A | Data/scripts, naming pipeline, denylist, presets, AP-world prep |
| Agent B | Save/load, mission completion, slot-data ingestion, compositions, items, traps |
| Agent C | UI only after Agent A/B contracts stabilize |

---

## Coordination Risks

| Conflict | Agents | Resolution |
|----------|--------|------------|
| Slot-data contract vs spawner implementation | A, B | B owns the spawner, A owns the schema; change both together |
| Archipelago state APIs vs UI tracker needs | B, C | B adds state/query APIs; C consumes them |
| Generated data changes vs upstream sync | A, B | Regenerate artifacts after merges instead of hand-merging generated files |

---

## Related

- [ARCHIPELAGO_CONTEXT_INDEX.md](ARCHIPELAGO_CONTEXT_INDEX.md)
- [Archipelago-Logic-Implementation-Guide.md](Archipelago-Logic-Implementation-Guide.md)
- [SuperHackers-Upstream-Sync.md](../Operations/SuperHackers-Upstream-Sync.md)
