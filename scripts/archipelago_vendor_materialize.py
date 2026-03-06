#!/usr/bin/env python3
"""Materialize the managed Archipelago vendor tree into a disposable working copy."""

from __future__ import annotations

import argparse
from pathlib import Path

from archipelago_vendor_helpers import DEFAULT_WORKTREE, materialize_vendor_worktree


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize the vendored Archipelago tree with overlay and patches")
    parser.add_argument("--output", type=Path, default=DEFAULT_WORKTREE)
    parser.add_argument("--no-clean", action="store_true", help="Do not delete the output directory before materializing")
    args = parser.parse_args()

    manifest = materialize_vendor_worktree(args.output, clean=not args.no_clean)
    print(f"Materialized Archipelago worktree at {args.output}")
    print(f"Release: {manifest['vendor_release_tag']}")
    print(f"Overlay files copied: {len(manifest['overlay_files'])}")
    print(f"Patches applied: {len(manifest['patches'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
