#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from gauntlet_diff_helpers import build_diff_intel, write_json


def main():
    parser = argparse.ArgumentParser(description="Classify the current diff into bounded Gauntlet workflow signals.")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--base", default="HEAD", help="git base ref to compare against")
    parser.add_argument("--changed-files", nargs="*", default=None, help="explicit relative files to classify")
    parser.add_argument("--output", type=Path, default=None, help="artifact path; defaults to .gauntlet/diff-intel.json")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    payload = build_diff_intel(project_root, args.changed_files, args.base)
    output = args.output or project_root / ".gauntlet" / "diff-intel.json"
    write_json(output, payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
