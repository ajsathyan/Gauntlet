"""Portable workflow and plugin policy cases."""

import json

from tests.workflow.fixtures import (
    ROOT,
    ROUTER_MD,
    SKILLS,
    assert_contains,
    read,
)


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


def test_normal_requests_use_minimum_scope_before_lifecycle_routing():
    router = read(ROUTER_MD)
    for marker in [
        "## Minimum scope",
        "bounded, low-consequence, reversible, and directly checkable",
        "deliver the requested artifact directly",
        "keep work in the main task",
        "do not create plans, Tickets, subagents",
        "stop when the requested result works",
    ]:
        assert_contains(router, marker, "normal-request minimum-scope routing")


def test_merge_and_archive_authority_requires_complete_safe_closeout():
    router = read(ROUTER_MD)
    archive = read(SKILLS / "archive" / "SKILL.md")
    for marker in [
        "one complete Git closeout",
        "wait for required CI",
        "revision-attributable post-merge monitoring",
        "fast-forward the local default branch",
        "safely remove the isolated worktree and local branch",
        "does not authorize local installation or task archival",
    ]:
        assert_contains(router, marker, "always-loaded merge closeout")
    for marker in [
        "## Land And Clean Up",
        "Only after landed verification and applicable monitoring pass",
        "remove a clean isolated worktree",
        "Generic merge or land requests stop after Git closeout",
        "Preserve the task branch/worktree",
    ]:
        assert_contains(archive, marker, "archive closeout")
