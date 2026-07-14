#!/usr/bin/env python3
import hashlib
import importlib.util
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
ROUTER_MD = ROOT / "router" / "AGENTS.md" if (ROOT / "router" / "AGENTS.md").exists() else AGENTS_MD
README_MD = ROOT / "README.md" if (ROOT / "README.md").exists() else ROOT.parent / "README.md"
RESPONSE_STYLE_MD = ROOT / "router" / "response-style.md"
GLOBAL_RESPONSE_STYLE = RESPONSE_STYLE_MD.read_text().strip()


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


def test_plugin_manifests_bundle_shared_skills():
    if not (ROOT / ".codex-plugin" / "plugin.json").is_file():
        return
    codex_manifest = json.loads(read(ROOT / ".codex-plugin" / "plugin.json"))
    claude_manifest = json.loads(read(ROOT / ".claude-plugin" / "plugin.json"))
    if codex_manifest["name"] != "gauntlet" or claude_manifest["name"] != "gauntlet":
        raise AssertionError("Codex and Claude plugin manifests must share the Gauntlet identity")
    if codex_manifest["version"] != claude_manifest["version"]:
        raise AssertionError("Codex and Claude plugin versions must stay aligned")
    if codex_manifest.get("skills") != "./skills/" or claude_manifest.get("skills") != "./skills/":
        raise AssertionError("both plugin manifests must bundle the shared skills directory")

    for path in sorted(SKILLS.glob("*/SKILL.md")):
        text = read(path)
        assert_contains(text, f"name: {path.parent.name}", f"skill name for {path.parent.name}")

    codex_marketplace = json.loads(read(ROOT / ".agents" / "plugins" / "marketplace.json"))
    claude_marketplace = json.loads(read(ROOT / ".claude-plugin" / "marketplace.json"))
    if codex_marketplace["plugins"][0]["name"] != "gauntlet":
        raise AssertionError("Codex marketplace must expose the Gauntlet plugin")
    if claude_marketplace["plugins"][0]["name"] != "gauntlet":
        raise AssertionError("Claude marketplace must expose the Gauntlet plugin")


def test_craft_product_terminology_contract():
    skill = read(SKILLS / "craft-product-terminology" / "SKILL.md")
    router = read(ROUTER_MD)

    for marker in [
        "smallest terminology system",
        "actual authority",
        "minimum-question rule",
        "company-specific branding",
        "Never promote unverified wording",
        "Candidate table",
        "concrete rejections",
    ]:
        assert_contains(skill, marker, "craft product terminology contract")

    assert_contains(
        router,
        "invoke `craft-product-terminology`",
        "craft product terminology routing",
    )


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
    router = read(ROUTER_MD)
    readme = read(README_MD)
    planner = read(SKILLS / "planner" / "SKILL.md")
    combined = "\n".join([agents, router, readme, planner])

    for label in ["Research", "Patch", "Feature", "Release"]:
        assert_contains(combined, label, "work path docs")
    for marker in [
        "Path: Research | Patch | Feature | Release",
        "Depth: Standard | Deep",
        "Proof scope: smoke | delta | full | not relevant",
        "Triggered Gates",
        "architecture hygiene",
        "TypeScript",
    ]:
        assert_contains(combined, marker, "simplified mode model")

    if len(router.encode("utf-8")) >= 32768:
        raise AssertionError("portable router must stay below the default 32 KiB instruction budget")
    if ROUTER_MD != AGENTS_MD and router == agents:
        raise AssertionError("portable router and repository contributor guide must be decoupled")

    for stale in ["### Deep Patch", "### Slice", "Deep Patch |", "| Deep Patch", "Slice |"]:
        assert_not_contains(combined, stale, "simplified mode model")


def test_normal_requests_use_minimum_scope_before_lifecycle_routing():
    agents = read(AGENTS_MD)
    router = read(ROUTER_MD)
    etiquette = read(ROOT / "docs" / "workflow-etiquette.md")
    rule_map = read(ROOT / "docs" / "global-router-rule-map.md")
    combined = "\n".join([agents, router, etiquette, rule_map])

    for marker in [
        "Normal Requests: Minimum Scope",
        "Before choosing a Gauntlet work path",
        "bounded, low-consequence, readily reversible, and directly checkable",
        "direct presentation or formatting changes",
        "copying existing results into an existing UI",
        "simple lookups",
        "routine administration",
        "Use minimum-scope execution. Deliver the requested artifact first.",
        "Ask before materially expanding scope.",
        "not to redesign a schema, methodology, or workflow",
        "does not require re-validating the underlying data",
        "Keep the work in the main task",
        "Stop when the requested artifact is delivered",
        "Explicit narrow user scope controls execution",
        "route only the affected part",
    ]:
        assert_contains(combined, marker, "normal-request minimum-scope routing")

    assert_contains(etiquette, "Normal Requests stay in the main task.", "normal-request delegation boundary")
    assert_contains(rule_map, "bypasses lifecycle ceremony", "normal-request router invariant")


