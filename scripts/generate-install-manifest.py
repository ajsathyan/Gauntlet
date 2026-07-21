#!/usr/bin/env python3
"""Generate the deterministic Codex runtime manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from gauntletlib.install.manifest import GENERATED_DESTINATIONS

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST"
RUNTIME_SCRIPTS = {
    "gauntlet.py",
    "install.sh",
    "install-git-hooks.sh",
    "security-review.py",
}
OWNERSHIP_TRANSFERS = (
    "skills/craft-customer-email",
    "skills/craft-product-terminology",
    "skills/promotion-scanner",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files() -> list[Path]:
    files = []
    files.extend(path for path in (ROOT / "router").rglob("*") if path.is_file())
    files.extend(path for path in (ROOT / "templates" / "local-docs").rglob("*") if path.is_file())
    files.extend(path for path in (ROOT / "skills").rglob("*") if path.is_file())
    files.extend(
        path
        for path in (ROOT / "scripts" / "gauntletlib").rglob("*.py")
        if "__pycache__" not in path.parts
    )
    files.extend(ROOT / "scripts" / name for name in RUNTIME_SCRIPTS)
    return sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())


def destination(source: str) -> str:
    return source if source.startswith("skills/") else f"gauntlet/{source}"


def build_manifest() -> dict:
    entries = []
    for path in source_files():
        source = path.relative_to(ROOT).as_posix()
        entries.append(
            {
                "destination": destination(source),
                "executable": bool(path.stat().st_mode & 0o111),
                "sha256": digest(path),
                "source": source,
            }
        )
    return {
        "schemaVersion": "1.0",
        "entries": entries,
        "generatedDestinations": list(GENERATED_DESTINATIONS),
        "ownershipTransfers": list(OWNERSHIP_TRANSFERS),
    }


def rendered_manifest() -> bytes:
    return (json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = rendered_manifest()
    if args.check:
        if not MANIFEST.is_file() or MANIFEST.read_bytes() != rendered:
            print("MANIFEST is stale; run scripts/generate-install-manifest.py")
            return 1
        return 0
    MANIFEST.write_bytes(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
