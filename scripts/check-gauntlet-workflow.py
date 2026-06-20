#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SKILLS = ROOT / "skills" if (ROOT / "skills").exists() else ROOT.parent / "skills"
AGENTS_MD = ROOT / "AGENTS.md" if (ROOT / "AGENTS.md").exists() else ROOT.parent / "AGENTS.md"
README_MD = ROOT / "README.md" if (ROOT / "README.md").exists() else ROOT.parent / "README.md"


def read(path):
    return path.read_text()


def run(args, cwd=None, check=True):
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"{args} failed with {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def assert_contains(text, needle, label):
    if needle not in text:
        raise AssertionError(f"{label} missing: {needle}")


def assert_not_contains(text, needle, label):
    if needle in text:
        raise AssertionError(f"{label} should not contain: {needle}")


def make_ts_project(root):
    (root / "package.json").write_text('{"devDependencies":{"typescript":"latest"}}\n')
    (root / "tsconfig.json").write_text('{"compilerOptions":{"strict":true}}\n')
    (root / "src").mkdir()
    (root / "src" / "App.tsx").write_text("export function App() { return null; }\n")


def read_durability_artifact(root):
    path = root / ".gauntlet-ts-durability.json"
    if not path.exists():
        raise AssertionError("missing .gauntlet-ts-durability.json")
    data = json.loads(path.read_text())
    for key in ["schemaVersion", "durabilityRequired", "reason", "filesScanned", "triggers", "generatedAt"]:
        if key not in data:
            raise AssertionError(f"durability artifact missing {key}")
    if not isinstance(data["durabilityRequired"], bool):
        raise AssertionError("durabilityRequired must be boolean")
    if not isinstance(data["triggers"], list):
        raise AssertionError("triggers must be an array")
    return data


def test_simplified_modes_and_depth_are_documented():
    agents = read(AGENTS_MD)
    readme = read(README_MD)
    planner = read(SKILLS / "planner" / "SKILL.md")
    combined = "\n".join([agents, readme, planner])

    for label in ["Patch", "Feature", "Release"]:
        assert_contains(combined, label, "mode docs")
    for marker in [
        "Mode: Patch | Feature | Release",
        "Depth: Standard | Deep",
        "Triggered gates:",
        "Review Brief",
        "Panel Guard",
        "Hygiene",
        "TS Durability",
    ]:
        assert_contains(combined, marker, "simplified mode model")

    for stale in ["### Deep Patch", "### Slice", "Deep Patch |", "| Deep Patch", "Slice |"]:
        assert_not_contains(combined, stale, "simplified mode model")


def test_guarded_panel_contract_is_uniform():
    files = {
        "AGENTS.md": read(AGENTS_MD),
        "planner": read(SKILLS / "planner" / "SKILL.md"),
        "issue-triager": read(SKILLS / "issue-triager" / "SKILL.md"),
        "deep-code-reviewer": read(SKILLS / "deep-code-reviewer" / "SKILL.md"),
        "review-brief-builder": read(SKILLS / "review-brief-builder" / "SKILL.md"),
    }
    required = [
        "| Concern | Decision | Why Not Defer | Proof | Plan Delta |",
        "Ship blocker",
        "Conditional blocker",
        "Manual fallback",
        "Private beta gate",
        "Defer",
        "Reject",
        "launch cut line",
        "panel delta",
    ]
    for name, text in files.items():
        for marker in required:
            assert_contains(text, marker, name)
    assert_contains(files["AGENTS.md"], "collapse", "AGENTS.md")
    assert_contains(files["planner"], "Do not union every idea", "planner")


def test_ts_durability_classifier_behavior():
    classifier = SCRIPTS / "classify-ts-durability.sh"
    if not classifier.exists() or not os.access(classifier, os.X_OK):
        raise AssertionError("scripts/classify-ts-durability.sh must exist and be executable")

    with tempfile.TemporaryDirectory() as tmp:
        no_ts = Path(tmp) / "no-ts"
        no_ts.mkdir()
        run([str(classifier), str(no_ts)])
        data = read_durability_artifact(no_ts)
        if data["durabilityRequired"]:
            raise AssertionError("non-TypeScript repo should not require durability")
        if "TypeScript not in scope" not in data["reason"]:
            raise AssertionError("non-TypeScript reason should explain TypeScript is not in scope")

        ui = Path(tmp) / "ui"
        ui.mkdir()
        make_ts_project(ui)
        run([str(classifier), str(ui), "src/App.tsx"])
        data = read_durability_artifact(ui)
        if data["durabilityRequired"]:
            raise AssertionError("UI-only TypeScript task should default durability off")
        if data["triggers"]:
            raise AssertionError("UI-only TypeScript task should not record durability triggers")

        auth = Path(tmp) / "auth"
        shutil.copytree(ui, auth)
        (auth / "src" / "auth").mkdir()
        (auth / "src" / "auth" / "session.ts").write_text("export const session = null;\n")
        run([str(classifier), str(auth), "src/auth/session.ts"])
        data = read_durability_artifact(auth)
        if not data["durabilityRequired"]:
            raise AssertionError("auth TypeScript task should require durability")
        if "auth" not in data["triggers"]:
            raise AssertionError("auth TypeScript task should record auth trigger")

        effect = Path(tmp) / "effect"
        effect.mkdir()
        make_ts_project(effect)
        (effect / "package.json").write_text('{"dependencies":{"effect":"latest"}}\n')
        run([str(classifier), str(effect), "src/App.tsx"])
        data = read_durability_artifact(effect)
        if data["durabilityRequired"]:
            raise AssertionError("existing durable TS patterns should not force durability for UI-only changed files")
        if data["triggers"]:
            raise AssertionError("UI-only changed files should suppress existing durable pattern triggers")

        run([str(classifier), str(effect)])
        data = read_durability_artifact(effect)
        if not data["durabilityRequired"]:
            raise AssertionError("existing durable TS patterns should require durability for broad or unclear TS work")
        if "existing-durable-patterns" not in data["triggers"]:
            raise AssertionError("Effect dependency should record existing durable patterns")


def test_installed_layout_supports_workflow_check():
    if not (ROOT / ".git").exists():
        return

    with tempfile.TemporaryDirectory() as tmp:
        agent_home = Path(tmp) / "agent-home"
        env = os.environ.copy()
        env["AGENT_HOME"] = str(agent_home)
        result = subprocess.run(
            [str(SCRIPTS / "install.sh")],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"install.sh failed with {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        installed_check = agent_home / "gauntlet" / "scripts" / "check-gauntlet-workflow.py"
        if not installed_check.exists():
            raise AssertionError("installed workflow check is missing")
        run([str(installed_check)])


def main():
    tests = [
        test_simplified_modes_and_depth_are_documented,
        test_guarded_panel_contract_is_uniform,
        test_ts_durability_classifier_behavior,
        test_installed_layout_supports_workflow_check,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"FAIL {error}", file=os.sys.stderr)
        raise SystemExit(1)
