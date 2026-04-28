# AP World Skeleton Notes

**Status**: checkpoint notes for the first GeneralsZH AP world skeleton.

**Target Archipelago version**: `0.6.7`.

**Skeleton source reviewed**: `hoppel16/APSkeleton`.

---

## 1. What We Kept From APSkeleton

The world keeps the useful APSkeleton shape:

- a small `World` class that delegates to item, location, region, rule, and option modules
- a separate item table
- a separate location table
- explicit `create_item`, `create_regions`, `create_items`, `set_rules`, and `fill_slot_data` hooks
- an `archipelago.json` manifest

This structure is intentionally simple so future agents can replace scaffold data without rewriting the whole world.

---

## 2. What We Rejected From The Attached Edits

The attached APSkeleton edits were not copied directly because they conflict with GeneralsAP's current vision.

Rejected assumptions:

- `44000` item/location IDs. GeneralsAP owns namespace `270000000+`.
- campaign missions as alpha checks. Current alpha goal is Generals Challenge plus boss.
- 63 challenge mission checks. Current model is one mission victory per challenge map plus selected cluster-unit checks.
- skirmish honors and skirmish medals as checks. These are outside alpha-core. Main challenge victory medals are different: they are core shuffled AP progression items.
- all locations accessible from start. Medium/hard cluster and boss logic need gates.
- empty `fill_slot_data`. GeneralsAP requires immutable seed slot data.
- `minimum_ap_version` below `0.6.7`.
- abstract mission items standing in for actual unit/building/general-power progression.

The edits are useful as beginner AP-world scaffolding, but not as the logic model.

---

## 3. Current Skeleton Contract

The committed skeleton now provides:

- AP overlay package under `vendor/archipelago/overlay/worlds/generalszh`
- manifest targeting Archipelago `0.6.7`
- canonical map keys and slots
- mission-victory AP IDs
- cluster-unit AP ID helper
- mission and cluster runtime-key helpers
- empty v2 slot-data shell
- deterministic testing slot-data payloads for `default` and `minimal`
- a slot-data validator shared by AP-world tests and the local bridge fixture path
- seven shuffled main challenge victory medal items
- boss gate requiring all seven victory medals
- boss mission victory location carrying the locked final `Victory` item as an AP event location with no normal AP address
- tests for IDs, runtime keys, manifest version, and slot-data shape
- real AP 0.6.7 generation/fill smoke and packaged bridge smoke against a local real `MultiServer.py`

The skeleton intentionally does not yet implement:

- real cluster selection
- weakness/capability logic
- unit + production facility satisfaction data
- mission `Hold` / `Win` rules
- final AP launcher/connect UI

---

## 4. Logic Expectations For Future Agents

Do not regress to generic randomizer logic.

GeneralsAP logic must preserve these rules:

- Player progression is concrete: usable units/items require their production facility.
- Units/items satisfy explicit weaknesses; players do not unlock a whole weakness category directly.
- Cluster weaknesses start mechanically derived from spawned enemy units, then become author-edited truth.
- Economy and buffs do not replace missing cluster weaknesses.
- Medium clusters require mission `Hold`.
- Hard clusters require mission `Win`.
- Mission `Hold` / `Win` logic is hybrid and hand-authored per map where needed.
- Detection, radar, and special powers can be true mission requirements.
- Slot data is immutable per seed and separate from mutable bridge state.
- Runtime consumes selected checks from slot data; it must not invent AP location IDs.

---

## 5. Next Framework Work

Recommended next framework tasks:

1. Replace the deterministic testing catalog with the authored cluster catalog exported by the visual authoring tool.
2. Add production-facility requirements to the capability data before treating weakness satisfaction as final.
3. Add the per-map mission `Hold` / `Win` table when the mission design pass is complete.
4. Teach runtime to ingest `Seed-Slot-Data.json` and spawn only selected cluster-unit checks.
5. Add AP-world smoke generation once Archipelago dependencies are installed in CI.

Do not implement final weakness tags here if another thread owns that schema.
