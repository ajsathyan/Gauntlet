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
    land = read(SKILLS / "land" / "SKILL.md")
    for marker in [
        "invokes the installed `land` skill",
        "Default to local `git` and `gh`",
        "Generic merge authority does not authorize local installation or task archival",
    ]:
        assert_contains(router, marker, "always-loaded merge closeout")
    for marker in [
        "Use local `git` and `gh` by default",
        "wait for required CI",
        "verify it contains the accepted head",
        "Run established push-to-default CI",
        "Fast-forward the checkout that owns the local default branch",
        "Remove a clean isolated worktree",
    ]:
        assert_contains(land, marker, "land closeout")
    for marker in [
        "Read `../land/SKILL.md` completely",
        "Complete the `land` skill",
        "Stop without archival if it does not pass",
    ]:
        assert_contains(archive, marker, "archive composition")
