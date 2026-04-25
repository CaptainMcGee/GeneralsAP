#!/usr/bin/env python3
"""Create a minimal AP smoke venv and run the real GeneralsZH AP generation smoke."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
DEFAULT_VENV = REPO_ROOT / "build" / "archipelago" / "ap-smoke-venv"
REQUIREMENTS = SCRIPTS / "requirements-archipelago-smoke.txt"
MATERIALIZE = SCRIPTS / "archipelago_vendor_materialize.py"
SMOKE = SCRIPTS / "tests" / "test_archipelago_generation_smoke_optional.py"


def venv_python(venv_dir: Path) -> Path:
    windows_python = venv_dir / "Scripts" / "python.exe"
    if windows_python.exists():
        return windows_python
    return venv_dir / "bin" / "python"


def run(args: list[str], cwd: Path = REPO_ROOT) -> None:
    print(f"> {' '.join(args)}", flush=True)
    subprocess.run(args, cwd=str(cwd), check=True)


def recreate_venv_if_requested(venv_dir: Path, recreate: bool) -> None:
    if not recreate or not venv_dir.exists():
        return
    resolved = venv_dir.resolve()
    allowed_root = (REPO_ROOT / "build" / "archipelago").resolve()
    if allowed_root not in resolved.parents:
        raise RuntimeError(f"Refusing to delete venv outside build/archipelago: {resolved}")
    shutil.rmtree(resolved)


def ensure_venv(venv_dir: Path) -> Path:
    python = venv_python(venv_dir)
    if not python.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])
    python = venv_python(venv_dir)
    if not python.exists():
        raise RuntimeError(f"Venv python not found after creation: {python}")
    return python


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real GeneralsZH AP generation smoke in an isolated venv.")
    parser.add_argument("--venv", type=Path, default=DEFAULT_VENV)
    parser.add_argument("--recreate-venv", action="store_true")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--skip-materialize", action="store_true")
    args = parser.parse_args()

    recreate_venv_if_requested(args.venv, args.recreate_venv)
    python = ensure_venv(args.venv)

    if not args.skip_install:
        run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(REQUIREMENTS),
            ]
        )

    if not args.skip_materialize:
        run([sys.executable, str(MATERIALIZE)])

    run([str(python), str(SMOKE)])
    print("PASS: real AP smoke environment is ready", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
