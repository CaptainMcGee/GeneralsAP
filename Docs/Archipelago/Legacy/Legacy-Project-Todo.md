# GeneralsAP Project TODO

**Last updated**: January 2025
**Purpose**: Consolidated project roadmap and task list.

---

## Current Focus: Unlockable Checks

**Goal**: Unlock units/buildings/upgrades by:
1. Completing every general × challenge mission combination
2. Defeating specific units/buildings within each mission

**Design**: See [Unlockable-Checks-Design.md](../UnlockableChecks/Unlockable-Checks-Design.md) for full architecture.

---

## TODO List (Prioritized)

### Phase 1: Check System Foundation
- [ ] **1.1** Create `Data/Archipelago/checks.json` schema and starter checks
- [ ] **1.2** Add `ArchipelagoCheckRegistry` class – load and validate checks
- [ ] **1.3** Extend `ArchipelagoState` with `m_completedChecks`, `markCheckComplete()`, `isCheckComplete()`
- [ ] **1.4** Add `ArchipelagoCheckEvaluator` – stub, no hooks yet
- [ ] **1.5** Script: `archipelago_validate_checks.py` – validate checks against groups.json

### Phase 2: Mission-Complete Checks
- [ ] **2.1** In ScoreScreen (on victory): call Evaluator to evaluate mission_complete checks
- [ ] **2.2** Evaluator: find matching checks, grant rewards via `unlockGroup()`, mark complete
- [ ] **2.3** Persist completed check IDs in ArchipelagoState.json

### Phase 3: Kill-Based Checks
- [ ] **3.1** Hook `Object::scoreTheKill` → `Evaluator::onKill(killer, victim)`
- [ ] **3.2** Evaluator: track kills per (general, mission, template); evaluate kill checks
- [ ] **3.3** Support template matching (base + general-prefixed names)
- [ ] **3.4** Only run in challenge campaign; get mission context from CampaignManager + ChallengeGenerals

### Phase 4: Config & Tooling
- [ ] **4.1** Document checks.json format and examples
- [ ] **4.2** Add `--validate-checks` to archipelago_run_checks or CI
- [ ] **4.3** Optional: preset support for `mission_only` vs `mission_and_kills`

### Phase 5: Polish
- [ ] **5.1** In-game toast/notification when check completes
- [ ] **5.2** Debug commands: `ap_check_status`, `ap_complete_check <id>`
- [ ] **5.3** Populate checks.json with full general × mission × kill matrix (design pass)

---

## Completed (Reference)

| Item | Notes |
|------|-------|
| UnlockRegistry | INI parsing, groups, AlwaysUnlocked, ArchipelagoSettings |
| ArchipelagoState | Unlock sets, markLocationComplete, save/load |
| ArchipelagoSettings parsing | StartingGeneralUSA/China/GLA now read from INI |
| Production/Build hooks | ProductionUpdate, BuildAssistant block locked templates |
| UI lock overlay | ControlBarCommand, ArchipelagoLock |
| Location completion | ScoreScreen marks location on mission win |
| General selection | ChallengeMenu restricts to unlocked generals |
| Dynamic config | groups.json, presets.json, archipelago_generate_ini.py |
| Display name resolution | FactionBuilding.ini for building classification |
| Upstream sync | ../Operations/SuperHackers-Upstream-Sync.md, sync scripts, GitHub workflow |
| archipelago_run_checks | Generate before validate |

---

## Future / Backlog

| Item | Priority |
|------|----------|
| Archipelago Python client (IPC) | Medium |
| Progress Tracker UI | Low |
| Buff system | Low |
| Spawnability audit fixes | Low (GLATunnelNetworkNoSpawn, etc.) |

---

## Related Documents

- [Archipelago-Code-Review.md](../Planning/Archipelago-Code-Review.md) – Feature verification, gaps
- [Unlockable-Checks-Design.md](../UnlockableChecks/Unlockable-Checks-Design.md) – Check system architecture
- [SuperHackers-Upstream-Sync.md](../Operations/SuperHackers-Upstream-Sync.md) – Syncing with SuperHackers
- [IMPLEMENTATION_GUIDE.md](../../../IMPLEMENTATION_GUIDE.md) – Step-by-step implementation notes
