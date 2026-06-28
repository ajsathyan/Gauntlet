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
        "Run Log",
        "Panel Guard",
        "Hygiene",
        "TS Durability",
    ]:
        assert_contains(combined, marker, "simplified mode model")

    for stale in ["### Deep Patch", "### Slice", "Deep Patch |", "| Deep Patch", "Slice |"]:
        assert_not_contains(combined, stale, "simplified mode model")


def test_v201_run_log_contract_replaces_default_review_brief():
    agents = read(AGENTS_MD)
    readme = read(README_MD)
    run_log = read(SKILLS / "run-log-builder" / "SKILL.md")
    combined = "\n".join([agents, readme, run_log])

    for marker in [
        "v2.0.1",
        "Run Log",
        "Decision Log Gate",
        "exceptions-first",
        "docs/gauntlet-runs/",
        "Assumptions",
        "Decisions",
        "Exceptions",
        "Things that went wrong",
        "Cannot verify",
    ]:
        assert_contains(combined, marker, "v2.0.1 run-log contract")

    for stale in [
        "Review Brief Startup Gate",
        "review brief startup gate is mandatory",
        "review-brief-builder",
        "review-brief.html",
        "review-brief-data.json",
    ]:
        assert_not_contains(agents, stale, "default workflow contract")

    assert_contains(run_log, "Do not list successful routine checks", "run-log proof policy")
    assert_contains(run_log, "Release", "run-log release proof exception")


def test_coverage_gap_and_design_lint_guidance_are_documented():
    agents = read(AGENTS_MD)
    readme = read(README_MD)
    coverage = read(ROOT / "docs" / "coverage-gaps.md")
    design_lints = read(ROOT / "docs" / "design-lint-candidates.md")
    run_log = read(SKILLS / "run-log-builder" / "SKILL.md")
    combined = "\n".join([agents, readme, coverage, design_lints, run_log])

    for marker in [
        "GAP-",
        "pending",
        "candidate",
        "human",
        "coverage-gaps.md",
        "same class of issue appears",
        "Cannot verify",
        "rule, reference, exemplar, lint, eval, coverage gap, or no change",
    ]:
        assert_contains(combined, marker, "coverage gap capture")

    for marker in [
        "nested modals",
        "radio buttons",
        "2-3 static options",
        "accessible names",
        "custom focus rings",
        "design-system component",
        "Modal.Body",
        "raw shadows",
        "4px grid",
        "deprecated Tailwind",
    ]:
        assert_contains(design_lints, marker, "design lint candidates")

    assert_not_contains(coverage, "Status: accepted", "coverage gaps should not auto-promote standards")


