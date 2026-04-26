# Item/Location Framework Branch Readiness

**Status**: branch confidence checkpoint for `codex/ap-item-location-framework`.

**Last checked**: April 26, 2026

**Scope**: AP item/location framework, future location-family scaffolding, tests, validation, and documentation only.

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
python scripts\archipelago_run_checks.py
```

Result: passed.

Coverage included:

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

Important invariants currently tested:

- mission victories remain AP locations/checks
- seven shuffled general medals gate Boss access
- Boss victory remains final `Victory`
- selected seeded mode does not mix with demo checks
- future capture/supply families are disabled by default
- production slot data rejects selected future-family checks
- local bridge mirrors future state arrays but does not translate them to AP IDs
- enable criteria require object identity, runtime completion event, replay persistence, selected-only bridge translation, explicit AP generation selection, guard regression tests, and manual playtest proof before enabling a family

---

## 4. Not Yet Proven

Runtime C++ build was attempted:

```powershell
cmake --build build\win32 --target z_gameengine -j 2
```

Result: failed before this branch's AP runtime changes could be validated.

Observed failure:

```text
fatal error C1083: Cannot open include file: 'time.h': No such file or directory
fatal error C1083: Cannot open include file: 'map': No such file or directory
```

Interpretation:

- Local MSVC/Windows SDK environment cannot find standard C/C++ headers.
- This is a toolchain setup failure, not evidence that the AP runtime changes fail to compile.
- Runtime compile remains unverified until build runs from a correct Visual Studio Developer Command Prompt or repaired CMake/toolchain environment.

Other unproven areas:

- real in-game playtest
- real AP network bridge
- capture/supply runtime object identity
- capture/supply completion events
- capture/supply replay persistence
- capture/supply AP generation selection
- mission `Hold` / `Win` logic
- weakness/capability evaluator

---

## 5. Merge Readiness Verdict

Ready for review against `codex/ap-world-skeleton-checkpoint` if reviewer accepts one known validation gap:

- AP/data/world/bridge tests pass.
- Real AP 0.6.7 generation smoke passes.
- Runtime C++ compile is blocked by local toolchain header discovery and must be rerun in a valid MSVC environment before merge to a playtest branch.

Do not merge this branch as if capture/supply gameplay is implemented. It is framework and guardrail work only.

---

## 6. Next Checkpoint

Best next checkpoint:

1. Fix or switch to a valid MSVC build environment.
2. Rerun `cmake --build build\win32 --target z_gameengine -j 2`.
3. If build passes, perform one local runtime smoke using existing seeded mission/cluster slot data.
4. Then open/review PR against the correct base branch.

If build environment cannot be repaired soon, branch can still be reviewed as AP/data/framework work, but the PR description must state that runtime compile was not proven locally.
