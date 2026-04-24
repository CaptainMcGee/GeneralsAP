#!/usr/bin/env bash
# Create a merge-based upstream sync branch for GeneralsAP.
# Usage: ./scripts/superhackers_upstream_sync.sh [--dry-run] [--skip-validate] [--base-branch main]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=""
SKIP_VALIDATE=""
BASE_BRANCH="main"

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --skip-validate)
            SKIP_VALIDATE=1
            ;;
        --base-branch)
            shift
            BASE_BRANCH="${1:-main}"
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
    shift
done

if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Working directory is not clean. Commit or stash changes first." >&2
    git status --short
    exit 1
fi

origin_url="$(git remote get-url origin 2>/dev/null || true)"
if echo "$origin_url" | grep -qE 'TheSuperHackers/GeneralsGameCode|GeneralsGameCode\.git'; then
    echo "WARNING: origin still points to TheSuperHackers/GeneralsGameCode. Configure your GitHub fork as origin before pushing sync branches." >&2
fi

upstream_url="$(git remote get-url upstream 2>/dev/null || true)"
if [ -z "$upstream_url" ]; then
    if echo "$origin_url" | grep -qE 'TheSuperHackers/GeneralsGameCode|GeneralsGameCode\.git'; then
        git remote rename origin upstream
        upstream_url="$(git remote get-url upstream)"
        echo "Renamed SuperHackers remote from origin to upstream."
    else
        git remote add upstream https://github.com/TheSuperHackers/GeneralsGameCode.git
        upstream_url="$(git remote get-url upstream)"
    fi
fi

echo "Using upstream remote: $upstream_url"
git fetch upstream main
if [ -n "$origin_url" ]; then
    git fetch origin "$BASE_BRANCH"
fi

merge_base="$(git merge-base "$BASE_BRANCH" upstream/main)"
upstream_tip="$(git rev-parse upstream/main)"
commits_behind="$(git rev-list --count "$merge_base..$upstream_tip")"
if [ "$commits_behind" = "0" ]; then
    echo "Already up to date with upstream/main."
    exit 0
fi

echo
echo "$commits_behind new commit(s) from upstream/main:"
git log --oneline "$merge_base..$upstream_tip"

if [ -n "$DRY_RUN" ]; then
    echo
    echo "Dry run only. No branch created."
    exit 0
fi

git checkout "$BASE_BRANCH"
if [ -n "$origin_url" ]; then
    git pull --ff-only origin "$BASE_BRANCH"
fi

base_branch_name="codex/upstream-sync-$(date +%Y-%m-%d)"
branch_name="$base_branch_name"
suffix=1
while git show-ref --verify --quiet "refs/heads/$branch_name" || { [ -n "$origin_url" ] && git ls-remote --exit-code --heads origin "$branch_name" >/dev/null 2>&1; }; do
    branch_name="${base_branch_name}-${suffix}"
    suffix=$((suffix + 1))
done

git checkout -b "$branch_name"
echo
echo "Created sync branch $branch_name"

if ! git merge upstream/main --no-ff --no-commit; then
    echo
    echo "Merge had conflicts. Resolve them on $branch_name, regenerate outputs, then commit." >&2
    git diff --name-only --diff-filter=U | sed 's/^/  /'
    echo "See Docs/Archipelago/Operations/SuperHackers-Upstream-Sync.md for the merge policy and regeneration steps." >&2
    exit 1
fi

if [ -z "$SKIP_VALIDATE" ]; then
    echo
    echo "Running scripts/archipelago_run_checks.py..."
    if command -v python >/dev/null 2>&1; then
        python scripts/archipelago_run_checks.py
    elif command -v python3 >/dev/null 2>&1; then
        python3 scripts/archipelago_run_checks.py
    else
        echo "ERROR: No usable Python interpreter found." >&2
        exit 1
    fi
fi

for file in \
    Data/Archipelago/ingame_names.json \
    Data/Archipelago/generated_unit_matchup_graph.json \
    Data/Archipelago/generated_unit_matchup_graph.csv \
    Data/Archipelago/generated_unit_matchup_graph_readable.txt \
    Data/INI/Archipelago.ini
    do
    if [ -f "$file" ]; then
        git add "$file"
    fi
done

if git diff --cached --quiet; then
    echo "ERROR: No staged changes found after merging upstream/main." >&2
    exit 1
fi

git commit -m "Merge upstream/main into $branch_name"

echo
echo "Sync branch committed successfully."
if [ -n "$origin_url" ]; then
    echo "Push it with: git push origin $branch_name"
else
    echo "Add your GitHub fork as origin before pushing this branch."
fi
echo "Open a PR into main after review and CI."
