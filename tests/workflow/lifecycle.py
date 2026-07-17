"""Local-document and delegated controller workflow cases."""

import json
import tempfile
from pathlib import Path

from tests.workflow.fixtures import (
    ROOT,
    SCRIPTS,
    assert_not_contains,
    commit_all,
    git,
    init_repo,
    read,
    run,
)


def _assert_profile_initialization(root, repo, linked, cli):
    exclude = repo / ".git" / "info" / "exclude"
    exclude_before = exclude.read_text() if exclude.exists() else ""
    default_check = run([str(cli), "docs", "check", "--project-root", str(linked), "--json"])
    default_check_data = json.loads(default_check.stdout)
    if (
        default_check_data.get("status") != "pass"
        or default_check_data.get("mode") != "default-on"
        or default_check_data.get("materialized")
    ):
        raise AssertionError(f"uninitialized projects must report the default-on lazy mode: {default_check.stdout}")
    dry_run = run(
        [
            str(cli),
            "docs",
            "init",
            "--project-root",
            str(linked),
            "--epic-prefix",
            "DEMO",
            "--dry-run",
            "--json",
        ]
    )
    if json.loads(dry_run.stdout)["status"] != "pass":
        raise AssertionError(f"local docs dry-run should pass: {dry_run.stdout}")
    if (repo / "doc_org.md").exists() or (repo / "local-docs").exists():
        raise AssertionError("local docs dry-run must not create canonical paths")
    if (exclude.read_text() if exclude.exists() else "") != exclude_before:
        raise AssertionError("local docs dry-run must not change Git exclusions")

    initialized = run(
        [
            str(cli),
            "docs",
            "init",
            "--project-root",
            str(linked),
            "--epic-prefix",
            "DEMO",
            "--json",
        ]
    )
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
    repeated = run(
        [
            str(cli),
            "docs",
            "init",
            "--project-root",
            str(linked),
            "--epic-prefix",
            "DEMO",
            "--json",
        ]
    )
    if json.loads(repeated.stdout)["status"] != "pass":
        raise AssertionError(f"repeat local docs init should pass: {repeated.stdout}")
    if (
        (repo / "doc_org.md").read_text() != policy_before
        or (repo / "local-docs" / "INDEX.md").read_text() != index_before
    ):
        raise AssertionError("repeat local docs init must preserve existing canonical documents")


def _assert_epic_creation(repo, linked, cli):
    checked = run([str(cli), "docs", "check", "--project-root", str(linked), "--json"])
    if json.loads(checked.stdout)["status"] != "pass":
        raise AssertionError(f"local docs check should pass: {checked.stdout}")
    epic = run(
        [
            str(cli),
            "docs",
            "epic",
            "create",
            "--project-root",
            str(linked),
            "--title",
            "Message surfaces",
            "--json",
        ]
    )
    epic_data = json.loads(epic.stdout)
    if epic_data.get("epicId") != "DEMO-001" or not Path(epic_data["prdPath"]).is_file():
        raise AssertionError(f"stable epic creation failed: {epic.stdout}")
    prd_relative = Path(epic_data["prdPath"]).resolve().relative_to((repo / "local-docs").resolve())
    appended = run(
        [
            str(cli),
            "docs",
            "epic",
            "create",
            "--project-root",
            str(linked),
            "--title",
            "Delivery controls",
            "--prd",
            str(prd_relative),
            "--json",
        ]
    )
    appended_data = json.loads(appended.stdout)
    if (
        appended_data.get("epicId") != "DEMO-002"
        or appended_data.get("prdPath") != epic_data["prdPath"]
        or not appended_data.get("appended")
    ):
        raise AssertionError(f"multi-Epic PRD append failed: {appended.stdout}")
    prd_text = Path(epic_data["prdPath"]).read_text()
    if prd_text.count("## Epic DEMO-") != 2 or "## Epic DEMO-002: Delivery controls" not in prd_text:
        raise AssertionError("appended Epic must share the canonical PRD with a stable searchable heading")
    duplicate = run(
        [
            str(cli),
            "docs",
            "epic",
            "create",
            "--project-root",
            str(linked),
            "--title",
            "Duplicate",
            "--number",
            "2",
            "--json",
        ],
        check=False,
    )
    if duplicate.returncode == 0 or json.loads(duplicate.stdout)["status"] != "fail":
        raise AssertionError("Epic allocation must reject IDs already present inside a multi-Epic PRD")
    bad_title = run(
        [
            str(cli),
            "docs",
            "epic",
            "create",
            "--project-root",
            str(linked),
            "--title",
            "Bad | table",
            "--json",
        ],
        check=False,
    )
    if bad_title.returncode == 0 or (repo / "local-docs" / "epics" / "003").exists():
        raise AssertionError("invalid epic titles must fail without a partial epic")
    injected_title = run(
        [
            str(cli),
            "docs",
            "epic",
            "create",
            "--project-root",
            str(linked),
            "--title",
            "Legit](https://example.invalid)[x",
            "--json",
        ],
        check=False,
    )
    if injected_title.returncode == 0 or "example.invalid" in (repo / "local-docs" / "INDEX.md").read_text():
        raise AssertionError("Epic titles must not inject Markdown into the canonical index")
    wrong_prefix = run(
        [
            str(cli),
            "docs",
            "init",
            "--project-root",
            str(linked),
            "--epic-prefix",
            "OTHER",
            "--json",
        ],
        check=False,
    )
    if wrong_prefix.returncode == 0 or json.loads(wrong_prefix.stdout)["status"] != "fail":
        raise AssertionError("repeat initialization must preserve the established epic prefix")


