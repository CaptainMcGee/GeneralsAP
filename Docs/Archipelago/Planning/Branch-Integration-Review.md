# Branch Integration Review

**Last checked**: May 7, 2026

This document records cross-branch merge risks for the AP item/location framework work. It is not a new design model.

## Branches Reviewed

| Branch | Observed role | Integration note |
|--------|---------------|------------------|
| `main` | Scrubbed project metadata and current canonical repository root | No merge base with this branch in local Git; do not assume a normal merge will be clean |
| `codex/ap-world-skeleton-checkpoint` | Previous AP skeleton checkpoint | Current branch is based on this line |
| `codex/ap-item-location-framework` | Current AP world/runtime/bridge/item-location framework branch | Contains the current AP foundation and should be the source for AP/runtime bridge work |
| `codex/logic-foundry-authoring` | Adds the Logic Foundry submodule pointer | Current branch already includes the submodule and advances it from `2211257` to `51770de` |

## Merge Reality

Local Git reports no merge base between `main` and the AP framework branches. The trees are related in content, but the history is not. A final merge into `main` should therefore be done through an explicit integration branch from `main`, not by assuming GitHub can produce a normal low-conflict PR.

Recommended integration path:

1. Create a fresh integration branch from `main`.
2. Apply the AP framework tree diff intentionally, excluding generated/transient artifacts.
3. Keep the current `tools/logic-foundry` submodule pointer unless the Logic Foundry branch has newer reviewed work.
4. Re-run AP data/world tests, bridge build, package fixture smoke, and runtime compile gates on the integration branch.
5. Only then open the final PR to `main`.

## Current Cross-Branch Risks

| Risk | Severity | Evidence | Recommended handling |
|------|----------|----------|----------------------|
| Unrelated histories | High | `git merge-base main codex/ap-item-location-framework` returns no merge base | Use a fresh branch from `main` and apply a reviewed tree diff; do not rely on a normal merge |
| Logic Foundry submodule pointer divergence | Medium | `codex/logic-foundry-authoring` points at `2211257`; current framework branch points at `51770de` | Prefer `51770de` because it contains the contract export smoke; verify against Logic Foundry branch before final merge |
| Economy item semantics drift | Medium | AP item classification, content framework policy, and bridge runtime effects used to disagree | Addressed here: economy items are `useful` until mission gates consume them; slot data now carries `economyItemEffects`; bridge reads that contract |
| Temporary cluster logic becoming permanent | Medium | `rules.py` still imports `testing_catalog` | Keep as alpha fixture only; future Weakness App / Logic Foundry import must replace this seam |
| Release/runtime prerequisite ambiguity | Medium | `generalszh.exe` depends on VC++ x86 runtime DLLs | Document and validate Visual C++ 2015-2022 x86 runtime prerequisite before public alpha |
| Visible launch confidence | Low/Medium | no-launch wrapper proof passes; visible launch was not rerun in this review | Run one short visible launch smoke before claiming player-machine readiness |

## What Should Survive Integration

- Canonical runtime keys stay stable: `mission.<map>.victory`, `cluster.<map>.cXX.uYY`, future `capture.<map>.bXXX`, future `supply.<map>.pXX.tYY`.
- `Seed-Slot-Data.json` remains the immutable selected-check contract.
- Bridge remains the only translator from runtime keys to AP numeric IDs.
- Medals remain shuffled AP items; Boss victory remains final `Victory`.
- Captured-building and supply-pile families remain disabled until runtime completion/persistence exists.
- Weakness/Hold/Win data remains contract-only until the dedicated design phase wires it in.

## Integration Validation Gate

Before the integration branch is merge-ready:

```powershell
python scripts\tests\test_archipelago_world_contract.py
python scripts\tests\test_archipelago_data_pipeline.py
python scripts\archipelago_run_checks.py
dotnet build tools\bridge\GeneralsAPBridge\GeneralsAPBridge.csproj -c Release
powershell -ExecutionPolicy Bypass -File scripts\windows_demo_run.ps1 -NoBridge -NoLaunch -ReferenceRuntimeDir "<legal Zero Hour runtime>"
```

If a legal runtime is available, also run the ordered non-human release gate with `-BaseRuntimeDir` before merging.

Latest local proof on May 7, 2026:

- `run_generalsap_nonhuman_release_checks.ps1 -BaseRuntimeDir "<Steam/TUC Zero Hour>" -RunIntegratedRealApRuntimeSmoke -RunSpawnedMaterializationSmoke`
- Result: `17` passed / `0` failed.
- Covered: AP data/world suite, Logic Foundry export handoff, generated-output cleanliness, packaged bridge file-mode smoke, fake AP network smoke, real local AP server smoke, full AP world simulated completion, alpha package fixture smoke, clean-runtime fixture smoke, prepared runtime build, legal-runtime auto-completion, spawned materialization, integrated real AP clean-runtime network smoke, and legal-runtime guard.
