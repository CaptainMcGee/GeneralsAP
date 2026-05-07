# Demo Proof Review

This document explains the non-human demo proof for the current AP item/location framework branch. It is a reviewer artifact, not a new design model.

## Command

Run from the repository root with a legal healthy Zero Hour install or clone:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_generalsap_demo_director.ps1 `
  -BaseRuntimeDir "C:\Games\ZeroHourCleanClone"
```

Shortcut for this maintainer machine:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_generalsap_demo_director.ps1 `
  -BaseRuntimeDir "C:\Program Files (x86)\Steam\steamapps\common\Command & Conquer Generals - Zero Hour" `
  -FastRealApSmoke
```

The command writes:

```text
build\archipelago\demo\Demo-Proof.json
```

Expected top-level result:

```json
{
  "status": "DEMO_PROOF_OK",
  "scope": "seed_runtime_bridge_demo_proof"
}
```

## What It Proves

The demo director runs the smallest useful automated AP plumbing story:

1. Seeds local bridge state with `human_demo_tank`.
2. Builds the packaged `GeneralsAPBridge.exe`.
3. Creates verified `Seed-Slot-Data.json` and `Bridge-Inbound.json`.
4. Launches a legal runtime clone into `Maps\GC_TankGeneral.map`.
5. Confirms selected spawned check object `cluster.tank.c02.u01` materializes in `ArchipelagoSpawnedUnitState.json`.
6. Injects guarded runtime completions for:
   - `mission.tank.victory`
   - `cluster.tank.c02.u01`
7. Confirms the runtime writes those canonical keys to `Bridge-Outbound.json`.
8. Confirms the packaged bridge translates those keys to AP location IDs:
   - `270000003`
   - `270040201`
9. Starts a real local Archipelago 0.6.7 server unless `-SkipNetworkProof` is passed.
10. Seeds the clean runtime through live AP network bridge mode, submits those same checks, and verifies fresh reconnect persistence.

This is strong proof for seed/runtime/bridge/AP plumbing. It is not, by itself, proof that the direct-map launch is a human-like Challenge mission start.

## Visual Survival Gate

Use this gate when reviewing whether the demo behaves like a player-visible mission start:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_generalsap_visual_demo_gate.ps1 `
  -BaseRuntimeDir "C:\Games\ZeroHourCleanClone"
```

The visual/survival gate captures game-window screenshots while the seeded runtime materialization smoke runs, then rejects the run if it reaches `Menus/ScoreScreen.wnd`, writes `Runtime-Smoke-ScoreScreen.json`, or the captured screen matches the defeat splash shape. It brings the Generals window to the foreground before each screenshot so unrelated desktop windows do not trigger false defeat-splash matches. It also verifies Challenge-start log markers: the requested AP general template, starting building/object placement, and the matching control-bar scheme. When selected cluster materialization is requested, it additionally requires the `ThePlayer` Challenge enemy-team marker and records `spawnedRuntimeKeyObserved` from `ArchipelagoSpawnedUnitState.json`. The summary also records basic screenshot usability stats (`usableScreenshotCount`, `uniqueScreenshotHashCount`, and per-frame brightness/color buckets) so reviewers can reject blank or non-game captures without manual image triage. This catches the important false positive where AP seeded checks materialize correctly but the mission immediately reaches a defeat score screen or launches outside proper Challenge setup. By default it copies review artifacts beside `Visual-Demo-Gate.json` and deletes the temporary installed runtime; pass `-KeepReviewInstall` only when a failed run needs full runtime inspection.

Use the matrix gate when reviewing that every AP player-general index maps to the intended Challenge persona:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_generalsap_visual_demo_matrix.ps1 `
  -BaseRuntimeDir "C:\Games\ZeroHourCleanClone"
