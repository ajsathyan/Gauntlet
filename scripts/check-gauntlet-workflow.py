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


def run(args, cwd=None, check=True, input_text=None):
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        input=input_text,
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


def git(args, cwd):
    return run(["git", *args], cwd=cwd)


def init_repo(root):
    root.mkdir()
    git(["init"], cwd=root)
    git(["config", "user.email", "gauntlet@example.test"], cwd=root)
    git(["config", "user.name", "Gauntlet Test"], cwd=root)


def commit_all(root, message):
    git(["add", "."], cwd=root)
    git(["commit", "-m", message], cwd=root)


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
    ui_constitution = read(ROOT / "docs" / "ui-constitution.md")
    run_log = read(SKILLS / "run-log-builder" / "SKILL.md")
    black_box = read(SKILLS / "black-box-tester" / "SKILL.md")
    experience = read(SKILLS / "experience-reviewer" / "SKILL.md")
    combined = "\n".join([agents, readme, coverage, design_lints, ui_constitution, run_log, black_box, experience])

    for marker in [
        "GAP-",
        "pending",
        "candidate",
        "human",
        "coverage-gaps.md",
        "same class of issue appears",
        "Cannot verify",
        "rule, reference, exemplar, lint, eval, coverage gap, or no change",
        "Reliable failure signal",
        "Resolved Gap Cleanup",
        "remove it from `docs/coverage-gaps.md`",
        "run log and git history are the archive",
        "new or updated gap IDs",
        "Added GAP-###: Short name",
    ]:
        assert_contains(combined, marker, "coverage gap capture")

    for marker in [
        "nested modals",
        "radio buttons",
        "2-3 static options",
        "accessible names",
        "semantic button/link usage",
        "associated input labels",
        "form semantics",
        "appropriate input types",
        "interactive tooltip content",
    ]:
        assert_contains(design_lints, marker, "design lint candidates")
    for marker in [
        "Earned Project Rules",
        "deprecated utility",
        "elevation tokens",
        "spacing tokens",
        "adapter",
        "component-library conventions",
    ]:
        assert_not_contains(design_lints, marker, "design lint candidates should stay general")

    for marker in [
        "UI Constitution",
        "substantial frontend work",
        "does not create one",
        "Black-Box Checks",
        "Experience Checks",
        "Once-In-A-While Checks",
        "duplicate-submit prevention",
        "state reachability",
    ]:
        assert_contains(combined, marker, "frontend quality gate")

    assert_not_contains(coverage, "Status: accepted", "coverage gaps should not auto-promote standards")
    assert_not_contains(coverage, "GAP-008: Skill Quality Bar", "resolved skill-quality gap should not remain pending")


def test_product_thinking_and_scope_routing_are_documented():
    agents = read(AGENTS_MD)
    readme = read(README_MD)
    black_box = read(SKILLS / "black-box-tester" / "SKILL.md")
    experience = read(SKILLS / "experience-reviewer" / "SKILL.md")
    combined = "\n".join([agents, readme, black_box, experience])

    for marker in [
        "v2.0.2",
        "product-thinking harness for AI coding agents",
        "thought-through, consistent features",
        "coherent product features",
        "Token efficiency",
    ]:
        assert_contains(readme, marker, "product-thinking positioning")

    for marker in [
        "Proof scope: smoke | delta | full | not relevant",
        "Every non-default ceremony must declare its trigger, cap, artifact, and exit condition",
        "Full checks are trigger-based",
        "Feature delta",
        "combined black-box and experience pass",
        "Second Release issue-triager only when",
        "Global install verification",
        "Skill eval full suite",
    ]:
        assert_contains(combined, marker, "scope routing")


def test_production_quality_bar_is_launch_gated():
    agents = read(AGENTS_MD)
    readme = read(README_MD)
    quality_bar = read(ROOT / "docs" / "production-quality-bar.md")
    pr_template_path = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
    pr_template = read(pr_template_path) if pr_template_path.exists() else ""
    planner = read(SKILLS / "planner" / "SKILL.md")
    product = read(SKILLS / "product-architect" / "SKILL.md")
    deep_review = read(SKILLS / "deep-code-reviewer" / "SKILL.md")
    adversarial = read(SKILLS / "adversarial-reviewer" / "SKILL.md")
    black_box = read(SKILLS / "black-box-tester" / "SKILL.md")
    experience = read(SKILLS / "experience-reviewer" / "SKILL.md")
    triager = read(SKILLS / "issue-triager" / "SKILL.md")
    run_log = read(SKILLS / "run-log-builder" / "SKILL.md")
    combined = "\n".join([
        agents,
        readme,
        quality_bar,
        planner,
        product,
        deep_review,
        adversarial,
        black_box,
        experience,
        triager,
        run_log,
        pr_template,
    ])

    for marker in [
        "Production Quality Bar",
        "near-launch",
        "launch-ready",
        "private beta",
        "production-bound",
        "explicitly being hardened or audited",
        "Skip",
        "ordinary Patch",
        "early prototype",
        "local demo",
        "automated GitHub release tags",
        "release proof",
        "no-mutation",
        "dry-run",
        "state machines",
        "redaction",
        "alerting/email",
        "rollback/restart",
        "decision-oriented UI",
        "Automatable",
        "Human judgment",
    ]:
        assert_contains(combined, marker, "production quality bar launch-gated guidance")

    for marker in [
        "control plane",
        "ownership boundaries",
        "invariants",
        "durable state",
        "operator/user feedback loop",
        "threat model",
        "destructive action boundaries",
        "confidence",
        "freshness",
        "sample size",
    ]:
        assert_contains(quality_bar, marker, "production quality bar guardrails")

    for name, text in {
        "planner": planner,
        "product-architect": product,
        "deep-code-reviewer": deep_review,
        "adversarial-reviewer": adversarial,
        "black-box-tester": black_box,
        "experience-reviewer": experience,
        "issue-triager": triager,
        "run-log-builder": run_log,
    }.items():
        assert_contains(text, "Production Quality Bar", name)
        assert_contains(text, "Not relevant because", name)

    if pr_template_path.exists():
        for marker in [
            "Release Proof (near-launch only)",
            "automated GitHub release tags",
            "dry-run/no-mutation",
        ]:
            assert_contains(pr_template, marker, "production quality bar PR template")


def test_subagent_parallelism_is_context_efficient():
    agents = read(AGENTS_MD)
    planner = read(SKILLS / "planner" / "SKILL.md")
    product = read(SKILLS / "product-architect" / "SKILL.md")
    implementer = read(SKILLS / "implementer" / "SKILL.md")

    for marker in [
        "Parallelism must beat its context cost.",
        "Do not use subagents when each one would need the same large spec",
        "scripts/check-subagent-plan.py",
        "subagent-plan-summary.json",
        "expected speedup",
    ]:
        assert_contains(agents, marker, "subagent context-efficiency guard")

    for marker in [
        "For independent task packets with disjoint files, state, and proof",
        "Do not repeat large shared context into subagents",
    ]:
        assert_contains(implementer, marker, "implementer subagent guidance")

    assert_contains(
        planner,
        "Use end-to-end steps unless files, state, and proof are independent enough to split.",
        "planner firm end-to-end rule",
    )
    assert_contains(planner, ".gauntlet/subagent-plan.json", "planner subagent manifest")
    assert_not_contains(planner, "Prefer end-to-end steps over component piles.", "planner soft end-to-end rule")

    assert_contains(
        product,
        "Include onboarding, activation, retention, or growth only when accepted scope or a real next action makes them relevant.",
        "product-architect firm scope rule",
    )
    assert_not_contains(
        product,
        "Consider onboarding, activation, retention, and growth only when tied to accepted scope or a real next action.",
        "product-architect soft scope rule",
    )


def test_kickoff_and_implementation_transition_gates_are_documented():
    agents = read(AGENTS_MD)
    etiquette = read(ROOT / "docs" / "workflow-etiquette.md")
    planner = read(SKILLS / "planner" / "SKILL.md")
    implementer = read(SKILLS / "implementer" / "SKILL.md")

    for marker in [
        "no later than the third user-assistant exchange",
        "Research is never assigned `p4` merely because it is research",
        "If the priority is unchanged, say nothing about it",
        "Subagent packetization: required",
        "before implementation, not merely before dispatch",
        "Scope delta checked: no material change.",
    ]:
        assert_contains("\n".join([agents, etiquette]), marker, "implementation-transition guidance")

    for marker in [
        "Subagent packetization: required",
        "Scope delta checked: no material change.",
        "before implementation",
    ]:
        assert_contains(planner, marker, "planner implementation-transition gate")

    for marker in [
        "Refuse delegated implementation",
        "current-run manifest",
        "scope-addition delta",
    ]:
        assert_contains(implementer, marker, "implementer implementation-transition gate")


def test_skill_quality_bar_is_trigger_bounded():
    agents = read(AGENTS_MD)
    readme = read(README_MD)
    quality_bar = read(ROOT / "docs" / "skill-quality-bar.md")
    coverage = read(ROOT / "docs" / "coverage-gaps.md")
    plan = read(ROOT / "docs" / "skill-quality-implementation-plan.md")
    combined = "\n".join([agents, readme, quality_bar, coverage, plan])

    for marker in [
        "Skill Quality Bar",
        "docs/skill-quality-bar.md",
        "Baseline Bar",
        "Escalation Bar",
        "behavior delta",
        "trigger clarity",
        "completion criterion",
        "output contract",
        "positive steering",
        "no-op pruning",
        "progressive disclosure",
        "bounded attempt memory",
        "writing-great-skills",
        "Matt Pocock",
    ]:
        assert_contains(combined, marker, "skill quality bar guidance")

    for marker in [
        "ordinary Patch",
        "copy edits",
        "local-only docs",
        "narrow accepted tweaks",
        "trigger, cap, artifact, and exit condition",
    ]:
        assert_contains(agents, marker, "skill quality bar trigger bounds")

    for marker in [
        "local analytics direction",
        ".gauntlet/analytics/",
        "analytics emit",
        "analytics summarize",
        "calendar_planning_span",
        "human_review_latency",
        "bounded attempt memory",
        "Local Closeout Facts",
        "do not auto-commit",
        "do not auto-archive",
        "git diff --numstat",
        "scc",
        "cloc",
    ]:
        assert_contains(plan, marker, "skill quality analytics plan")


