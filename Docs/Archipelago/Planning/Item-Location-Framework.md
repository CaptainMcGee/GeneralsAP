# GeneralsAP Item and Location Framework

**Status**: framework scaffold for adding more items and locations without replacing the current seed/runtime contract.

**Scope**: item and location families, ID/runtime-key lanes, economy/buff semantics, and count strategy.

**Out of scope**: weakness evaluator, mission `Hold` / `Win` tables, authoring UI, tracker UI, YAML difficulty modes, and final game balance.

---

## 1. Core Rule

Do not add one-off AP items or locations directly to fill pressure.

Every new check must belong to a named location family with:

- deterministic AP ID formula
- canonical runtime key pattern
- clear runtime owner
- clear persistence rule
- default-enabled status
- validation tests

Every new item must belong to a named item family with:

- AP classification
- runtime effect
- stacking rule
- cap rule
- bridge/session transport rule if it affects runtime state

---

## 2. Current Implemented Families

| Family | Runtime key | ID range | Default | Runtime support | Notes |
|--------|-------------|----------|---------|-----------------|-------|
| Mission victory | `mission.<map>.victory` | `270000000+` | Enabled | Implemented | Boss mission victory owns locked final `Victory` |
| Cluster unit | `cluster.<map>.cXX.uYY` | `270010000+` | Enabled | Implemented for seeded clusters | One AP location per spawned cluster unit |

---

## 3. Reserved Planned Families

| Family | Runtime key | ID range | Default | Runtime support | Notes |
|--------|-------------|----------|---------|-----------------|-------|
| Captured building | `capture.<map>.bXXX` | `270090000+` | Disabled | Planned | Completing check means player captured an authored building/objective |
| Supply pile threshold | `supply.<map>.pXX.tYY` | `270095000+` | Disabled | Planned | Each threshold is a one-shot AP location; pile depletion persists across mission reset |

These ranges intentionally stay below `270100000`, where item IDs begin.

---

## 4. Economy And Filler Items

| Item | Type | Runtime effect | Stack/cap |
|------|------|----------------|-----------|
| `Progressive Starting Money` | useful now, possible progression later | Permanent starting-cash floor through `startingCashBonus` | Final floor decided by bridge/runtime options |
| `Progressive Production` | useful now, possible progression later | Permanent production speed through `productionMultiplier` | Configurable `+25%` to `+100%` per item, capped at `+300%` total / `4x` multiplier |
| `Supply Cache` | filler | One-time cash drop | Apply immediately in-mission, otherwise queue for next mission start |

Production copy count formula:

```text
copies = ceil(300 / step_percent)
```

Examples:

| Step | Copies to cap | Final multiplier |
|------|---------------|------------------|
| `+25%` | `12` | `4x` |
| `+50%` | `6` | `4x` |
| `+75%` | `4` | `4x` |
| `+100%` | `3` | `4x` |

Economy/buff items should not replace missing cluster weaknesses. They can support mission `Hold` / `Win` later.

Planning-only copy counts now live in `vendor/archipelago/overlay/worlds/generalszh/content_framework.py`.
They do not change active AP item generation yet.

| Planned entry | Min | Target | Max | Notes |
|---------------|----:|-------:|----:|-------|
| `Progressive Starting Money` | `3` | `6` | `8` | Permanent economy floor granularity; final floor table waits for mission logic |
| `Progressive Production` | `3` | `6` | `12` | `3` at `+100%`, `6` at `+50%`, `12` at `+25%`, capped at `+300%` total |
| `Supply Cache` | `20` | `50` | `100` | One-time cash filler/relief, never weakness replacement |
| `Future Filler Slot` | `0` | `25` | `75` | Placeholder bucket for harmless filler items not active today |
| `Future Trap Slot` | `0` | `10` | `25` | Placeholder bucket for optional trap content not active today |

With current fixed core items, the target economy/filler plan is `109` total items before per-general unit expansion and requires `137` locations with the `25%` / `25` spare-location buffer.

---

