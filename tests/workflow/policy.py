"""Router and skill policy checks."""

import json

from tests.workflow.fixtures import ROOT, ROUTER_MD, SKILLS, assert_contains, read


def test_plugin_manifests_bundle_shared_skills():
    manifest = json.loads(read(ROOT / ".codex-plugin" / "plugin.json"))
    if manifest["name"] != "gauntlet-lite" or manifest.get("skills") != "./skills/":
        raise AssertionError("plugin manifest must expose shared Gauntlet Lite skills")
    names = sorted(path.parent.name for path in SKILLS.glob("*/SKILL.md"))
    expected = sorted(
        [
            "adversarial-reviewer", "debugger", "design", "land",
            "refactor-codebase", "refactor-performance", "researcher", "ship", "verify",
        ]
    )
    if names != expected:
        raise AssertionError(f"unexpected installed skill surface: {names}")


def test_normal_requests_and_research_use_minimum_scope():
    router = read(ROUTER_MD)
    for marker in ("**Normal:**", "**Research:**", "Use the lightest workflow"):
        assert_contains(router, marker, "minimum-scope routing")


def test_lifecycle_authority_and_six_lenses():
    router = read(ROUTER_MD)
    reviewer = read(SKILLS / "adversarial-reviewer" / "SKILL.md")
    for lens in ("Product", "Engineering", "Design", "Analytics", "QA", "Performance"):
        assert_contains(reviewer, f"**{lens}:**", "six-lens review")
    for marker in (
        "main agent reviews",
        "Show every material recommendation",
        "without another routine prompt",
        "Gauntlet has no merge queue",
    ):
        assert_contains(router, marker, "lifecycle policy")
