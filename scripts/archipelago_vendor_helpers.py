#!/usr/bin/env python3
"""Helpers for managing the vendored Archipelago upstream snapshot."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = REPO_ROOT / "vendor" / "archipelago"
VENDOR_UPSTREAM = VENDOR_ROOT / "upstream"
VENDOR_OVERLAY = VENDOR_ROOT / "overlay"
VENDOR_PATCHES = VENDOR_ROOT / "patches"
VENDOR_METADATA = VENDOR_ROOT / "vendor.json"
DEFAULT_WORKTREE = REPO_ROOT / "build" / "archipelago" / "archipelago-worktree"
DEFAULT_UPSTREAM_REPO = "ArchipelagoMW/Archipelago"


def run_command(args: list[str], cwd: Path | None = None, capture_output: bool = False) -> str:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=capture_output,
        check=False,
    )
    if result.returncode != 0:
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        message = f"Command failed ({result.returncode}): {' '.join(args)}"
        if stdout:
            message += f"\nSTDOUT:\n{stdout}"
        if stderr:
            message += f"\nSTDERR:\n{stderr}"
        raise RuntimeError(message)
    return result.stdout.strip() if capture_output else ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sanitize_ref_fragment(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in ".-_":
            safe.append(char)
        else:
            safe.append("-")
    return "".join(safe).strip(".-") or "unknown"


def load_vendor_metadata() -> dict:
    if not VENDOR_METADATA.exists():
        return {}
    return json.loads(VENDOR_METADATA.read_text(encoding="utf-8"))


def save_vendor_metadata(data: dict) -> None:
    VENDOR_METADATA.parent.mkdir(parents=True, exist_ok=True)
    VENDOR_METADATA.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_clean_worktree() -> None:
    status = run_command(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True)
    if status:
        raise RuntimeError("Working directory is not clean. Commit or stash changes before syncing Archipelago.")


def resolve_release_tag(repo: str, requested_tag: str | None = None) -> str:
    if requested_tag:
        return requested_tag.strip()
    payload = run_command(
        ["gh", "release", "view", "--repo", repo, "--json", "tagName"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    data = json.loads(payload)
    tag = str(data.get("tagName", "")).strip()
    if not tag:
        raise RuntimeError(f"Could not resolve latest release tag for {repo}")
    return tag


def download_release_archive(repo: str, tag: str, download_dir: Path) -> Path:
    if download_dir.exists():
        shutil.rmtree(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        ["gh", "release", "download", tag, "--repo", repo, "--archive", "zip", "--clobber", "--dir", str(download_dir)],
        cwd=REPO_ROOT,
    )
    archives = sorted(download_dir.glob("*.zip"))
    if not archives:
        raise RuntimeError(f"No release archive downloaded for {repo} {tag}")
    return archives[0]


def extract_release_archive(archive_path: Path, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(destination)
    children = [path for path in destination.iterdir()]
    child_dirs = [path for path in children if path.is_dir()]
    child_files = [path for path in children if path.is_file()]
    if len(child_dirs) == 1 and not child_files:
        return child_dirs[0]
    return destination


def replace_tree_contents(destination: Path, source: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def copy_overlay(target_root: Path) -> list[str]:
    copied: list[str] = []
    if not VENDOR_OVERLAY.exists():
        return copied
    for path in sorted(VENDOR_OVERLAY.rglob("*")):
        relative = path.relative_to(VENDOR_OVERLAY)
        if relative == Path("README.md"):
            continue
        destination = target_root / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied.append(relative.as_posix())
    return copied


def patch_files() -> list[Path]:
    if not VENDOR_PATCHES.exists():
        return []
    return sorted(path for path in VENDOR_PATCHES.rglob("*.patch") if path.is_file())


def apply_patches(target_root: Path) -> list[str]:
    applied: list[str] = []
    patches = patch_files()
    if not patches:
        return applied
    temp_git_dir = target_root / ".git"
    if temp_git_dir.exists():
        shutil.rmtree(temp_git_dir)
    run_command(["git", "init", "-q"], cwd=target_root)
    try:
        for patch in patches:
            run_command(["git", "apply", "--check", str(patch)], cwd=target_root)
            run_command(["git", "apply", str(patch)], cwd=target_root)
            applied.append(patch.relative_to(VENDOR_ROOT).as_posix())
    finally:
        if temp_git_dir.exists():
            shutil.rmtree(temp_git_dir)
    return applied


def materialize_vendor_worktree(output_root: Path = DEFAULT_WORKTREE, clean: bool = True) -> dict:
    if clean and output_root.exists():
        shutil.rmtree(output_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(VENDOR_UPSTREAM, output_root, dirs_exist_ok=not clean)
    copied_overlay = copy_overlay(output_root)
    applied_patches = apply_patches(output_root)
    metadata = load_vendor_metadata()
    manifest = {
        "generated_at_utc": utc_now_iso(),
        "vendor_release_tag": metadata.get("upstream", {}).get("current_release_tag", "unknown"),
        "overlay_files": copied_overlay,
        "patches": applied_patches,
    }
    manifest_path = output_root / ".generalsap_archipelago_vendor_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def import_release(repo: str, tag: str) -> None:
    with tempfile.TemporaryDirectory(prefix="generalsap-archipelago-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        download_dir = temp_dir / "download"
        extract_dir = temp_dir / "extract"
        archive = download_release_archive(repo, tag, download_dir)
        source_root = extract_release_archive(archive, extract_dir)
        replace_tree_contents(VENDOR_UPSTREAM, source_root)
