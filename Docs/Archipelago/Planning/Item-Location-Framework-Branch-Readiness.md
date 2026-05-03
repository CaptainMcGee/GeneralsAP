# Item/Location Framework Branch Readiness

**Status**: branch confidence checkpoint for `codex/ap-item-location-framework`.

**Last checked**: May 2, 2026 local / May 3, 2026 UTC

**Scope**: AP item/location framework, future location-family scaffolding, bridge/release validation harnesses, tests, validation, and documentation only.

**Do not include**: weakness evaluator, mission `Hold` / `Win` logic, authoring UI, tracker UI, YAML difficulty modes, new cluster content, packaging polish, or enabled capture/supply gameplay.

---

## 1. Merge Target Reality

This branch is based on `origin/codex/ap-world-skeleton-checkpoint`, not `origin/main`.

Observed locally:

- `git merge-base HEAD origin/codex/ap-world-skeleton-checkpoint` returned `aafde953a91fde110e52055ff7cb5a2e3e963ffe`
- `git merge-base HEAD origin/main` found no merge base
- `origin/main` currently points at `a44a68e chore: finalize scrubbed project metadata`

Recommendation:

- Review and merge this branch against `codex/ap-world-skeleton-checkpoint`, or first decide the repository-wide branch ancestry plan.
- Do not treat a direct PR to `origin/main` as normal until the unrelated-history issue is intentionally resolved.

---

## 2. Branch Scope Summary

Compared with `origin/codex/ap-world-skeleton-checkpoint`, this branch adds the item/location framework checkpoint:

- planning-only economy/filler item copy accounting
- item/location capacity report
- disabled future captured-building and supply-pile-threshold ID/runtime-key lanes
- authoring schema for future capture/supply candidates
- test-only example candidate fixtures
- read-only future-family sections in slot data
- production guard preventing future-family checks from entering generated seeds
- runtime parse-only support for future-family slot-data sections
- runtime state scaffold for future capture/supply state arrays
- local bridge mirroring for future state arrays without AP translation
- enable criteria that define what must exist before any future family can be enabled

Net effect:

- Project can plan enough future low-risk locations for large item pools.
- Runtime and bridge can tolerate future-state sections.
- AP generation still cannot expose unfinishable capture/supply locations.

---

## 3. Proven By Automated Checks

Command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_generalsap_nonhuman_release_checks.ps1
```

Result: passed. Report written to `build\archipelago\nonhuman-release-checks\nonhuman-release-checks.md`.

Coverage included:

- packaged bridge build
- generated Archipelago INI validation
- future location catalog validation
- item/location capacity report
- Archipelago data pipeline tests
- local bridge translation tests
- seeded bridge loop smoke
- runtime fallback boundary smoke
- future location-family parse-only tests
- future runtime state scaffold tests
- WND workbench sanity tests
- AP world contract tests
- optional real Archipelago 0.6.7 generation/fill smoke
- packaged bridge file-mode smoke
- packaged bridge fake AP network smoke
- packaged bridge real local AP 0.6.7 `MultiServer.py` smoke
- alpha package fixture smoke
- clean-runtime fixture harness smoke
- clean-runtime legal-runtime guard
- Archipelago vendor materialize / smoke / capture sequence

Important invariants currently tested:

- mission victories remain AP locations/checks
- seven shuffled general medals gate Boss access
- Boss victory remains locked final `Victory` event state, not a normal `LocationChecks` location
- selected seeded mode does not mix with demo checks
- future capture/supply families are disabled by default
- production slot data rejects selected future-family checks
- local bridge mirrors future state arrays but does not translate them to AP IDs
- packaged bridge rejects unknown runtime keys / AP IDs
- packaged bridge submits one mission victory and one cluster-unit check through real local AP server and preserves checked locations across reconnect
- duplicate bridge submissions remain harmless
- clean-runtime fixture harness can package, clone, overlay, seed `UserData\Archipelago`, and keep file-bridge setup isolated from public AP network mode
- clean-runtime smoke fails unless a real `-BaseRuntimeDir` or explicit `-UseFixtureRuntime` is supplied
- vendor capture keeps only GeneralsZH additive source files and skips AP runtime artifacts such as `host.yaml`, `logs/`, `__pycache__/`, and `.pyc`
- enable criteria require object identity, runtime completion event, replay persistence, selected-only bridge translation, explicit AP generation selection, guard regression tests, and manual playtest proof before enabling a family

---

## 4. Not Yet Proven

Remaining unproven areas:

- legal cloned Zero Hour runtime launch through `scripts\smoke_generalsap_clean_runtime.ps1 -BaseRuntimeDir ...`
- manual in-game proof that one mission victory and one seeded cluster kill write `mission.tank.victory` and `cluster.tank.c02.u01` to `Bridge-Outbound.json`
- clean-machine package smoke on a separate Windows environment
- capture/supply runtime object identity
- capture/supply completion events
- capture/supply replay persistence
- capture/supply AP generation selection
- mission `Hold` / `Win` logic
- weakness/capability evaluator

---

## 5. Merge Readiness Verdict

Ready for review against `codex/ap-world-skeleton-checkpoint` if reviewer accepts one known validation gap:

- AP/data/world/bridge/package non-human checks pass.
- Real AP 0.6.7 generation smoke and real local AP server bridge smoke pass.
- Legal-runtime launch and manual in-game completion proof are still asset-gated.

Do not merge this branch as if capture/supply gameplay is implemented. It is framework and guardrail work only.

---

## 6. Next Checkpoint

Best next checkpoint:

1. Run `scripts\smoke_generalsap_clean_runtime.ps1` with a legal healthy Zero Hour clone as `-BaseRuntimeDir`.
2. If launch passes, rerun with `-WaitForRuntimeKey mission.tank.victory -WaitForRuntimeKey cluster.tank.c02.u01 -CompletionTimeoutSeconds 900`.
3. During that run, complete one mission victory and one seeded cluster kill in game.
4. Then open/review PR against the correct base branch.

If legal-runtime assets are unavailable, branch can still be reviewed as AP/data/framework/release-harness work, but the PR description must state that launch and manual in-game completion proof are not yet proven.