def _assert_profile_safety_and_optout(root, cli):
    collision = root / "collision"
    init_repo(collision)
    (collision / "doc_org.md").write_text("# Tracked policy\n")
    commit_all(collision, "tracked policy")
    refused = run(
        [
            str(cli),
            "docs",
            "init",
            "--project-root",
            str(collision),
            "--epic-prefix",
            "DEMO",
            "--json",
        ],
        check=False,
    )
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
    symlink_refused = run(
        [
            str(cli),
            "docs",
            "init",
            "--project-root",
            str(symlink_repo),
            "--epic-prefix",
            "DEMO",
            "--json",
        ],
        check=False,
    )
    if symlink_refused.returncode == 0 or any(outside.iterdir()):
        raise AssertionError("local-document symlinks must fail without writing outside the primary worktree")

    optout = root / "optout"
    init_repo(optout)
    before_optout = run([str(cli), "docs", "check", "--project-root", str(optout), "--json"])
    if json.loads(before_optout.stdout).get("mode") != "default-on":
        raise AssertionError("new projects must start in default-on mode")
    disabled = run([str(cli), "docs", "disable", "--project-root", str(optout), "--json"])
    if (
        json.loads(disabled.stdout).get("status") != "pass"
        or not (optout / ".gauntlet" / "doc-org.disabled").is_file()
    ):
        raise AssertionError(f"project opt-out must create its ignored marker: {disabled.stdout}")
    opted_out_check = run([str(cli), "docs", "check", "--project-root", str(optout), "--json"])
    opted_out_data = json.loads(opted_out_check.stdout)
    if opted_out_data.get("mode") != "opted-out" or opted_out_data.get("status") != "pass":
        raise AssertionError(f"opted-out projects must pass without a local-document profile: {opted_out_check.stdout}")
    opted_out_ensure = run([str(cli), "docs", "ensure", "--project-root", str(optout), "--json"])
    if (
        json.loads(opted_out_ensure.stdout).get("mode") != "opted-out"
        or (optout / "doc_org.md").exists()
    ):
        raise AssertionError("docs ensure must respect the project opt-out without creating files")
    enabled = run([str(cli), "docs", "enable", "--project-root", str(optout), "--json"])
    if (
        json.loads(enabled.stdout).get("status") != "pass"
        or (optout / ".gauntlet" / "doc-org.disabled").exists()
    ):
        raise AssertionError(f"project opt-in must remove the marker: {enabled.stdout}")
    reenabled = run([str(cli), "docs", "ensure", "--project-root", str(optout), "--json"])
    reenabled_data = json.loads(reenabled.stdout)
    if reenabled_data.get("status") != "pass" or not (optout / "doc_org.md").is_file():
        raise AssertionError(f"re-enabled projects must lazily materialize the profile: {reenabled.stdout}")


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
        _assert_profile_initialization(root, repo, linked, cli)
        _assert_epic_creation(repo, linked, cli)
        _assert_profile_safety_and_optout(root, cli)


def test_prd_execution_run_controller_behavior():
    result = run(["python3", str(SCRIPTS / "test-prd-run.py")], check=False)
    if result.returncode != 0 or "Ran " not in result.stderr or "OK" not in result.stderr:
        raise AssertionError(f"PRD execution-run controller behavior failed:\n{result.stdout}\n{result.stderr}")


def test_live_progress_projection_dashboard_and_production_assets():
    for script in ["test-progress-projection.py", "test-progress-dashboard.py", "test-prd-project.py"]:
        result = run(["python3", str(SCRIPTS / script)], check=False)
        if result.returncode != 0 or "OK" not in result.stderr:
            raise AssertionError(f"Live progress behavior failed for {script}:\n{result.stdout}\n{result.stderr}")
    production = "\n".join(
        read(ROOT / relative)
        for relative in [
            "templates/progress-dashboard/index.html",
            "templates/progress-dashboard/assets/app.js",
        ]
    )
    for forbidden in ["data-fixture", "fixture caption", "state switcher", "sample values"]:
        assert_not_contains(production.lower(), forbidden, "production progress dashboard demo controls")


def test_document_draft_lifecycle_behavior():
    for script in [
        "test-doc-lifecycle.py",
        "test-flexible-prd.py",
        "test-context-audit.py",
        "test-prd-project.py",
    ]:
        result = run(["python3", str(SCRIPTS / script)], check=False)
        if result.returncode != 0 or "OK" not in result.stderr:
            raise AssertionError(f"Document workflow behavior failed for {script}:\n{result.stdout}\n{result.stderr}")


def test_subagent_orchestration_v2_behavior():
    for script in [
        "test-generated-context.py",
        "test-subagent-orchestration.py",
        "test-eval-task.py",
        "test-eval-run.py",
        "test-eval-harness.py",
    ]:
        result = run(["python3", str(SCRIPTS / script)], check=False)
        if result.returncode != 0:
            raise AssertionError(f"Subagent Orchestration V2 check failed for {script}:\n{result.stdout}\n{result.stderr}")
