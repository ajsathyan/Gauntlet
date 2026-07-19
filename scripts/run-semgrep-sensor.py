#!/usr/bin/env python3
"""Run the repository's high-signal Semgrep rules on changed source files."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


SOURCE_SUFFIXES = {
    ".cjs",
    ".cts",
    ".js",
    ".jsx",
    ".mjs",
    ".mts",
    ".py",
    ".ts",
    ".tsx",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    semgrep = shutil.which("semgrep")
    if not semgrep:
        print("semgrep executable is unavailable")
        return 2
    paths = sorted(
        {
            path
            for value in args.paths
            if (path := root / value).is_file()
            and path.suffix.lower() in SOURCE_SUFFIXES
        }
    )
    if not paths:
        print("No changed source file needs Semgrep.")
        return 0
    result = subprocess.run(
        [
            semgrep,
            "scan",
            "--config",
            args.config,
            "--error",
            "--json",
            "--quiet",
            *[str(path) for path in paths],
        ],
        cwd=root,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
