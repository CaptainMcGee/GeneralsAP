# Upstream Sync Workflow

This repository should be operated as a normal project fork:

- `origin` = your GeneralsAP GitHub repository
- `upstream` = `https://github.com/TheSuperHackers/GeneralsGameCode.git`

Do not keep day-to-day work on a remote setup where `origin` still points to SuperHackers. That makes PRs, pushes, and upstream sync review harder than necessary.

Archipelago release tracking is separate. See [Archipelago-Vendor-Sync.md](Archipelago-Vendor-Sync.md) for the managed vendor-release workflow.

## Initial Remote Setup

PowerShell:

```powershell
./scripts/repo_configure_remotes.ps1 -OriginUrl https://github.com/YOUR_USER/GeneralsAP.git
```

Shell:

```bash
./scripts/repo_configure_remotes.sh https://github.com/YOUR_USER/GeneralsAP.git
```

These helpers normalize remotes so `origin` is your repo and `upstream` is SuperHackers.

## Local Sync Flow

Use a dedicated merge branch for every upstream ingest:

```powershell
./scripts/superhackers_upstream_sync.ps1
```

```bash
./scripts/superhackers_upstream_sync.sh
```

The sync scripts now:

1. Require a clean working tree.
2. Fetch `origin/main` and `upstream/main`.
3. Create a fresh `codex/upstream-sync-YYYY-MM-DD[-N]` branch from `main`.
4. Merge `upstream/main` with `--no-ff --no-commit`.
5. Regenerate Archipelago artifacts with `scripts/archipelago_run_checks.py`.
6. Commit the merge branch once the regenerated outputs are staged.

## Merge Policy

- Prefer merge commits for upstream sync branches.
- Do not rebase published project history to ingest upstream.
- Do not hand-merge generated Archipelago artifacts when a regeneration step can recreate them.
- Review shared engine files carefully when both projects changed them.

## Generated Files to Refresh After Sync

The sync scripts and GitHub Actions workflow regenerate and restage these outputs:

- `Data/Archipelago/ingame_names.json`
- `Data/Archipelago/generated_unit_matchup_graph.json`
- `Data/Archipelago/generated_unit_matchup_graph.csv`
- `Data/Archipelago/generated_unit_matchup_graph_readable.txt`
- `Data/INI/Archipelago.ini`

## Conflict Resolution Guidance

When merge conflicts happen:

- Keep GeneralsAP-only files and generated-data contracts consistent with the current Archipelago pipeline.
- Merge shared gameplay files manually so upstream bug fixes and Archipelago hooks both survive.
- After conflict resolution, rerun `scripts/archipelago_run_checks.py` before committing the sync branch.

Paths that often require manual review:

- `GeneralsMD/Code/GameEngine/Source/GameLogic/ArchipelagoState.cpp`
- `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockRegistry.cpp`
- `GeneralsMD/Code/GameEngine/Source/GameClient/GUI/GUICallbacks/Menus/ScoreScreen.cpp`
- `GeneralsMD/Code/GameEngine/Source/GameLogic/UnlockableCheckSpawner.cpp`
- `GeneralsMD/Code/Main/CMakeLists.txt`
- `.github/workflows/*.yml`

## GitHub Actions Flow

`.github/workflows/sync-superhackers-upstream.yml` follows the same policy:

- creates a `codex/upstream-sync-*` branch
- merges `upstream/main`
- regenerates Archipelago artifacts
- validates the result
- pushes the branch and optionally opens a PR

Use that workflow for routine upstream checks, but resolve conflicts locally when the automated merge stops.
