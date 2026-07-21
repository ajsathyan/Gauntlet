"""Portable workflow and plugin policy cases."""

import json

from tests.workflow.fixtures import ROOT, ROUTER_MD, SKILLS, assert_contains, read


def test_plugin_manifests_bundle_shared_skills():
    codex_manifest = json.loads(read(ROOT / ".codex-plugin" / "plugin.json"))
    if codex_manifest["name"] != "gauntlet-lite":
        raise AssertionError("Codex plugin manifest must use the Gauntlet Lite identity")
    if codex_manifest.get("skills") != "./skills/":
        raise AssertionError("Codex plugin manifest must bundle the shared skills directory")
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        assert_contains(
            read(path),
            f"name: {path.parent.name}",
            f"skill name for {path.parent.name}",
        )

    marketplace = json.loads(read(ROOT / ".agents" / "plugins" / "marketplace.json"))
    if marketplace["plugins"][0]["name"] != "gauntlet-lite":
        raise AssertionError("Codex marketplace must expose Gauntlet Lite")


def test_normal_requests_use_minimum_scope_before_design():
    router = read(ROUTER_MD)
    for marker in (
        "## Minimum scope",
        "bounded, low-consequence, reversible, directly checkable",
        "Deliver it directly in the main task",
        "run its smoke check",
    ):
        assert_contains(router, marker, "normal-request minimum-scope routing")


def test_merge_and_archive_authority_requires_complete_safe_closeout():
    router = read(ROUTER_MD)
    design = read(SKILLS / "design" / "SKILL.md")
    land = read(SKILLS / "land" / "SKILL.md")
    ship = read(SKILLS / "ship" / "SKILL.md")
    for marker in (
        "require the user to accept its exact `Acceptance` section",
        "merge to the default branch",
        "Do not request a second production acceptance",
        "ordinary declared production deployment",
    ):
        assert_contains(router, marker, "accepted lifecycle authority")
    for marker in (
        "No second acceptance is required",
        "Inspect repository automation",
        "waits for required CI",
        "tree-equivalent merge",
    ):
        assert_contains(land, marker, "land closeout")
    for marker in (
        "Do not request another acceptance",
        "Merge-triggered deployment proceeds automatically",
        "attributable production oracle",
        "rollback",
    ):
        assert_contains(ship, marker, "automatic production follow-through")
    assert_contains(design, "stop before implementation", "design acceptance gate")
