#!/usr/bin/env python3
"""Import an official Archipelago release into the managed vendor lane."""

from __future__ import annotations

import argparse
from pathlib import Path

from archipelago_vendor_helpers import (
    DEFAULT_UPSTREAM_REPO,
    DEFAULT_WORKTREE,
    REPO_ROOT,
    ensure_clean_worktree,
    import_release,
    load_vendor_metadata,
    materialize_vendor_worktree,
    resolve_release_tag,
    save_vendor_metadata,
    utc_now_iso,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync the managed Archipelago vendor tree to an upstream release")
    parser.add_argument("--tag", help="Release tag to import. Defaults to the latest release.")
    parser.add_argument("--repo", default=DEFAULT_UPSTREAM_REPO)
    parser.add_argument("--skip-materialize", action="store_true")
    parser.add_argument("--materialize-output", type=Path, default=DEFAULT_WORKTREE)
    parser.add_argument("--allow-dirty", action="store_true", help="Skip the clean-worktree safety check")
    parser.add_argument("--print-latest-tag", action="store_true", help="Resolve and print the latest release tag, then exit")
    args = parser.parse_args()

    if args.print_latest_tag:
        print(resolve_release_tag(args.repo, None))
        return 0

    if not args.allow_dirty:
        ensure_clean_worktree()

    tag = resolve_release_tag(args.repo, args.tag)
    import_release(args.repo, tag)

    metadata = load_vendor_metadata()
    metadata.setdefault("upstream", {})
    metadata.setdefault("layout", {})
    metadata.setdefault("policy", {})
    metadata["upstream"]["repo"] = args.repo
    metadata["upstream"]["tracking"] = "latest_release" if args.tag is None else "explicit_release"
    metadata["upstream"]["current_release_tag"] = tag
    metadata["upstream"]["sync_strategy"] = "release_archive_plus_overlay_and_patches"
    metadata["upstream"]["last_synced_at_utc"] = utc_now_iso()
    metadata["layout"]["upstream_dir"] = "vendor/archipelago/upstream"
    metadata["layout"]["overlay_dir"] = "vendor/archipelago/overlay"
    metadata["layout"]["patch_dir"] = "vendor/archipelago/patches"
    metadata["layout"]["materialized_worktree_dir"] = (
        args.materialize_output.relative_to(REPO_ROOT).as_posix()
        if args.materialize_output.is_absolute()
        else args.materialize_output.as_posix()
    )
    metadata["policy"]["edit_upstream_directly"] = False
    metadata["policy"]["use_overlay_for_additive_files"] = True
    metadata["policy"]["use_patches_for_upstream_edits"] = True
    save_vendor_metadata(metadata)

    if args.skip_materialize:
        print(f"Imported Archipelago release {tag} into vendor/archipelago/upstream")
        return 0

    manifest = materialize_vendor_worktree(args.materialize_output)
    metadata["upstream"]["last_materialized_at_utc"] = utc_now_iso()
    save_vendor_metadata(metadata)
    print(f"Imported Archipelago release {tag} into vendor/archipelago/upstream")
    print(f"Materialized worktree at {args.materialize_output}")
    print(f"Overlay files copied: {len(manifest['overlay_files'])}")
    print(f"Patches applied: {len(manifest['patches'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