def test_subagent_plan_validator_logs_rejections():
    validator = SCRIPTS / "check-subagent-plan.py"
    if not validator.exists() or not os.access(validator, os.X_OK):
        raise AssertionError("missing executable subagent plan validator")

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        project.mkdir()
        plan = project / "subagent-plan.json"
        plan.write_text(json.dumps({
            "schemaVersion": "1.0",
            "lanes": [
                {
                    "id": "ui-review",
                    "skill": "experience-reviewer",
                    "scope": "Review checkout UI",
                    "filesRead": ["src/checkout/**"],
                    "filesWrite": ["src/checkout/page.tsx"],
                    "stateScope": "checkout-session",
                    "stateAccess": "mutates",
                    "proof": ["npm test"],
                    "inlineContext": "shared checkout context " * 90,
                },
                {
                    "id": "browser-proof",
                    "skill": "black-box-tester",
                    "scope": "Exercise checkout UI",
                    "filesRead": ["src/checkout/**"],
                    "filesWrite": ["src/checkout/page.tsx"],
                    "stateScope": "checkout-session",
                    "stateAccess": "mutates",
                    "proof": ["npm test"],
                    "inlineContext": "shared checkout context " * 90,
                },
            ],
        }))

        result = run([str(validator), str(project), str(plan), "--run-id", "workflow-test"], check=False)
        if result.returncode == 0:
            raise AssertionError("invalid subagent plan should fail")
        for marker in ["Subagent plan rejected", "rejection(s)", ".gauntlet/subagent-plan-log.jsonl"]:
            assert_contains(result.stdout, marker, "subagent rejection output")

        log_path = project / ".gauntlet" / "subagent-plan-log.jsonl"
        summary_path = project / ".gauntlet" / "subagent-plan-summary.json"
        if not log_path.exists():
            raise AssertionError("subagent rejection log was not written")
        if not summary_path.exists():
            raise AssertionError("subagent summary was not written")
        record = json.loads(log_path.read_text().splitlines()[-1])
        summary = json.loads(summary_path.read_text())
        if record["status"] != "rejected" or record["rejectionCount"] < 4:
            raise AssertionError("subagent rejection record missing expected failures")
        if summary["runId"] != "workflow-test" or summary["rejectedPlans"] != 1:
            raise AssertionError("subagent summary should track rejected plans for the run")

        stats = run([str(validator), str(project), "--stats", "--run-id", "workflow-test"])
        assert_contains(stats.stdout, "Subagent plans: 1 checked, 1 rejected", "subagent stats output")


def test_subagent_plan_validator_rejects_secret_and_overbroad_scope():
    validator = SCRIPTS / "check-subagent-plan.py"

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        project.mkdir()
        plan = project / "subagent-plan.json"
        plan.write_text(json.dumps({
            "schemaVersion": "1.0",
            "lanes": [
                {
                    "id": "all-repo-review",
                    "skill": "deep-code-reviewer",
                    "scope": "Review everything",
                    "filesRead": ["**/*"],
                    "filesWrite": [],
                    "stateScope": "repo",
                    "stateAccess": "read-only",
                    "proof": ["manual review"],
                    "inlineContext": "Use OPENAI_API_KEY=sk-live-secret-value while reviewing.",
                },
                {
                    "id": "docs-review",
                    "skill": "deep-code-reviewer",
                    "scope": "Review docs",
                    "filesRead": ["docs/**"],
                    "filesWrite": [],
                    "stateScope": "docs",
                    "stateAccess": "read-only",
                    "proof": ["manual docs review"],
                    "inlineContext": "Short context.",
                },
            ],
        }))

        result = run([str(validator), str(project), str(plan), "--run-id", "secret-test"], check=False)
        if result.returncode == 0:
            raise AssertionError("secret-bearing overbroad subagent plan should fail")

        record = json.loads((project / ".gauntlet" / "subagent-plan-log.jsonl").read_text().splitlines()[-1])
        codes = {rejection["code"] for rejection in record["rejections"]}
        for code in ["secret_in_inline_context", "overbroad_scope"]:
            if code not in codes:
                raise AssertionError(f"subagent validator missing {code} rejection")


def test_subagent_plan_validator_requires_complete_lane_packets():
    validator = SCRIPTS / "check-subagent-plan.py"

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        project.mkdir()
        plan = project / "subagent-plan.json"
        incomplete_lanes = []
        for lane_id in ["C1", "C2"]:
            incomplete_lanes.append({
                "id": lane_id,
                "skill": "implementer",
                "scope": f"Implement {lane_id}",
                "filesRead": [f"src/{lane_id}/**"],
                "filesWrite": [f"src/{lane_id}/**"],
                "stateScope": lane_id,
                "stateAccess": "mutates",
                "proof": [f"test-{lane_id}"],
                "inlineContext": f"Short context for {lane_id}.",
            })
        plan.write_text(json.dumps({"schemaVersion": "1.1", "lanes": incomplete_lanes}))

        incomplete = run([str(validator), str(project), str(plan), "--run-id", "packet-fields"], check=False)
        if incomplete.returncode == 0:
            raise AssertionError("incomplete lane packets should fail before implementation")
        record = json.loads((project / ".gauntlet" / "subagent-plan-log.jsonl").read_text().splitlines()[-1])
        if "missing_field" not in {rejection["code"] for rejection in record["rejections"]}:
            raise AssertionError("incomplete lane packets should report missing_field")

        complete_lanes = []
        for lane_id in ["C1", "C2"]:
            complete_lanes.append({
                "id": lane_id,
                "status": "To Do",
                "title": f"p2-auto: [{lane_id}][To Do] Implement lane",
                "skill": "implementer",
                "objective": f"Implement bounded lane {lane_id}",
                "projectRoot": ".",
                "worktreePath": ".",
                "acceptedSource": "docs/accepted-spec.md",
                "scope": f"Implement {lane_id}",
                "inScope": [f"src/{lane_id}/**"],
                "outOfScope": ["src/shared/**"],
                "filesRead": [f"src/{lane_id}/**"],
                "filesWrite": [f"src/{lane_id}/**"],
                "filesAvoid": ["src/shared/**"],
                "stateScope": lane_id,
                "stateAccess": "mutates",
                "dependencies": [],
                "consumes": ["accepted spec"],
                "produces": [f"{lane_id} patch"],
                "constraints": ["preserve unrelated work"],
                "proof": [f"test-{lane_id}"],
                "inlineContext": f"Short context for {lane_id}.",
                "taskPacketRef": f".gauntlet/packets/{lane_id}.md",
                "expectedReturn": "Compact implementation report",
                "askUserPolicy": "Return Needs decision to the orchestrator.",
            })
        plan.write_text(json.dumps({"schemaVersion": "1.1", "lanes": complete_lanes}))

        missing_packet = run([str(validator), str(project), str(plan), "--run-id", "packet-files"], check=False)
        if missing_packet.returncode == 0:
            raise AssertionError("missing task packet references should fail before implementation")
        record = json.loads((project / ".gauntlet" / "subagent-plan-log.jsonl").read_text().splitlines()[-1])
        if "task_packet_missing" not in {rejection["code"] for rejection in record["rejections"]}:
            raise AssertionError("missing task packets should report task_packet_missing")

        packet_dir = project / ".gauntlet" / "packets"
        packet_dir.mkdir(parents=True)
        for lane_id in ["C1", "C2"]:
            (packet_dir / f"{lane_id}.md").write_text(f"# {lane_id} Task Packet\n")

        accepted = run([str(validator), str(project), str(plan), "--run-id", "packet-accepted"], check=False)
        if accepted.returncode != 0:
            raise AssertionError(f"complete lane packets should pass:\n{accepted.stdout}\n{accepted.stderr}")


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


def test_diff_intel_test_plan_and_review_pack_are_bounded():
    diff_intel = SCRIPTS / "diff-intel.py"
    test_plan = SCRIPTS / "test-plan.py"
    review_pack = SCRIPTS / "review-pack.py"
    for script in [diff_intel, test_plan, review_pack]:
        if not script.exists() or not os.access(script, os.X_OK):
            raise AssertionError(f"missing executable workflow helper: {script}")

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        init_repo(project)
        (project / "src" / "auth").mkdir(parents=True)
        (project / "src" / "components").mkdir(parents=True)
        (project / "generated").mkdir()
        (project / "docs").mkdir()
        (project / "package.json").write_text(json.dumps({
            "scripts": {
                "test": "vitest run",
                "lint": "eslint .",
                "typecheck": "tsc --noEmit",
            },
            "devDependencies": {"typescript": "latest", "vitest": "latest"},
        }) + "\n")
        (project / "src" / "auth" / "session.ts").write_text("export const session = null;\n")
        (project / "src" / "auth" / "session.test.ts").write_text("import './session';\n")
        (project / "src" / "components" / "Dashboard.tsx").write_text("export function Dashboard() { return null; }\n")
        (project / "generated" / "client.ts").write_text("export const generated = true;\n")
        (project / "docs" / "guide.md").write_text("# Guide\n")
        commit_all(project, "baseline")

        (project / "src" / "auth" / "session.ts").write_text(
            "export const session = { token: 'sk-live-secret-value' };\n"
        )
        (project / "src" / "components" / "Dashboard.tsx").write_text(
            "export function Dashboard() { return <main>Fleet</main>; }\n"
        )
        (project / "generated" / "client.ts").write_text("export const generated = false;\n")

        run([str(diff_intel), str(project)])
        intel_path = project / ".gauntlet" / "diff-intel.json"
        intel = json.loads(intel_path.read_text())
        changed_paths = {item["path"] for item in intel["changedFiles"]}
        for path in ["src/auth/session.ts", "src/components/Dashboard.tsx", "generated/client.ts"]:
            if path not in changed_paths:
                raise AssertionError(f"diff intel missing changed path {path}")
        for trigger in ["auth", "security-privacy", "ui", "generated"]:
            if trigger not in intel["riskTriggers"]:
                raise AssertionError(f"diff intel missing risk trigger {trigger}")
        if intel["confidence"] != "medium":
            raise AssertionError("mixed risky/generated diff should have medium confidence")

        run([str(test_plan), str(project), "--diff-intel", str(intel_path)])
        plan = json.loads((project / ".gauntlet" / "test-plan.json").read_text())
        commands = [item["command"] for item in plan["commands"]]
        expected_commands = [
            "npm test -- src/auth/session.test.ts",
            "npm run lint",
            "npm run typecheck",
        ]
        for command in expected_commands:
            if command not in commands:
                raise AssertionError(f"test plan missing command: {command}")
        if not any(item["tier"] == "broader" and item["command"] == "npm test" for item in plan["commands"]):
            raise AssertionError("durable/security diffs should recommend broader npm test with rationale")

        implementation_memory = project / "docs" / "implementation-memory.md"
        implementation_memory.write_text(
            "\n".join([
                "# Implementation Memory",
                "",
                "## Goal",
                "",
                "Build a safer session path.",
                "",
                "## Scan Index",
                "",
                "- Search: `rg session-token src/auth`",
                "- Read first: `src/auth/session.ts`",
                "",
                "## Private Raw Notes",
                "",
                "This section should not be copied into the review pack.",
                "",
            ]),
            encoding="utf-8",
        )

        run([
            str(review_pack),
            str(project),
            "--diff-intel",
            str(intel_path),
            "--implementation-memory",
            "docs/implementation-memory.md",
        ])
        packet = (project / ".gauntlet" / "review-pack.md").read_text()
        for marker in [
            "Changed Files",
            "Risk Triggers",
            "src/auth/session.ts",
            "Test Plan Summary",
            "npm run typecheck",
            "Implementation Memory",
            "docs/implementation-memory.md",
            "rg session-token src/auth",
            "Expected Return Format",
            "Cannot verify",
        ]:
            assert_contains(packet, marker, "review packet")
        assert_not_contains(packet, "This section should not be copied", "review packet implementation memory excerpt")
        assert_not_contains(packet, "\n- - ", "review packet list formatting")
        assert_contains(packet, "[REDACTED_SECRET]", "review packet redaction")
        assert_not_contains(packet, "sk-live-secret-value", "review packet secret redaction")


