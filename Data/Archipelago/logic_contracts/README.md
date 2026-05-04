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
- `fixtures/example_logic_contracts.json`: disabled example fixture proving shape and validation.

## Validation

Run:

```powershell
python scripts\archipelago_logic_contract_validate.py
```

Validator checks:

- allowed map keys align with AP world constants
- allowed requirement keys align with current temporary requirement list
- money and production floors align with slot-data validator floors
- fixture remains disabled and contract-only
- no Boss medal or final Victory item appears as normal capability-source output

## Future Enable Path

Before these contracts can feed real logic:

1. Weakness App exports capability-source records from author-edited data.
2. Mission-gate pass exports per-map gate rows.
3. Validator runs in AP-world CI.
4. AP world converts validated records into access rules.
5. Slot-data still emits only selected checks, not item placement.
6. Runtime remains ignorant of AP numeric IDs and only consumes runtime keys.

Do not use this folder to sneak in final requirement tables. It is contract shape only.