def test_v201_run_log_contract_replaces_default_review_brief():
    agents = read(AGENTS_MD)
    router = read(ROUTER_MD)
    readme = read(README_MD)
    run_log = read(SKILLS / "run-log-builder" / "SKILL.md")
    combined = "\n".join([agents, router, readme, run_log])

    for marker in [
        "v2.0.1",
        "Run Log",
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
        "Remove a `GAP-###` entry from this file",
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
    router = read(ROUTER_MD)
    readme = read(README_MD)
    black_box = read(SKILLS / "black-box-tester" / "SKILL.md")
    experience = read(SKILLS / "experience-reviewer" / "SKILL.md")
    combined = "\n".join([agents, router, readme, black_box, experience])

    for marker in [
        "v2.0.2",
        "product-thinking harness for AI coding agents",
        "thought-through features",
        "coherent product features",
        "Token efficiency",
    ]:
        assert_contains(readme, marker, "product-thinking positioning")

    for marker in [
        "Proof scope: smoke | delta | full | not relevant",
        "Run gates only when their trigger applies",
        "bounded architecture hygiene",
        "Substantial frontend work",
        "Near-launch, private-beta, production-bound, hardened, or audited work",
        "Meaningful skill or workflow changes",
    ]:
        assert_contains(combined, marker, "scope routing")


def test_production_quality_bar_is_launch_gated():
    agents = read(AGENTS_MD)
    router = read(ROUTER_MD)
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
        router,
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
        if name != "planner":
            assert_contains(text, "Not relevant because", name)

def test_subagent_parallelism_is_context_efficient():
    agents = read(AGENTS_MD)
    router = read(ROUTER_MD)
    planner = read(SKILLS / "planner" / "SKILL.md")
    product = read(SKILLS / "product-architect" / "SKILL.md")
    implementer = read(SKILLS / "implementer" / "SKILL.md")
    combined = "\n".join([agents, router, planner, implementer])

    for marker in [
        "Parallelism must beat its context cost",
        "Delegate only independent files, state, contracts, or evidence lanes",
        "spawn subagents automatically without waiting for the user to request delegation",
        "Standing authorization",
        "bounded ticket",
        "Native Codex state",
        "main-task messages",
    ]:
        assert_contains(combined, marker, "subagent context-efficiency guard")

    assert_contains(
        planner,
        "Use end-to-end steps unless files, state, and proof are independent enough to split.",
        "planner firm end-to-end rule",
    )
    assert_contains(
        product,
        "Include onboarding, activation, retention, or growth only when accepted scope or a real next action makes them relevant.",
        "product-architect firm scope rule",
    )


def test_direct_dispatch_and_quiet_execution_are_documented():
    agents = read(AGENTS_MD)
    router = read(ROUTER_MD)
    etiquette = read(ROOT / "docs" / "workflow-etiquette.md")
    planner = read(SKILLS / "planner" / "SKILL.md")
    implementer = read(SKILLS / "implementer" / "SKILL.md")
    combined = "\n".join([agents, router, etiquette, planner, implementer])

    for marker in [
        "Quiet Execution",
        "compact receipt",
        "bounded ticket",
        "objective",
        "ownership",
        "dependencies",
        "constraints",
        "proof",
        "return contract",
        "ask-parent policy",
    ]:
        assert_contains(combined, marker, "direct dispatch guidance")

    for marker in [
        "one bounded Gauntlet Ticket",
        "Native Codex state",
        "Resolve material added-scope deltas",
    ]:
        assert_contains(implementer, marker, "implementer direct dispatch contract")


def test_workflow_guidance_keeps_routine_controls_silent():
    agents = read(AGENTS_MD)
    etiquette = read(ROOT / "docs" / "workflow-etiquette.md")
    planner = read(SKILLS / "planner" / "SKILL.md")
    implementer = read(SKILLS / "implementer" / "SKILL.md")
    combined = "\n".join([agents, etiquette, planner, implementer])

    for marker in [
        "Keep routine reads, searches, formatting, command setup, generated tickets, and unchanged polls in tools or artifacts",
        "Classify path, depth, verification, execution posture, and priority internally",
        "All applicable workflow etiquette remains active during quiet execution",
        "Native Codex state owns child progress; do not require title or status churn",
        "Surface:",
        "changed judgment, scope, risk, or verification",
    ]:
        assert_contains(combined, marker, "quiet workflow contract")

    for obsolete in [
        "Title child chats with the normal priority prefix plus lane/status tags",
        "Subagent packetization: not relevant because",
    ]:
        assert_not_contains(combined, obsolete, "quiet workflow contract")


def test_skill_quality_bar_is_trigger_bounded():
    agents = read(AGENTS_MD)
    router = read(ROUTER_MD)
    readme = read(README_MD)
    quality_bar = read(ROOT / "docs" / "skill-quality-bar.md")
    coverage = read(ROOT / "docs" / "coverage-gaps.md")
    plan = read(ROOT / "docs" / "skill-quality-implementation-plan.md")
    combined = "\n".join([agents, router, readme, quality_bar, coverage, plan])

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
        assert_contains(combined, marker, "skill quality bar trigger bounds")

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


def test_guarded_panel_contract_is_uniform():
    files = {
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

        accepted_spec = project / "docs" / "accepted-spec.md"
        accepted_spec.write_text(
            "\n".join([
                "# Accepted Spec",
                "",
                "## Goal",
                "",
                "Build a safer session path.",
            ]),
            encoding="utf-8",
        )
        canonical_plan = project / "docs" / "canonical-plan.md"
        canonical_plan.write_text("# Canonical Plan\n\n- Search: `rg session-token src/auth`\n", encoding="utf-8")

        run([
            str(review_pack),
            str(project),
            "--diff-intel",
            str(intel_path),
            "--accepted-spec",
            "docs/accepted-spec.md",
            "--plan",
            "docs/canonical-plan.md",
        ])
        packet = (project / ".gauntlet" / "review-pack.md").read_text()
        for marker in [
            "Changed Files",
            "Risk Triggers",
            "src/auth/session.ts",
            "Test Plan Summary",
            "npm run typecheck",
            "Accepted Spec",
            "docs/accepted-spec.md",
            "Canonical Plan",
            "docs/canonical-plan.md",
            "rg session-token src/auth",
            "Expected Return Format",
            "Cannot verify",
        ]:
            assert_contains(packet, marker, "review packet")
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
        assert_contains("\n".join(plan["cannotVerify"]), "No runtime-code test inferred", "docs-only cannot verify note")


def test_instruction_surfaces_are_not_classified_as_docs_only():
    diff_intel = SCRIPTS / "diff-intel.py"
    test_plan = SCRIPTS / "test-plan.py"

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        init_repo(project)
        for directory in ["router", "skills/demo/examples", "prompts", "templates", "src/prompts", "packages/app/templates", "config", "docs", ".codex-plugin", "scripts"]:
            (project / directory).mkdir(parents=True, exist_ok=True)
        instruction_paths = [
            "AGENTS.md",
            "router/AGENTS.md",
            "router/response-style.md",
            "skills/demo/SKILL.md",
            "skills/demo/examples/report.md",
            "prompts/system.md",
            "templates/agent.md",
            "src/prompts/system.txt",
            "packages/app/templates/system.md",
            "config/settings.toml",
            "config/assistant.yaml",
            "docs/meaningful-proof.md",
            ".codex-plugin/plugin.json",
        ]
        for path in instruction_paths:
            (project / path).write_text("plain setting\n")
        (project / "scripts" / "run-skill-change-checks.sh").write_text("#!/bin/sh\n")
        (project / "scripts" / "check-gauntlet-workflow.py").write_text("pass\n")
        commit_all(project, "baseline")
        (project / "config" / "settings.toml").write_text('system_prompt = "Steer the agent"\n')
        (project / "config" / "assistant.yaml").write_text('prompt: "Steer the agent"\n')

        run([str(diff_intel), str(project), "--changed-files", *instruction_paths])
        intel_path = project / ".gauntlet" / "diff-intel.json"
        intel = json.loads(intel_path.read_text())
        if "instruction-surface" not in intel["riskTriggers"] or "docs-only" in intel["riskTriggers"]:
            raise AssertionError(f"instruction surfaces must not be docs-only: {intel['riskTriggers']}")
        for item in intel["changedFiles"]:
            if "instruction" not in item["flags"]:
                raise AssertionError(f"instruction flag missing for {item['path']}: {item['flags']}")

        run([str(test_plan), str(project), "--diff-intel", str(intel_path)])
        plan = json.loads((project / ".gauntlet" / "test-plan.json").read_text())
        commands = [item["command"] for item in plan["commands"]]
        expected = [
            "scripts/run-skill-change-checks.sh --changed-files skills/demo/SKILL.md",
            "python3 scripts/check-gauntlet-workflow.py",
        ]
        for command in expected:
            if command not in commands:
                raise AssertionError(f"instruction-surface plan missing {command}: {commands}")


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
    planner = read(SKILLS / "planner" / "SKILL.md")
    combined = "\n".join([agents, readme, speedups])

    for marker in [
        "diff-intel.py",
        "test-plan.py",
        "review-pack.py",
        "gauntlet.py changelog pr",
        "gauntlet.py followup thread",
        "accepted spec and canonical plan remain the sources",
        "create_thread",
        "advisory",
        "confidence",
        "Cannot verify",
        "quality-check --surface",
        "deferred",
        "dirty worktree",
    ]:
        assert_contains(combined, marker, "workflow speedup guidance")

    for marker in [
        "reports `Needs decision` to the main task instead of asking the user",
        "Native Codex state owns child progress; do not require title or status churn",
        "archives a child task after its report is integrated",
        "returns a compact Role Report",
    ]:
        assert_contains(read(ROOT / "docs" / "workflow-etiquette.md"), marker, "delegation etiquette child lane guidance")

    for marker in [
        "separate git worktrees by default",
        "Child chats return compact reports and archive after integration",
        "Native Codex state owns child progress",
    ]:
        assert_contains(speedups, marker, "workflow speedup child lane guidance")

    for marker in [
        "router/AGENTS.md",
        "one bounded ticket",
        "Native Codex state",
        "main-task messages",
    ]:
        assert_contains("\n".join([agents, read(ROUTER_MD), readme, planner]), marker, "workflow speedup routing")


def test_contextual_merge_contract_is_documented():
    agents = read(AGENTS_MD)
    etiquette = read(ROOT / "docs" / "workflow-etiquette.md")
    github = read(ROOT / "docs" / "github-discipline.md")
    combined = "\n".join([agents, etiquette, github])
    for marker in [
        '"Merge this," "land this," or "merge this to main" authorizes',
        "prepare the contextual handoff",
        "update `CHANGELOG.md`",
        "create or update one pull request",
        "wait for required checks",
        "verify the default branch",
        '"push to git" means push the current branch',
        "scripts/gauntlet.py merge prepare",
        "scripts/gauntlet.py merge plan",
        "scripts/gauntlet.py merge execute",
    ]:
        assert_contains(combined, marker, "contextual merge contract")
    for marker in [
        "gauntlet.py closeout execute",
        "explicit `--stage` paths",
        "remainingAppActions",
        "cannot archive the task by itself",
    ]:
        assert_contains("\n".join([agents, read(ROUTER_MD), github]), marker, "guarded closeout command guidance")


def test_response_style_guidance_is_single_global_policy():
    for marker in [
        "without reducing technical precision",
        "Start with the bottom line on top",
        "Preserve material evidence, constraints, tradeoffs, caveats, and uncertainty",
        "Do not rewrite code, identifiers, commands, quoted text, or prescribed formats",
        "logically categorized chunks",
        "practical, grounded examples",
    ]:
        assert_contains(GLOBAL_RESPONSE_STYLE, marker, "accepted response-style policy")
    assert_contains(read(ROUTER_MD), "{{RESPONSE_STYLE}}", "global response-style install placeholder")
    if (ROOT / ".git").exists():
        assert_not_contains(read(AGENTS_MD), GLOBAL_RESPONSE_STYLE, "contributor response-style duplication")
        assert_not_contains(
            read(AGENTS_MD),
            "Write user-facing explanations and prose artifacts in plain, concise language.",
            "legacy contributor response-style duplication",
        )


def test_version_changelog_preserves_release_history():
    marker = "move the shipped entries from `Unreleased` under a heading for that version and release date"
    assert_contains(read(AGENTS_MD), marker, "contributor version changelog guidance")
    assert_contains(read(ROUTER_MD), marker, "global version changelog guidance")
    assert_contains(read(ROOT / "docs" / "github-discipline.md"), marker, "detailed version changelog guidance")


def test_contextual_pr_template_changelog_and_run_log_contract():
    template_path = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
    if not template_path.exists():
        return
    template = read(template_path)
    required = ["## Problem", "## Solution", "## Changelog", "## Testing"]
    for marker in required:
        assert_contains(template, marker, "contextual PR template")
    positions = [template.index(item) for item in required]
    if positions != sorted(positions):
        raise AssertionError("contextual PR template sections are out of order")
    for obsolete in [
        "## Functional Changes",
        "## User Or Agent Impact",
        "## Workflow Or Behavior Changes",
        "## Release Proof (near-launch only)",
        "## PR Note",
    ]:
        assert_not_contains(template, obsolete, "contextual PR template")

    changelog = read(ROOT / "CHANGELOG.md")
    entry = "- Gauntlet now keeps routine workflow controls out of the conversation and automatically creates contextual PR and changelog handoffs when merging work."
    if changelog.count(entry) != 1:
        raise AssertionError("CHANGELOG must contain the exact contextual merge entry once")

    run_log = read(ROOT / "docs" / "gauntlet-runs" / "2026-07-09-quiet-workflow-guaranteed-merge.md")
    for marker in [
        "nine attempts across seven unique validator runs",
        "148 tokens",
        "+7.7%",
        "866 repeated exact-sentence tokens",
        "2,143 instruction tokens",
        "total billed or cached child context was unavailable",
    ]:
        assert_contains(run_log, marker, "quiet workflow run log")
    assert_not_contains(run_log, "All tests passed", "exceptions-only run log")


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
                "Suggested thread label: p2-auto: fix deterministic archive closeout",
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
            "p2-auto: fix deterministic archive closeout",
            "--content",
            str(content),
            "--require-kickoff",
            "--json",
        ])
        data = json.loads(result.stdout)
        if data["status"] != "warn":
            raise AssertionError(f"legacy five-field kickoff should warn without blocking: {data}")
        if not any(finding["code"] == "kickoff_check_deprecated" for finding in data["findings"]):
            raise AssertionError(f"legacy kickoff warning missing: {data}")
        if data["parsedTitle"]["executionMode"] != "autonomous":
            raise AssertionError("auto title should parse as autonomous")
        if data["effectiveExecutionMode"] != "autonomous":
            raise AssertionError("auto kickoff should report effective execution mode")

        quiet = Path(tmp) / "quiet.md"
        quiet.write_text("Implementation can proceed without a user decision.\n")
        quiet_result = run([
            str(checker),
            "--title",
            "p2-auto: fix deterministic archive closeout",
            "--content",
            str(quiet),
            "--require-kickoff",
            "--json",
        ])
        quiet_data = json.loads(quiet_result.stdout)
        if quiet_data["status"] != "warn":
            raise AssertionError(f"deprecated require-kickoff mode should warn without blocking: {quiet_data}")

        legacy = run([str(checker), "--title", "p2 - fix archive closeout", "--json"], check=False)
        legacy_data = json.loads(legacy.stdout)
        if legacy.returncode != 1 or legacy_data["status"] != "fail":
            raise AssertionError(f"legacy title should fail: {legacy_data}")
        if not any(finding["code"] == "malformed_title" for finding in legacy_data["findings"]):
            raise AssertionError(f"legacy title failure missing: {legacy_data}")

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
                "Suggested thread label: p3: fix deterministic archive closeout",
                "",
            ])
        )
        legacy_review_result = run([
            str(checker),
            "--title",
            "p3: fix deterministic archive closeout",
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

        multiline = run([
            str(checker),
            "--title",
            "p2-auto:\nharden deterministic archive workflow",
            "--json",
        ], check=False)
        if multiline.returncode != 1:
            raise AssertionError(f"multiline title should fail: {multiline.stdout}")

        for invalid_title, actual_words in [
            ("p2-auto: fix archive closeout", 3),
            ("p2-auto: fix deterministic archive closeout flow", 5),
        ]:
            wrong_word_count = run(
                [str(checker), "--title", invalid_title, "--json"],
                check=False,
            )
            if wrong_word_count.returncode != 1:
                raise AssertionError(
                    f"{actual_words}-word title should fail with exit 1: {wrong_word_count.stdout}"
                )
            wrong_word_data = json.loads(wrong_word_count.stdout)
            finding = next(
                (
                    item
                    for item in wrong_word_data["findings"]
                    if item["code"] == "title_goal_word_count"
                ),
                None,
            )
            if not finding or finding.get("actualWordCount") != actual_words:
                raise AssertionError(
                    f"title word-count finding missing deterministic count: {wrong_word_data}"
                )

        exact_title = run(
            [str(checker), "--title", "p2-auto: harden deterministic archive workflow", "--json"]
        )
        if json.loads(exact_title.stdout)["status"] != "pass":
            raise AssertionError(f"four-word title should pass: {exact_title.stdout}")

        missing_auto = Path(tmp) / "missing-auto.md"
        missing_auto.write_text(
            "\n".join([
                "Mode: Patch",
                "Depth: Standard",
                "Verification Scope: smoke",
                "Execution Mode: autonomous",
                "Suggested thread label: p3-auto: fix deterministic archive closeout",
                "",
            ])
        )
        auto_result = run([
            str(checker),
            "--title",
            "p3-auto: fix deterministic archive closeout",
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

        wrong_word_suggestion = run([
            str(checker),
            "--title",
            "Indexed implementation context docs",
            "--suggested-title",
            "p1-auto: formalize etiquette checks",
            "--archive",
            "--json",
        ], check=False)
        wrong_word_suggestion_data = json.loads(wrong_word_suggestion.stdout)
        if wrong_word_suggestion.returncode != 1:
            raise AssertionError(
                f"three-word archive suggestion should fail: {wrong_word_suggestion.stdout}"
            )
        if wrong_word_suggestion_data.get("archivePlan", {}).get("actions"):
            raise AssertionError(
                f"invalid archive suggestion must emit no actions: {wrong_word_suggestion_data}"
            )

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
        if anyway_data.get("archivePlan", {}).get("actions"):
            raise AssertionError(f"low-level checker must not emit archive app actions: {anyway_data}")
        if not any(finding["code"] == "strong_followup_archived_anyway" for finding in anyway_data["findings"]):
            raise AssertionError(f"archive anyway warning missing: {anyway_data}")


def merge_handoff_fixture():
    return {
        "schemaVersion": "1.0",
        "title": "workflow: generate contextual merge handoffs",
        "problem": {
            "context": "Gauntlet's useful controls are exposed as conversation ceremony.",
            "impact": "The user has to read process narration and manually reconstruct merge context.",
        },
        "solution": {
            "outcome": "Keep material controls internal and make merge handoffs automatic.",
            "invariants": [
                "Child ownership and proof controls remain enforced.",
                "The PR changelog line exactly matches CHANGELOG.md.",
            ],
            "preserved": ["Quick local prototype development remains the default."],
            "nonGoals": ["No new child thread provenance machinery."],
        },
        "changelog": "Gauntlet now keeps routine workflow controls out of the conversation and automatically creates contextual PR and changelog handoffs when merging work.",
        "testing": [
            {
                "command": "python3 scripts/check-gauntlet-workflow.py",
                "result": "PASS",
                "proves": "Packet, conversation, handoff, and merge contracts pass together.",
            }
        ],
        "securityRisk": None,
    }


def test_gauntlet_cli_merge_prepare_renders_contextual_handoff():
    cli = SCRIPTS / "gauntlet.py"
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        init_repo(repo)
        git(["branch", "-M", "main"], cwd=repo)
        (repo / "README.md").write_text("# Repo\n")
        commit_all(repo, "baseline")
        handoff = merge_handoff_fixture()
        handoff_path = repo / ".gauntlet" / "merge-handoff.json"
        body_path = repo / ".gauntlet" / "pr-body.md"
        handoff_path.parent.mkdir(parents=True)
        handoff_path.write_text(json.dumps(handoff))

        first = run([
            str(cli),
            "merge",
            "prepare",
            "--git-root",
            str(repo),
            "--handoff",
            str(handoff_path),
            "--body-output",
            str(body_path),
            "--json",
        ], cwd=repo, check=False)
        if first.returncode != 0:
            raise AssertionError(f"merge prepare should pass:\n{first.stdout}\n{first.stderr}")
        first_data = json.loads(first.stdout)
        if first_data["status"] != "pass" or not first_data["changelogChanged"]:
            raise AssertionError(f"first prepare should create changelog: {first_data}")

        body = body_path.read_text()
        required = ["## Problem", "## Solution", "## Changelog", "## Testing"]
        if [body.index(item) for item in required] != sorted(body.index(item) for item in required):
            raise AssertionError(f"PR body sections are out of order:\n{body}")
        if "## Security / Risk" in body or "## PR Note" in body or "Files changed" in body:
            raise AssertionError(f"PR body contains empty risk or a file tour:\n{body}")
        bullet = f"- {handoff['changelog']}"
        if bullet not in body:
            raise AssertionError(f"PR body missing exact changelog bullet:\n{body}")
        changelog = (repo / "CHANGELOG.md").read_text()
        if changelog.count(bullet) != 1:
            raise AssertionError(f"CHANGELOG should contain one exact entry:\n{changelog}")

        second = run([
            str(cli),
            "merge",
            "prepare",
            "--git-root",
            str(repo),
            "--handoff",
            str(handoff_path),
            "--body-output",
            str(body_path),
            "--json",
        ], cwd=repo)
        second_data = json.loads(second.stdout)
        if second_data["changelogChanged"] or (repo / "CHANGELOG.md").read_text().count(bullet) != 1:
            raise AssertionError(f"merge prepare must be idempotent: {second_data}")

        handoff["securityRisk"] = "A failed merge leaves the branch intact for recovery."
        handoff_path.write_text(json.dumps(handoff))
        run([
            str(cli), "merge", "prepare", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--body-output", str(body_path), "--json",
        ], cwd=repo)
        if "## Security / Risk" not in body_path.read_text():
            raise AssertionError("material security/risk text should add the optional section")

        handoff["changelog"] = "invalid\nmultiline entry"
        handoff_path.write_text(json.dumps(handoff))
        invalid = run([
            str(cli), "merge", "prepare", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--body-output", str(body_path), "--json",
        ], cwd=repo, check=False)
        if invalid.returncode != 1:
            raise AssertionError(f"multiline changelog should fail: {invalid.stdout}")


def prepare_merge_fixture(cli, repo):
    (repo / ".gitignore").write_text("/.gauntlet/\n")
    handoff = merge_handoff_fixture()
    handoff_path = repo / ".gauntlet" / "merge-handoff.json"
    body_path = repo / ".gauntlet" / "pr-body.md"
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(json.dumps(handoff))
    prepared = run([
        str(cli), "merge", "prepare", "--git-root", str(repo),
        "--handoff", str(handoff_path), "--body-output", str(body_path), "--json",
    ], cwd=repo)
    if json.loads(prepared.stdout)["status"] != "pass":
        raise AssertionError(f"merge fixture preparation failed: {prepared.stdout}")
    return handoff_path, body_path


def write_merge_fake_gh(path, log_path, state_path, check_conclusion="SUCCESS", empty_checks_once=False):
    path.write_text(
        "\n".join([
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "printf '%s\\n' \"$*\" >> \"$GH_LOG\"",
            "if [ \"$1\" = \"repo\" ] && [ \"$2\" = \"view\" ]; then",
            "  printf '%s\\n' '{\"defaultBranchRef\":{\"name\":\"main\"},\"mergeCommitAllowed\":true,\"squashMergeAllowed\":true,\"rebaseMergeAllowed\":true}'",
            "  exit 0",
            "fi",
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"view\" ]; then",
            "  if [ ! -f \"$GH_STATE\" ]; then exit 1; fi",
            "  if [ \"${GH_EMPTY_CHECKS_ONCE:-0}\" = \"1\" ] && [ ! -f \"${GH_STATE}.empty-served\" ]; then",
            "    touch \"${GH_STATE}.empty-served\"",
            "    printf '%s\\n' '{\"number\":7,\"state\":\"OPEN\",\"isDraft\":false,\"mergeable\":\"MERGEABLE\",\"mergedAt\":null,\"statusCheckRollup\":[],\"url\":\"https://example.test/pr/7\",\"baseRefName\":\"main\",\"headRefName\":\"codex/merge-flow\",\"reviewDecision\":\"\"}'",
            "    exit 0",
            "  fi",
            "  touch \"${GH_STATE}.checks-ready\"",
            f"  printf '%s\\n' '{{\"number\":7,\"state\":\"OPEN\",\"isDraft\":false,\"mergeable\":\"MERGEABLE\",\"mergedAt\":null,\"statusCheckRollup\":[{{\"__typename\":\"CheckRun\",\"name\":\"gauntlet\",\"status\":\"COMPLETED\",\"conclusion\":\"{check_conclusion}\"}}],\"url\":\"https://example.test/pr/7\",\"baseRefName\":\"main\",\"headRefName\":\"codex/merge-flow\",\"reviewDecision\":\"\"}}'",
            "  exit 0",
            "fi",
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"create\" ]; then",
            "  touch \"$GH_STATE\"",
            "  printf '%s\\n' 'https://example.test/pr/7'",
            "  exit 0",
            "fi",
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"edit\" ]; then exit 0; fi",
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"checks\" ]; then",
            "  if [ \"${GH_EMPTY_CHECKS_ONCE:-0}\" = \"1\" ] && [ ! -f \"${GH_STATE}.checks-ready\" ]; then",
            "    printf '%s\\n' 'no checks reported' >&2",
            "    exit 1",
            "  fi",
            "  exit 0",
            "fi",
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"merge\" ]; then",
            "  git push origin HEAD:main >/dev/null",
            "  exit 0",
            "fi",
            "exit 1",
        ]) + "\n"
    )
    path.chmod(0o755)
    return {
        "GAUNTLET_GH": str(path),
        "GH_LOG": str(log_path),
        "GH_STATE": str(state_path),
        "GH_EMPTY_CHECKS_ONCE": "1" if empty_checks_once else "0",
    }


def test_gauntlet_cli_merge_plan_requires_clean_task_branch():
    cli = SCRIPTS / "gauntlet.py"
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        init_repo(repo)
        git(["branch", "-M", "main"], cwd=repo)
        (repo / "README.md").write_text("# Repo\n")
        commit_all(repo, "baseline")
        handoff_path, body_path = prepare_merge_fixture(cli, repo)
        commit_all(repo, "changelog")

        on_main = run([
            str(cli), "merge", "plan", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--body", str(body_path), "--json",
        ], cwd=repo, check=False)
        if on_main.returncode != 1:
            raise AssertionError(f"merge plan on main should fail: {on_main.stdout}")
        if "task_branch_required" not in {item["code"] for item in json.loads(on_main.stdout)["findings"]}:
            raise AssertionError(f"main-branch blocker missing: {on_main.stdout}")

        git(["checkout", "-b", "codex/merge-flow"], cwd=repo)
        (repo / "feature.txt").write_text("feature\n")
        commit_all(repo, "feature")
        (repo / "dirty.txt").write_text("dirty\n")
        dirty = run([
            str(cli), "merge", "plan", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--body", str(body_path), "--json",
        ], cwd=repo, check=False)
        if dirty.returncode != 1:
            raise AssertionError(f"dirty merge plan should fail: {dirty.stdout}")
        if "uncommitted_merge_work" not in {item["code"] for item in json.loads(dirty.stdout)["findings"]}:
            raise AssertionError(f"dirty-work blocker missing: {dirty.stdout}")
        (repo / "dirty.txt").unlink()

        gh_log = Path(tmp) / "gh.log"
        state = Path(tmp) / "gh-state"
        fake_gh = Path(tmp) / "gh"
        env = write_merge_fake_gh(fake_gh, gh_log, state)
        plan_result = subprocess.run([
            str(cli), "merge", "plan", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--body", str(body_path), "--json",
        ], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, **env})
        if plan_result.returncode != 0:
            raise AssertionError(f"clean merge plan should pass:\n{plan_result.stdout}\n{plan_result.stderr}")
        data = json.loads(plan_result.stdout)
        action_types = [action["type"] for action in data["mergePlan"]["actions"]]
        expected = ["git_push", "gh_pr_create", "gh_pr_checks_watch", "gh_pr_merge", "delete_remote_branch", "verify_default_branch"]
        if action_types != expected:
            raise AssertionError(f"new-PR merge action order mismatch: {action_types}")

        state.touch()
        existing_result = subprocess.run([
            str(cli), "merge", "plan", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--body", str(body_path), "--json",
        ], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, **env})
        existing_actions = [action["type"] for action in json.loads(existing_result.stdout)["mergePlan"]["actions"]]
        expected_existing = ["git_push", "gh_pr_edit", "gh_pr_checks_watch", "gh_pr_merge", "delete_remote_branch", "verify_default_branch"]
        if existing_result.returncode != 0 or existing_actions != expected_existing:
            raise AssertionError(f"existing PR should be updated, not duplicated: {existing_result.stdout}")

        original_body = body_path.read_text()
        body_path.write_text("## Changelog\n\n- wrong entry\n")
        mismatch = subprocess.run([
            str(cli), "merge", "plan", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--body", str(body_path), "--json",
        ], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, **env})
        if mismatch.returncode != 1 or "pr_body_out_of_date" not in {item["code"] for item in json.loads(mismatch.stdout)["findings"]}:
            raise AssertionError(f"stale PR body should block merge: {mismatch.stdout}")

        body_path.write_text(original_body)
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n- wrong entry\n")
        changelog_mismatch = subprocess.run([
            str(cli), "merge", "plan", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--body", str(body_path), "--json",
        ], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, **env})
        if changelog_mismatch.returncode != 1 or "changelog_mismatch" not in {item["code"] for item in json.loads(changelog_mismatch.stdout)["findings"]}:
            raise AssertionError(f"mismatched changelog should block merge: {changelog_mismatch.stdout}")

        failing_gh = Path(tmp) / "gh-failing"
        failing_log = Path(tmp) / "gh-failing.log"
        failing_env = write_merge_fake_gh(failing_gh, failing_log, state, check_conclusion="FAILURE")
        (repo / "CHANGELOG.md").write_text(f"# Changelog\n\n## Unreleased\n\n- {merge_handoff_fixture()['changelog']}\n")
        git(["add", "CHANGELOG.md"], cwd=repo)
        git(["commit", "--amend", "--no-edit"], cwd=repo)
        failing = subprocess.run([
            str(cli), "merge", "plan", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--body", str(body_path), "--json",
        ], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, **failing_env})
        if failing.returncode != 2 or "pull_request_checks_failing" not in {item["code"] for item in json.loads(failing.stdout)["findings"]}:
            raise AssertionError(f"failing PR checks should block merge: {failing.stdout}")