```

The matrix fixture `human_demo_all_generals` unlocks and starts AP general indices `0..8` only for this smoke proof. It does not change AP item placement or final mission logic. Default matrix behavior uses `GC_TankGeneral` plus selected-cluster materialization for the eight non-Tank starter generals. AP general `3` (`FactionChinaTankGeneral`) uses `GC_ChemGeneral` with `-NoSpawnProof` start-only proof because retail Challenge campaigns do not contain a Tank-vs-Tank self-match; this start-only row uses a longer startup/capture window so the control-bar scheme marker has time to appear.

Run visual gates serially. Do not launch two Generals visual gates in parallel: game-window focus, process detection, and shared engine assumptions can interfere and create false smoke failures. The matrix script is intentionally serial for this reason.

Current verified status on May 6 2026: raw direct `-file Maps\GC_TankGeneral.map` materialization can pass AP plumbing while still failing visual survival because it bypasses Challenge game setup. The smoke harness therefore uses explicit `-apSmokeChallenge 2` / `-SmokeChallengePlayerGeneralIndex 2`, where `2` is the AP Superweapon general index, not the Challenge menu persona slot. Treat `run_generalsap_demo_director.ps1` as a seed/runtime/bridge proof unless the visual gate also passes.

For the current Superweapon-vs-Tank demo path, accepted visual gate proof should include:

- `status = VISUAL_DEMO_GATE_OK`
- `challengeStartVerified = true`
- `expectedPlayerTemplate = FactionAmericaSuperWeaponGeneral`
- `startingBuildingDetected = true`
- `startingObjectDetected = true`
- `challengeEnemyTeamDetected = true`
- `spawnedRuntimeKeyObserved = true`
- `usableScreenshotCount > 0`
- `defeatSplashDetected = false`

## What It Does Not Prove

Do not overclaim this proof.

- It does not prove natural 45-minute score-screen mission victory.
- It does not prove the direct-map launch survived past mission start unless `run_generalsap_visual_demo_gate.ps1` also passes.
- It does not prove a human can naturally kill the spawned cluster.
- It does not prove combat balance, pathing, or fairness.
- It does not prove final weakness/capability evaluator behavior.
- It does not prove final mission `Hold` / `Win` logic.
- It does not prove captured-building or supply-pile gameplay.
- It does not prove public release install UX.

Those are later gates. This proof exists because future logic work depends on the game reliably consuming selected AP seed checks and returning selected runtime keys.

## Fixture Meaning

`Data\Archipelago\bridge_fixtures\human_demo_tank.json` is a demo fixture only.

It gives a Superweapon starter, broad conventional unlock groups, fast starting economy, fast production, and no zoom limit. It is meant to make recording and non-human runtime proof practical.

It is not:

- AP item placement
- final logic
- mission gate design
- weakness/capability data
- balance truth

## Reviewer Checklist

Reviewers should accept the demo proof only when all checks below are true:

- `Demo-Proof.json` exists.
- `status` is `DEMO_PROOF_OK`.
- `fixture` is `human_demo_tank`.
- `runtimeKeys` contains `mission.tank.victory` and `cluster.tank.c02.u01`.
- `selected_cluster_materialization.status` is `passed`.
- `guarded_runtime_completion_loop.status` is `passed`.
- `live_ap_network_loop.status` is `passed`, unless intentionally skipped and documented.
- completed runtime keys map to AP IDs `270000003` and `270040201`.
- caveats are preserved in the proof JSON.
- for human-like demo claims, `run_generalsap_visual_demo_gate.ps1` also passes and does not detect `Menus/ScoreScreen.wnd`.

## Relationship To Full Gate

`run_generalsap_demo_director.ps1` is not a replacement for:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_generalsap_nonhuman_release_checks.ps1 `
  -BaseRuntimeDir "C:\Games\ZeroHourCleanClone" `
  -RunIntegratedRealApRuntimeSmoke `
  -RunSpawnedMaterializationSmoke `
  -RunVisualDemoGate `
  -RunVisualDemoMatrixGate
```

The full gate still owns branch readiness. The demo director owns "can AP seed data reach the runtime, selected checks spawn, runtime keys return, and bridge/AP translation hold without manual gameplay grind?" Human-like visual survival is owned by `run_generalsap_visual_demo_gate.ps1`.

## Current Scope Boundary

This branch may keep improving:

- slot-data proof clarity
- bridge/runtime testability
- package/release smoke confidence
- item/location framework scaffolds
- reviewer handoff docs

This branch must not start:

- weakness evaluator implementation
- final mission `Hold` / `Win` implementation
- authoring UI implementation
- tracker UI
- new cluster content
- YAML difficulty modes
- public packaging polish beyond current smoke contracts
