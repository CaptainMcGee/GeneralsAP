#!/usr/bin/env bash
# Normalize Git remotes for GeneralsAP.
# Usage: ./scripts/repo_configure_remotes.sh https://github.com/YOUR_USER/GeneralsAP.git [upstream-url]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

origin_url="${1:-}"
upstream_url="${2:-https://github.com/TheSuperHackers/GeneralsGameCode.git}"

if [ -z "$origin_url" ]; then
    echo "Usage: $0 <origin-url> [upstream-url]" >&2
    exit 1
fi

current_origin="$(git remote get-url origin 2>/dev/null || true)"
current_upstream="$(git remote get-url upstream 2>/dev/null || true)"

if [ -n "$current_origin" ] && [ "$current_origin" = "$upstream_url" ] && [ -z "$current_upstream" ]; then
    git remote rename origin upstream
    current_origin=""
    current_upstream="$upstream_url"
fi

if [ -n "$current_upstream" ]; then
    if [ "$current_upstream" != "$upstream_url" ]; then
        git remote set-url upstream "$upstream_url"
    fi
else
    git remote add upstream "$upstream_url"
fi

if [ -n "$current_origin" ]; then
    if [ "$current_origin" != "$origin_url" ]; then
        git remote set-url origin "$origin_url"
    fi
else
    git remote add origin "$origin_url"
fi

git remote -v