def test_gauntlet_cli_merge_execute_creates_pr_waits_and_verifies_main():
    cli = SCRIPTS / "gauntlet.py"
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        remote = Path(tmp) / "remote.git"
        init_repo(repo)
        git(["branch", "-M", "main"], cwd=repo)
        (repo / "README.md").write_text("# Repo\n")
        (repo / ".gitignore").write_text("/.gauntlet/\n")
        commit_all(repo, "baseline")
        git(["init", "--bare", str(remote)], cwd=tmp)
        git(["remote", "add", "origin", str(remote)], cwd=repo)
        git(["push", "-u", "origin", "main"], cwd=repo)
        git(["checkout", "-b", "codex/merge-flow"], cwd=repo)
        feature_path = repo / "skills" / "archive" / "SKILL.md"
        feature_path.parent.mkdir(parents=True)
        feature_path.write_text("# Archive\n")
        handoff_path, body_path = prepare_merge_fixture(cli, repo)
        commit_all(repo, "feature with changelog")

        gh_log = Path(tmp) / "gh.log"
        state = Path(tmp) / "gh-state"
        fake_gh = Path(tmp) / "gh"
        env = write_merge_fake_gh(fake_gh, gh_log, state, empty_checks_once=True)

        result = subprocess.run([
            str(cli), "merge", "execute", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--body", str(body_path), "--json",
        ], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, **env})
        if result.returncode != 0:
            raise AssertionError(f"merge execute should pass:\n{result.stdout}\n{result.stderr}")
        data = json.loads(result.stdout)
        executed = [action["type"] for action in data["executedActions"]]
        expected = ["git_push", "gh_pr_create", "gh_pr_checks_watch", "gh_pr_merge", "delete_remote_branch", "verify_default_branch"]
        if executed != expected:
            raise AssertionError(f"executed merge order mismatch: {executed}")
        git(["fetch", "origin", "main"], cwd=repo)
        ancestor = git(["merge-base", "--is-ancestor", "HEAD", "origin/main"], cwd=repo)
        if ancestor.returncode != 0:
            raise AssertionError("merge execute did not verify the feature commit on origin/main")


