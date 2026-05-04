# Item/Location Framework Branch Readiness

**Status**: branch confidence checkpoint for `codex/ap-item-location-framework`.

**Last checked**: May 3, 2026 local / May 4, 2026 UTC; latest non-human release report generated `2026-05-04T01:27:06Z`

**Scope**: AP item/location framework, future location-family scaffolding, bridge/release validation harnesses, tests, validation, and documentation only.

**Do not include**: weakness evaluator, mission `Hold` / `Win` logic, authoring UI, tracker UI, YAML difficulty modes, new cluster content, packaging polish, or enabled capture/supply gameplay.

**Draft PR**: https://github.com/CaptainMcGee/GeneralsAP/pull/2, targeting `codex/ap-world-skeleton-checkpoint`.

---

## 1. Merge Target Reality

This branch is based on `origin/codex/ap-world-skeleton-checkpoint`, not `origin/main`.

Observed locally:

- `git merge-base HEAD origin/codex/ap-world-skeleton-checkpoint` returned `aafde953a91fde110e52055ff7cb5a2e3e963ffe`
- `git merge-base HEAD origin/main` found no merge base
- `origin/main` currently points at `a44a68e chore: finalize scrubbed project metadata`
- Latest branch-scope audit found 31 commits and 52 changed files against `origin/codex/ap-world-skeleton-checkpoint`.
- Changed-file lanes are expected for this branch: AP data, docs, `GeneralsMD` runtime slot/state parsing, bridge/package scripts, tests, bridge sidecar, and APWorld overlay.
- No branch-scope audit finding showed enabled weakness evaluator, mission `Hold` / `Win` implementation, tracker UI, authoring UI, YAML difficulty modes, or new cluster content.
- Latest PR self-review found zero unexpected changed-file lanes. Focused implementation scan across `GeneralsMD`, `tools/bridge`, and `scripts` found zero forbidden-scope implementation matches.

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
- clean-runtime real launch can now run a guarded automatic runtime completion smoke by writing `Enable-Runtime-Smoke.flag` plus `Runtime-Smoke-Complete.json`; the runtime still validates selected keys through verified slot data before writing `Bridge-Outbound.json`, and the packaged bridge verifies AP numeric ID translation afterward
- ordered non-human release checks can now include that guarded legal-runtime smoke when `-BaseRuntimeDir` or `GENERALSAP_BASE_RUNTIME_DIR` is supplied, rebuild the prepared game runtime first, and wait long enough for slower cloned legal-runtime startup paths
- source-wiring contract tests now lock the natural completion callbacks: score-screen victory must use the selected canonical mission runtime key, spawned-unit kills must call `grantCheckForKill(..., TRUE)`, normal tagged kills remain non-spawned checks, and seeded cluster spawned-unit IDs come from verified slot data
- vendor capture keeps only GeneralsZH additive source files and skips AP runtime artifacts such as `host.yaml`, `logs/`, `__pycache__/`, and `.pyc`
- enable criteria require object identity, runtime completion event, replay persistence, selected-only bridge translation, explicit AP generation selection, guard regression tests, and manual playtest proof before enabling a family

---

## 4. Not Yet Proven

Remaining unproven areas:

- natural in-game execution proof that the score-screen mission victory event and a spawned-unit kill event write `mission.tank.victory` and `cluster.tank.c02.u01` to `Bridge-Outbound.json`; source wiring is contract-tested, but the slow gameplay events have not been naturally exercised
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
- Legal-runtime launch proof passed locally against the Steam/TUC install path on May 3, 2026.
- Guarded automatic runtime completion proof passed locally on May 3, 2026: selected keys `mission.tank.victory` and `cluster.tank.c02.u01` reached `Bridge-Outbound.json` and translated to AP IDs `270000003` and `270040201`.
- Ordered non-human release gate passed locally with `-BaseRuntimeDir` on May 3, 2026, again after source-wiring tests were added, and again on May 4, 2026 UTC.
- Latest run `2026-05-04T01:27:06Z`: 10 passed / 0 failed without `-FastRealApSmoke`, so the packaged real local AP server smoke used the full install/materialize path; prepared game runtime build and legal-runtime auto-completion smoke also passed.
- Natural score-screen victory and spawned-kill callback source wiring is contract-tested. Full in-game execution proof is still slow/manual.
- Draft PR #2 is open, draft, and mergeable against `codex/ap-world-skeleton-checkpoint` as of the latest local check. No GitHub status checks, comments, or reviews were reported yet.
- Latest targeted PR self-review checks passed: `test_archipelago_world_contract.py`, `test_archipelago_data_pipeline.py`, and focused forbidden-scope implementation scan. `gh pr checks` reported no configured checks for this branch.

Do not merge this branch as if capture/supply gameplay is implemented. It is framework and guardrail work only.
For this branch, the non-human recommendation is to proceed to review with the natural-execution caveat instead of requiring a 45-minute manual victory proof before PR.

---

## 6. Next Checkpoint

Best next checkpoint:

1. Keep `scripts\smoke_generalsap_clean_runtime.ps1 -SmokeCompleteRuntimeKey mission.tank.victory,cluster.tank.c02.u01 -CompletionTimeoutSeconds 90` as the fast release gate.
2. Review draft PR #2 with the remaining natural-execution caveat stated plainly.
3. Run one slow `-WaitForRuntimeKey` natural-event playtest only if reviewer or release owner requires it before merge.

If manual play time is unavailable, branch can still be reviewed as AP/data/framework/release-harness work, but the PR description must state that natural mission-victory and spawned-kill execution proof is not yet proven.
