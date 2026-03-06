#!/usr/bin/env python3
"""Capture materialized Archipelago worktree changes back into overlay and patch lanes."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from archipelago_vendor_helpers import (
    DEFAULT_WORKTREE,
    VENDOR_OVERLAY,
    VENDOR_PATCHES,
    VENDOR_UPSTREAM,
    materialize_vendor_worktree,
    run_command,
)

PRESERVE_FILES = {"README.md"}
MANIFEST_NAME = ".generalsap_archipelago_vendor_manifest.json"


def clear_directory_contents(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    for child in path.iterdir():
        if child.name in PRESERVE_FILES:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.name == MANIFEST_NAME:
            continue
        if ".git" in relative.parts:
            continue
        files.append(relative)
    return files


def refresh_overlay(worktree: Path) -> list[str]:
    clear_directory_contents(VENDOR_OVERLAY)
    copied: list[str] = []
    for relative in iter_files(worktree):
        if (VENDOR_UPSTREAM / relative).exists():
            continue
        destination = VENDOR_OVERLAY / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(worktree / relative, destination)
        copied.append(relative.as_posix())
    return copied


def build_patch_from_worktree(worktree: Path, patch_path: Path) -> bool:
    with tempfile.TemporaryDirectory(prefix="generalsap-archipelago-capture-") as temp_dir_name:
        temp_root = Path(temp_dir_name)
        repo = temp_root / "repo"
        shutil.copytree(VENDOR_UPSTREAM, repo)

        run_command(["git", "init", "-q"], cwd=repo)
        run_command(["git", "config", "user.name", "GeneralsAP Vendor Bot"], cwd=repo)
        run_command(["git", "config", "user.email", "vendor@example.invalid"], cwd=repo)
        run_command(["git", "config", "core.autocrlf", "false"], cwd=repo)
        run_command(["git", "add", "-A"], cwd=repo)
        run_command(["git", "commit", "-q", "-m", "baseline"], cwd=repo)

        for relative in iter_files(VENDOR_UPSTREAM):
            upstream_copy = repo / relative
            materialized = worktree / relative
            if materialized.exists():
                upstream_copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(materialized, upstream_copy)
            elif upstream_copy.exists():
                upstream_copy.unlink()

        run_command(["git", "add", "-A"], cwd=repo)
        patch_text = run_command(["git", "diff", "--binary", "--cached", "HEAD"], cwd=repo, capture_output=True)

    clear_directory_contents(VENDOR_PATCHES)
    if not patch_text.strip():
        if patch_path.exists():
            patch_path.unlink()
        return False

    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(patch_text, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture materialized Archipelago changes into overlay/patch lanes")
    parser.add_argument("--worktree", type=Path, default=DEFAULT_WORKTREE)
    parser.add_argument("--patch-name", default="0001-generalsap.patch")
    parser.add_argument(
        "--materialize-first",
        action="store_true",
        help="Rebuild the materialized worktree before capturing changes",
    )
    args = parser.parse_args()

    worktree = args.worktree
    if args.materialize_first:
        materialize_vendor_worktree(worktree)
    if not worktree.exists():
        raise FileNotFoundError(
            f"{worktree} not found. Run scripts/archipelago_vendor_materialize.py first or pass --materialize-first."
        )

    overlay_files = refresh_overlay(worktree)
    patch_path = VENDOR_PATCHES / args.patch_name
    has_patch = build_patch_from_worktree(worktree, patch_path)

    print(f"Captured overlay files: {len(overlay_files)}")
    print(f"Patch written: {patch_path if has_patch else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
