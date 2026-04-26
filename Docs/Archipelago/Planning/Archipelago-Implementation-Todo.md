# Archipelago Implementation TODO

**Primary source of truth**:

- [Archipelago-Logic-Implementation-Guide.md](Archipelago-Logic-Implementation-Guide.md)
- [Item-Location-Framework.md](Item-Location-Framework.md)
- [Archipelago-Logic-Mapping-Draft.md](Archipelago-Logic-Mapping-Draft.md)
- [ARCHIPELAGO_CONTEXT_INDEX.md](../../../ARCHIPELAGO_CONTEXT_INDEX.md)

**Status note**: The April 12, 2026 decision pass is mostly complete. The AP world skeleton, fixture slot-data path, local bridge translation, runtime seed ingestion, and fallback-boundary smoke checks now exist. Open items below are remaining implementation work, except for the exact per-general `Hold` / `Win` mission table, which is intentionally deferred for a later design pass.

---

## 1. Locked Alpha Snapshot

| Area | Locked decision |
|------|-----------------|
| World goal | Collect the 7 shuffled main challenge victory medals, then unlock and beat the Boss map |
| Replayability | Missions are replayable; medium and hard cluster access assumes replay safety |
| Accessibility default | `full` |
| Tracker colors | `Green` and `Red` are logic-authoritative; `Yellow` is tracker-only and never grants AP access |
| Mission gates | `Hold` and `Win` are separate from cluster-local logic |
| Per-general mission table | Deferred | The framework is locked, but exact per-map `Hold` / `Win` requirements still need a later dedicated pass |
| Alpha locations | Mission victories plus per-unit cluster kills only |
| Cluster access model | Each unit stays its own AP location, but units in the same cluster share one cluster-level rule |
| Alpha item model | Grouped-only progression, progressive mission buffs, and one shuffled victory medal per main challenge general |
| Future location families | Captured buildings and supply-pile thresholds have reserved ID/runtime-key lanes and a disabled author catalog; runtime support still required before enabling |
| Capability satisfaction | Unit/item unlocks satisfy weaknesses only when the required production facility is also available |
| Mission buffs | `Progressive Starting Money` and `Progressive Production` are real logic items for mission gates |
| Deferred scope | Extra location families, alternate granularities, superweapon logic toggles, future trap content, and the exact per-general mission table |

---

## 2. Verified Repo Reality

| Area | Current state | Notes |
|------|---------------|-------|
| Canonical design docs | Done | The guide and mapping draft now reflect the approved alpha model |
| Cluster placement tool | Done | `tools/cluster-editor` web app submodule is the active placement authoring path |
| Logic authoring tool | Needed | Expand the web app into a visual unit/item/weakness authoring and validation tool |
| Manual cluster layouts | External / ongoing | Cluster placement is handled manually and is not the active repo-side blocker |
| State bridge seam | Local fixture ready | `Bridge-Inbound.json` / `Bridge-Outbound.json`, fixture slot-data materialization, runtime-key translation, duplicate merge, and fallback-boundary checks exist; real AP network client still pending |
| AP world files | Skeleton ready | `vendor/archipelago/overlay/worlds/generalszh` has grouped alpha skeleton, stable IDs, fixture slot-data, and contract tests |
| Future location catalog | Scaffold ready | `Data/Archipelago/location_families/catalog.json` carries disabled author lanes for captured buildings and supply piles, with validator/deriver tests |
| Runtime slot-data ingestion | Phase 1 ready | Runtime loads verified `Seed-Slot-Data.json`, spawns selected seeded checks, rejects bad hash without demo fallback, and keeps `UnlockableChecksDemo.ini` as no-reference fallback only; in-game playtest smoke still pending |
| Logic evaluator | Stub / historical drift | `scripts/archipelago_logic_prerequisites.py` still contains the older numeric scaffold and stubbed `compute_player_strength()` |
| Main-menu AP UI | Stub / tooling ready | No dedicated connect / tracker / mission-select menu flow yet, but generated-only WND extraction, audit, and loose-override workbench tooling now exists |
| Packaging pipeline | Partial | Clone + `-userDataDir` model is documented; release packaging is not built |

---

## 3. Remaining Implementation Work

### P1. Static Contract Cleanup