def test_docs_only_diff_gets_no_runtime_test_commands():
    diff_intel = SCRIPTS / "diff-intel.py"
    test_plan = SCRIPTS / "test-plan.py"

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        init_repo(project)
        (project / "docs").mkdir()
        (project / "package.json").write_text(json.dumps({"scripts": {"test": "vitest run"}}) + "\n")
        (project / "docs" / "guide.md").write_text("# Guide\n")
        commit_all(project, "baseline")

        (project / "docs" / "guide.md").write_text("# Guide\n\nUpdate docs only.\n")

        run([str(diff_intel), str(project)])
        intel = json.loads((project / ".gauntlet" / "diff-intel.json").read_text())
        if intel["riskTriggers"] != ["docs-only"]:
            raise AssertionError(f"docs-only diff should only report docs-only trigger: {intel['riskTriggers']}")
        if intel["confidence"] != "high":
            raise AssertionError("docs-only diff should have high classification confidence")

        run([str(test_plan), str(project)])
        plan = json.loads((project / ".gauntlet" / "test-plan.json").read_text())
        if plan["commands"]:
            raise AssertionError(f"docs-only diff should not recommend runtime tests: {plan['commands']}")
        assert_contains("\n".join(plan["cannotVerify"]), "No runtime behavior changed", "docs-only cannot verify note")


