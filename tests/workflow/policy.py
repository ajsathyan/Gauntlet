"""Portable workflow and plugin policy cases."""

import json

from tests.workflow.fixtures import (
    ROOT,
    ROUTER_MD,
    SKILLS,
    assert_contains,
    assert_not_contains,
    read,
)


def test_plugin_manifests_bundle_shared_skills():
    if not (ROOT / ".codex-plugin" / "plugin.json").is_file():
        return
    codex_manifest = json.loads(read(ROOT / ".codex-plugin" / "plugin.json"))
    if codex_manifest["name"] != "gauntlet":
        raise AssertionError("Codex plugin manifest must use the Gauntlet identity")
    if codex_manifest.get("skills") != "./skills/":
        raise AssertionError("Codex plugin manifest must bundle the shared skills directory")
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        text = read(path)
        assert_contains(text, f"name: {path.parent.name}", f"skill name for {path.parent.name}")

    codex_marketplace = json.loads(read(ROOT / ".agents" / "plugins" / "marketplace.json"))
    if codex_marketplace["plugins"][0]["name"] != "gauntlet":
        raise AssertionError("Codex marketplace must expose the Gauntlet plugin")


def test_normal_requests_use_minimum_scope_before_design():
    router = read(ROUTER_MD)
    for marker in [
        "## Minimum scope",
        "bounded, low-consequence, reversible, directly checkable",
        "deliver the artifact directly",
        "run its smoke check",
        "keep work in the main task",
        "do not create a durable design",
        "stop when it works",
    ]:
        assert_contains(router, marker, "normal-request minimum-scope routing")


def test_merge_and_archive_authority_requires_complete_safe_closeout():
    router = read(ROUTER_MD)
    archive = read(SKILLS / "archive" / "SKILL.md")
    land = read(SKILLS / "land" / "SKILL.md")
    ship = read(SKILLS / "ship" / "SKILL.md")
    for marker in [
        "An implementation request authorizes the ordinary code lifecycle",
        "Do not ask for another acceptance between those stages",
        "merge itself deploys, publishes, migrates",
        "requires explicit acceptance before merge",
        "met acceptance criteria and",
        "material decisions made independently",
        "the exact revision",
        "rollback",
    ]:
        assert_contains(router, marker, "autonomous implementation authority")
    assert_not_contains(
        router,
        "Opening a PR does not authorize merge",
        "retired separate merge acceptance",
    )
    for marker in [
        "implementation request authorizes this flow",
        "no separate merge acceptance is required",
        "Inspect default-branch automation",
        "Use local `git` and authenticated `gh` by default",
        "waits for required CI",
        "tree-equivalent merge",
        "Run established post-merge CI",
        "fast-forward the checkout that owns the local default branch",
        "remove a clean isolated worktree",
    ]:
        assert_contains(land, marker, "land closeout")
    for marker in [
        "Production Acceptance Request",
        "acceptance criteria met, with evidence",
        "decisions made independently during implementation",
        "unmet criteria, verification limits, and remaining risk",
        "exact candidate revision",
        "rollback path",
        "Never perform the production action from implementation authority alone",
    ]:
        assert_contains(ship, marker, "production acceptance boundary")
    for marker in [
        "Read `../land/SKILL.md` completely",
        "Complete the `land` skill",
        "Stop without archival if it does not pass",
    ]:
        assert_contains(archive, marker, "archive composition")