- [x] Implement the rewritten [Slot-Data-Format.md](../../../Data/Archipelago/Slot-Data-Format.md) contract for fixture-backed generation and runtime ingestion:
  - selected per-unit cluster locations
  - stable numeric location IDs
  - runtime string keys such as `mission.<map>.victory` and `cluster.<map>.cXX.uYY`
  - no generic `slots_per_cluster` contract
- [ ] Introduce a machine-readable mission-gate source file for `Hold`, `Win`, and mission buff floors after the per-general mission table is authored.
- [ ] Introduce a machine-readable item-classification source file for grouped alpha items and mission buffs.
- [ ] Introduce machine-readable capability-satisfaction data:
  - player unit/item to weakness coverage
  - required production facility per unit
  - faction/general/YAML-granularity applicability
  - non-unit mission requirements such as general powers
- [ ] Expand `tools/cluster-editor` or create a sibling web app for visual logic authoring:
  - derive default cluster weaknesses from selected spawnable enemy units
  - allow author edits, grouping, and notes
  - show player unit/item icons and the weaknesses they satisfy
  - show required production-facility prerequisites
  - validate edited explicit weaknesses against obtainable player items
  - export the canonical data consumed by the AP world and runtime slot-data generator
- [ ] Annotate or retire the older numeric-model artifacts so future work does not treat them as authoritative:
  - [Data/Archipelago/enemy_general_profiles.json](../../../Data/Archipelago/enemy_general_profiles.json)
  - [scripts/archipelago_logic_prerequisites.py](../../../scripts/archipelago_logic_prerequisites.py)
  - [Data/Archipelago/options_schema.yaml](../../../Data/Archipelago/options_schema.yaml)

### P2. AP World and Static Seed Data

- [x] Create the first committed `worlds/generalszh` implementation under `vendor/archipelago/overlay`.
- [x] Define the grouped-only alpha item table with current Archipelago item classifications:
  - `progression`
  - `useful`
  - `filler`
  - `trap`
- [x] Define the stable numeric location table for:
  - mission victory checks
  - per-unit cluster checks
- [ ] Tune early progression balance through AP pool/configuration work instead of adding a custom Generals-side early-item guarantee system.
- [x] Implement the approved alpha fixture presets:
  - `default`
  - `minimal`
- [x] Emit fixture slot data that contains selected per-unit locations and mission-logic metadata instead of the older generic-slot scaffolding.
- [x] Add disabled author catalog scaffolding for future captured-building and supply-pile-threshold locations.
- [ ] Add runtime/persistence support before selecting any non-cluster catalog locations into slot data.

### P3. Bridge Translation and Runtime Ingestion

- [ ] Implement the external Archipelago bridge process that:
  - reads AP session state
  - writes `Bridge-Inbound.json`
  - consumes `Bridge-Outbound.json`
- [x] Implement the local fixture bridge process that writes `Bridge-Inbound.json`, consumes `Bridge-Outbound.json`, materializes `Seed-Slot-Data.json`, and translates runtime keys back to AP numeric IDs.
- [x] Translate mission and cluster runtime string check IDs using the approved grammar in the local fixture path.
- [x] Replace `UnlockableChecksDemo.ini` as the seeded path with verified slot-data ingestion for selected seed content.
- [x] Confirm runtime fallback boundary:
  - no slot-data reference permits explicit demo fallback
  - bad slot-data hash rejects seeded mode
  - selected seeded mode does not mix in demo checks or local fallback rewards
- [ ] Ensure real bridge import remains merge-safe and replay-safe across mission restarts and revisits.

### P4. Runtime Logic Evaluator and Tracker APIs

- [ ] Replace the numeric prerequisite path with a discrete evaluator built around:
  - cluster-local unit-type rules
  - individual unit/item weakness coverage
  - required production-facility checks
  - mission `Hold`
  - mission `Win`
  - mission buff floors
- [ ] Implement runtime queries that return:
  - final `Green / Yellow / Red`
  - mission `Hold` status
  - mission `Win` status
  - missing-type text for clusters
- [ ] Keep `Yellow` tracker-only in runtime behavior and ensure it never grants AP access.
- [ ] Gate medium clusters on `Hold` and hard clusters on `Win`.
- [ ] Add automated coverage for the evaluator truth tables and ID translation rules.

