# Archipelago Vendor Sync Workflow

GeneralsAP tracks two upstreams with different shapes:

- SuperHackers game code: merge-based Git upstream (`origin`/`upstream` model)
- Archipelago: managed vendor lane based on official releases

Archipelago should not be maintained as a permanently hand-edited snapshot. Instead, keep a clean imported release under `vendor/archipelago/upstream`, keep our additive files in `vendor/archipelago/overlay`, and keep unavoidable upstream-file edits in `vendor/archipelago/patches`.

## Layout

- `vendor/archipelago/upstream`
- `vendor/archipelago/overlay`
- `vendor/archipelago/patches`
- `vendor/archipelago/vendor.json`
- `build/archipelago/archipelago-worktree`

## Rules

- Do not edit `vendor/archipelago/upstream` directly during feature work.
- Add new Generals-specific content to `overlay` with upstream-relative paths.
- Encode edits to upstream-owned files as ordered patch files in `patches`.
- Treat `build/archipelago/archipelago-worktree` as disposable.
- `vendor/archipelago/overlay/README.md` is metadata only and is intentionally not copied into the materialized worktree.

## Local Workflow

1. Materialize a combined Archipelago worktree:
   - `python scripts/archipelago_vendor_materialize.py`
2. Run the real GeneralsZH AP generation smoke:
   - `python scripts/archipelago_run_real_ap_smoke.py --skip-install`
   - omit `--skip-install` the first time, or after dependency changes
3. Review or experiment in `build/archipelago/archipelago-worktree`.
4. When you want to preserve Generals-owned changes back into the managed vendor lane:
   - `python scripts/archipelago_vendor_capture.py`
5. Re-materialize and confirm the worktree reproduces the intended result.

`archipelago_vendor_capture.py` rewrites `overlay/` from additive files and regenerates a patch file for edits to upstream-managed files. That keeps the vendor delta reviewable and replayable across future Archipelago releases.

## Release Sync Workflow

Use a dedicated branch for every Archipelago release ingest:

```powershell
./scripts/archipelago_vendor_sync.ps1
```

```bash
./scripts/archipelago_vendor_sync.sh
```

These wrappers:

1. require a clean worktree
2. resolve the latest release tag unless one is supplied
3. create `codex/archipelago-sync-<tag>`
4. import the upstream release into `vendor/archipelago/upstream`
5. refresh `vendor/archipelago/vendor.json`
6. materialize the combined worktree to verify overlay/patch compatibility
7. commit the vendor refresh

## Why Releases, Not Live Mainline

Archipelago is its own fast-moving project with broad ecosystem churn. Tracking official releases instead of arbitrary commits keeps the Generals integration stable, makes regression windows smaller, and reduces the number of times we need to re-resolve the same conflicts.

## Conflict Model

When a new Archipelago release lands:

- upstream snapshot changes are isolated to `vendor/archipelago/upstream`
- Generals-owned new files stay in `overlay`
- Generals-owned edits to upstream files fail fast if a patch no longer applies

That gives a precise maintenance signal: either the overlay still composes cleanly, or a specific patch needs to be updated for the new release.

## Automation

`.github/workflows/sync-archipelago-vendor-vendor.yml` can create a vendor-sync PR for the latest release. Use it for routine updates, then review the overlay/patch compatibility before merging.
