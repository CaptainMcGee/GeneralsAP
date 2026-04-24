# Archipelago Vendor Lane

This directory manages the third-party Archipelago codebase used as GeneralsAP reference material and future integration surface.

## Layout

- `upstream/`: imported source snapshot from the official Archipelago release
- `overlay/`: GeneralsAP-owned additive files that should be layered on top of upstream
- `patches/`: ordered patch files for unavoidable edits to upstream-managed files
- `vendor.json`: tracking metadata for the imported upstream release and sync policy

## Policy

- Do not hand-edit `upstream/` on normal feature branches.
- Put new Generals-specific files under `overlay/` using the same relative paths they should have in an Archipelago checkout.
- If GeneralsAP must change an upstream file, capture that change as a patch in `patches/` instead of keeping an unstructured fork.
- Rebuild a combined working copy with `python scripts/archipelago_vendor_materialize.py`.
- Preserve edits from the disposable worktree with `python scripts/archipelago_vendor_capture.py`.
- Update upstream releases with `python scripts/archipelago_vendor_sync.py --tag <release>` or the sync workflow.
- `overlay/README.md` is vendor-lane metadata and is intentionally excluded from the materialized worktree.

## Why This Model

A raw vendored snapshot is easy to import but hard to maintain across releases. A submodule keeps upstream history, but pushes the real merge problem into another repository. This vendor lane keeps the upstream snapshot explicit while making Generals-specific changes deliberate, reviewable, and replayable.

## Commands

```bash
python scripts/archipelago_vendor_materialize.py
python scripts/archipelago_vendor_capture.py
python scripts/archipelago_vendor_sync.py --print-latest-tag
python scripts/archipelago_vendor_sync.py --tag 0.6.5
```

The materialized output defaults to `build/archipelago/archipelago-worktree` and is intentionally treated as disposable build output.