### P5. UI, Packaging, and Optional Follow-On Work

- [ ] Use the generated-only WND workbench flow in [WND-UI-Workbench.md](../Operations/WND-UI-Workbench.md) to extract `MainMenu.wnd` and reference menus, audit control names, and iterate on loose overrides before touching live AP backend code.
- [ ] Build the main-menu AP shell:
  - connect flow
  - check tracker
  - logic tracker
  - mission select
- [ ] Build the first-player packaging / staging flow around clone + `-userDataDir`.
- [ ] Add a release manifest that records:
  - GeneralsAP commit
  - SuperHackers upstream state
  - Archipelago vendor version
- [ ] Implement alpha items that survive the grouped-only contract cleanly.
- [ ] Leave trap content as future work rather than part of the current alpha presets.
- [ ] Revisit transport compositions only after the core evaluator and AP seed contract are stable.
- [ ] Revisit optional location families only after alpha mission + cluster logic is proven.

---

## 4. Explicitly Deferred From Alpha-Core

These are not blockers for the first AP alpha unless the design is deliberately reopened:

- [ ] Capture, build-count, survive-duration, and destroy-building location families
- [ ] Unit / building / upgrade granularity toggles
- [ ] `clusters_per_map`, `slots_per_cluster`, and `include_superweapons_in_logic` as user-facing supported options
- [ ] Stealth / marksman progression clusters
- [ ] Making `Shared_BaseDefenses` a primary cluster-logic proof
- [ ] Numeric player-strength logic as the main access oracle

---

## 5. Recommended Implementation Lanes

| Lane | Scope | Depends on | Deliverable checkpoint |
|------|-------|------------|------------------------|
| `L1` | Contract + seed schema | none | rewritten [Slot-Data-Format.md](../../../Data/Archipelago/Slot-Data-Format.md), stable runtime keys, stable numeric ID contract |
| `L1A` | Visual logic authoring tool | `L1` capability schema draft | expanded `tools/cluster-editor` or sibling web app for unit/item/weakness editing, icon review, derivation, overrides, and validation |
| `L2` | AP world skeleton | `L1` | committed `worlds/generalszh` scaffold, grouped item table, mission/cluster location table |
| `L3` | Bridge sidecar | `L1`, partial `L2` | real bridge lifecycle, slot-data materialization, ID translation, duplicate protection |
| `L4` | Runtime ingestion + evaluator | `L1`, `L3` | selected-check registry, slot-data loader, discrete evaluator, tracker query API |
| `L5` | UI / tracker / mission select | `L1` mock payload, `L4` query surface | fixture-driven menu shell and tracker presentation |
| `L6` | Packaging + fixtures + playtest | none | release manifest, package layout, validation matrix, profile-isolation checks |

Practical order:

1. `L1`
2. `L1A` starts as soon as the capability schema draft exists
3. `L2` + `L3` + `L6` in parallel
4. `L4`
5. `L5`

---

## 6. Exit Criteria For This Phase

- [ ] Canonical docs, static contract docs, and context index all agree on the approved alpha model.
- [ ] Capability-satisfaction data can express unit item + production facility requirements.
- [ ] The visual logic authoring tool can derive, edit, validate, and export explicit cluster weaknesses.
- [ ] A committed `worlds/generalszh` implementation exists.
- [ ] Stable numeric item and location IDs are committed.
- [x] Local fixture bridge translation can round-trip runtime check keys into AP numeric location IDs.
- [ ] Runtime logic uses the discrete evaluator instead of the older numeric scaffold.
- [ ] Tracker/UI work consumes the approved payload instead of inventing a parallel contract.

---

## 7. Related Documents

- [Archipelago-Logic-Implementation-Guide.md](Archipelago-Logic-Implementation-Guide.md)
- [Archipelago-Logic-Mapping-Draft.md](Archipelago-Logic-Mapping-Draft.md)
- [ARCHIPELAGO_CONTEXT_INDEX.md](../../../ARCHIPELAGO_CONTEXT_INDEX.md)
- [Archipelago-State-Sync-Architecture.md](../Operations/Archipelago-State-Sync-Architecture.md)
- [Player-Release-Architecture.md](../Operations/Player-Release-Architecture.md)
