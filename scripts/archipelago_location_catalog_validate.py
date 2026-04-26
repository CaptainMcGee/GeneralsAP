#!/usr/bin/env python3
"""Validate future non-cluster Archipelago location family catalogs."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OVERLAY_WORLDS = REPO / "vendor" / "archipelago" / "overlay" / "worlds"
DEFAULT_CATALOG = REPO / "Data" / "Archipelago" / "location_families" / "catalog.json"
DEFAULT_AUTHORING_SCHEMA = REPO / "Data" / "Archipelago" / "location_families" / "authoring_schema.json"


def load_generalszh_location_catalog_helpers():
    if str(OVERLAY_WORLDS) not in sys.path:
        sys.path.insert(0, str(OVERLAY_WORLDS))
    worlds_pkg = types.ModuleType("worlds")
    worlds_pkg.__path__ = [str(OVERLAY_WORLDS)]  # type: ignore[attr-defined]
    sys.modules.setdefault("worlds", worlds_pkg)
    generals_pkg = types.ModuleType("worlds.generalszh")
    generals_pkg.__path__ = [str(OVERLAY_WORLDS / "generalszh")]  # type: ignore[attr-defined]
    sys.modules.setdefault("worlds.generalszh", generals_pkg)
    from worlds.generalszh.location_catalog import (  # type: ignore[import-not-found]
        catalog_location_counts,
        iter_catalog_location_records,
        validate_location_authoring_schema,
        validate_location_catalog,
    )

    return catalog_location_counts, iter_catalog_location_records, validate_location_catalog, validate_location_authoring_schema


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    catalog_path = Path(argv[0]) if argv else DEFAULT_CATALOG
    if not catalog_path.is_absolute():
        catalog_path = REPO / catalog_path
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    catalog_location_counts, iter_catalog_location_records, validate_location_catalog, validate_location_authoring_schema = load_generalszh_location_catalog_helpers()
    warnings = validate_location_catalog(catalog)
    counts = catalog_location_counts(catalog)
    records = list(iter_catalog_location_records(catalog))
    schema = json.loads(DEFAULT_AUTHORING_SCHEMA.read_text(encoding="utf-8"))
    schema_warnings = validate_location_authoring_schema(schema)

    print(f"Catalog: {catalog_path.relative_to(REPO)}")
    print(f"Authoring schema: {DEFAULT_AUTHORING_SCHEMA.relative_to(REPO)}")
    print(f"Captured buildings: {counts['captured_building']}")
    print(f"Supply pile thresholds: {counts['supply_pile_threshold']}")
    print(f"Total future locations: {counts['total']}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for warning in schema_warnings:
        print(f"WARNING: {warning}")
    if records:
        print("First records:")
        for record in records[:5]:
            print(f"- {record['runtimeKey']} -> {record['apLocationId']} ({record['locationName']})")
    print("OK: location catalog validates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
