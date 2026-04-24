#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

tag="${1:-}"
base_branch="${BASE_BRANCH:-main}"
skip_materialize="${SKIP_MATERIALIZE:-0}"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working directory is not clean. Commit or stash changes first." >&2
  git status --short
  exit 1
fi

python_cmd=()
if command -v python >/dev/null 2>&1; then
  python_cmd=(python)
elif command -v python3 >/dev/null 2>&1; then
  python_cmd=(python3)
elif command -v py >/dev/null 2>&1; then
  python_cmd=(py -3)
else
  echo "No usable Python interpreter found." >&2
  exit 1
fi

if [[ -z "$tag" ]]; then
  tag="$(${python_cmd[@]} scripts/archipelago_vendor_sync.py --print-latest-tag)"
fi

safe_tag="${tag//[^A-Za-z0-9._-]/-}"
branch_name="codex/archipelago-sync-$safe_tag"
suffix=1
while git show-ref --verify --quiet "refs/heads/$branch_name"; do
  branch_name="codex/archipelago-sync-$safe_tag-$suffix"
  suffix=$((suffix + 1))
done

git switch "$base_branch"
git switch -c "$branch_name"

args=(scripts/archipelago_vendor_sync.py --tag "$tag")
if [[ "$skip_materialize" == "1" ]]; then
  args+=(--skip-materialize)
fi
"${python_cmd[@]}" "${args[@]}"

git add vendor/archipelago/upstream vendor/archipelago/vendor.json
if git diff --cached --quiet; then
  echo "No Archipelago vendor changes detected for $tag" >&2
  exit 0
fi

git commit -m "vendor(archipelago): import upstream $tag"
echo "Created $branch_name"
