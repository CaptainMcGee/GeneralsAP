#!/usr/bin/env python3
"""Optional real-Archipelago import smoke for the materialized GeneralsZH world."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AP_WORKTREE = REPO / "build" / "archipelago" / "archipelago-worktree"


def main() -> int:
    if not AP_WORKTREE.exists():
        print(f"SKIP: materialized Archipelago worktree missing: {AP_WORKTREE}")
        return 0

    code = f"""
import sys
from pathlib import Path
root = Path({str(AP_WORKTREE)!r})
sys.path.insert(0, str(root))
try:
    import schema  # noqa: F401
except ModuleNotFoundError as exc:
    print(f"SKIP: optional Archipelago dependency missing: {{exc}}")
    raise SystemExit(0)
try:
    from worlds.generalszh import GeneralsZHWorld
except ModuleNotFoundError as exc:
    print(f"SKIP: optional Archipelago dependency missing: {{exc}}")
    raise SystemExit(0)
except Exception as exc:
    print(f"FAIL: GeneralsZH real Archipelago import failed: {{exc}}")
    raise SystemExit(1)
print(f"PASS: imported {{GeneralsZHWorld.game}} from materialized Archipelago worktree")
"""
    return subprocess.run([sys.executable, "-c", code], cwd=str(AP_WORKTREE)).returncode


if __name__ == "__main__":
    raise SystemExit(main())