def test_gauntlet_cli_closeout_execute_commits_merges_cleans_and_returns_archive_actions():
    cli = SCRIPTS / "gauntlet.py"
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
        git(["checkout", "-b", "codex/merge-flow"], cwd=repo)
        feature_path = repo / "skills" / "archive" / "SKILL.md"
        feature_path.parent.mkdir(parents=True)
        feature_path.write_text("# Archive\n")

        handoff_path = Path(tmp) / "handoff.json"
        handoff_path.write_text(json.dumps(merge_handoff_fixture()))
        archive_content = Path(tmp) / "archive.md"
        archive_content.write_text("## Archive Summary\n\n- Shipped one guarded closeout command.\n")

        gh_log = Path(tmp) / "gh.log"
        state = Path(tmp) / "gh-state"
        fake_gh = Path(tmp) / "gh"
        env = write_merge_fake_gh(fake_gh, gh_log, state, empty_checks_once=True)

        rejected = subprocess.run([
            str(cli), "closeout", "execute", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--stage", "skills/archive/SKILL.md",
            "--install-target", "none", "--title", "Unlabeled closeout task",
            "--content", str(archive_content), "--json",
        ], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, **env})
        if rejected.returncode != 1 or "invalid_archive_title" not in {item["code"] for item in json.loads(rejected.stdout)["findings"]}:
            raise AssertionError(f"invalid archive input should fail before closeout: {rejected.stdout}")
        if git(["log", "-1", "--pretty=%s"], cwd=repo).stdout.strip() != "baseline":
            raise AssertionError("archive preflight failure must happen before the closeout commit")

        (repo / "unrelated.txt").write_text("preserve me\n")
        unscoped = subprocess.run([
            str(cli), "closeout", "execute", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--stage", "skills/archive/SKILL.md",
            "--install-target", "none", "--title", "Unlabeled closeout task",
            "--suggested-title", "p2-auto: complete guarded release closeout",
            "--content", str(archive_content), "--json",
        ], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, **env})
        if unscoped.returncode != 1 or "unscoped_dirty_work" not in {item["code"] for item in json.loads(unscoped.stdout)["findings"]}:
            raise AssertionError(f"unlisted dirty work should block closeout: {unscoped.stdout}")
        (repo / "unrelated.txt").unlink()

        result = subprocess.run([
            str(cli), "closeout", "execute", "--git-root", str(repo),
            "--handoff", str(handoff_path), "--stage", "skills/archive/SKILL.md",
            "--install-target", "none", "--title", "Unlabeled closeout task",
            "--suggested-title", "p2-auto: complete guarded release closeout",
            "--content", str(archive_content), "--json",
        ], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, **env})
        if result.returncode != 0:
            raise AssertionError(f"closeout execute should pass:\n{result.stdout}\n{result.stderr}")
        data = json.loads(result.stdout)
        if data["status"] not in {"pass", "warn"}:
            raise AssertionError(f"closeout status should allow archive: {data}")
        if data.get("commit", {}).get("subject") != merge_handoff_fixture()["title"]:
            raise AssertionError(f"closeout should commit with the handoff title: {data}")
        merge_actions = [action["type"] for action in data.get("merge", {}).get("executedActions", [])]
        expected_merge = ["git_push", "gh_pr_create", "gh_pr_checks_watch", "gh_pr_merge", "delete_remote_branch", "verify_default_branch"]
        if merge_actions != expected_merge:
            raise AssertionError(f"closeout merge actions mismatch: {merge_actions}")
        current_branch = git(["branch", "--show-current"], cwd=repo).stdout.strip()
        worktree_status = git(["status", "--porcelain"], cwd=repo).stdout.strip()
        if current_branch != "main" or worktree_status:
            raise AssertionError("closeout should leave a clean local default branch")
        if run(["git", "show-ref", "--verify", "refs/heads/codex/merge-flow"], cwd=repo, check=False).returncode == 0:
            raise AssertionError("closeout should delete the merged local task branch")
        app_actions = [action["type"] for action in data.get("remainingAppActions", [])]
        if app_actions != ["set_thread_title", "present_archive_summary", "archive_thread"]:
            raise AssertionError(f"closeout should return ordered app actions: {app_actions}")
        log = gh_log.read_text()
        for marker in ["pr create", "pr checks 7 --watch", "pr merge 7 --merge"]:
            if marker not in log:
                raise AssertionError(f"missing GitHub action {marker}:\n{log}")
        if "--delete-branch" in log:
            raise AssertionError(f"GitHub CLI must not manipulate local worktrees during merge:\n{log}")
        if log.count("pr view") < 3:
            raise AssertionError(f"merge execute did not poll for delayed check registration:\n{log}")
        remote_branch = run(["git", "ls-remote", "--exit-code", "--heads", "origin", "codex/merge-flow"], cwd=repo, check=False)
        if remote_branch.returncode != 2:
            raise AssertionError(f"merge execute did not delete the remote task branch: {remote_branch.stdout}")


def test_remote_branch_cleanup_accepts_concurrent_auto_delete():
    module_path = SCRIPTS / "gauntlet.py"
    spec = importlib.util.spec_from_file_location("gauntlet_cli", module_path)
    gauntlet_cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gauntlet_cli)
    if not hasattr(gauntlet_cli, "delete_remote_branch"):
        raise AssertionError("merge helper is missing postcondition-based remote branch cleanup")

    results = iter([
        subprocess.CompletedProcess(["git", "ls-remote"], 0, "branch\n", ""),
        subprocess.CompletedProcess(["git", "push", "--delete"], 1, "", "remote ref disappeared"),
        subprocess.CompletedProcess(["git", "ls-remote"], 2, "", ""),
    ])

    def fake_git(_args, _repo):
        return next(results)

    result = gauntlet_cli.delete_remote_branch(Path("/test/repo"), "codex/merge-flow", git_runner=fake_git)
    if result.returncode != 0:
        raise AssertionError("remote cleanup should pass when the branch is absent after a concurrent auto-delete")


