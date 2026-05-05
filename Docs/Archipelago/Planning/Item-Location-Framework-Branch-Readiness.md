# Item/Location Framework Branch Readiness

**Status**: branch confidence checkpoint for `codex/ap-item-location-framework`.

**Last checked**: May 4, 2026 UTC; latest local non-human release report generated `2026-05-04T15:50:18Z`

**Checkpoint goal**: prove the AP item/location framework and non-human release harnesses are reviewable without implying capture/supply gameplay, weakness evaluation, mission `Hold` / `Win`, or player UI work is complete.

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
- Latest branch-scope audit against `origin/codex/ap-world-skeleton-checkpoint` found zero unexpected changed-file lanes, zero forbidden-scope filenames, and zero forbidden implementation matches.
- Changed-file lanes are expected for this branch: AP data, docs, `GeneralsMD` runtime slot/state parsing, bridge/package scripts, tests, bridge sidecar, and APWorld overlay.
- No branch-scope audit finding showed enabled weakness evaluator, mission `Hold` / `Win` implementation, tracker UI, authoring UI, YAML difficulty modes, or new cluster content.
- Latest PR self-review used `scripts\archipelago_pr_scope_audit.py` and found zero unexpected changed-file lanes, zero forbidden-scope filenames, and zero forbidden implementation matches across `GeneralsMD`, `tools/bridge`, `scripts`, and APWorld overlay implementation files.

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
- local bridge mirroring for future state arrays; packaged bridge translation for selected future-family fixture checks only
- enable criteria that define what must exist before any future family can be enabled
- disabled future logic contract handoff files for Weakness App capability-source output and mission-gate authoring output; these validate shape/policy only and do not feed AP generation

Net effect:

- Project can plan enough future low-risk locations for large item pools.
- Runtime and bridge can tolerate future-state sections.
- AP generation still cannot expose unfinishable capture/supply locations.
- Future authoring output has a contract-shaped landing zone without implementing the evaluator or final mission gates on this branch.

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
- future logic contract validation
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
- Archipelago vendor materialize / real AP generation smoke, plus vendor-capture guard contract tests

Important invariants currently tested:

