# Future Location Family Catalog

This folder is the author-facing source for future non-cluster Archipelago checks.

Current status: catalog-only and disabled. Entries here must not become reachable AP locations until runtime completion and persistence exist for the family. Production slot-data generation has a guard that rejects selected records from these families; tests may still inject them to prove IDs and bridge translation.

`capacity_targets.json` is separate from `catalog.json`. It records planning quotas by map so future authoring knows how many captured-building and supply-pile checks to seek. It does not define real AP locations and must not feed production generation.

## Captured Buildings

Use `capturedBuildings` for authored capturable objectives.

Minimum entry shape:

```json
{
  "buildingIndex": 1,
  "label": "Near-base Oil Derrick",
  "template": "CivilianTechOilDerrick",
  "position": { "x": 1000, "y": 1200 },
  "sphere": 0,
  "authorStatus": "candidate"
}
```

Derived fields are optional in the source catalog and validated if present:

- `runtimeKey`: `capture.<map>.bXXX`
- `apLocationId`: derived from `270090000`
- `locationName`: `Captured Building - <map display> bXXX`

Do not assume this location grants itself. A separate shuffled item may later pre-capture that building at mission start.

## Supply Piles

Use `supplyPiles` for authored supply piles that produce several one-shot threshold checks.

Minimum entry shape:

```json
{
  "pileIndex": 1,
  "label": "Near-base supply pile",
  "template": "SupplyPile",
  "startingAmount": 30000,
  "position": { "x": 900, "y": 1000 },
  "sphere": 0,
  "authorStatus": "candidate",
  "thresholds": [
    { "thresholdIndex": 1, "fractionCollected": 0.1 },
    { "thresholdIndex": 2, "fractionCollected": 0.33 },
    { "thresholdIndex": 3, "fractionCollected": 0.66 },
    { "thresholdIndex": 4, "fractionCollected": 1.0 }
  ]
}
```

Each threshold becomes one AP location:

- `runtimeKey`: `supply.<map>.pXX.tYY`
- `apLocationId`: derived from `270095000`
- `locationName`: `Supply Pile - <map display> pXX tYY`

Runtime must persist pile depletion across mission restart before this family can be enabled.

## Validation

Run:

```powershell
python scripts\archipelago_location_catalog_validate.py
```