## 5. Captured Building Locations

AP check:

- player captures an authored building/objective in a mission
- runtime completes `capture.<map>.bXXX`
- bridge translates to AP numeric location ID

AP item:

- a separate shuffled item may grant a permanent pre-captured building/objective
- receiving that item should cause runtime to spawn or transfer the matching building at mission start
- this effect persists across mission replays

Do not assume the captured-building location grants itself. AP item placement must stay shuffled.

---

## 6. Supply Pile Locations

AP locations are one-time. Repeatable supply piles must be represented as several threshold checks, not one repeatable AP location.

Example:

```text
supply.tank.p03.t01
supply.tank.p03.t02
supply.tank.p03.t03
supply.tank.p03.t04
```

Runtime behavior:

- track collected amount per pile in persistent AP state
- complete threshold checks when enough money has been collected from that pile
- do not reset thresholds after mission restart
- dry pile stays dry for AP progression purposes

Good default threshold model:

- `t01`: first meaningful collection
- `t02`: 33% depleted
- `t03`: 66% depleted
- `t04`: fully depleted

This family is good for sphere-zero and early filler because it is understandable, low-combat, and can provide many checks without requiring final weakness logic.

---

## 7. Sphere-Zero Location Strategy

Sphere-zero checks should exist to prevent several hundred unit/building/general items from choking generation.

Best candidates:

- near-start supply pile thresholds
- near-start capturable buildings
- easy clusters with one explicit weakness and no `Hold`
- main mission victory only when mission access and survival are intentionally sphere-zero

Avoid:

- hard clusters
- mission `Win` checks
- checks requiring unrevealed detection/radar/special powers
- map-object checks that can be permanently missed

Sphere-zero checks must still be real gameplay actions, not free menu clicks, unless an option explicitly enables starter freebies.

---

## 8. Count Strategy

The project needs enough locations for worst-case item granularity.

Target formula:

```text
target_location_count =
  progression_item_count
  + useful_buff_item_count
  + filler_item_count
  + trap_item_count
  + location_buffer
```

Recommended buffer:

- minimum: `+10%`
- safer for early alpha: `+25%`
- never below `+25` spare locations once per-general item mode exists

Do not solve item-count pressure by making mission logic looser. Add more low-risk checks through authored location families.

Current accounting command:

```powershell
python scripts\archipelago_item_location_capacity_report.py
```

Current scaffold findings:

- `minimal` preset has `35` fillable locations: `7` mission checks and `28` cluster-unit checks.
- `default` preset has `51` fillable locations: `7` mission checks and `44` cluster-unit checks.
- current fixed skeleton item pool has `15` item entries; `default` has `36` duplicate `Supply Cache` slots that future real items can replace before more locations are needed.
- target economy/filler/trap planning bucket has `109` total items with current fixed core included and needs `137` locations with buffer.
- inactive target location-family quotas add `107` future checks at target mode, projecting `158` default locations and covering target economy/filler pressure once runtime support exists.
- disabled future ID lanes reserve `3992` captured-building locations and `3528` supply-pile-threshold locations, but authored active future checks remain `0`.
- target `300` items with `25%` buffer requires `375` locations, so current `default` is short by `324`; this confirms future item granularity depends on adding real low-risk locations, not on loosening mission or cluster logic.

Planning-only future location targets live in `Data/Archipelago/location_families/capacity_targets.json`.
They are quotas for future authoring, not catalog records.

Planning-only candidate metadata requirements live in `Data/Archipelago/location_families/authoring_schema.json`.
They are the checklist future authoring tools must satisfy before candidates move from rough map picks to disabled catalog records.

Planning-only runtime replay/idempotency requirements live in `Data/Archipelago/location_families/runtime_persistence_contract.json`.
They are the contract future runtime and bridge work must satisfy before captured-building or supply-pile checks can be selected in production slot data.

Test-only copyable examples live in `Data/Archipelago/location_families/fixtures/example_candidates.json`.
They include one fake captured building and one fake supply pile with full authoring metadata, derived runtime keys, and production-guard coverage in tests.

