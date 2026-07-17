#!/usr/bin/env python3
"""Generate the deterministic Gauntlet runtime install manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST"

PAYLOAD_ROOTS = ("router", "docs", "scripts", "templates", "agents", "evals")
ROOT_FILES = ("README.md",)
EXCLUDED_PARTS = {"__pycache__", "node_modules", "generated-prompts", "results"}
LEGACY_RETIRED = {
    "review-brief.html": "0a12db60b96ba50aad544882021d05db431766303f97a5827f090787227a42bd",
    "review-brief-data.json": "70edae77f59c3125feb3b6d934deb72b2da0322b8c0cc1195ddcc51fc8d6cf76",
    "review-brief-data.schema.json": "daa313f86f578676531b016110055e1db4b8f414321df20907299791d88a31dc",
    "scripts/serve-notes.sh": "1b9e6e9c6263cdb87763419253a74c01727f81ad798ebc94d4f634585b3f6e46",
    "scripts/check-review-brief.py": "b07357aea64ba7f32153a71050dc87ccdbc9dce99d923c52c71faf9e83961428",
    "scripts/embed-review-brief-data.py": "22697fd5999c15b4d656e66807ca4b4a47152827f832677d9389226d98574cb0",
    "scripts/init-review-brief.sh": "65625abec816bc793f11b614c829c12e2de89c2492c201ef4afdabe5efbe2e9b",
    "scripts/require-review-brief-started.sh": "764512573c6bc1e5d821dd3d84ad77216b957bed1cde454282476f90d3576626",
    "scripts/serve-review-brief.sh": "6e22bedee20c5c4b69601bb5eda61c269b4e0fc2bd26fa57ae6eebd976d3b2cc",
    "scripts/start-review-brief.sh": "1e46cdbecf63991f91d920ca8c3c11c824a50eb7268eeac38afa53e001a9d478",
    "scripts/validate-review-brief-data.py": "6c6b4cf5204249a4657b598e478ff4f2ab918efbf2c0559e2b15963f2df9f3b2",
    "templates/local-docs/IMPLEMENTATION_PLAN.md.tmpl": "c5bc0c05ce73ae0e5173ae8f8a28c8a8f24eee08a402cb34628b900faca7c384",
}
LEGACY_SKILLS = (
    "review-brief-builder",
    "build-review-interface",
    "error-analysis",
    "evaluate-rag",
    "generate-synthetic-data",
    "validate-evaluator",
    "write-judge-prompt",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_runtime_script(path: Path) -> bool:
    relative = path.relative_to(ROOT / "scripts")
    return relative.name not in {
        "check-gauntlet-workflow.py",
        "generate-install-manifest.py",
    } and not (
        len(relative.parts) == 1
        and relative.name.startswith("test-")
        and relative.name != "test-plan.py"
        and relative.suffix == ".py"
    )


def source_files() -> list[Path]:
    files = [ROOT / name for name in ROOT_FILES]
    for root_name in PAYLOAD_ROOTS:
        for path in (ROOT / root_name).rglob("*"):
            if (
                path.is_file()
                and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
                and (root_name != "scripts" or is_runtime_script(path))
            ):
                files.append(path)
    files.extend(path for path in (ROOT / "skills").rglob("*") if path.is_file())
    return sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())


def destination(source: str) -> str:
    if source.startswith("skills/"):
        return source
    return f"gauntlet/{source}"


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

    legacy = []
    for path in sorted((ROOT / "scripts").glob("test-*.py")):
        if path.name == "test-plan.py":
            continue
        legacy.append(
            {
                "destination": f"gauntlet/scripts/{path.name}",
                "sha256": digest(path),
                "type": "file",
            }
        )
    workflow_check = ROOT / "scripts" / "check-gauntlet-workflow.py"
    legacy.append(
        {
            "destination": "gauntlet/scripts/check-gauntlet-workflow.py",
            "sha256": digest(workflow_check),
            "type": "file",
        }
    )
    legacy.extend(
        {"destination": f"gauntlet/{path}", "sha256": sha256, "type": "retired-file"}
        for path, sha256 in LEGACY_RETIRED.items()
    )
    legacy.extend(
        {"destination": f"skills/{name}", "type": "retired-directory"}
        for name in LEGACY_SKILLS
    )
    legacy.sort(key=lambda row: row["destination"])
    return {
        "schemaVersion": "1.0",
        "entries": entries,
        "generatedDestinations": [
            "gauntlet/AGENTS.md",
            "gauntlet/.install-manifest.json",
        ],
        "legacyManaged": legacy,
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