def test_closeout_forwards_install_conflict_choices_to_preflight_and_apply():
    module_path = SCRIPTS / "gauntlet.py"
    spec = importlib.util.spec_from_file_location("gauntlet_cli_install", module_path)
    gauntlet_cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gauntlet_cli)
    args = gauntlet_cli.argparse.Namespace(
        install_target="codex",
        instructions_reviewed=True,
        response_style="existing",
        codex_preferences="existing",
    )
    apply_command = gauntlet_cli.closeout_install_command(ROOT, args)
    preflight_command = gauntlet_cli.closeout_install_command(ROOT, args, check=True)
    for command in [apply_command, preflight_command]:
        for marker in ["--instructions-reviewed", "--response-style", "--codex-preferences", "existing"]:
            if marker not in command:
                raise AssertionError(f"closeout install command should forward {marker}: {command}")
    if "--check" in apply_command or "--check" not in preflight_command:
        raise AssertionError("closeout should add --check only to the pre-merge install preflight")


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
        archive_summary = Path(tmp) / "archive-summary.md"
        archive_summary.write_text(
            "## Archive Summary\n\n- Hardened deterministic archive execution.\n",
            encoding="utf-8",
        )

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
                "p2-auto: fix deterministic archive closeout",
                "--content",
                str(archive_summary),
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
            if action_types != ["gh_pr_merge", "present_archive_summary", "archive_thread"]:
                raise AssertionError(f"green PR should merge, present summary, then archive: {plan_data}")
            merge_action = plan_data["archivePlan"]["actions"][0]
            if merge_action.get("mergeMethod") != "merge" or merge_action.get("prNumber") != 7:
                raise AssertionError(f"merge action should use merge commit for PR 7: {plan_data}")

            execute = run([
                str(cli),
                "archive",
                "execute",
                "--title",
                "p2-auto: fix deterministic archive closeout",
                "--content",
                str(archive_summary),
                "--git-root",
                str(repo),
                "--allow-dirty",
                "allowed-dirty.txt",
                "--json",
            ], cwd=repo)
            execute_data = json.loads(execute.stdout)
            if execute_data["status"] != "warn":
                raise AssertionError(f"archive execute should pass with fake gh: {execute_data}")
            remaining_types = [
                action.get("type") for action in execute_data.get("remainingAppActions", [])
            ]
            if remaining_types != ["present_archive_summary", "archive_thread"]:
                raise AssertionError(f"execute should present summary before app archive: {execute_data}")
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
        archive_summary = Path(tmp) / "archive-summary.md"
        archive_summary.write_text(
            "## Archive Summary\n\n- Preserved archive safety under dirty worktree pressure.\n",
            encoding="utf-8",
        )

        missing_summary = run([
            str(cli),
            "archive",
            "plan",
            "--title",
            "p3: tidy deterministic archive flow",
            "--git-root",
            str(repo),
            "--confirm-git-risk",
            "--json",
        ], cwd=repo, check=False)
        missing_summary_data = json.loads(missing_summary.stdout)
        if missing_summary.returncode != 1 or missing_summary_data["archivePlan"].get("actions"):
            raise AssertionError(f"missing summary must block archive actions: {missing_summary_data}")
        if not any(
            finding["code"] == "missing_archive_summary_content"
            for finding in missing_summary_data["findings"]
        ):
            raise AssertionError(f"missing summary failure missing: {missing_summary_data}")

        missing_summary_text = run([
            str(cli),
            "archive",
            "plan",
            "--title",
            "p3: tidy deterministic archive flow",
            "--git-root",
            str(repo),
            "--confirm-git-risk",
        ], cwd=repo, check=False)
        assert_contains(
            missing_summary_text.stdout,
            "missing_archive_summary_content",
            "missing summary text output",
        )

        archive_anyway = run([
            str(cli),
            "archive",
            "plan",
            "--title",
            "p3: tidy deterministic archive flow",
            "--content",
            str(archive_summary),
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
            "p3: tidy deterministic archive flow",
            "--content",
            str(archive_summary),
            "--git-root",
            str(repo),
            "--confirm-git-risk",
            "--json",
        ], cwd=repo)
        confirmed_data = json.loads(confirmed.stdout)
        if confirmed_data["status"] != "warn":
            raise AssertionError(f"confirmed git risk should warn, not block: {confirmed_data}")
        if [action["type"] for action in confirmed_data["archivePlan"].get("actions", [])] != [
            "present_archive_summary",
            "archive_thread",
        ]:
            raise AssertionError(f"confirmed git risk should present summary then archive: {confirmed_data}")

        allowlisted = run([
            str(cli),
            "archive",
            "plan",
            "--title",
            "p3: tidy deterministic archive flow",
            "--content",
            str(archive_summary),
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
        if [action["type"] for action in allowlisted_data["archivePlan"].get("actions", [])] != [
            "present_archive_summary",
            "archive_thread",
        ]:
            raise AssertionError(f"allowlisted dirty file should present summary then archive: {allowlisted_data}")


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
                "--accepted-spec",
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
        if changelog_data.get("source") != str(memory) or changelog_data.get("sources") != [str(memory)]:
            raise AssertionError(f"changelog should preserve the legacy string source and add sources: {changelog_data}")
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
            "p2-auto: build deterministic changelog helpers",
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
        archive_action_types = [
            action["type"] for action in archive_data["archivePlan"]["actions"]
        ]
        if archive_action_types[-2:] != ["present_archive_summary", "archive_thread"]:
            raise AssertionError(f"archive summary must be presented before archive: {archive_data}")

        archive_text = run([
            str(cli),
            "archive",
            "plan",
            "--title",
            "p2-auto: build deterministic changelog helpers",
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
            "p2-auto: build deterministic changelog helpers",
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
        if unverified_data.get("source") != str(memory) or unverified_data.get("sources") != [str(memory)]:
            raise AssertionError(f"legacy changelog input should preserve the source string contract: {unverified_data}")
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
            "p2-auto: build deterministic followup shortcut",
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
        if actions[0].get("title") != "p2-auto: build deterministic followup shortcut":
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

        wrong_word_thread = run([
            str(cli),
            "followup",
            "thread",
            "--content",
            str(followup_content),
            "--title",
            "p2-auto: build followup shortcut",
            "--json",
        ], cwd=repo, check=False)
        wrong_word_thread_data = json.loads(wrong_word_thread.stdout)
        if wrong_word_thread.returncode != 1:
            raise AssertionError(
                f"three-word follow-up title should fail: {wrong_word_thread.stdout}"
            )
        if wrong_word_thread_data.get("actions"):
            raise AssertionError(
                f"invalid follow-up title must not emit actions: {wrong_word_thread_data}"
            )
        if not any(
            finding["code"] == "title_goal_word_count"
            for finding in wrong_word_thread_data["findings"]
        ):
            raise AssertionError(
                f"follow-up word-count finding missing: {wrong_word_thread_data}"
            )

        legacy_thread = run([
            str(cli),
            "followup",
            "thread",
            "--content",
            str(followup_content),
            "--title",
            "p2 - build deterministic followup shortcut",
            "--json",
        ], cwd=repo, check=False)
        legacy_thread_data = json.loads(legacy_thread.stdout)
        if legacy_thread.returncode != 1 or legacy_thread_data.get("actions"):
            raise AssertionError(
                f"legacy format must not create new thread actions: {legacy_thread_data}"
            )
        if not any(
            finding["code"] == "malformed_thread_title"
            for finding in legacy_thread_data["findings"]
        ):
            raise AssertionError(f"legacy thread finding missing: {legacy_thread_data}")

        no_followup = repo / "no-followup.md"
        no_followup.write_text("No follow-up block here.\n", encoding="utf-8")
        missing_followup = run([
            str(cli),
            "followup",
            "thread",
            "--content",
            str(no_followup),
            "--title",
            "p2-auto: build deterministic followup shortcut",
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
            "p2-auto: build deterministic followup shortcut",
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
            "p2-auto: build deterministic followup shortcut",
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
    router = read(ROUTER_MD)
    etiquette = read(ROOT / "docs" / "workflow-etiquette.md")
    combined = "\n".join([agents, router, etiquette])

    for marker in [
        "Quiet Execution",
        "Execution: review | autonomous",
        "Decision gate:",
        "## Archive",
        "scripts/check-workflow-etiquette.py",
        "{{GAUNTLET_ROOT}}/scripts/gauntlet.py",
        "confirm-git-risk",
        "Archive Summary",
        "compact machine receipts",
        "final outcome and proof",
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
        "explicit user request",
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
        "Do not run automatically for ordinary Patch",
        "GAP-###",
        "Gauntlet-general missing guidance",
    ]:
        assert_contains(combined, marker, "promotion scanner guidance")

    if not any(case.get("id") == "promotion-scanner-contract" for case in evals.get("cases", [])):
        raise AssertionError("promotion-scanner eval case is missing")


def run_install(agent_home, target="codex", extra_args=None, check=True):
    env = os.environ.copy()
    env["AGENT_HOME"] = str(agent_home)
    env["GAUNTLET_SKIP_GIT_HOOKS"] = "1"
    args = [str(SCRIPTS / "install.sh"), "--target", target]
    args.extend(extra_args or [])
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
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
    router_source = agent_home / "gauntlet" / "router" / "AGENTS.md"
    if not router_source.exists():
        raise AssertionError("installed portable router source is missing")
    assert_contains(read(router_source), "{{GAUNTLET_ROOT}}", "installed router source placeholder")
    assert_contains(read(router_source), "{{RESPONSE_STYLE}}", "installed response-style placeholder")
    if not (agent_home / "gauntlet" / "router" / "response-style.md").is_file():
        raise AssertionError("installed response-style source is missing")
    installed_agents = read(agent_home / "gauntlet" / "AGENTS.md")
    installed_root = str(agent_home / "gauntlet")
    installed_skills = str(agent_home / "skills")
    for marker in [
        "Gauntlet Workflow Router",
        GLOBAL_RESPONSE_STYLE,
        installed_root,
        installed_skills,
        f"{installed_root}/docs/production-quality-bar.md",
        f"{installed_root}/docs/ui-constitution.md",
        "bounded ticket",
        "Native Codex state",
        "a request to open a PR does not authorize merging it",
        f"{installed_root}/scripts/gauntlet.py merge prepare|plan|execute",
        "compact machine receipts",
    ]:
        assert_contains(installed_agents, marker, "installed router guidance")
    for unresolved in ["{{GAUNTLET_ROOT}}", "{{AGENT_HOME}}", "{{RESPONSE_STYLE}}"]:
        assert_not_contains(installed_agents, unresolved, "installed router path rendering")
    if len(installed_agents.encode("utf-8")) >= 32768:
        raise AssertionError("installed router exceeds the default 32 KiB instruction budget")
    for skill in [
        "craft-customer-email",
        "craft-product-terminology",
        "eval-audit",
        "eval-error-analysis",
        "eval-judge-prompt",
        "eval-rag",
        "eval-review-interface",
        "eval-synthetic-data",
        "eval-validate-evaluator",
    ]:
        if not (agent_home / "skills" / skill / "SKILL.md").is_file():
            raise AssertionError(f"installed Gauntlet skill is missing: {skill}")
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
        user_content = (
            "# My Global Instructions\n\n"
            f"{personal_block}\n\n"
            "Always preserve this unrelated company policy.\n"
        )
        (agent_home / "AGENTS.md").write_text(user_content)
        run_install(agent_home, target="codex", extra_args=["--instructions-reviewed"])
        assert_installed_gauntlet_layout(agent_home)
        config = read(agent_home / "config.toml")
        assert_contains(config, 'model_verbosity = "low"', "Codex low-verbosity default")
        assert_contains(config, 'personality = "none"', "Codex no-personality default")
        installed_agents = read(agent_home / "AGENTS.md")
        if not installed_agents.startswith(user_content):
            raise AssertionError("Codex install must preserve every pre-existing user byte before the managed block")
        assert_contains(installed_agents, "Gauntlet Workflow Router", "Codex AGENTS install")
        assert_contains(installed_agents, personal_block, "Codex personal house voice preservation")
        if installed_agents.count("BEGIN GAUNTLET MANAGED BLOCK") != 1:
            raise AssertionError("Codex install should create exactly one managed block")
        installed_mode = (agent_home / "AGENTS.md").stat().st_mode & 0o777
        if installed_mode != 0o644:
            raise AssertionError(f"Codex AGENTS install mode should be 0644, got {installed_mode:04o}")
        if (agent_home / "CLAUDE.md").exists():
            raise AssertionError("Codex install should not create CLAUDE.md")

        stale_script = agent_home / "gauntlet" / "scripts" / "removed-workflow-helper.py"
        stale_script.write_text("stale installed payload\n")
        for legacy_skill in [
            "build-review-interface",
            "error-analysis",
            "evaluate-rag",
            "generate-synthetic-data",
            "validate-evaluator",
            "write-judge-prompt",
        ]:
            legacy_dir = agent_home / "skills" / legacy_skill
            legacy_dir.mkdir(parents=True)
            (legacy_dir / "SKILL.md").write_text("stale legacy skill\n")
        run_install(agent_home, target="codex")
        reinstalled_agents = read(agent_home / "AGENTS.md")
        if reinstalled_agents != installed_agents:
            raise AssertionError("Codex reinstall should be byte-idempotent")
        if stale_script.exists():
            raise AssertionError("Codex reinstall should remove scripts deleted from the source payload")
        for legacy_skill in [
            "build-review-interface",
            "error-analysis",
            "evaluate-rag",
            "generate-synthetic-data",
            "validate-evaluator",
            "write-judge-prompt",
        ]:
            if (agent_home / "skills" / legacy_skill).exists():
                raise AssertionError(f"Codex reinstall should retire legacy eval skill: {legacy_skill}")

        verify = run([
            str(agent_home / "gauntlet" / "scripts" / "gauntlet.py"),
            "install",
            "verify",
            "--agent-home",
            str(agent_home),
            "--target",
            "codex",
            "--json",
        ])
        if json.loads(verify.stdout)["status"] != "pass":
            raise AssertionError(f"Codex install verify should pass: {verify.stdout}")

        installed_env = os.environ.copy()
        installed_env["AGENT_HOME"] = str(agent_home)
        installed_env["GAUNTLET_SKIP_GIT_HOOKS"] = "1"
        installed_reinstall = subprocess.run(
            [str(agent_home / "gauntlet" / "scripts" / "install.sh"), "--target", "codex"],
            cwd=agent_home / "gauntlet",
            env=installed_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if installed_reinstall.returncode != 0:
            raise AssertionError(
                "installed Gauntlet should support an idempotent self-reinstall:\n"
                f"{installed_reinstall.stdout}\n{installed_reinstall.stderr}"
            )
        if read(agent_home / "AGENTS.md") != installed_agents:
            raise AssertionError("installed self-reinstall should not change the managed Codex file")
        if not (agent_home / "gauntlet" / "docs" / "workflow-etiquette.md").exists():
            raise AssertionError("installed self-reinstall must not delete its own payload")

        linked_home = Path(tmp) / "linked-agent-home"
        linked_home.mkdir()
        linked_target = Path(tmp) / "shared-global-agents.md"
        linked_content = "# Shared global policy\n\nKeep this through linked installs.\n"
        linked_target.write_text(linked_content)
        linked_target.chmod(0o600)
        (linked_home / "AGENTS.md").symlink_to(linked_target)

        run_install(linked_home, target="codex", extra_args=["--instructions-reviewed"])
        if not (linked_home / "AGENTS.md").is_symlink():
            raise AssertionError("Codex install must preserve an existing AGENTS.md symlink")
        linked_installed = linked_target.read_text()
        if not linked_installed.startswith(linked_content):
            raise AssertionError("Codex install must preserve user bytes through an AGENTS.md symlink")
        linked_mode = linked_target.stat().st_mode & 0o777
        if linked_mode != 0o600:
            raise AssertionError(f"Codex install must preserve existing permissions, got {linked_mode:04o}")
        run_install(linked_home, target="codex")
        if linked_target.read_text() != linked_installed:
            raise AssertionError("linked Codex reinstall should be byte-idempotent")


def test_install_migrates_exact_legacy_layout_and_rejects_malformed_blocks():
    if not (ROOT / ".git").exists():
        return

    with tempfile.TemporaryDirectory() as tmp:
        agent_home = Path(tmp) / "agent-home"
        (agent_home / "gauntlet").mkdir(parents=True)
        legacy = "# Legacy Gauntlet Router\n\nLegacy managed workflow body.\n"
        personal = "<!-- BEGIN PERSONAL HOUSE VOICE -->\nKeep my voice.\n<!-- END PERSONAL HOUSE VOICE -->\n"
        (agent_home / "gauntlet" / "AGENTS.md").write_text(legacy)
        first_line_end = legacy.index("\n") + 1
        (agent_home / "AGENTS.md").write_text(legacy[:first_line_end] + "\n" + personal + legacy[first_line_end:])

        run_install(agent_home, target="codex", extra_args=["--instructions-reviewed"])
        migrated = read(agent_home / "AGENTS.md")
        assert_contains(migrated, personal.strip(), "legacy personal block migration")
        assert_contains(migrated, "BEGIN GAUNTLET MANAGED BLOCK", "legacy managed migration")
        assert_not_contains(migrated, "Legacy managed workflow body.", "legacy body removal")

        before = migrated
        (agent_home / "AGENTS.md").write_text(before.replace("<!-- END GAUNTLET MANAGED BLOCK -->", ""))
        malformed_before = (agent_home / "AGENTS.md").read_bytes()
        env = os.environ.copy()
        env["AGENT_HOME"] = str(agent_home)
        env["GAUNTLET_SKIP_GIT_HOOKS"] = "1"
        malformed = subprocess.run(
            [str(SCRIPTS / "install.sh"), "--target", "codex"],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if malformed.returncode == 0:
            raise AssertionError("malformed managed markers must reject installation")
        if (agent_home / "AGENTS.md").read_bytes() != malformed_before:
            raise AssertionError("malformed managed markers must not mutate AGENTS.md")

        (agent_home / "AGENTS.md").write_text(
            "<!-- BEGIN GAUNTLET MANAGED BLOCK -->\n"
            "<!-- BEGIN GAUNTLET MANAGED BLOCK -->\n"
            "nested\n"
            "<!-- END GAUNTLET MANAGED BLOCK -->\n"
            "<!-- END GAUNTLET MANAGED BLOCK -->\n"
        )
        nested_before = (agent_home / "AGENTS.md").read_bytes()
        nested = subprocess.run(
            [str(SCRIPTS / "install.sh"), "--target", "codex"],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if nested.returncode == 0 or (agent_home / "AGENTS.md").read_bytes() != nested_before:
            raise AssertionError("nested managed markers must reject without mutation")


def test_claude_install_layout_adapts_agents_without_overwriting_user_memory():
    if not (ROOT / ".git").exists():
        return

    with tempfile.TemporaryDirectory() as tmp:
        agent_home = Path(tmp) / "agent-home"
        agent_home.mkdir()
        claude_md = agent_home / "CLAUDE.md"
        claude_md.write_text("# My Existing Claude Memory\n\nKeep this personal note.\n")

        run_install(agent_home, target="claude", extra_args=["--instructions-reviewed"])
        assert_installed_gauntlet_layout(agent_home)

        installed_claude = read(claude_md)
        assert_contains(installed_claude, "Keep this personal note.", "Claude user memory preservation")
        assert_contains(installed_claude, "BEGIN GAUNTLET MANAGED BLOCK", "Claude Gauntlet managed block")
        assert_contains(installed_claude, f"@{agent_home}/gauntlet/AGENTS.md", "Claude AGENTS import")
        assert_contains(installed_claude, "Gauntlet Adapter For Claude Code", "Claude adapter guidance")
        assert_contains(read(agent_home / "gauntlet" / "AGENTS.md"), GLOBAL_RESPONSE_STYLE, "Claude imported response style")
        if (agent_home / "AGENTS.md").exists():
            raise AssertionError("Claude install should not write root AGENTS.md")
        if (agent_home / "config.toml").exists():
            raise AssertionError("Claude install should not write Codex config.toml")

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
        "preserving unrelated instructions",
        "--instructions-reviewed",
        "--response-style gauntlet",
        "--response-style existing",
        "--check",
        "--codex-preferences gauntlet",
        "--codex-preferences existing",
        "model_verbosity = \"low\"",
        "personality = \"none\"",
        "show both conflicting passages",
        "never removes or rewrites user-owned instructions",
        "reject malformed managed markers",
        "router/AGENTS.md",
    ]:
        assert_contains(readme, marker, "install target docs")
    archive = read(SKILLS / "archive" / "SKILL.md")
    for marker in [
        "preflights local installation",
        "--instructions-reviewed",
        "--response-style gauntlet|existing",
        "--codex-preferences gauntlet|existing|skip",
    ]:
        assert_contains(archive, marker, "archive install-conflict guidance")


def test_install_requires_review_before_layering_over_existing_instructions():
    if not (ROOT / ".git").exists():
        return

    for target, filename in [("codex", "AGENTS.md"), ("claude", "CLAUDE.md")]:
        with tempfile.TemporaryDirectory() as tmp:
            agent_home = Path(tmp) / "agent-home"
            agent_home.mkdir()
            instructions = agent_home / filename
            original = "# Existing voice\n\nUse an exuberant, highly detailed style.\n"
            instructions.write_text(original)

            result = run_install(agent_home, target=target, check=False)
            if result.returncode == 0:
                raise AssertionError(f"{target} install should stop for unreviewed existing instructions")
            if instructions.read_text() != original:
                raise AssertionError(f"{target} conflict preflight must preserve existing instructions")
            if (agent_home / "gauntlet").exists():
                raise AssertionError(f"{target} conflict preflight must run before payload mutation")
            for marker in [
                "Existing user instructions require conflict review",
                str(instructions),
                "--instructions-reviewed",
                "show both conflicting passages",
            ]:
                assert_contains(result.stderr, marker, f"{target} instruction conflict guidance")

            run_install(agent_home, target=target, extra_args=["--instructions-reviewed"])
            assert_contains(instructions.read_text(), original.strip(), f"{target} reviewed instruction preservation")
            review_state = agent_home / "gauntlet" / f"install-review-{target}.json"
            if not review_state.is_file():
                raise AssertionError(f"{target} install should record the reviewed instruction and candidate hashes")
            run_install(agent_home, target=target)

            changed = "# Newly changed user guidance\n\n" + instructions.read_text()
            instructions.write_text(changed)
            changed_result = run_install(agent_home, target=target, check=False)
            if changed_result.returncode == 0:
                raise AssertionError(f"{target} install should re-review changed user instructions")
            if instructions.read_text() != changed:
                raise AssertionError(f"{target} re-review preflight must preserve changed user instructions")
            assert_contains(changed_result.stderr, "--instructions-reviewed", f"{target} changed-instruction review guidance")
            run_install(
                agent_home,
                target=target,
                extra_args=["--instructions-reviewed", "--response-style", "existing"],
            )
            effective = instructions.read_text() if target == "codex" else read(agent_home / "gauntlet" / "AGENTS.md")
            assert_not_contains(effective, GLOBAL_RESPONSE_STYLE, f"{target} existing-style choice")


def test_codex_install_merges_preferences_without_silent_overwrite():
    if not (ROOT / ".git").exists():
        return

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        clean_home = root / "clean"
        clean_home.mkdir()
        run_install(clean_home, extra_args=["--check"])
        if any(clean_home.iterdir()):
            raise AssertionError("Codex install --check should not create or modify agent-home files")
        run_install(clean_home)
        clean_config = read(clean_home / "config.toml")
        if clean_config.count('model_verbosity = "low"') != 1 or clean_config.count('personality = "none"') != 1:
            raise AssertionError("new Codex config should contain each Gauntlet preference exactly once")
        run_install(clean_home)
        if read(clean_home / "config.toml") != clean_config:
            raise AssertionError("Codex preference reinstall should be byte-idempotent")

        conflict_home = root / "conflict"
        conflict_home.mkdir()
        conflict_config = conflict_home / "config.toml"
        original = 'model = "custom"\nmodel_verbosity = "high" # keep comment\n\n[features]\ngoals = true\n'
        conflict_config.write_text(original)
        conflict_config.chmod(0o600)
        result = run_install(conflict_home, check=False)
        if result.returncode == 0:
            raise AssertionError("conflicting Codex preferences should require an explicit choice")
        if conflict_config.read_text() != original or (conflict_home / "gauntlet").exists():
            raise AssertionError("Codex preference conflict must stop before any mutation")
        for marker in [
            'model_verbosity = "high"',
            'model_verbosity = "low"',
            "--codex-preferences gauntlet",
            "--codex-preferences existing",
        ]:
            assert_contains(result.stderr, marker, "Codex preference conflict report")

        run_install(conflict_home, extra_args=["--codex-preferences", "gauntlet"])
        resolved = conflict_config.read_text()
        assert_contains(resolved, 'model = "custom"', "Codex unrelated config preservation")
        assert_contains(resolved, 'model_verbosity = "low"', "Gauntlet verbosity choice")
        assert_contains(resolved, 'personality = "none"', "Gauntlet personality insertion")
        assert_contains(resolved, "# keep comment", "Codex config trailing-comment preservation")
        assert_contains(resolved, "[features]\ngoals = true", "Codex table preservation")
        if conflict_config.stat().st_mode & 0o777 != 0o600:
            raise AssertionError("Codex config update should preserve permissions")

        combined_home = root / "combined-conflict"
        combined_home.mkdir()
        combined_agents = combined_home / "AGENTS.md"
        combined_config = combined_home / "config.toml"
        combined_agents.write_text("# Existing voice\n\nAlways be expansive.\n")
        combined_config.write_text('personality = "friendly"\n')
        combined = run_install(combined_home, check=False)
        if combined.returncode == 0:
            raise AssertionError("combined instruction and preference conflicts should stop installation")
        for marker in ["Existing user instructions require conflict review", "Codex preference conflict requires a user choice"]:
            assert_contains(combined.stderr, marker, "combined Codex conflict report")
        if (combined_home / "gauntlet").exists():
            raise AssertionError("combined Codex conflicts must stop before payload mutation")

        existing_home = root / "existing"
        existing_home.mkdir()
        existing_config = existing_home / "config.toml"
        existing_original = 'model_verbosity = "high"\npersonality = "friendly"\n'
        existing_config.write_text(existing_original)
        run_install(existing_home, extra_args=["--codex-preferences", "existing"])
        if existing_config.read_text() != existing_original:
            raise AssertionError("existing Codex preference choice should preserve both values byte-for-byte")

        skip_home = root / "skip"
        skip_home.mkdir()
        skip_config = skip_home / "config.toml"
        skip_original = 'model_verbosity = "high"\n'
        skip_config.write_text(skip_original)
        run_install(skip_home, extra_args=["--codex-preferences", "skip"])
        if skip_config.read_text() != skip_original:
            raise AssertionError("skipped Codex preferences should not modify config.toml")

        linked_home = root / "linked"
        linked_home.mkdir()
        linked_target = root / "shared-config.toml"
        linked_target.write_text('model_verbosity = "low"\npersonality = "none"\n')
        linked_target.chmod(0o600)
        (linked_home / "config.toml").symlink_to(linked_target)
        run_install(linked_home)
        if not (linked_home / "config.toml").is_symlink():
            raise AssertionError("Codex config install must preserve an existing symlink")
        if linked_target.stat().st_mode & 0o777 != 0o600:
            raise AssertionError("Codex config install must preserve symlink target permissions")

        crlf_home = root / "crlf"
        crlf_home.mkdir()
        crlf_config = crlf_home / "config.toml"
        crlf_config.write_bytes(b'personality_notes = "keep"\r\n[features]\r\ngoals = true\r\n')
        run_install(crlf_home)
        crlf_result = crlf_config.read_bytes()
        for marker in [b'personality_notes = "keep"', b'model_verbosity = "low"', b'personality = "none"']:
            if marker not in crlf_result:
                raise AssertionError(f"Codex CRLF config missing preserved or inserted value: {marker!r}")
        if b"\n" in crlf_result.replace(b"\r\n", b""):
            raise AssertionError("Codex config insertion should preserve CRLF newline style")


def test_skill_text_coverage_compares_all_arms():
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
        raise AssertionError("skill text coverage must compare one_shot, current_skill, and new_skill")
    if not data.get("cases"):
        raise AssertionError("skill text coverage must include cases")
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
        raise AssertionError("skill text coverage must support targeted --only-skill filtering")


def test_structural_scorers_are_labeled_and_reject_negative_canaries():
    runner = SCRIPTS / "run-skill-evals.py"
    fixture = ROOT / "evals" / "scorer-smoke-fixtures.json"
    results = ROOT / "evals" / "results" / "workflow-scorer-smoke-check.json"
    orchestration_runner = SCRIPTS / "run-orchestration-evals.py"
    orchestration_fixture = ROOT / "evals" / "orchestration-trace-fixtures.json"
    orchestration_results = ROOT / "evals" / "results" / "workflow-orchestration-check.json"
    refactor_fixture = ROOT / "evals" / "refactor-skill-trace-fixtures.json"
    refactor_results = ROOT / "evals" / "results" / "workflow-refactor-orchestration-check.json"

    for path in [runner, fixture, orchestration_runner, orchestration_fixture, refactor_fixture]:
        if not path.exists():
            raise AssertionError(f"missing scorer/eval artifact: {path}")

    with tempfile.TemporaryDirectory() as tmp:
        prompts = Path(tmp) / "scorer-smoke-prompts"
        run([
            str(runner),
            "--scorer-smoke-responses",
            str(fixture),
            "--scorer-smoke-prompts-dir",
            str(prompts),
            "--results",
            str(results),
        ])
        data = json.loads(results.read_text())
        if data.get("scorerSmokeComparisonArms") != ["no_guidance", "one_shot", "current_skill", "new_skill"]:
            raise AssertionError("scorer smoke must compare no_guidance, one_shot, current_skill, and new_skill")
        if "behaviorComparisonArms" in data:
            raise AssertionError("phrase scorer output must not be labeled behavioral")
        if not data.get("cases"):
            raise AssertionError("scorer smoke must include cases")
        for case in data["cases"]:
            scorer_smoke = case.get("scorerSmoke")
            if not scorer_smoke:
                raise AssertionError(f"{case['id']} missing scorer-smoke results")
            if scorer_smoke.get("minReps", 0) < 1:
                raise AssertionError(f"{case['id']} must require matcher canaries")
            if not (prompts / case["id"] / "new_skill.md").exists():
                raise AssertionError(f"{case['id']} missing generated scorer-smoke prompt")
            new_scorer = scorer_smoke["arms"]["new_skill"]
            if new_scorer["repsFound"] < scorer_smoke["minReps"]:
                raise AssertionError(f"{case['id']} new_skill missing scorer-smoke reps")
            if new_scorer["expectationMatchRate"] < 1:
                raise AssertionError(f"{case['id']} new_skill matcher canaries should match expectations")
            if new_scorer["passRate"] != 0.5:
                raise AssertionError(f"{case['id']} matcher pass rate must count actual positive matches")
            if not any(rep.get("expectedPassed") is False for rep in new_scorer["reps"]):
                raise AssertionError(f"{case['id']} missing negative matcher canary")
            for arm_name, arm in case["arms"].items():
                if arm.get("promptWordCount", 0) <= 0:
                    raise AssertionError(f"{case['id']} {arm_name} missing prompt word metric")
                if arm.get("scoreElapsedMs", -1) < 0:
                    raise AssertionError(f"{case['id']} {arm_name} missing score speed metric")

        malformed = Path(tmp) / "malformed-scorer-smoke.json"
        malformed.write_text(json.dumps({
            "responses": [{
                "case": "*",
                "arm": "new_skill",
                "expectedPassed": "false",
                "text": "invalid boolean",
            }]
        }))
        malformed_result = run([
            str(runner),
            "--scorer-smoke-responses",
            str(malformed),
            "--results",
            str(results),
        ], check=False)
        if malformed_result.returncode == 0 or "must be a JSON boolean" not in malformed_result.stderr:
            raise AssertionError("string expectedPassed values must fail fixture validation")

    run([
        str(orchestration_runner),
        "--pack",
        str(orchestration_fixture),
        "--results",
        str(orchestration_results),
    ])
    outcomes = json.loads(orchestration_results.read_text())
    if outcomes.get("evidenceScope") != "declared_trace_fields_only":
        raise AssertionError("trace scorer must disclose that it scores declared fields only")
    if not outcomes.get("cannotVerify"):
        raise AssertionError("trace scorer must disclose unresolved behavioral proof")
    if not outcomes.get("summary", {}).get("expectationsMatched"):
        raise AssertionError(f"orchestration outcome expectations failed: {outcomes}")
    pairs = {pair["id"]: pair for pair in outcomes.get("pairs", [])}
    for required in [
        "correct-outcome",
        "missing-proof",
        "authority-violation",
        "verbose-output",
        "automatic-quiet-delegation",
        "coupled-lanes-stay-main",
        "phrase-echo-wrong-action",
        "field-correct-wrong-outcome",
        "self-attested-proof-is-not-resolved",
        "different-prose-same-contract",
        "subjective-needs-judgment",
    ]:
        if required not in pairs:
            raise AssertionError(f"missing orchestration outcome case: {required}")
    if pairs["phrase-echo-wrong-action"]["arms"]["current"]["verdict"] != "fail":
        raise AssertionError("phrase echo with the wrong declared action must fail")
    if pairs["field-correct-wrong-outcome"]["arms"]["current"]["verdict"] != "fail":
        raise AssertionError("correct report fields with the wrong declared outcome must fail")
    proof_canary = pairs["self-attested-proof-is-not-resolved"]["arms"]
    if proof_canary["current"]["verdict"] != "fail" or proof_canary["candidate"]["verdict"] != "pass":
        raise AssertionError("declared self-attested proof must not satisfy a harness-event matcher")
    prose_canary = pairs["different-prose-same-contract"]["arms"]
    if any(arm["verdict"] != "pass" for arm in prose_canary.values()):
        raise AssertionError("valid declared fields must pass independently of exact report prose")
    delegation = pairs["automatic-quiet-delegation"]["arms"]
    if delegation["current"]["verdict"] != "fail" or delegation["candidate"]["verdict"] != "pass":
        raise AssertionError("automatic quiet delegation canary must reject serial execution and accept bounded child dispatch")
    coupled = pairs["coupled-lanes-stay-main"]["arms"]
    if coupled["current"]["verdict"] != "fail" or coupled["candidate"]["verdict"] != "pass":
        raise AssertionError("coupled-lane canary must reject needless delegation and accept end-to-end execution")
    if pairs["subjective-needs-judgment"]["arms"]["candidate"]["verdict"] != "cannot_verify":
        raise AssertionError("uncalibrated subjective judgment must remain Cannot verify")

    run([
        str(orchestration_runner),
        "--pack",
        str(refactor_fixture),
        "--results",
        str(refactor_results),
    ])
    refactor_outcomes = json.loads(refactor_results.read_text())
    if not refactor_outcomes.get("summary", {}).get("expectationsMatched"):
        raise AssertionError(f"refactor orchestration expectations failed: {refactor_outcomes}")
    refactor_pairs = {pair["id"]: pair for pair in refactor_outcomes.get("pairs", [])}
    for required in [
        "route-comprehensive-refactor-to-codebase",
        "route-performance-only-to-performance",
        "baseline-only-does-not-edit",
        "immutable-source-negative-canary",
        "capability-removal-negative-canary",
        "premature-completion-negative-canary",
        "completion-and-delegation-trace",
        "breakthrough-no-history-frozen-packet",
        "chat-only-context-stays-root",
        "web-verification-browser-default",
        "explicit-computer-use-wins",
        "native-cross-app-uses-computer-use",
        "chrome-only-for-profile-session-extension",
        "efficiency-telemetry-host-exposure-gate",
    ]:
        if required not in refactor_pairs:
            raise AssertionError(f"missing refactor orchestration outcome case: {required}")
    for required in [
        "breakthrough-no-history-frozen-packet",
        "chat-only-context-stays-root",
        "completion-and-delegation-trace",
        "web-verification-browser-default",
        "explicit-computer-use-wins",
        "native-cross-app-uses-computer-use",
        "chrome-only-for-profile-session-extension",
    ]:
        arms = refactor_pairs[required]["arms"]
        if (
            arms["current"]["verdict"] != "fail"
            or arms["candidate"]["verdict"] != "pass"
        ):
            raise AssertionError(
                f"{required} must reject the negative canary and accept the candidate"
            )
    telemetry = refactor_pairs["efficiency-telemetry-host-exposure-gate"]["arms"]
    if (
        telemetry["current"]["verdict"] != "fail"
        or telemetry["candidate"]["verdict"] != "cannot_verify"
    ):
        raise AssertionError(
            "efficiency telemetry must reject invented numbers and preserve "
            "Cannot verify without host evidence"
        )


def test_skill_linter_examples_and_noop_pruning():
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


def test_skill_changes_are_guarded_by_pre_commit():
    hook_installer = SCRIPTS / "install-git-hooks.sh"
    skill_check = SCRIPTS / "run-skill-change-checks.sh"
    for path in [hook_installer, skill_check]:
        if not path.exists() or not os.access(path, os.X_OK):
            raise AssertionError(f"missing executable skill-change guard: {path}")
    assert_contains(skill_check.read_text(), "--diff-filter=ACMRD", "skill deletion guard")

    with tempfile.TemporaryDirectory() as tmp:
        deletion_repo = Path(tmp) / "deletion-repo"
        (deletion_repo / "scripts").mkdir(parents=True)
        (deletion_repo / "skills" / "refactor-codebase" / "assets").mkdir(parents=True)
        copied_check = deletion_repo / "scripts" / "run-skill-change-checks.sh"
        shutil.copy2(skill_check, copied_check)
        deleted_asset = deletion_repo / "skills" / "refactor-codebase" / "assets" / "packet.md"
        deleted_asset.write_text("frozen packet\n")
        run(["git", "init", "-q"], cwd=deletion_repo)
        run(["git", "add", "."], cwd=deletion_repo)
        run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"], cwd=deletion_repo)
        deleted_asset.unlink()
        run(["git", "add", "-u"], cwd=deletion_repo)
        deletion = run([str(copied_check), "--detect-only"], cwd=deletion_repo)
        assert_contains(deletion.stdout, "Gauntlet skill changes detected: refactor-codebase", "staged skill deletion guard")

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
            raise AssertionError("non-skill changes should skip skill text coverage")

    result = run([str(skill_check), "--changed-files", "skills/planner/SKILL.md"], cwd=ROOT)
    for marker in ["Gauntlet skill changes detected", "targeted skill evals: planner", "skill text coverage:", "declared trace-field scorer contracts:", "skill linter"]:
        assert_contains(result.stdout, marker, "skill change checks")

    result = run([
        str(skill_check), "--changed-files",
        "skills/refactor-codebase/assets/breakthrough-agent-packet.md",
    ], cwd=ROOT)
    for marker in ["Gauntlet skill changes detected", "targeted skill evals: refactor-codebase", "Ran 25 tests", "skill linter"]:
        assert_contains(result.stdout + result.stderr, marker, "refactor asset change checks")


def test_refactor_agent_prompt_renderer_integrity():
    result = run([
        "python3", "-m", "unittest", "discover",
        "-s", str(SKILLS / "refactor-codebase" / "scripts"),
        "-p", "test_render_agent_prompt.py", "-v",
    ], cwd=ROOT)
    assert_contains(result.stdout + result.stderr, "Ran 6 tests", "refactor prompt renderer tests")


def test_superpowers_sources_are_attributed_and_retirement_is_allowlisted():
    attribution = ROOT / "docs" / "upstream-superpowers.md"
    manifest_path = ROOT / "docs" / "upstream-superpowers.json"
    sync = SCRIPTS / "check-superpowers-sync.py"
    retire = SCRIPTS / "retire-superpowers.py"
    for path in [attribution, manifest_path, sync, retire]:
        if not path.exists():
            raise AssertionError(f"missing Superpowers migration artifact: {path}")

    attribution_text = read(attribution)
    for marker in ["Jesse Vincent", "obra/superpowers", "MIT", "5.1.3", "adapted concepts, not vendored text"]:
        assert_contains(attribution_text, marker, "Superpowers attribution")

    manifest = json.loads(read(manifest_path))
    if manifest.get("upstream", {}).get("repository") != "https://github.com/obra/superpowers":
        raise AssertionError("Superpowers upstream repository is not pinned")
    if not manifest.get("techniques") or not manifest.get("retiredSkills"):
        raise AssertionError("Superpowers mapping needs techniques and retiredSkills")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source"
        (source / "skills" / "systematic-debugging").mkdir(parents=True)
        source_text = "root-cause-first\n"
        source_skill = source / "skills" / "systematic-debugging" / "SKILL.md"
        source_skill.write_text(source_text)
        (source / ".codex-plugin").mkdir()
        (source / ".codex-plugin" / "plugin.json").write_text(json.dumps({"version": "5.1.3"}))
        fixture_manifest = root / "manifest.json"
        fixture_manifest.write_text(json.dumps({
            "schemaVersion": "1.0",
            "upstream": {"repository": "https://github.com/obra/superpowers", "reviewedVersion": "5.1.3"},
            "techniques": [{
                "sourceSkill": "systematic-debugging",
                "sourcePath": "skills/systematic-debugging/SKILL.md",
                "reviewedSha256": hashlib.sha256(source_text.encode()).hexdigest(),
                "destinations": ["skills/debugger/SKILL.md"],
            }],
            "retiredSkills": ["brainstorming", "using-superpowers"],
        }))
        current = run([str(sync), "--source", str(source), "--manifest", str(fixture_manifest), "--json"])
        if json.loads(current.stdout)["status"] != "pass":
            raise AssertionError(f"matching upstream map should pass: {current.stdout}")
        source_skill.write_text("changed upstream\n")
        changed = run([str(sync), "--source", str(source), "--manifest", str(fixture_manifest), "--json"], check=False)
        if changed.returncode == 0 or json.loads(changed.stdout)["status"] != "review":
            raise AssertionError(f"changed upstream source should require review: {changed.stdout}")

        active = root / "active-skills"
        (active / "brainstorming").mkdir(parents=True)
        (active / "using-superpowers").mkdir()
        (active / "personal-skill").mkdir()
        config = root / "config.toml"
        config.write_text('[plugins."superpowers@openai-curated"]\nenabled = true\n')
        archive = root / "retired"
        dry_run = run([
            str(retire), "--active-skills", str(active), "--config", str(config),
            "--archive", str(archive), "--manifest", str(fixture_manifest), "--json",
        ])
        if not (active / "brainstorming").exists() or json.loads(dry_run.stdout)["applied"]:
            raise AssertionError("retirement must be dry-run by default")
        applied = run([
            str(retire), "--active-skills", str(active), "--config", str(config),
            "--archive", str(archive), "--manifest", str(fixture_manifest), "--apply", "--json",
        ])
        applied_data = json.loads(applied.stdout)
        if applied_data["status"] != "pass" or not applied_data["applied"]:
            raise AssertionError(f"Superpowers retirement should apply cleanly: {applied.stdout}")
        if (active / "brainstorming").exists() or (active / "using-superpowers").exists():
            raise AssertionError("allowlisted Superpowers skills should leave the active directory")
        if not (active / "personal-skill").exists():
            raise AssertionError("unrelated skills must be preserved")
        assert_contains(config.read_text(), "enabled = false", "disabled Superpowers plugin")

        for label, config_text in {
            "missing-section": '[plugins."another-plugin"]\nenabled = true\n',
            "missing-enabled-key": '[plugins."superpowers@openai-curated"]\nmode = "manual"\n',
        }.items():
            unsafe_active = root / f"unsafe-active-{label}"
            (unsafe_active / "brainstorming").mkdir(parents=True)
            unsafe_config = root / f"unsafe-{label}.toml"
            unsafe_config.write_text(config_text)
            unsafe_result = run([
                str(retire), "--active-skills", str(unsafe_active), "--config", str(unsafe_config),
                "--archive", str(root / f"unsafe-archive-{label}"), "--manifest", str(fixture_manifest), "--apply", "--json",
            ], check=False)
            if unsafe_result.returncode == 0:
                raise AssertionError(f"retirement should stop when plugin disablement is unresolved: {label}")
            if not (unsafe_active / "brainstorming").exists() or unsafe_config.read_text() != config_text:
                raise AssertionError(f"unverified plugin disablement must preserve skills and config: {label}")


def test_local_document_profile_preserves_tracked_docs_and_primary_canonical_copy():
    cli = SCRIPTS / "gauntlet.py"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        init_repo(repo)
        (repo / "docs").mkdir()
        (repo / "docs" / "public-contract.md").write_text("# Public contract\n")
        commit_all(repo, "tracked docs")
        linked = root / "linked"
        git(["worktree", "add", "-b", "feature/local-docs", str(linked)], cwd=repo)

        exclude = repo / ".git" / "info" / "exclude"
        exclude_before = exclude.read_text() if exclude.exists() else ""
        dry_run = run([
            str(cli), "docs", "init", "--project-root", str(linked),
            "--epic-prefix", "DEMO", "--dry-run", "--json",
        ])
        if json.loads(dry_run.stdout)["status"] != "pass":
            raise AssertionError(f"local docs dry-run should pass: {dry_run.stdout}")
        if (repo / "doc_org.md").exists() or (repo / "local-docs").exists():
            raise AssertionError("local docs dry-run must not create canonical paths")
        if (exclude.read_text() if exclude.exists() else "") != exclude_before:
            raise AssertionError("local docs dry-run must not change Git exclusions")

        initialized = run([
            str(cli), "docs", "init", "--project-root", str(linked),
            "--epic-prefix", "DEMO", "--json",
        ])
        initialized_data = json.loads(initialized.stdout)
        if initialized_data["status"] != "pass":
            raise AssertionError(f"local docs init should pass: {initialized.stdout}")
        if Path(initialized_data["primaryRoot"]).resolve() != repo.resolve():
            raise AssertionError("linked-worktree initialization must resolve the primary worktree")
        if not (repo / "doc_org.md").is_file() or not (repo / "local-docs" / "INDEX.md").is_file():
            raise AssertionError("local docs init must create canonical files in the primary worktree")
        if (linked / "doc_org.md").exists() or (linked / "local-docs").exists():
            raise AssertionError("linked worktree must not receive alternate canonical local documents")
        if git(["status", "--porcelain"], cwd=repo).stdout.strip():
            raise AssertionError("ignored local documents must not dirty the tracked repository")
        if git(["ls-files", "docs/public-contract.md"], cwd=repo).stdout.strip() != "docs/public-contract.md":
            raise AssertionError("existing tracked documentation must remain tracked")
        policy_before = (repo / "doc_org.md").read_text()
        index_before = (repo / "local-docs" / "INDEX.md").read_text()
        repeated = run([
            str(cli), "docs", "init", "--project-root", str(linked),
            "--epic-prefix", "DEMO", "--json",
        ])
        if json.loads(repeated.stdout)["status"] != "pass":
            raise AssertionError(f"repeat local docs init should pass: {repeated.stdout}")
        if (repo / "doc_org.md").read_text() != policy_before or (repo / "local-docs" / "INDEX.md").read_text() != index_before:
            raise AssertionError("repeat local docs init must preserve existing canonical documents")

        checked = run([str(cli), "docs", "check", "--project-root", str(linked), "--json"])
        if json.loads(checked.stdout)["status"] != "pass":
            raise AssertionError(f"local docs check should pass: {checked.stdout}")
        epic = run([
            str(cli), "docs", "epic", "create", "--project-root", str(linked),
            "--title", "Message surfaces", "--json",
        ])
        epic_data = json.loads(epic.stdout)
        if epic_data.get("epicId") != "DEMO-001" or not Path(epic_data["prdPath"]).is_file():
            raise AssertionError(f"stable epic creation failed: {epic.stdout}")
        appended = run([
            str(cli), "docs", "epic", "create", "--project-root", str(linked),
            "--title", "Delivery controls", "--prd", str(Path(epic_data["prdPath"]).resolve().relative_to((repo / "local-docs").resolve())), "--json",
        ])
        appended_data = json.loads(appended.stdout)
        if appended_data.get("epicId") != "DEMO-002" or appended_data.get("prdPath") != epic_data["prdPath"] or not appended_data.get("appended"):
            raise AssertionError(f"multi-Epic PRD append failed: {appended.stdout}")
        prd_text = Path(epic_data["prdPath"]).read_text()
        if prd_text.count("## Epic DEMO-") != 2 or "## Epic DEMO-002: Delivery controls" not in prd_text:
            raise AssertionError("appended Epic must share the canonical PRD with a stable searchable heading")
        duplicate = run([
            str(cli), "docs", "epic", "create", "--project-root", str(linked),
            "--title", "Duplicate", "--number", "2", "--json",
        ], check=False)
        if duplicate.returncode == 0 or json.loads(duplicate.stdout)["status"] != "fail":
            raise AssertionError("Epic allocation must reject IDs already present inside a multi-Epic PRD")
        bad_title = run([
            str(cli), "docs", "epic", "create", "--project-root", str(linked),
            "--title", "Bad | table", "--json",
        ], check=False)
        if bad_title.returncode == 0 or (repo / "local-docs" / "epics" / "003").exists():
            raise AssertionError("invalid epic titles must fail without a partial epic")
        injected_title = run([
            str(cli), "docs", "epic", "create", "--project-root", str(linked),
            "--title", "Legit](https://example.invalid)[x", "--json",
        ], check=False)
        if injected_title.returncode == 0 or "example.invalid" in (repo / "local-docs" / "INDEX.md").read_text():
            raise AssertionError("Epic titles must not inject Markdown into the canonical index")
        wrong_prefix = run([
            str(cli), "docs", "init", "--project-root", str(linked),
            "--epic-prefix", "OTHER", "--json",
        ], check=False)
        if wrong_prefix.returncode == 0 or json.loads(wrong_prefix.stdout)["status"] != "fail":
            raise AssertionError("repeat initialization must preserve the established epic prefix")

        collision = root / "collision"
        init_repo(collision)
        (collision / "doc_org.md").write_text("# Tracked policy\n")
        commit_all(collision, "tracked policy")
        refused = run([
            str(cli), "docs", "init", "--project-root", str(collision),
            "--epic-prefix", "DEMO", "--json",
        ], check=False)
        refused_data = json.loads(refused.stdout)
        if refused.returncode == 0 or refused_data["status"] != "fail":
            raise AssertionError("initialization must refuse tracked local-document collisions")
        if (collision / "local-docs").exists():
            raise AssertionError("collision failure must not partially initialize local documents")

        symlink_repo = root / "symlink"
        init_repo(symlink_repo)
        outside = root / "outside"
        outside.mkdir()
        (symlink_repo / "local-docs").symlink_to(outside, target_is_directory=True)
        symlink_refused = run([
            str(cli), "docs", "init", "--project-root", str(symlink_repo),
            "--epic-prefix", "DEMO", "--json",
        ], check=False)
        if symlink_refused.returncode == 0 or any(outside.iterdir()):
            raise AssertionError("local-document symlinks must fail without writing outside the primary worktree")


def test_prd_execution_run_controller_behavior():
    result = run(["python3", str(SCRIPTS / "test-prd-run.py")], check=False)
    if result.returncode != 0 or "Ran " not in result.stderr or "OK" not in result.stderr:
        raise AssertionError(f"PRD execution-run controller behavior failed:\n{result.stdout}\n{result.stderr}")


def main():
    tests = [
        test_plugin_manifests_bundle_shared_skills,
        test_craft_product_terminology_contract,
        test_simplified_modes_and_depth_are_documented,
        test_normal_requests_use_minimum_scope_before_lifecycle_routing,
        test_v201_run_log_contract_replaces_default_review_brief,
        test_coverage_gap_and_design_lint_guidance_are_documented,
        test_product_thinking_and_scope_routing_are_documented,
        test_production_quality_bar_is_launch_gated,
        test_subagent_parallelism_is_context_efficient,
        test_direct_dispatch_and_quiet_execution_are_documented,
        test_workflow_guidance_keeps_routine_controls_silent,
        test_guarded_panel_contract_is_uniform,
        test_ts_durability_classifier_behavior,
        test_diff_intel_test_plan_and_review_pack_are_bounded,
        test_docs_only_diff_gets_no_runtime_test_commands,
        test_instruction_surfaces_are_not_classified_as_docs_only,
        test_workflow_helpers_filter_artifacts_and_find_python_tests,
        test_workflow_speedup_helpers_are_documented_as_advisory,
        test_contextual_merge_contract_is_documented,
        test_response_style_guidance_is_single_global_policy,
        test_version_changelog_preserves_release_history,
        test_contextual_pr_template_changelog_and_run_log_contract,
        test_workflow_etiquette_checker_validates_titles_kickoff_and_auto_assumptions,
        test_workflow_etiquette_checker_pauses_archive_on_followups_and_git_state,
        test_workflow_etiquette_checker_builds_archive_action_plan,
        test_gauntlet_cli_merge_prepare_renders_contextual_handoff,
        test_gauntlet_cli_merge_plan_requires_clean_task_branch,
        test_gauntlet_cli_merge_execute_creates_pr_waits_and_verifies_main,
        test_gauntlet_cli_closeout_execute_commits_merges_cleans_and_returns_archive_actions,
        test_remote_branch_cleanup_accepts_concurrent_auto_delete,
        test_closeout_forwards_install_conflict_choices_to_preflight_and_apply,
        test_gauntlet_cli_archive_plans_and_executes_github_merge,
        test_gauntlet_cli_archive_keeps_archive_anyway_from_overriding_git_risk,
        test_gauntlet_cli_small_helper_commands,
        test_gauntlet_cli_changelog_memory_and_followup_helpers,
        test_gauntlet_cli_local_analytics_and_closeout_facts,
        test_gauntlet_cli_bounded_attempt_memory,
        test_thread_changelog_captures_pr_history_and_followups,
        test_workflow_etiquette_is_in_global_workflow,
        test_promotion_scanner_is_release_wrapup_not_patch_gate,
        test_skill_text_coverage_compares_all_arms,
        test_structural_scorers_are_labeled_and_reject_negative_canaries,
        test_skill_linter_examples_and_noop_pruning,
        test_skill_changes_are_guarded_by_pre_commit,
        test_refactor_agent_prompt_renderer_integrity,
        test_codex_install_layout_supports_workflow_check,
        test_install_migrates_exact_legacy_layout_and_rejects_malformed_blocks,
        test_superpowers_sources_are_attributed_and_retirement_is_allowlisted,
        test_claude_install_layout_adapts_agents_without_overwriting_user_memory,
        test_install_requires_review_before_layering_over_existing_instructions,
        test_codex_install_merges_preferences_without_silent_overwrite,
        test_install_docs_explain_codex_and_claude_targets,
        test_local_document_profile_preserves_tracked_docs_and_primary_canonical_copy,
        test_prd_execution_run_controller_behavior,
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