def test_guarded_panel_contract_is_uniform():
    files = {
        "AGENTS.md": read(AGENTS_MD),
        "planner": read(SKILLS / "planner" / "SKILL.md"),
        "issue-triager": read(SKILLS / "issue-triager" / "SKILL.md"),
        "deep-code-reviewer": read(SKILLS / "deep-code-reviewer" / "SKILL.md"),
        "run-log-builder": read(SKILLS / "run-log-builder" / "SKILL.md"),
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
        env["GAUNTLET_SKIP_GIT_HOOKS"] = "1"
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


def test_skill_evals_compare_all_arms():
    runner = SCRIPTS / "run-skill-evals.py"
    evals = ROOT / "evals" / "skill-evals.json"
    current = ROOT / "evals" / "baselines" / "current" / "skills"
    results = ROOT / "evals" / "results" / "workflow-check.json"

    for path in [runner, evals, current]:
        if not path.exists():
            raise AssertionError(f"missing skill eval artifact: {path}")

    run([str(runner), "--results", str(results)])
    data = json.loads(results.read_text())
    if data.get("comparisonArms") != ["one_shot", "current_skill", "new_skill"]:
        raise AssertionError("skill evals must compare one_shot, current_skill, and new_skill")
    if not data.get("cases"):
        raise AssertionError("skill evals must include cases")
    for case in data["cases"]:
        arms = case.get("arms", {})
        for arm in data["comparisonArms"]:
            if arm not in arms:
                raise AssertionError(f"{case['id']} missing {arm}")
        if not arms["new_skill"]["passed"]:
            raise AssertionError(f"{case['id']} new_skill did not pass")


def test_skill_evals_include_behavior_and_metrics():
    runner = SCRIPTS / "run-skill-evals.py"
    fixture = ROOT / "evals" / "behavior-fixtures.json"
    results = ROOT / "evals" / "results" / "workflow-behavior-check.json"

    for path in [runner, fixture]:
        if not path.exists():
            raise AssertionError(f"missing behavior eval artifact: {path}")

    with tempfile.TemporaryDirectory() as tmp:
        prompts = Path(tmp) / "behavior-prompts"
        run([
            str(runner),
            "--behavior-responses",
            str(fixture),
            "--behavior-prompts-dir",
            str(prompts),
            "--results",
            str(results),
        ])
        data = json.loads(results.read_text())
        if data.get("behaviorComparisonArms") != ["no_guidance", "one_shot", "current_skill", "new_skill"]:
            raise AssertionError("behavior evals must compare no_guidance, one_shot, current_skill, and new_skill")
        if not data.get("cases"):
            raise AssertionError("behavior evals must include cases")
        for case in data["cases"]:
            behavior = case.get("behavior")
            if not behavior:
                raise AssertionError(f"{case['id']} missing behavior results")
            if behavior.get("minReps", 0) < 5:
                raise AssertionError(f"{case['id']} must require at least five behavioral reps")
            if not (prompts / case["id"] / "new_skill.md").exists():
                raise AssertionError(f"{case['id']} missing generated behavior prompt")
            new_behavior = behavior["arms"]["new_skill"]
            if new_behavior["repsFound"] < behavior["minReps"]:
                raise AssertionError(f"{case['id']} new_skill missing behavior reps")
            if new_behavior["passRate"] < 1:
                raise AssertionError(f"{case['id']} new_skill behavior reps should pass")
            for arm_name, arm in case["arms"].items():
                if arm.get("promptWordCount", 0) <= 0:
                    raise AssertionError(f"{case['id']} {arm_name} missing prompt word metric")
                if arm.get("scoreElapsedMs", -1) < 0:
                    raise AssertionError(f"{case['id']} {arm_name} missing score speed metric")


def test_skill_linter_examples_and_na_defaults():
    linter = SCRIPTS / "lint-skills.py"
    evals = ROOT / "evals" / "skill-evals.json"
    if not linter.exists():
        raise AssertionError("missing skill linter")

    skill_names = sorted({case["skill"] for case in json.loads(evals.read_text())["cases"]})
    result = run([
        str(linter),
        "--skills-root",
        str(SKILLS),
        "--only",
        ",".join(skill_names),
        "--json",
    ])
    data = json.loads(result.stdout)
    if data.get("failures"):
        raise AssertionError(f"skill linter failures: {json.dumps(data['failures'], indent=2)}")
    if not data.get("skills"):
        raise AssertionError("skill linter did not scan skills")
    for skill in data["skills"]:
        if skill.get("wordCount", 0) > 500:
            raise AssertionError(f"{skill['name']} exceeds 500 words")
        if not skill.get("optionalExamples"):
            raise AssertionError(f"{skill['name']} missing optional examples")
        if not skill.get("hasNotRelevantDefault"):
            raise AssertionError(f"{skill['name']} missing Not relevant because default")


def test_skill_changes_are_guarded_by_pre_commit():
    hook_installer = SCRIPTS / "install-git-hooks.sh"
    skill_check = SCRIPTS / "run-skill-change-checks.sh"
    for path in [hook_installer, skill_check]:
        if not path.exists() or not os.access(path, os.X_OK):
            raise AssertionError(f"missing executable skill-change guard: {path}")

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        run(["git", "init"], cwd=repo)
        run([str(hook_installer), "--repo", str(repo), "--gauntlet-root", str(ROOT)])
        hook = repo / ".git" / "hooks" / "pre-commit"
        if not hook.exists() or not os.access(hook, os.X_OK):
            raise AssertionError("pre-commit hook was not installed")
        hook_text = hook.read_text()
        for marker in ["GAUNTLET SKILL CHECKS", "run-skill-change-checks.sh"]:
            assert_contains(hook_text, marker, "pre-commit hook")

    for args in [[str(skill_check)], [str(skill_check), "--changed-files", "README.md"]]:
        result = run(args, cwd=ROOT)
        if "No Gauntlet skill changes detected" not in result.stdout:
            raise AssertionError("non-skill changes should skip skill evals")

    result = run([str(skill_check), "--changed-files", "skills/planner/SKILL.md"], cwd=ROOT)
    for marker in ["Gauntlet skill changes detected", "skill evals:", "skill linter"]:
        assert_contains(result.stdout, marker, "skill change checks")


def main():
    tests = [
        test_simplified_modes_and_depth_are_documented,
        test_v201_run_log_contract_replaces_default_review_brief,
        test_coverage_gap_and_design_lint_guidance_are_documented,
        test_guarded_panel_contract_is_uniform,
        test_ts_durability_classifier_behavior,
        test_skill_evals_compare_all_arms,
        test_skill_evals_include_behavior_and_metrics,
        test_skill_linter_examples_and_na_defaults,
        test_skill_changes_are_guarded_by_pre_commit,
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