| Mode | Captured buildings | Supply piles | Supply thresholds | Total future checks | Projected default locations |
|------|-------------------:|-------------:|------------------:|--------------------:|----------------------------:|
| `min` | `7` | `7` | `21` | `28` | `79` |
| `target` | `15` | `23` | `92` | `107` | `158` |
| `max` | `46` | `62` | `248` | `294` | `345` |

Map-level target mode means each main challenge map should eventually look for about `2` captured buildings and `3` supply piles with `4` thresholds each. Boss is lower at target mode: `1` captured building and `2` supply piles. These are authoring goals, not proof that every map has suitable objects yet.

Future candidate records should include:

- `authoring.candidateStatus`
- `authoring.sphereZeroRole`
- `authoring.missabilityRisk`
- `authoring.persistenceRequirement`
- `authoring.visual.icon`
- `authoring.visual.mapMarker`
- `authoring.visual.screenshotRef`
- `authoring.notes`

These fields exist so the future visual tool can show what the object is, why it is fair, whether it is safe for early spheres, and what runtime persistence it needs.

---

## 9. Catalog Files

Author-facing catalog:

- `Data/Archipelago/location_families/catalog.json`
- `Data/Archipelago/location_families/authoring_schema.json`
- `Data/Archipelago/location_families/runtime_persistence_contract.json`
- `Data/Archipelago/location_families/fixtures/example_candidates.json`
- `Data/Archipelago/location_families/README.md`

Runtime/world helpers:

- `vendor/archipelago/overlay/worlds/generalszh/location_catalog.py`
- `vendor/archipelago/overlay/worlds/generalszh/constants.py`
- `vendor/archipelago/overlay/worlds/generalszh/slot_data.py`

Validation:

```powershell
python scripts\archipelago_location_catalog_validate.py
```

The catalog currently has all map lanes and source map references, but no active future checks. That is intentional. It lets authors add capturable buildings and supply piles in a structured way while preventing AP generation from exposing checks the runtime cannot finish.

Catalog entries may omit derived fields. The validator derives and checks:

- stable AP location name
- canonical runtime key
- AP numeric location ID

If an authoring/export tool includes those fields for visualization, validation rejects drift.

`Seed-Slot-Data.json` now has empty `capturedBuildings` and `supplyPileThresholds` arrays per map. Translation plumbing can map selected catalog records in tests. Runtime can parse those sections read-only, but production generation now has an explicit guard that rejects selected future-family checks until completion and persistence exist.

The persistence contract now locks what "completion and persistence exist" means:

- future-family runtime keys must come from verified slot data only
- bridge receives runtime keys and translates them to AP numeric IDs
- duplicate completion is idempotent
- mission replay preserves family state
- wrong-seed profile import is rejected
- demo fallback cannot expose capture/supply checks
- captured-building state tracks completed `capture.<map>.bXXX` keys
- supply-pile state tracks persistent collected amount and completed `supply.<map>.pXX.tYY` thresholds

Current runtime/bridge support is only a compatibility scaffold: `ArchipelagoState.json`, `Bridge-Outbound.json`, `LocalBridgeSession.json`, and `Bridge-Inbound.json` can carry `capturedBuildingState` and `supplyPileState`, defaulting to empty arrays and preserving loaded raw arrays. The local bridge mirrors these arrays as opaque future state and does not translate them to AP IDs. This is not enough to enable the families because no capture event, supply collection tracker, or production slot-data selection exists yet.

---

## 10. Implementation Order

1. Keep new families disabled by default.
2. Add ID/runtime-key helpers and tests.
3. Add static extracted/authored catalogs.
4. Add slot-data sections for selected non-cluster checks.
5. Keep the production guard active while future-family completion is absent.
6. Teach runtime to complete and persist each family.
7. Enable family through AP option only after runtime persistence works.
8. Only then use these locations to balance full item-pool size.

This order prevents valid-looking AP seeds that the game cannot actually complete.