def test_workflow_helpers_filter_artifacts_and_find_python_tests():
    diff_intel = SCRIPTS / "diff-intel.py"
    test_plan = SCRIPTS / "test-plan.py"

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        init_repo(project)
        (project / "src" / "twitter_tg_notifs").mkdir(parents=True)
        (project / "scripts").mkdir()
        (project / "tests").mkdir()
        (project / "docs").mkdir()
        (project / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n")
        (project / "src" / "twitter_tg_notifs" / "classifier.py").write_text(
            "def classify(text):\n    return 'token secret api auth password words in clean content'\n"
        )
        (project / "scripts" / "agora_fleet.py").write_text("def fleet():\n    return []\n")
        (project / "tests" / "test_twitter_notifs_classifier.py").write_text("def test_classifier():\n    assert True\n")
        (project / "tests" / "test_agora_fleet.py").write_text("def test_fleet():\n    assert True\n")
        (project / "docs" / "guide.md").write_text("# Guide\n")
        commit_all(project, "baseline")

        run([
            str(diff_intel),
            str(project),
            "--changed-files",
            "src/twitter_tg_notifs/classifier.py",
            "scripts/agora_fleet.py",
        ])
        intel_path = project / ".gauntlet" / "diff-intel.json"
        intel = json.loads(intel_path.read_text())
        candidates = {
            item["path"]: item["testCandidates"]
            for item in intel["changedFiles"]
        }
        if candidates["src/twitter_tg_notifs/classifier.py"] != ["tests/test_twitter_notifs_classifier.py"]:
            raise AssertionError(f"src package Python test mapping missing: {candidates}")
        if candidates["scripts/agora_fleet.py"] != ["tests/test_agora_fleet.py"]:
            raise AssertionError(f"scripts Python test mapping missing: {candidates}")
        if "security-privacy" in intel["riskTriggers"]:
            raise AssertionError("explicit clean tracked files should not scan full contents for noisy risk triggers")

        run([str(test_plan), str(project), "--diff-intel", str(intel_path)])
        plan = json.loads((project / ".gauntlet" / "test-plan.json").read_text())
        commands = [item["command"] for item in plan["commands"]]
        for command in [
            "python -m pytest tests/test_twitter_notifs_classifier.py",
            "python -m pytest tests/test_agora_fleet.py",
        ]:
            if command not in commands:
                raise AssertionError(f"test plan missing Python command: {command}; got {commands}")

        (project / "docs" / "guide.md").write_text("# Guide\n\nChanged docs.\n")
        (project / ".review-brief-server.log").write_text("local server log\n")
        (project / ".review-brief-server.pid").write_text("123\n")
        (project / "implementation-notes.html").write_text("<p>local notes</p>\n")
        run([str(diff_intel), str(project)])
        artifact_intel = json.loads((project / ".gauntlet" / "diff-intel.json").read_text())
        paths = [item["path"] for item in artifact_intel["changedFiles"]]
        for path in [".review-brief-server.log", ".review-brief-server.pid", "implementation-notes.html"]:
            if path in paths:
                raise AssertionError(f"local run artifact should be ignored: {paths}")
        if artifact_intel["riskTriggers"] != ["docs-only"]:
            raise AssertionError(f"artifact-filtered docs diff should remain docs-only: {artifact_intel['riskTriggers']}")


def test_workflow_speedup_helpers_are_documented_as_advisory():
    agents = read(AGENTS_MD)
    readme = read(README_MD)
    speedups = read(ROOT / "docs" / "workflow-speedups.md")
    combined = "\n".join([agents, readme, speedups])

    for marker in [
        "diff-intel.py",
        "test-plan.py",
        "review-pack.py",
        "gauntlet.py memory lint",
        "gauntlet.py changelog pr",
        "gauntlet.py followup thread",
        "Implementation Memory remains the source",
        "create_thread",
        "advisory",
        "confidence",
        "Cannot verify",
        "quality-check --surface",
        "deferred",
        "stale",
        "dirty worktree",
    ]:
        assert_contains(combined, marker, "workflow speedup guidance")

    for marker in [
        "p#-auto: [C1][In Progress]",
        "main chat is the orchestrator",
        "do not ask the user directly",
        "Needs decision",
        "`To Do`, `In Progress`, `Blocked`, `In Review`, `Done`, and `Canceled`",
        "Use `Blocked` only for a concrete blocker",
        "Create a separate git worktree by default for write-heavy child chats",
        "Archive the child chat after its report is integrated",
        "Child task packet shape",
    ]:
        assert_contains(read(ROOT / "docs" / "workflow-etiquette.md"), marker, "delegation etiquette child lane guidance")

    for marker in [
        "separate git worktrees by default",
        "p1-auto: [C1][In Progress]",
        "main chat owns the child-lane ledger",
        "archive after their reports are integrated",
    ]:
        assert_contains(speedups, marker, "workflow speedup child lane guidance")

    for marker in [
        "scripts/gauntlet.py memory lint",
        "scripts/gauntlet.py changelog pr",
        "scripts/gauntlet.py followup thread",
        "Edge Cases From This Ask",
        "Need user decision",
        "Safe defaults I will apply",
        "before implementation",
        "emit app-action packets",
        "p#-auto: [C1][In Progress]",
        "main chat as orchestrator",
        "create a separate git worktree by default",
        "Child lane id, title, status, dependency note, and worktree path",
    ]:
        assert_contains(agents, marker, "active AGENTS workflow speedup routing")


def test_workflow_etiquette_checker_validates_titles_kickoff_and_auto_assumptions():
    checker = SCRIPTS / "check-workflow-etiquette.py"
    if not checker.exists() or not os.access(checker, os.X_OK):
        raise AssertionError(f"missing executable workflow etiquette checker: {checker}")

    with tempfile.TemporaryDirectory() as tmp:
        content = Path(tmp) / "kickoff.md"
        content.write_text(
            "\n".join([
                "Mode: Feature",
                "Depth: Standard",
                "Verification Scope: delta",
                "Execution Mode: autonomous",
                "Suggested thread label: p2-auto: fix archive closeout",
                "",
                "Assumptions Made:",
                "- Assumptions made: local fixtures cover archive examples.",
                "- Ambiguity handled: no real archive action is taken.",
                "- Verification: checker fixtures pass.",
                "",
            ])
        )
        result = run([
            str(checker),
            "--title",
            "p2-auto: fix archive closeout",
            "--content",
            str(content),
            "--require-kickoff",
            "--json",
        ])
        data = json.loads(result.stdout)
        if data["status"] != "pass":
            raise AssertionError(f"valid autonomous kickoff should pass: {data}")
        if data["parsedTitle"]["executionMode"] != "autonomous":
            raise AssertionError("auto title should parse as autonomous")
        if data["effectiveExecutionMode"] != "autonomous":
            raise AssertionError("auto kickoff should report effective execution mode")

        legacy = run([str(checker), "--title", "p2 - fix archive closeout", "--json"])
        legacy_data = json.loads(legacy.stdout)
        if legacy_data["status"] != "warn":
            raise AssertionError(f"legacy title should warn, not fail: {legacy_data}")
        if not any(finding["code"] == "legacy_title_format" for finding in legacy_data["findings"]):
            raise AssertionError(f"legacy title warning missing: {legacy_data}")

        decision_gate = Path(tmp) / "decision-gate.md"
        decision_gate.write_text(
            "\n".join([
                "Mode: Feature",
                "Depth: Standard",
                "Verification Scope: delta",
                "Execution Mode: autonomous",
                "Decision Gate: before unsafe archive action",
                "Suggested thread label: p1-auto: formalize workflow etiquette checks",
                "",
            ])
        )
        decision_gate_result = run([
            str(checker),
            "--title",
            "p1-auto: formalize workflow etiquette checks",
            "--content",
            str(decision_gate),
            "--require-kickoff",
            "--json",
        ])
        decision_gate_data = json.loads(decision_gate_result.stdout)
        if decision_gate_data["effectiveExecutionMode"] != "autonomous":
            raise AssertionError(f"decision-gated autonomous kickoff should report effective mode: {decision_gate_data}")
        if decision_gate_data["decisionGate"] != "before unsafe archive action":
            raise AssertionError(f"decision gate should be reported: {decision_gate_data}")

        legacy_review = Path(tmp) / "legacy-review.md"
        legacy_review.write_text(
            "\n".join([
                "Mode: Patch",
                "Depth: Standard",
                "Verification Scope: smoke",
                "Execution Mode: reviewed",
                "Suggested thread label: p3: fix archive closeout",
                "",
            ])
        )
        legacy_review_result = run([
            str(checker),
            "--title",
            "p3: fix archive closeout",
            "--content",
            str(legacy_review),
            "--require-kickoff",
            "--json",
        ])
        legacy_review_data = json.loads(legacy_review_result.stdout)
        if legacy_review_data["effectiveExecutionMode"] != "review":
            raise AssertionError(f"legacy reviewed mode should normalize to review: {legacy_review_data}")
        if not any(finding["code"] == "legacy_reviewed_execution_mode" for finding in legacy_review_data["findings"]):
            raise AssertionError(f"legacy reviewed mode warning missing: {legacy_review_data}")

        malformed = run([str(checker), "--title", "priority two archive thing", "--json"], check=False)
        if malformed.returncode != 1:
            raise AssertionError(f"malformed title should fail with exit 1: {malformed.stdout}")
        if not any(finding["code"] == "malformed_title" for finding in json.loads(malformed.stdout)["findings"]):
            raise AssertionError(f"malformed title finding missing: {malformed.stdout}")

        missing_auto = Path(tmp) / "missing-auto.md"
        missing_auto.write_text(
            "\n".join([
                "Mode: Patch",
                "Depth: Standard",
                "Verification Scope: smoke",
                "Execution Mode: autonomous",
                "Suggested thread label: p3-auto: fix archive closeout",
                "",
            ])
        )
        auto_result = run([
            str(checker),
            "--title",
            "p3-auto: fix archive closeout",
            "--content",
            str(missing_auto),
            "--require-kickoff",
            "--require-assumptions",
            "--json",
        ], check=False)
        if auto_result.returncode != 1:
            raise AssertionError(f"auto without assumptions should fail: {auto_result.stdout}")
        if not any(finding["code"] == "missing_assumptions_made" for finding in json.loads(auto_result.stdout)["findings"]):
            raise AssertionError(f"missing assumptions finding missing: {auto_result.stdout}")


def test_workflow_etiquette_checker_pauses_archive_on_followups_and_git_state():
    checker = SCRIPTS / "check-workflow-etiquette.py"
    if not checker.exists() or not os.access(checker, os.X_OK):
        raise AssertionError(f"missing executable workflow etiquette checker: {checker}")

    with tempfile.TemporaryDirectory() as tmp:
        strong = Path(tmp) / "strong.md"
        strong.write_text(
            "\n".join([
                "Follow-up captured:",
                "- Topic: Gauntlet CLI speedups",
                "- Strength: strong follow-up",
                "- Why it matters: deterministic helpers can reduce chat overhead.",
                "",
            ])
        )
        strong_result = run([str(checker), "--content", str(strong), "--archive", "--json"], check=False)
        if strong_result.returncode != 2:
            raise AssertionError(f"strong follow-up should pause archive with exit 2: {strong_result.stdout}")
        strong_data = json.loads(strong_result.stdout)
        if strong_data["status"] != "review":
            raise AssertionError(f"strong follow-up should require review: {strong_data}")
        if not any(finding["code"] == "strong_followup_open" for finding in strong_data["findings"]):
            raise AssertionError(f"strong follow-up finding missing: {strong_data}")

        later = Path(tmp) / "later.md"
        later.write_text(
            "\n".join([
                "Follow-up captured:",
                "- Topic: Mermaid rendering polish",
                "- Strength: follow-up for later",
                "",
            ])
        )
        later_result = run([str(checker), "--content", str(later), "--archive", "--json"])
        later_data = json.loads(later_result.stdout)
        if later_data["status"] != "pass":
            raise AssertionError(f"later follow-up should not pause archive: {later_data}")

        repo = Path(tmp) / "repo"
        init_repo(repo)
        (repo / "README.md").write_text("# Repo\n")
        commit_all(repo, "baseline")
        clean = run([str(checker), "--git-root", str(repo), "--archive", "--json"])
        if json.loads(clean.stdout)["status"] != "pass":
            raise AssertionError(f"clean archive git state should pass: {clean.stdout}")

        remote = Path(tmp) / "remote.git"
        git(["init", "--bare", str(remote)], cwd=tmp)
        git(["remote", "add", "origin", str(remote)], cwd=repo)
        git(["push", "-u", "origin", "HEAD"], cwd=repo)
        (repo / "README.md").write_text("# Repo\n\nLocal change.\n")
        commit_all(repo, "local change")
        ahead = run([str(checker), "--git-root", str(repo), "--archive", "--json"])
        ahead_data = json.loads(ahead.stdout)
        if ahead_data["status"] != "pass":
            raise AssertionError(f"clean ahead branch should plan push without review: {ahead_data}")
        push_actions = [
            action for action in ahead_data["archivePlan"]["actions"]
            if action.get("type") == "git_push"
        ]
        if not push_actions or push_actions[0].get("ahead") != 1 or not push_actions[0].get("upstream", "").startswith("origin/"):
            raise AssertionError(f"ahead branch should plan git push before archive: {ahead_data}")
        git(["push"], cwd=repo)

        missing_root = run([
            str(checker),
            "--git-root",
            str(Path(tmp) / "missing-repo"),
            "--archive",
            "--json",
        ], check=False)
        if missing_root.returncode != 2:
            raise AssertionError(f"missing git root should require review: {missing_root.stdout}")
        if not any(finding["code"] == "git_root_missing" for finding in json.loads(missing_root.stdout)["findings"]):
            raise AssertionError(f"missing git root finding missing: {missing_root.stdout}")

        (repo / "dirty.txt").write_text("dirty\n")
        (repo / "dirty-2.txt").write_text("dirty\n")
        (repo / "dirty-3.txt").write_text("dirty\n")
        (repo / "dirty-4.txt").write_text("dirty\n")
        dirty = run([str(checker), "--git-root", str(repo), "--archive", "--json"], check=False)
        if dirty.returncode != 2:
            raise AssertionError(f"dirty git state should require review: {dirty.stdout}")
        dirty_data = json.loads(dirty.stdout)
        if not any(finding["code"] == "dirty_worktree" for finding in dirty_data["findings"]):
            raise AssertionError(f"dirty worktree finding missing: {dirty.stdout}")
        if not any("and 1 more" in finding["message"] for finding in dirty_data["findings"]):
            raise AssertionError(f"dirty worktree finding should disclose abbreviated files: {dirty.stdout}")


def test_workflow_etiquette_checker_builds_archive_action_plan():
    checker = SCRIPTS / "check-workflow-etiquette.py"
    if not checker.exists() or not os.access(checker, os.X_OK):
        raise AssertionError(f"missing executable workflow etiquette checker: {checker}")

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        init_repo(repo)
        (repo / "README.md").write_text("# Repo\n")
        commit_all(repo, "baseline")

        result = run([
            str(checker),
            "--title",
            "Indexed implementation context docs",
            "--suggested-title",
            "p1-auto: formalize workflow etiquette checks",
            "--git-root",
            str(repo),
            "--archive",
            "--json",
        ])
        data = json.loads(result.stdout)
        plan = data.get("archivePlan", {})
        if data["status"] != "warn":
            raise AssertionError(f"archive rename plan should be warning-only: {data}")
        if not plan.get("canArchive"):
            raise AssertionError(f"archive plan should be executable: {data}")
        actions = plan.get("actions", [])
        expected = [
            {"type": "set_thread_title", "title": "p1-auto: formalize workflow etiquette checks"},
            {"type": "archive_thread"},
        ]
        if actions != expected:
            raise AssertionError(f"archive action plan mismatch: {actions}")
        if not any(finding["code"] == "title_requires_rename" for finding in data["findings"]):
            raise AssertionError(f"title rename warning missing: {data}")

        malformed_suggestion = run([
            str(checker),
            "--title",
            "Indexed implementation context docs",
            "--suggested-title",
            "priority one etiquette checks",
            "--archive",
            "--json",
        ], check=False)
        if malformed_suggestion.returncode != 1:
            raise AssertionError(f"malformed suggested title should fail: {malformed_suggestion.stdout}")
        if json.loads(malformed_suggestion.stdout).get("archivePlan", {}).get("canArchive"):
            raise AssertionError(f"malformed suggestion must not be executable: {malformed_suggestion.stdout}")

        strong = Path(tmp) / "strong.md"
        strong.write_text(
            "\n".join([
                "Follow-up captured:",
                "- Topic: Gauntlet CLI speedups",
                "- Strength: strong follow-up",
                "- Why it matters: deterministic helpers can reduce chat overhead.",
                "",
            ])
        )
        anyway = run([
            str(checker),
            "--title",
            "p1-auto: formalize workflow etiquette checks",
            "--content",
            str(strong),
            "--archive",
            "--archive-anyway",
            "--json",
        ])
        anyway_data = json.loads(anyway.stdout)
        if anyway_data["status"] != "warn":
            raise AssertionError(f"archive anyway should warn, not review: {anyway_data}")
        if anyway_data.get("archivePlan", {}).get("actions") != [{"type": "archive_thread"}]:
            raise AssertionError(f"archive anyway should still plan archive: {anyway_data}")
        if not any(finding["code"] == "strong_followup_archived_anyway" for finding in anyway_data["findings"]):
            raise AssertionError(f"archive anyway warning missing: {anyway_data}")


def test_gauntlet_cli_archive_plans_and_executes_github_merge():
    cli = SCRIPTS / "gauntlet.py"
    if not cli.exists() or not os.access(cli, os.X_OK):
        raise AssertionError(f"missing executable Gauntlet CLI: {cli}")

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        remote = Path(tmp) / "remote.git"
        init_repo(repo)
        git(["branch", "-M", "main"], cwd=repo)
        (repo / "README.md").write_text("# Repo\n")
        commit_all(repo, "baseline")
        git(["init", "--bare", str(remote)], cwd=tmp)
        git(["remote", "add", "origin", str(remote)], cwd=repo)
        git(["push", "-u", "origin", "main"], cwd=repo)

        git(["checkout", "-b", "codex/archive-flow"], cwd=repo)
        (repo / "feature.txt").write_text("archive flow\n")
        commit_all(repo, "feature")
        git(["push", "-u", "origin", "HEAD"], cwd=repo)
        (repo / "allowed-dirty.txt").write_text("unrelated local note\n")

        gh_log = Path(tmp) / "gh.log"
        fake_gh = Path(tmp) / "gh"
        fake_gh.write_text(
            "\n".join([
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "printf '%s\\n' \"$*\" >> \"$GH_LOG\"",
                "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"view\" ]; then",
                "  cat <<'JSON'",
                '{"number":7,"state":"OPEN","isDraft":false,"mergeable":"MERGEABLE","mergedAt":null,"statusCheckRollup":[{"__typename":"CheckRun","name":"gauntlet","status":"COMPLETED","conclusion":"SUCCESS"}],"url":"https://example.test/pr/7","baseRefName":"main","headRefName":"codex/archive-flow","reviewDecision":""}',
                "JSON",
                "  exit 0",
                "fi",
                "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"merge\" ]; then",
                "  exit 0",
                "fi",
                "echo unexpected gh args: \"$*\" >&2",
                "exit 2",
                "",
            ])
        )
        fake_gh.chmod(0o755)
        old_gh = os.environ.get("GAUNTLET_GH")
        old_gh_log = os.environ.get("GH_LOG")
        os.environ["GAUNTLET_GH"] = str(fake_gh)
        os.environ["GH_LOG"] = str(gh_log)
        try:
            plan = run([
                str(cli),
                "archive",
                "plan",
                "--title",
                "p2-auto: fix archive closeout",
                "--git-root",
                str(repo),
                "--allow-dirty",
                "allowed-dirty.txt",
                "--json",
            ], cwd=repo)
            plan_data = json.loads(plan.stdout)
            if plan_data["status"] != "warn":
                raise AssertionError(f"green PR archive plan should pass: {plan_data}")
            action_types = [action["type"] for action in plan_data["archivePlan"]["actions"]]
            if action_types != ["gh_pr_merge", "archive_thread"]:
                raise AssertionError(f"green PR should plan merge then archive: {plan_data}")
            merge_action = plan_data["archivePlan"]["actions"][0]
            if merge_action.get("mergeMethod") != "merge" or merge_action.get("prNumber") != 7:
                raise AssertionError(f"merge action should use merge commit for PR 7: {plan_data}")

            execute = run([
                str(cli),
                "archive",
                "execute",
                "--title",
                "p2-auto: fix archive closeout",
                "--git-root",
                str(repo),
                "--allow-dirty",
                "allowed-dirty.txt",
                "--json",
            ], cwd=repo)
            execute_data = json.loads(execute.stdout)
            if execute_data["status"] != "warn":
                raise AssertionError(f"archive execute should pass with fake gh: {execute_data}")
            if execute_data.get("remainingAppActions") != [{"type": "archive_thread"}]:
                raise AssertionError(f"execute should leave app archive action for agent: {execute_data}")
            if "pr merge 7 --merge --delete-branch" not in gh_log.read_text():
                raise AssertionError(f"execute should merge PR through gh: {gh_log.read_text()}")
        finally:
            if old_gh is None:
                os.environ.pop("GAUNTLET_GH", None)
            else:
                os.environ["GAUNTLET_GH"] = old_gh
            if old_gh_log is None:
                os.environ.pop("GH_LOG", None)
            else:
                os.environ["GH_LOG"] = old_gh_log


def test_gauntlet_cli_archive_keeps_archive_anyway_from_overriding_git_risk():
    cli = SCRIPTS / "gauntlet.py"
    if not cli.exists() or not os.access(cli, os.X_OK):
        raise AssertionError(f"missing executable Gauntlet CLI: {cli}")

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        init_repo(repo)
        git(["branch", "-M", "main"], cwd=repo)
        (repo / "README.md").write_text("# Repo\n")
        commit_all(repo, "baseline")
        (repo / "scratch.md").write_text("next feature\n")

        archive_anyway = run([
            str(cli),
            "archive",
            "plan",
            "--title",
            "p3: tidy archive flow",
            "--git-root",
            str(repo),
            "--archive-anyway",
            "--json",
        ], cwd=repo, check=False)
        if archive_anyway.returncode != 2:
            raise AssertionError(f"archive-anyway must not override dirty git risk: {archive_anyway.stdout}")
        archive_anyway_data = json.loads(archive_anyway.stdout)
        if not any(finding["code"] == "git_risk_confirmation_required" for finding in archive_anyway_data["findings"]):
            raise AssertionError(f"git risk confirmation finding missing: {archive_anyway_data}")
        if archive_anyway_data["archivePlan"].get("canArchive"):
            raise AssertionError(f"git risk should block archive until explicitly confirmed: {archive_anyway_data}")

        confirmed = run([
            str(cli),
            "archive",
            "plan",
            "--title",
            "p3: tidy archive flow",
            "--git-root",
            str(repo),
            "--confirm-git-risk",
            "--json",
        ], cwd=repo)
        confirmed_data = json.loads(confirmed.stdout)
        if confirmed_data["status"] != "warn":
            raise AssertionError(f"confirmed git risk should warn, not block: {confirmed_data}")
        if confirmed_data["archivePlan"].get("actions") != [{"type": "archive_thread"}]:
            raise AssertionError(f"confirmed git risk should archive without git actions: {confirmed_data}")

        allowlisted = run([
            str(cli),
            "archive",
            "plan",
            "--title",
            "p3: tidy archive flow",
            "--git-root",
            str(repo),
            "--allow-dirty",
            "scratch.md",
            "--json",
        ], cwd=repo)
        allowlisted_data = json.loads(allowlisted.stdout)
        if allowlisted_data["status"] != "warn":
            raise AssertionError(f"allowlisted dirty file should warn only: {allowlisted_data}")
        if not any(finding["code"] == "dirty_worktree_allowlisted" for finding in allowlisted_data["findings"]):
            raise AssertionError(f"allowlisted dirty finding missing: {allowlisted_data}")
        if allowlisted_data["archivePlan"].get("actions") != [{"type": "archive_thread"}]:
            raise AssertionError(f"allowlisted dirty file should still archive: {allowlisted_data}")


def test_gauntlet_cli_small_helper_commands():
    cli = SCRIPTS / "gauntlet.py"
    if not cli.exists() or not os.access(cli, os.X_OK):
        raise AssertionError(f"missing executable Gauntlet CLI: {cli}")

    followup = run([
        str(cli),
        "followup",
        "note",
        "--topic",
        "Gauntlet CLI speedups",
        "--strength",
        "strong follow-up",
        "--why",
        "deterministic helpers reduce chat overhead",
        "--context",
        "archive planning now emits actions",
        "--opener",
        "Review which Gauntlet flows should become CLI commands.",
    ])
    for marker in [
        "Follow-up captured:",
        "- Topic: Gauntlet CLI speedups",
        "- Strength: strong follow-up",
        "- Why it matters: deterministic helpers reduce chat overhead",
        "- Context already known: archive planning now emits actions",
        "- Suggested opener: Review which Gauntlet flows should become CLI commands.",
    ]:
        assert_contains(followup.stdout, marker, "follow-up note")

    diagram = run([str(cli), "diagram", "find", "--query", "workflow-etiquette", "--json"])
    diagram_data = json.loads(diagram.stdout)
    if not diagram_data.get("matches"):
        raise AssertionError(f"diagram find should locate saved workflow etiquette diagram: {diagram_data}")

    with tempfile.TemporaryDirectory() as tmp:
        agent_home = Path(tmp) / "agent-home"
        run_install(agent_home, target="claude")
        verify = run([
            str(cli),
            "install",
            "verify",
            "--target",
            "claude",
            "--agent-home",
            str(agent_home),
            "--json",
        ])
        verify_data = json.loads(verify.stdout)
        if verify_data["status"] != "pass":
            raise AssertionError(f"install verify should pass for Claude install: {verify_data}")


def test_gauntlet_cli_changelog_memory_and_followup_helpers():
    cli = SCRIPTS / "gauntlet.py"
    if not cli.exists() or not os.access(cli, os.X_OK):
        raise AssertionError(f"missing executable Gauntlet CLI: {cli}")

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        init_repo(repo)
        git(["branch", "-M", "main"], cwd=repo)
        (repo / "README.md").write_text("# Repo\n")
        commit_all(repo, "baseline")
        git(["checkout", "-b", "codex/changelog"], cwd=repo)
        (repo / "feature.txt").write_text("helper\n")
        commit_all(repo, "feature")

        memory = repo / "docs" / "implementation-memory.md"
        memory.parent.mkdir()
        memory.write_text(
            "\n".join([
                "# Implementation Memory",
                "",
                "## Goal",
                "",
                "Build changelog and follow-up helpers for Gauntlet.",
                "",
                "## Scope",
                "",
                "- Add non-mutating CLI helpers.",
                "",
                "## Non-goals",
                "",
                "- Do not create threads from the shell.",
                "",
                "## Scan Index",
                "",
                "- `scripts/gauntlet.py`",
                "- `docs/workflow-speedups.md`",
                "",
                "## Source-of-truth files",
                "",
                "- `scripts/gauntlet.py`",
                "- `scripts/check-gauntlet-workflow.py`",
                "",
                "## Edge cases and invariants",
                "",
                "- GitHub metadata verifies PR facts but does not replace the implementation summary.",
                "- Missing external state becomes Cannot verify.",
                "",
                "## Verification",
                "",
                "- `python3 scripts/check-gauntlet-workflow.py`",
                "",
                "## Archive Summary",
                "",
                "- Added agent-authored archive summaries to the PR changelog helper.",
                "- Reused the same summary block in archive planning output.",
                "- Kept summary output compact so archive review does not require status plumbing.",
                "",
                "## Follow-ups",
                "",
                "Follow-up captured:",
                "- Topic: Follow-up thread shortcut",
                "- Strength: strong follow-up",
                "- Why it matters: handoff context gets lost.",
                "- Context already known: follow-up note format exists.",
                "- Suggested opener: Build a shortcut that emits a create-thread action packet.",
                "",
                "## Stale context warning",
                "",
                "GitHub PR state can change after generation.",
                "",
                "## Redaction notes",
                "",
                "No secrets or private operational data included.",
                "",
            ]),
            encoding="utf-8",
        )

        lint = run([
            str(cli),
            "memory",
            "lint",
            "--path",
            str(memory),
            "--json",
        ], cwd=repo)
        lint_data = json.loads(lint.stdout)
        if lint_data["status"] != "pass":
            raise AssertionError(f"complete implementation memory should pass lint: {lint_data}")

        bad_memory = repo / "docs" / "bad-memory.md"
        bad_memory.write_text("# Implementation Memory\n\n## Goal\n\nToo thin.\n", encoding="utf-8")
        bad_lint = run([
            str(cli),
            "memory",
            "lint",
            "--path",
            str(bad_memory),
            "--json",
        ], cwd=repo, check=False)
        if bad_lint.returncode != 1:
            raise AssertionError(f"incomplete implementation memory should fail lint: {bad_lint.stdout}")
        bad_lint_data = json.loads(bad_lint.stdout)
        if not any(finding["code"] == "missing_memory_section" for finding in bad_lint_data["findings"]):
            raise AssertionError(f"memory lint should report missing sections: {bad_lint_data}")
        secret_memory = repo / "docs" / "secret-memory.md"
        secret_memory.write_text(memory.read_text() + "\nAPI_TOKEN=sk-live-secret-value\n", encoding="utf-8")
        secret_lint = run([
            str(cli),
            "memory",
            "lint",
            "--path",
            str(secret_memory),
            "--json",
        ], cwd=repo, check=False)
        if secret_lint.returncode != 1:
            raise AssertionError(f"secret-like implementation memory should fail lint: {secret_lint.stdout}")
        secret_data = json.loads(secret_lint.stdout)
        if not any(finding["code"] == "secret_like_memory_content" for finding in secret_data["findings"]):
            raise AssertionError(f"secret-like memory finding missing: {secret_data}")

        gh_log = Path(tmp) / "gh.log"
        fake_gh = Path(tmp) / "gh"
        fake_gh.write_text(
            "\n".join([
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "printf '%s\\n' \"$*\" >> \"$GH_LOG\"",
                "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"view\" ]; then",
                "  cat <<'JSON'",
                '{"number":12,"state":"MERGED","isDraft":false,"mergeable":"MERGEABLE","mergedAt":"2026-07-08T12:00:00Z","statusCheckRollup":[{"__typename":"CheckRun","name":"gauntlet","status":"COMPLETED","conclusion":"SUCCESS"}],"url":"https://example.test/pr/12","baseRefName":"main","headRefName":"codex/changelog","reviewDecision":"APPROVED","title":"Build changelog helpers","body":"PR body from GitHub should verify facts, not replace memory."}',
                "JSON",
                "  exit 0",
                "fi",
                "echo unexpected gh args: \"$*\" >&2",
                "exit 2",
                "",
            ]),
            encoding="utf-8",
        )
        fake_gh.chmod(0o755)
        old_gh = os.environ.get("GAUNTLET_GH")
        old_gh_log = os.environ.get("GH_LOG")
        os.environ["GAUNTLET_GH"] = str(fake_gh)
        os.environ["GH_LOG"] = str(gh_log)
        try:
            changelog = run([
                str(cli),
                "changelog",
                "pr",
                "--implementation-memory",
                str(memory),
                "--git-root",
                str(repo),
                "--json",
            ], cwd=repo)
        finally:
            if old_gh is None:
                os.environ.pop("GAUNTLET_GH", None)
            else:
                os.environ["GAUNTLET_GH"] = old_gh
            if old_gh_log is None:
                os.environ.pop("GH_LOG", None)
            else:
                os.environ["GH_LOG"] = old_gh_log
        changelog_data = json.loads(changelog.stdout)
        if changelog_data["status"] != "pass":
            raise AssertionError(f"verified changelog should pass: {changelog_data}")
        for marker in [
            "Build changelog and follow-up helpers for Gauntlet.",
            "## Archive Summary",
            "- Added agent-authored archive summaries to the PR changelog helper.",
            "- Reused the same summary block in archive planning output.",
            "| [#12](https://example.test/pr/12) | MERGED | Build changelog helpers |",
            "Follow-up thread shortcut",
            "GitHub PR state can change after generation.",
        ]:
            assert_contains(changelog_data["markdown"], marker, "PR changelog markdown")
        assert_not_contains(changelog_data["markdown"], "PR body from GitHub should verify facts", "PR changelog source precedence")

        changelog_output = repo / "docs" / "pr-changelog.md"
        changelog_output.write_text(changelog_data["markdown"], encoding="utf-8")
        archive = run([
            str(cli),
            "archive",
            "plan",
            "--title",
            "p2-auto: build changelog helpers",
            "--content",
            str(changelog_output),
            "--git-root",
            str(repo),
            "--confirm-git-risk",
            "--json",
        ], cwd=repo)
        archive_data = json.loads(archive.stdout)
        if archive_data["archiveSummary"]["bullets"] != [
            "Added agent-authored archive summaries to the PR changelog helper.",
            "Reused the same summary block in archive planning output.",
            "Kept summary output compact so archive review does not require status plumbing.",
        ]:
            raise AssertionError(f"archive plan should reuse changelog Archive Summary: {archive_data}")
        if archive_data["archiveSummary"]["source"] != "content":
            raise AssertionError(f"archive summary should report content source: {archive_data}")

        archive_text = run([
            str(cli),
            "archive",
            "plan",
            "--title",
            "p2-auto: build changelog helpers",
            "--content",
            str(changelog_output),
            "--git-root",
            str(repo),
            "--confirm-git-risk",
        ], cwd=repo)
        assert_contains(archive_text.stdout, "Archive Summary", "archive summary output")
        assert_contains(
            archive_text.stdout,
            "- Reused the same summary block in archive planning output.",
            "archive summary output",
        )
        assert_not_contains(archive_text.stdout, "Gauntlet:", "archive summary output should avoid status plumbing")
        assert_not_contains(archive_text.stdout, "canArchive", "archive summary output should avoid JSON plumbing")

        archive_stdin = run([
            str(cli),
            "archive",
            "plan",
            "--title",
            "p2-auto: build changelog helpers",
            "--content",
            "-",
            "--git-root",
            str(repo),
            "--confirm-git-risk",
            "--json",
        ], cwd=repo, input_text=changelog_data["markdown"])
        archive_stdin_data = json.loads(archive_stdin.stdout)
        if archive_stdin_data["archiveSummary"]["source"] != "content":
            raise AssertionError(f"stdin archive summary should be treated as content: {archive_stdin_data}")
        if archive_stdin_data["archiveSummary"]["bullets"][0] != "Added agent-authored archive summaries to the PR changelog helper.":
            raise AssertionError(f"stdin archive summary should reuse changelog bullets: {archive_stdin_data}")

        failing_gh = Path(tmp) / "failing-gh"
        failing_gh.write_text(
            "\n".join([
                "#!/usr/bin/env bash",
                "echo gh unavailable >&2",
                "exit 2",
                "",
            ]),
            encoding="utf-8",
        )
        failing_gh.chmod(0o755)
        old_gh = os.environ.get("GAUNTLET_GH")
        os.environ["GAUNTLET_GH"] = str(failing_gh)
        try:
            unverified = run([
                str(cli),
                "changelog",
                "pr",
                "--implementation-memory",
                str(memory),
                "--git-root",
                str(repo),
                "--json",
            ], cwd=repo)
        finally:
            if old_gh is None:
                os.environ.pop("GAUNTLET_GH", None)
            else:
                os.environ["GAUNTLET_GH"] = old_gh
        unverified_data = json.loads(unverified.stdout)
        if unverified_data["status"] != "warn":
            raise AssertionError(f"missing gh should warn while producing markdown: {unverified_data}")
        if not any(finding["code"] == "cannot_verify_pr_metadata" for finding in unverified_data["findings"]):
            raise AssertionError(f"missing gh should produce Cannot verify finding: {unverified_data}")
        assert_contains(unverified_data["markdown"], "Cannot verify", "unverified PR changelog")

        followup_content = repo / "followup.md"
        followup_content.write_text(
            "\n".join([
                "Follow-up captured:",
                "- Topic: Follow-up thread shortcut",
                "- Strength: strong follow-up",
                "- Why it matters: handoff context gets lost.",
                "- Context already known: follow-up note format exists.",
                "- Suggested opener: Build a shortcut that emits a create-thread action packet.",
                "",
            ]),
            encoding="utf-8",
        )
        thread = run([
            str(cli),
            "followup",
            "thread",
            "--content",
            str(followup_content),
            "--title",
            "p2-auto: build followup shortcut",
            "--cwd",
            str(repo),
            "--source-thread",
            "thread-123",
            "--json",
        ], cwd=repo)
        thread_data = json.loads(thread.stdout)
        if thread_data["status"] != "pass":
            raise AssertionError(f"follow-up thread packet should pass: {thread_data}")
        actions = thread_data.get("actions", [])
        if len(actions) != 1 or actions[0].get("type") != "create_thread":
            raise AssertionError(f"follow-up helper should emit one create_thread action: {thread_data}")
        if actions[0].get("title") != "p2-auto: build followup shortcut":
            raise AssertionError(f"follow-up helper should preserve selected title: {thread_data}")
        assert_contains(actions[0].get("message", ""), "Build a shortcut", "follow-up thread message")
        assert_contains(actions[0].get("message", ""), "Source thread: thread-123", "follow-up thread source")

        malformed_thread = run([
            str(cli),
            "followup",
            "thread",
            "--content",
            str(followup_content),
            "--title",
            "build followup shortcut",
            "--json",
        ], cwd=repo, check=False)
        if malformed_thread.returncode != 1:
            raise AssertionError(f"malformed follow-up thread title should fail: {malformed_thread.stdout}")
        malformed_data = json.loads(malformed_thread.stdout)
        if malformed_data.get("actions"):
            raise AssertionError(f"malformed follow-up thread title should not emit actions: {malformed_data}")
        if not any(finding["code"] == "malformed_thread_title" for finding in malformed_data["findings"]):
            raise AssertionError(f"malformed follow-up title finding missing: {malformed_data}")

        no_followup = repo / "no-followup.md"
        no_followup.write_text("No follow-up block here.\n", encoding="utf-8")
        missing_followup = run([
            str(cli),
            "followup",
            "thread",
            "--content",
            str(no_followup),
            "--title",
            "p2-auto: build followup shortcut",
            "--json",
        ], cwd=repo, check=False)
        if missing_followup.returncode != 1:
            raise AssertionError(f"missing follow-up block should fail: {missing_followup.stdout}")
        missing_followup_data = json.loads(missing_followup.stdout)
        if missing_followup_data.get("actions"):
            raise AssertionError(f"missing follow-up block should not emit actions: {missing_followup_data}")
        if not any(finding["code"] == "missing_followup_block" for finding in missing_followup_data["findings"]):
            raise AssertionError(f"missing follow-up block finding missing: {missing_followup_data}")

        missing_followup_file = run([
            str(cli),
            "followup",
            "thread",
            "--content",
            str(repo / "missing-followup.md"),
            "--title",
            "p2-auto: build followup shortcut",
            "--json",
        ], cwd=repo, check=False)
        if missing_followup_file.returncode != 1:
            raise AssertionError(f"missing follow-up file should fail: {missing_followup_file.stdout}")
        missing_file_data = json.loads(missing_followup_file.stdout)
        if not any(finding["code"] == "missing_followup_file" for finding in missing_file_data["findings"]):
            raise AssertionError(f"missing follow-up file finding missing: {missing_file_data}")

        secret_followup = repo / "secret-followup.md"
        secret_followup.write_text(
            "\n".join([
                "Follow-up captured:",
                "- Topic: Secret follow-up",
                "- Strength: strong follow-up",
                "- Why it matters: API_TOKEN=sk-live-secret-value",
                "- Context already known: secret should not be copied.",
                "- Suggested opener: Do not emit this.",
                "",
            ]),
            encoding="utf-8",
        )
        secret_followup_result = run([
            str(cli),
            "followup",
            "thread",
            "--content",
            str(secret_followup),
            "--title",
            "p2-auto: build followup shortcut",
            "--json",
        ], cwd=repo, check=False)
        if secret_followup_result.returncode != 1:
            raise AssertionError(f"secret-like follow-up should fail: {secret_followup_result.stdout}")
        secret_followup_data = json.loads(secret_followup_result.stdout)
        if secret_followup_data.get("actions"):
            raise AssertionError(f"secret-like follow-up should not emit actions: {secret_followup_data}")
        if not any(finding["code"] == "secret_like_followup_content" for finding in secret_followup_data["findings"]):
            raise AssertionError(f"secret-like follow-up finding missing: {secret_followup_data}")


def test_gauntlet_cli_local_analytics_and_closeout_facts():
    cli = SCRIPTS / "gauntlet.py"
    if not cli.exists() or not os.access(cli, os.X_OK):
        raise AssertionError(f"missing executable Gauntlet CLI: {cli}")

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        init_repo(repo)
        git(["branch", "-M", "main"], cwd=repo)
        (repo / ".gitignore").write_text("/.gauntlet/\n")
        (repo / "README.md").write_text("# Repo\n")
        commit_all(repo, "baseline")

        event_payload = {
            "repo_name": "private-project-name",
            "branch_name": "feature/private-branch",
            "command": "npm test -- --token sk-live-secret-value",
            "command_label": "npm test",
            "mode": "Feature",
            "depth": "Deep",
            "proof_scope": "delta",
            "task_type": "feature",
            "cohort": "v2.0.2",
        }
        emitted = run([
            str(cli),
            "analytics",
            "emit",
            "--project-root",
            str(repo),
            "--run-id",
            "run-analytics",
            "--event-type",
            "run_started",
            "--gauntlet-version",
            "2.0.2",
            "--payload-json",
            json.dumps(event_payload),
            "--json",
        ], cwd=repo)
        emitted_data = json.loads(emitted.stdout)
        if emitted_data["status"] != "pass":
            raise AssertionError(f"analytics emit should pass: {emitted_data}")
        event = emitted_data["event"]
        if event["schema_version"] != "gauntlet.analytics.v1":
            raise AssertionError(f"analytics event should carry schema version: {event}")
        if event["payload"].get("command_label") != "npm test":
            raise AssertionError(f"safe coarse command label should be preserved: {event}")
        if "command_hash" not in event["payload"]:
            raise AssertionError(f"raw command should be replaced by hash: {event}")

        analytics_file = repo / ".gauntlet" / "analytics" / "events.ndjson"
        if not analytics_file.exists():
            raise AssertionError("analytics emit should create local events.ndjson")
        stored = analytics_file.read_text()
        for secret_text in [
            "private-project-name",
            "feature/private-branch",
            "sk-live-secret-value",
            "npm test -- --token",
        ]:
            assert_not_contains(stored, secret_text, "analytics event storage privacy")

        closeout = run([
            str(cli),
            "analytics",
            "closeout",
            "--project-root",
            str(repo),
            "--run-id",
            "run-analytics",
            "--file-changed",
            "scripts/gauntlet.py",
            "--file-changed",
            "docs/workflow-speedups.md",
            "--proof",
            "python3 scripts/check-gauntlet-workflow.py",
            "--risk",
            "Cannot verify adoption impact until more local runs exist.",
            "--json",
        ], cwd=repo)
        closeout_data = json.loads(closeout.stdout)
        if closeout_data["status"] != "pass":
            raise AssertionError(f"analytics closeout should pass: {closeout_data}")
        summary = closeout_data["summary"]
        if summary["filesChangedCount"] != 2:
            raise AssertionError(f"closeout should count changed files: {summary}")
        if summary["proofCompleted"] != ["python3 scripts/check-gauntlet-workflow.py"]:
            raise AssertionError(f"closeout should preserve proof facts: {summary}")
        if summary["unresolvedRisks"] != ["Cannot verify adoption impact until more local runs exist."]:
            raise AssertionError(f"closeout should preserve unresolved risk facts: {summary}")
        if closeout_data.get("actions") != []:
            raise AssertionError(f"closeout must not plan commit/changelog/push/archive actions: {closeout_data}")
        if closeout_data["event"]["payload"].get("files_changed_count") != 2:
            raise AssertionError(f"closeout analytics should preserve safe numeric counts: {closeout_data}")

        stored_after_closeout = analytics_file.read_text()
        assert_contains(stored_after_closeout, "closeout_completed", "closeout analytics event")
        for raw_file in ["scripts/gauntlet.py", "docs/workflow-speedups.md"]:
            assert_not_contains(stored_after_closeout, raw_file, "analytics closeout should hash file names")
        for forbidden_action in ["commit_created", "changelog_updated", "archive_thread", "git_push"]:
            assert_not_contains(stored_after_closeout, forbidden_action, "closeout should not emit abandoned automation events")

        missing_labels = run([
            str(cli),
            "analytics",
            "summarize",
            "--project-root",
            str(repo),
            "--json",
        ], cwd=repo, check=False)
        if missing_labels.returncode != 2:
            raise AssertionError(f"missing release labels should return review exit code: {missing_labels.stdout}")
        missing_data = json.loads(missing_labels.stdout)
        if missing_data["status"] != "review":
            raise AssertionError(f"missing labels should produce review status: {missing_data}")
        if not any(finding["code"] == "missing_baseline_or_candidate" for finding in missing_data["findings"]):
            raise AssertionError(f"summarize should ask for baseline and candidate: {missing_data}")

        for cohort, verified in [("v2.0.1", True), ("v2.0.3-rc1", False)]:
            run([
                str(cli),
                "analytics",
                "emit",
                "--project-root",
                str(repo),
                "--run-id",
                f"run-{cohort}",
                "--event-type",
                "run_completed",
                "--gauntlet-version",
                cohort,
                "--payload-json",
                json.dumps({
                    "cohort": cohort,
                    "mode": "Feature",
                    "depth": "Standard",
                    "proof_scope": "delta",
                    "task_type": "feature",
                    "verified": verified,
                }),
                "--json",
            ], cwd=repo)

        timing_events = [
            ("run_started", "2026-07-01T09:00:00Z", {}),
            ("mode_selected", "2026-07-01T09:02:00Z", {"active_agent_seconds": 60}),
            ("plan_created", "2026-07-01T09:05:00Z", {"active_agent_seconds": 120}),
            ("human_review_requested", "2026-07-01T10:00:00Z", {}),
            ("human_review_completed", "2026-07-03T10:00:00Z", {}),
            ("annotation_added", "2026-07-03T10:04:00Z", {"autonomous_eligible": True}),
            ("implementation_started", "2026-07-03T10:05:00Z", {}),
            ("run_completed", "2026-07-03T10:35:00Z", {"autonomous_completed": True, "verified": True}),
        ]
        for event_type, created_at, extra_payload in timing_events:
            payload = {
                "cohort": "v2.0.3-rc1",
                "mode": "Feature",
                "depth": "Standard",
                "proof_scope": "delta",
                "task_type": "feature",
                **extra_payload,
            }
            run([
                str(cli),
                "analytics",
                "emit",
                "--project-root",
                str(repo),
                "--run-id",
                "run-timing",
                "--event-type",
                event_type,
                "--created-at",
                created_at,
                "--gauntlet-version",
                "v2.0.3-rc1",
                "--payload-json",
                json.dumps(payload),
                "--json",
            ], cwd=repo)

        summary_result = run([
            str(cli),
            "analytics",
            "summarize",
            "--project-root",
            str(repo),
            "--baseline",
            "v2.0.1",
            "--candidate",
            "v2.0.3-rc1",
            "--json",
        ], cwd=repo)
        summary_data = json.loads(summary_result.stdout)
        if summary_data["status"] != "pass":
            raise AssertionError(f"release-candidate summary should pass with labels: {summary_data}")
        if summary_data["localPrivate"] is not True:
            raise AssertionError(f"release-candidate summary should be local/private: {summary_data}")
        if summary_data["confidence"] != "anecdotal":
            raise AssertionError(f"tiny cohorts should be labeled anecdotal: {summary_data}")
        if summary_data["baseline"]["label"] != "v2.0.1" or summary_data["candidate"]["label"] != "v2.0.3-rc1":
            raise AssertionError(f"summary should preserve explicit baseline/candidate labels: {summary_data}")
        if not summary_data["segments"]:
            raise AssertionError(f"summary should segment mode/depth/proof/task facts: {summary_data}")
        timing = summary_data["candidate"]["timing"]
        if timing["calendarPlanningSpanSeconds"]["total"] != 176700:
            raise AssertionError(f"calendar planning span should include async elapsed time: {timing}")
        if timing["activeAgentPlanningSeconds"]["total"] != 180:
            raise AssertionError(f"active agent planning should sum explicit planning work: {timing}")
        if timing["humanReviewLatencySeconds"]["total"] != 172800:
            raise AssertionError(f"human review latency should be measured separately: {timing}")
        if timing["humanReviewLongGapCount"] != 1:
            raise AssertionError(f"long human review gaps should be bucketed: {timing}")
        if timing["autonomousEligibleRuns"] != 1 or timing["autonomousCompletedRuns"] != 1:
            raise AssertionError(f"autonomy should be annotation-based, not title-based: {timing}")


def test_gauntlet_cli_bounded_attempt_memory():
    cli = SCRIPTS / "gauntlet.py"
    if not cli.exists() or not os.access(cli, os.X_OK):
        raise AssertionError(f"missing executable Gauntlet CLI: {cli}")

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        init_repo(repo)
        git(["branch", "-M", "main"], cwd=repo)
        (repo / ".gitignore").write_text("/.gauntlet/\n")
        (repo / "README.md").write_text("# Repo\n")
        commit_all(repo, "baseline")

        for _ in range(2):
            added = run([
                str(cli),
                "attempt-memory",
                "add",
                "--project-root",
                str(repo),
                "--run-id",
                "run-memory",
                "--kind",
                "proof_failure",
                "--fingerprint",
                "pytest failed in private/path/test_secret.py",
                "--summary",
                "pytest failed because the fixture was missing",
                "--max-active",
                "5",
                "--json",
            ], cwd=repo)
            added_data = json.loads(added.stdout)
            if added_data["status"] != "pass":
                raise AssertionError(f"attempt-memory add should pass: {added_data}")

        listed = run([
            str(cli),
            "attempt-memory",
            "list",
            "--project-root",
            str(repo),
            "--run-id",
            "run-memory",
            "--json",
        ], cwd=repo)
        listed_data = json.loads(listed.stdout)
        entries = listed_data["entries"]
        if len(entries) != 1:
            raise AssertionError(f"repeated attempt should summarize to one entry: {listed_data}")
        if entries[0]["repeatCount"] != 2:
            raise AssertionError(f"repeated attempt should increment count: {listed_data}")

        bounded = run([
            str(cli),
            "attempt-memory",
            "add",
            "--project-root",
            str(repo),
            "--run-id",
            "run-memory",
            "--kind",
            "rejected_alternative",
            "--fingerprint",
            "alternate implementation rejected",
            "--summary",
            "alternate implementation was too broad",
            "--max-active",
            "1",
            "--json",
        ], cwd=repo)
        bounded_data = json.loads(bounded.stdout)
        if bounded_data["activeCount"] != 1:
            raise AssertionError(f"attempt memory should enforce max-active: {bounded_data}")

        listed_again = run([
            str(cli),
            "attempt-memory",
            "list",
            "--project-root",
            str(repo),
            "--run-id",
            "run-memory",
            "--json",
        ], cwd=repo)
        listed_again_data = json.loads(listed_again.stdout)
        if len(listed_again_data["entries"]) != 1:
            raise AssertionError(f"bounded attempt memory should list one active entry: {listed_again_data}")
        if listed_again_data["entries"][0]["summary"] != "alternate implementation was too broad":
            raise AssertionError(f"bounded attempt memory should retain most recent entry: {listed_again_data}")

        memory_file = repo / ".gauntlet" / "attempt-memory.jsonl"
        if not memory_file.exists():
            raise AssertionError("attempt memory should write local scratchpad file")
        memory_text = memory_file.read_text()
        assert_not_contains(memory_text, "private/path/test_secret.py", "attempt memory should hash fingerprints")

        old_entry = {
            "schemaVersion": "1.0",
            "kind": "proof_failure",
            "fingerprintHash": "old-entry",
            "summary": "old failed attempt",
            "repeatCount": 1,
            "firstSeen": "2026-01-01T00:00:00Z",
            "lastSeen": "2026-01-01T00:00:00Z",
            "runIds": ["run-memory"],
        }
        memory_file.write_text(memory_file.read_text() + json.dumps(old_entry) + "\n")
        pruned = run([
            str(cli),
            "attempt-memory",
            "list",
            "--project-root",
            str(repo),
            "--run-id",
            "run-memory",
            "--max-age-days",
            "7",
            "--now",
            "2026-07-09T00:00:00Z",
            "--json",
        ], cwd=repo)
        pruned_data = json.loads(pruned.stdout)
        if pruned_data["activeCount"] != 1:
            raise AssertionError(f"attempt memory should prune old entries by age: {pruned_data}")
        assert_not_contains(memory_file.read_text(), "old-entry", "attempt memory age pruning should rewrite scratchpad")

        expired = run([
            str(cli),
            "analytics",
            "closeout",
            "--project-root",
            str(repo),
            "--run-id",
            "run-memory",
            "--attempt-memory-path",
            str(memory_file),
            "--expire-attempt-memory",
            "--json",
        ], cwd=repo)
        expired_data = json.loads(expired.stdout)
        if expired_data["attemptMemoryExpired"] != 1:
            raise AssertionError(f"closeout should expire run-scoped attempt memory when requested: {expired_data}")
        if memory_file.read_text().strip():
            raise AssertionError("closeout should remove run-scoped scratchpad entries")

        events = (repo / ".gauntlet" / "analytics" / "events.ndjson").read_text()
        assert_contains(events, "attempt_memory_written", "attempt memory write analytics")
        assert_contains(events, "attempt_memory_read", "attempt memory read analytics")
        assert_not_contains(events, "private/path/test_secret.py", "attempt memory analytics should not store raw fingerprints")


def test_thread_changelog_captures_pr_history_and_followups():
    changelog = read(ROOT / "docs" / "gauntlet-runs" / "2026-07-04-thread-changelog.md")
    for marker in [
        "#5",
        "#6",
        "scripts/gauntlet.py",
        "docs/workflow-etiquette.md",
        "docs/gauntlet-runs/2026-07-04-claude-install-target.md",
        "docs/gauntlet-runs/2026-07-04-archive-execution-cli.md",
        "Follow-up captured:",
        "GitHub discipline and strategy",
        "House voice workflow",
        "Remaining Gauntlet CLI speedups",
    ]:
        assert_contains(changelog, marker, "thread changelog")


def test_workflow_etiquette_is_in_global_workflow():
    agents = read(AGENTS_MD)
    etiquette = read(ROOT / "docs" / "workflow-etiquette.md")
    combined = "\n".join([agents, etiquette])

    for marker in [
        "Workflow Etiquette",
        "Execution Mode: review | autonomous",
        "Decision Gate",
        "Archival Etiquette",
        "scripts/check-workflow-etiquette.py",
        "scripts/gauntlet.py",
        "confirm-git-risk",
        "After selecting a kickoff label, call `set_thread_title` immediately",
        "If the user supplies an alternate priority/title, call `set_thread_title` with the user's version",
        "set_thread_title",
        "set_thread_archived",
        "Archive Summary",
        "Pass the PR changelog or closeout content to `scripts/gauntlet.py archive plan --content`",
        "the final response includes files changed, proof/tests completed, and unresolved risks",
    ]:
        assert_contains(combined, marker, "workflow etiquette global guidance")


def test_promotion_scanner_is_release_wrapup_not_patch_gate():
    agents = read(AGENTS_MD)
    readme = read(README_MD)
    promotion_doc = read(ROOT / "docs" / "promotion-scanner.md")
    promotion_skill = read(SKILLS / "promotion-scanner" / "SKILL.md")
    coverage = read(ROOT / "docs" / "coverage-gaps.md")
    evals = json.loads(read(ROOT / "evals" / "skill-evals.json"))
    combined = "\n".join([agents, readme, promotion_doc, promotion_skill, coverage])

    for marker in [
        "promotion-scanner",
        "Promotion Brief",
        "Release or live-ops wrap-up",
        "repeated manual verification",
        "stale vs latest evidence",
        "repo code",
        "repo test",
        "Gauntlet skill/tool",
        "coverage gap",
        "Reject",
        "No live operational actions",
        "Do not infer",
        "secrets/redaction",
        "Do not run for ordinary Patch",
        "GAP-###",
        "Gauntlet-general missing guidance",
    ]:
        assert_contains(combined, marker, "promotion scanner guidance")

    if not any(case.get("id") == "promotion-scanner-contract" for case in evals.get("cases", [])):
        raise AssertionError("promotion-scanner eval case is missing")


def run_install(agent_home, target="codex"):
    env = os.environ.copy()
    env["AGENT_HOME"] = str(agent_home)
    env["GAUNTLET_SKIP_GIT_HOOKS"] = "1"
    result = subprocess.run(
        [str(SCRIPTS / "install.sh"), "--target", target],
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
    return result


def assert_installed_gauntlet_layout(agent_home):
    installed_check = agent_home / "gauntlet" / "scripts" / "check-gauntlet-workflow.py"
    if not installed_check.exists():
        raise AssertionError("installed workflow check is missing")
    installed_cli = agent_home / "gauntlet" / "scripts" / "gauntlet.py"
    if not installed_cli.exists() or not os.access(installed_cli, os.X_OK):
        raise AssertionError("installed Gauntlet CLI is missing or not executable")
    installed_agents = read(agent_home / "gauntlet" / "AGENTS.md")
    assert_contains(
        installed_agents,
        "$AGENT_HOME/gauntlet/docs/production-quality-bar.md",
        "installed AGENTS production quality bar path",
    )
    assert_contains(
        installed_agents,
        "$AGENT_HOME/gauntlet/docs/ui-constitution.md",
        "installed AGENTS frontend quality path",
    )
    for marker in [
        "no later than the third user-assistant exchange",
        "Research is never assigned `p4` merely because it is research",
        "Subagent packetization: required",
        "Scope delta checked: no material change.",
    ]:
        assert_contains(installed_agents, marker, "installed implementation-transition guidance")
    run([str(installed_check)])


def test_codex_install_layout_supports_workflow_check():
    if not (ROOT / ".git").exists():
        return

    with tempfile.TemporaryDirectory() as tmp:
        agent_home = Path(tmp) / "agent-home"
        agent_home.mkdir()
        personal_block = """<!-- BEGIN PERSONAL HOUSE VOICE -->
## Personal Test Voice

Keep this user-owned instruction across Gauntlet reinstalls.
<!-- END PERSONAL HOUSE VOICE -->"""
        (agent_home / "AGENTS.md").write_text(
            "# Global Agent Coding Workflow\n\n"
            f"{personal_block}\n\n"
            "Stale Gauntlet workflow content.\n"
        )
        run_install(agent_home, target="codex")
        assert_installed_gauntlet_layout(agent_home)
        installed_agents = read(agent_home / "AGENTS.md")
        assert_contains(installed_agents, "Global Agent Coding Workflow", "Codex AGENTS install")
        assert_contains(installed_agents, personal_block, "Codex personal house voice preservation")
        for marker in [
            "no later than the third user-assistant exchange",
            "Research is never assigned `p4` merely because it is research",
            "Subagent packetization: required",
            "Scope delta checked: no material change.",
        ]:
            assert_contains(installed_agents, marker, "Codex root implementation-transition guidance")
        if (agent_home / "CLAUDE.md").exists():
            raise AssertionError("Codex install should not create CLAUDE.md")

        run_install(agent_home, target="codex")
        reinstalled_agents = read(agent_home / "AGENTS.md")
        if reinstalled_agents.count("BEGIN PERSONAL HOUSE VOICE") != 1:
            raise AssertionError("Codex reinstall should preserve one personal house voice block")


def test_claude_install_layout_adapts_agents_without_overwriting_user_memory():
    if not (ROOT / ".git").exists():
        return

    with tempfile.TemporaryDirectory() as tmp:
        agent_home = Path(tmp) / "agent-home"
        agent_home.mkdir()
        claude_md = agent_home / "CLAUDE.md"
        claude_md.write_text("# My Existing Claude Memory\n\nKeep this personal note.\n")

        run_install(agent_home, target="claude")
        assert_installed_gauntlet_layout(agent_home)

        installed_claude = read(claude_md)
        assert_contains(installed_claude, "Keep this personal note.", "Claude user memory preservation")
        assert_contains(installed_claude, "BEGIN GAUNTLET MANAGED BLOCK", "Claude Gauntlet managed block")
        assert_contains(installed_claude, f"@{agent_home}/gauntlet/AGENTS.md", "Claude AGENTS import")
        assert_contains(installed_claude, "Gauntlet Adapter For Claude Code", "Claude adapter guidance")
        if (agent_home / "AGENTS.md").exists():
            raise AssertionError("Claude install should not write root AGENTS.md")

        run_install(agent_home, target="claude")
        reinstalled_claude = read(claude_md)
        if reinstalled_claude.count("BEGIN GAUNTLET MANAGED BLOCK") != 1:
            raise AssertionError("Claude reinstall should replace, not duplicate, the managed block")


def test_install_docs_explain_codex_and_claude_targets():
    readme = read(README_MD)
    for marker in [
        "./scripts/install.sh --target codex",
        "./scripts/install.sh --target claude",
        "GAUNTLET_INSTALL_TARGET=claude",
        "Claude Code",
        "CLAUDE.md",
        "scripts/gauntlet.py",
        "managed import block",
        "does not overwrite unrelated existing Claude instructions",
    ]:
        assert_contains(readme, marker, "install target docs")


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

    targeted = ROOT / "evals" / "results" / "workflow-check-planner-only.json"
    run([str(runner), "--only-skill", "planner", "--results", str(targeted)])
    targeted_data = json.loads(targeted.read_text())
    targeted_cases = targeted_data.get("cases", [])
    if not targeted_cases or any(case["skill"] != "planner" for case in targeted_cases):
        raise AssertionError("skill evals must support targeted --only-skill filtering")


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
    for marker in ["Gauntlet skill changes detected", "targeted skill evals: planner", "skill evals:", "skill linter"]:
        assert_contains(result.stdout, marker, "skill change checks")


def main():
    tests = [
        test_simplified_modes_and_depth_are_documented,
        test_v201_run_log_contract_replaces_default_review_brief,
        test_coverage_gap_and_design_lint_guidance_are_documented,
        test_product_thinking_and_scope_routing_are_documented,
        test_production_quality_bar_is_launch_gated,
        test_subagent_parallelism_is_context_efficient,
        test_kickoff_and_implementation_transition_gates_are_documented,
        test_subagent_plan_validator_logs_rejections,
        test_subagent_plan_validator_rejects_secret_and_overbroad_scope,
        test_subagent_plan_validator_requires_complete_lane_packets,
        test_guarded_panel_contract_is_uniform,
        test_ts_durability_classifier_behavior,
        test_diff_intel_test_plan_and_review_pack_are_bounded,
        test_docs_only_diff_gets_no_runtime_test_commands,
        test_workflow_helpers_filter_artifacts_and_find_python_tests,
        test_workflow_speedup_helpers_are_documented_as_advisory,
        test_workflow_etiquette_checker_validates_titles_kickoff_and_auto_assumptions,
        test_workflow_etiquette_checker_pauses_archive_on_followups_and_git_state,
        test_workflow_etiquette_checker_builds_archive_action_plan,
        test_gauntlet_cli_archive_plans_and_executes_github_merge,
        test_gauntlet_cli_archive_keeps_archive_anyway_from_overriding_git_risk,
        test_gauntlet_cli_small_helper_commands,
        test_gauntlet_cli_changelog_memory_and_followup_helpers,
        test_gauntlet_cli_local_analytics_and_closeout_facts,
        test_gauntlet_cli_bounded_attempt_memory,
        test_thread_changelog_captures_pr_history_and_followups,
        test_workflow_etiquette_is_in_global_workflow,
        test_promotion_scanner_is_release_wrapup_not_patch_gate,
        test_skill_evals_compare_all_arms,
        test_skill_evals_include_behavior_and_metrics,
        test_skill_linter_examples_and_na_defaults,
        test_skill_changes_are_guarded_by_pre_commit,
        test_codex_install_layout_supports_workflow_check,
        test_claude_install_layout_adapts_agents_without_overwriting_user_memory,
        test_install_docs_explain_codex_and_claude_targets,
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
