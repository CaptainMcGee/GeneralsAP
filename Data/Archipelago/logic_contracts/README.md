# Logic Contract Handoff

This folder defines planning-only handoff contracts for future capability-source and mission-gate authoring output.

Current status: disabled contract only. Nothing in this folder feeds AP generation, slot-data fill, access rules, runtime spawning, or bridge translation yet.

Purpose:

- make future visual authoring/export tools produce data the AP world can validate
- keep player-unit capability mapping item-specific, not whole-tag unlocks
- keep unit/building prerequisites explicit
- keep economy and production floors separate from combat requirement tags
- let mission gate data be authored per map without locking final mission design today

## Current Locked Semantics

Capability-source records describe AP items that can satisfy requirement tags.

Important policy:

- a unit item does not imply the player can build that unit by itself
- a formal green source requires its listed production-facility items too
- individual AP items satisfy requirements; the player does not unlock an entire requirement category at once
- weak/support/yellow sources are notes for alpha and do not combine into one formal green requirement
- upgrades and buffs do not promote yellow sources into green cluster counters
- economy and production buffs do not replace missing cluster requirements
- economy and production floors primarily support mission gate logic later
- mission-specific special requirements may name non-unit items or powers

Examples:

- `Shared_RocketInfantry` may satisfy `anti_vehicle` and `anti_air`, but only with its required production facility.
- `GLA Ambush` may be a mission-specific special requirement for a GLA route against Superweapons General.

## Files

- `capability_sources_schema.json`: copyable shape for future Weakness App export.
- `mission_gate_schema.json`: copyable shape for future mission gate export.
- `requirement_aliases.json`: planning-only tag handoff between Logic Foundry canonical tags and current temporary AP-world requirement keys.
- `logic_foundry_export_schema.json`: copyable shape for future Logic Foundry export data.
- `fixtures/example_logic_contracts.json`: disabled example fixture proving shape and validation.
- `fixtures/logic_foundry_export_fixture.json`: disabled Logic Foundry-style fixture proving dry-run import normalization.

## Validation

Run:

```powershell
python scripts\archipelago_logic_contract_validate.py
python scripts\archipelago_logic_contract_validate.py --foundry-output Data\Archipelago\logic_contracts\fixtures\logic_foundry_export_fixture.json
```

Validator checks:

- allowed map keys align with AP world constants
- allowed requirement keys align with current temporary requirement list
- money and production floors align with slot-data validator floors
- Logic Foundry canonical tags can normalize through the temporary AP-world aliases
- mission-only and review-only tags cannot become normal AP requirements
- economy and buff items do not satisfy normal requirements
- formal unit sources list production facilities
- cluster tier/gate rules match the approved Easy / Medium / Hard contract
- fixture remains disabled and contract-only
- no Boss medal or final Victory item appears as normal capability-source output

`--foundry-output` is a dry-run validator for future app exports. It reads a JSON file, normalizes canonical tags through the alias contract, and reports what AP-facing requirements would be produced. It does not write generated data and does not enable access rules.

## Future Enable Path

Before these contracts can feed real logic:

1. Weakness App exports capability-source records from author-edited data.
2. Export data uses canonical tags such as `siege`, `frontline`, and `detection`.
3. Validator normalizes temporary AP-world aliases such as `siege_units`, `frontline_units`, and `detectors`.
4. Mission-gate pass exports per-map gate rows separately from cluster requirements.
5. Validator runs in AP-world CI.
6. AP world converts validated records into access rules in a later intentional pass.
7. Slot-data still emits only selected checks, not item placement.
8. Runtime remains ignorant of AP numeric IDs and only consumes runtime keys.

Do not use this folder to sneak in final requirement tables. It is contract shape only.
