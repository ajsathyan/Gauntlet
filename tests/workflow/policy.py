"""Router and skill policy checks."""

import json

from tests.workflow.fixtures import ROOT, ROUTER_MD, SKILLS, assert_contains, read


def test_package_and_plugin_identity():
    manifest = json.loads(read(ROOT / ".codex-plugin" / "plugin.json"))
    expected = {
        "name": "gauntlet",
        "version": "3.0.0",
        "description": "A lean implementation and release workflow for GPT-5.6 Sol in Codex.",
        "homepage": "https://github.com/ajsathyan/Gauntlet",
        "repository": "https://github.com/ajsathyan/Gauntlet",
        "keywords": [
            "codex", "gpt-5.6-sol", "product", "engineering", "verification", "release",
        ],
        "skills": "./skills/",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise AssertionError(f"unexpected plugin {key}: {manifest.get(key)!r}")
    interface = manifest.get("interface", {})
    expected_interface = {
        "displayName": "Gauntlet",
        "shortDescription": "Lean Codex workflow for GPT-5.6 Sol",
        "longDescription": "Proportional planning, orchestrated implementation, Verify, consistent pull requests, and explicit deployment accounting for Codex.",
        "websiteURL": "https://github.com/ajsathyan/Gauntlet",
    }
    for key, value in expected_interface.items():
        if interface.get(key) != value:
            raise AssertionError(f"unexpected plugin interface {key}: {interface.get(key)!r}")
    package = read(ROOT / "pyproject.toml")
    for marker in (
        'name = "gauntlet"',
        'version = "3.0.0"',
        'description = "A lean implementation and release workflow for GPT-5.6 Sol in Codex."',
    ):
        assert_contains(package, marker, "Python package identity")


def test_plugin_bundles_shared_skills():
    names = sorted(path.parent.name for path in SKILLS.glob("*/SKILL.md"))
    expected = sorted(
        [
            "adversarial-reviewer", "debugger", "design", "land",
            "orchestrate", "refactor-codebase", "refactor-performance", "researcher",
            "ship", "verify",
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
        "Always invoke `orchestrate` for implementation",
        "without another routine prompt",
        "Gauntlet has no merge queue",
    ):
        assert_contains(router, marker, "lifecycle policy")
