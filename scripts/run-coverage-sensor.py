#!/usr/bin/env python3
"""Run Gauntlet's workflow suite under coverage and report measured scope."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def run(arguments, root, *, env=None):
    return subprocess.run(arguments, cwd=root, env=env)


def main():
    root = Path(__file__).resolve().parents[1]
    coverage = shutil.which("coverage")
    if not coverage:
        print("coverage executable is unavailable")
        return 2
    run([coverage, "erase"], root)
    env = os.environ.copy()
    python_path = str(root / "scripts")
    if env.get("PYTHONPATH"):
        python_path = f"{python_path}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONPATH"] = python_path
    measured = run(
        [
            coverage,
            "run",
            "--branch",
            "--source=scripts/gauntletlib",
            "scripts/check-gauntlet-workflow.py",
        ],
        root,
        env=env,
    )
    if measured.returncode:
        return measured.returncode
    report = run(
        [
            coverage,
            "report",
            "--show-missing",
            "--skip-covered",
        ],
        root,
    )
    return report.returncode


if __name__ == "__main__":
    raise SystemExit(main())