- mission victories remain AP locations/checks
- seven shuffled general medals gate Boss access
- Boss victory remains locked final `Victory` event state, not a normal `LocationChecks` location
- selected seeded mode does not mix with demo checks
- future capture/supply families are disabled by default
- production slot data rejects selected future-family checks
- local bridge mirrors future state arrays, and packaged bridge executable smoke proves selected future-family fixture keys `capture.tank.b001` and `supply.tank.p02.t02` translate to AP IDs while unselected future keys still fail; packaged bridge smoke also preserves future state arrays without turning them into completions
- packaged bridge rejects unknown runtime keys / AP IDs
- packaged bridge accepts valid numeric `completedLocations` and keeps duplicate numeric submissions idempotent
- packaged bridge rejects reused session files when seed, slot, or session nonce changes without `--reset-session`
- fake AP network smoke covers incremental `ReceivedItems` packets before deriving runtime unlocks and session options
- fake AP network smoke submits selected future-family fixture checks through AP `LocationChecks` and rejects unselected future-family keys
- fake AP network smoke advertises the Boss victory marker as a known server ID and still verifies `mission.boss.victory` sends only `StatusUpdate`, never `LocationChecks`
- packaged bridge submits one mission victory and one cluster-unit check through real local AP server and preserves checked locations across reconnect
- full real local AP server simulation completes all selected main-world mission/cluster checks, verifies all seven shuffled medals arrive, submits Boss-cluster checks after medals, sends Boss victory through AP goal status, and verifies duplicate replay is idempotent
- duplicate bridge submissions remain harmless
- real local AP server smoke serializes shared venv/worktree setup and retries fresh server ports to reduce false failures under concurrent harness runs
- clean-runtime fixture harness can package, clone, overlay, seed `UserData\Archipelago`, and keep file-bridge setup isolated from public AP network mode
- clean-runtime smoke fails unless a real `-BaseRuntimeDir` or explicit `-UseFixtureRuntime` is supplied
- clean-runtime real launch can now run a guarded automatic runtime completion smoke by writing `Enable-Runtime-Smoke.flag` plus `Runtime-Smoke-Complete.json`; the runtime still validates selected keys through verified slot data before writing `Bridge-Outbound.json`, the harness fails if `generalszh.exe` exits immediately after the proof, and the packaged bridge verifies AP numeric ID translation afterward
- ordered non-human release checks can now include that guarded legal-runtime smoke when `-BaseRuntimeDir` or `GENERALSAP_BASE_RUNTIME_DIR` is supplied, rebuild the prepared game runtime first, wait long enough for slower cloned legal-runtime startup paths, and reject staged/untracked generated-output drift
- alpha package validation now checks both package roots and produced zip files, validates the release manifest against `Data/Archipelago/release_manifest_schema.json`, rejects unsafe zip paths, rejects zip entries outside the selected package root, rejects retail `.big` payloads, rejects transient APWorld artifacts such as `__pycache__/`, `.pyc`, `.log`, `.tmp`, and `host.yaml`, rejects bundled `bridgeKind=staging_stub`, requires claimed game overlay files, requires the full current APWorld module dependency set, and verifies bundled bridge/APWorld layout from manifest claims
- alpha package fixture smoke now runs bridge translation against `payload\Bridge\GeneralsAPBridge.exe` from the produced package, not the source/staging bridge path
- integrated real-AP clean-runtime smoke can now seed the installed runtime through the packaged bridge's live AP `--connect` path, launch the game, submit guarded runtime completions back through the same AP server, and fresh-reconnect to verify server-persisted checked locations
- optional spawned materialization smoke can launch Tank challenge directly and prove selected spawned check `cluster.tank.c02.u01` exists, is alive, has an object ID, and writes current position into `ArchipelagoSpawnedUnitState.json`; it does not prove spawned-kill completion
- source-wiring contract tests now lock the natural completion callbacks: score-screen victory must use the selected canonical mission runtime key, spawned-unit kills must call `grantCheckForKill(..., TRUE)`, normal tagged kills remain non-spawned checks, and seeded cluster spawned-unit IDs come from verified slot data
- vendor capture guard tests keep only GeneralsZH additive source files and skip AP runtime artifacts such as `host.yaml`, `logs/`, `__pycache__/`, and `.pyc`; the ordered non-human runner does not currently run a full vendor capture
- enable criteria require object identity, runtime completion event, replay persistence, selected-only bridge translation, explicit AP generation selection, guard regression tests, and manual playtest proof before enabling a family
- disabled logic contract validation requires item-specific capability sources, production-facility prerequisites for green unit sources, yellow/support rows staying non-formal, economy floors staying separate from requirement tags, and no Boss medal or normal Victory item in capability-source output
- GitHub workflow contract gate is limited to GitHub-safe non-human validation: AP data pipeline tests, AP world contract tests, Logic Foundry export handoff smoke, generated-output cleanliness, package fixture smoke with packaged bridge translation, bridge file-mode smoke, fake AP network smoke, real local AP server smoke, PR scope audit, and a narrow `GeneralsMD` `win32-vcpkg-playtest` runtime compile smoke. It intentionally does not require retail assets, legal-runtime launch, hosted AP room access, or natural gameplay.
- GitHub framework-contract CI now stages retained package, bridge executable, and AP-smoke temp directories from the Python temp root into `build\archipelago\ci-framework-smoke-artifacts`; after successful smokes, missing retained temp proof fails the job before artifact upload.

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
- Latest run `2026-05-04T15:50:18Z`: 14 passed / 0 failed without `-FastRealApSmoke` and with `-RunIntegratedRealApRuntimeSmoke` plus `-RunSpawnedMaterializationSmoke`; this was the third consecutive full local loop after checkpoint `ea9997e`. The ordered gate includes PR scope audit, generated-output cleanliness, packaged-bridge package smoke, real local AP server smoke with shared-cache locking and port retry, package root/zip validation with sibling-entry rejection, prepared game runtime build, clean-runtime completion-proof process liveness guard, legal-runtime auto-completion smoke, selected spawned check materialization, live AP network seeding/submission into the clean runtime, future-family fixture bridge checks, APWorld payload dependency checks, and bundled `staging_stub` package rejection.
- That run exposed timestamp-only churn in `generated_unit_matchup_graph.json`; `scripts\archipelago_generate_matchup_graph.py` now preserves the previous timestamp when graph semantics are unchanged, and `test_matchup_graph_generation_preserves_timestamp_when_unchanged` locks this release-gate cleanliness contract.
- Natural score-screen victory and spawned-kill callback source wiring is contract-tested. Full in-game execution proof is still slow/manual.
- Draft PR #2 is open against `codex/ap-world-skeleton-checkpoint`; commit `dec0d7d` exposed a GitHub generated-output drift failure on `Data/Archipelago/generated_unit_matchup_graph.csv` because the CSV writer used platform-default CRLF. The generator now pins `lineterminator="\n"`, and the local CI-equivalent generated-output gate passes. A later `65c52db` GitHub failure happened after successful runtime compile because artifact collection assumed an optional `Core\Release` directory existed; `7ad6fcb` fixed optional artifact collection, and GitHub passed on checkpoint `ea9997e`. Commit `85ce224` added smoke artifact upload, and a follow-up review found the smoke temp upload path was too narrow for GitHub's Python temp root; the workflow now stages retained smoke dirs from `[System.IO.Path]::GetTempPath()` before upload.
- Latest targeted PR self-review checks passed: `test_archipelago_world_contract.py`, `test_archipelago_data_pipeline.py`, `archipelago_run_checks.py`, package fixture smoke, real local AP server smoke, and `archipelago_pr_scope_audit.py`. The ordered non-human release runner calls `archipelago_pr_scope_audit.py` by default before build/package/runtime gates. `.github/workflows/validate-archipelago-data.yml` now defines Windows AP framework contract and `GeneralsMD` runtime compile gates; checkpoint `ea9997e` passed both push and PR GitHub runs, and current branch validation is expected to verify staged AP smoke artifacts in CI.

Do not merge this branch as if capture/supply gameplay is implemented. It is framework and guardrail work only.
For this branch, the non-human recommendation is to proceed to review with the natural-execution caveat instead of requiring a 45-minute manual victory proof before PR.

---

## 6. Review Checkpoint

Post-checkpoint follow-up:

1. Keep `scripts\smoke_generalsap_clean_runtime.ps1 -SmokeCompleteRuntimeKey mission.tank.victory,cluster.tank.c02.u01 -CompletionTimeoutSeconds 90` as the fast release gate.
2. Keep `scripts\archipelago_pr_scope_audit.py --base origin/codex/ap-world-skeleton-checkpoint --head HEAD` as the quick PR scope guard; the ordered non-human runner now includes it by default.
3. Review draft PR #2 with the remaining natural-execution caveat stated plainly.
4. Run one slow `-WaitForRuntimeKey` natural-event playtest only if reviewer or release owner requires it before merge.

If manual play time is unavailable, branch can still be reviewed as AP/data/framework/release-harness work, but the PR description must state that natural mission-victory and spawned-kill execution proof is not yet proven.
