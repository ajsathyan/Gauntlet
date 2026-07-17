"""Installer migration and Codex preference workflow cases."""

import os
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from tests.workflow.fixtures import (
    ROOT,
    SCRIPTS,
    assert_contains,
    assert_not_contains,
    read,
)


def fake_codex_plugin_cli(agent_home, available=True):
    suffix = "available" if available else "unavailable"
    path = agent_home.parent / f".fake-codex-{agent_home.name}-{suffix}.py"
    if path.exists():
        return path
    plugin_rows = [
        {"pluginId": plugin, "installed": False, "enabled": False}
        for plugin in ["browser@openai-bundled", "computer-use@openai-bundled"]
    ] if available else []
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"PLUGINS = {plugin_rows!r}\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['plugin', 'list']:\n"
        "    print(json.dumps({'installed': [], 'available': PLUGINS}))\n"
        "    raise SystemExit(0)\n"
        "if args[:2] == ['plugin', 'add'] and '--help' in args:\n"
        "    raise SystemExit(0)\n"
        "if args[:2] == ['plugin', 'add'] and len(args) >= 3:\n"
        "    plugin = args[2]\n"
        "    if not any(row['pluginId'] == plugin for row in PLUGINS):\n"
        "        print(f'plugin unavailable: {plugin}', file=sys.stderr)\n"
        "        raise SystemExit(1)\n"
        "    home = os.environ.get('CODEX_HOME')\n"
        "    if not home:\n"
        "        print('CODEX_HOME is required', file=sys.stderr)\n"
        "        raise SystemExit(1)\n"
        "    with open(os.path.join(home, 'plugin-add.log'), 'a', encoding='utf-8') as handle:\n"
        "        handle.write(plugin + '\\n')\n"
        "    print(json.dumps({'pluginId': plugin}))\n"
        "    raise SystemExit(0)\n"
        "print('unsupported fake Codex invocation', file=sys.stderr)\n"
        "raise SystemExit(2)\n"
    )
    path.chmod(0o755)
    return path


def run_install(agent_home, target="codex", extra_args=None, check=True, plugins_available=True):
    env = os.environ.copy()
    env["AGENT_HOME"] = str(agent_home)
    env["GAUNTLET_SKIP_GIT_HOOKS"] = "1"
    if target == "codex":
        env["GAUNTLET_CODEX_BIN"] = str(fake_codex_plugin_cli(agent_home, plugins_available))
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


def _assert_clean_preferences(root):
    clean_home = root / "clean"
    clean_home.mkdir()
    run_install(clean_home, extra_args=["--check"])
    if any(clean_home.iterdir()):
        raise AssertionError("Codex install --check should not create or modify agent-home files")
    run_install(clean_home)
    clean_config = read(clean_home / "config.toml")
    if (
        clean_config.count('model_verbosity = "low"') != 1
        or clean_config.count('personality = "none"') != 1
        or clean_config.count('model_reasoning_summary = "concise"') != 1
    ):
        raise AssertionError("new Codex config should contain each Gauntlet preference exactly once")
    if clean_config.count("[agents]") != 1 or clean_config.count("max_threads = 24") != 1:
        raise AssertionError("new Codex config should set the Gauntlet agent thread cap exactly once")
    assert_contains(
        clean_config,
        "[desktop]\nshow-context-window-usage = true",
        "Gauntlet context-window visibility default",
    )
    for plugin in ["browser@openai-bundled", "computer-use@openai-bundled"]:
        assert_contains(
            clean_config,
            f'[plugins."{plugin}"]\nenabled = true',
            f"Gauntlet {plugin} enablement default",
        )
    if sorted((clean_home / "plugin-add.log").read_text().splitlines()) != [
        "browser@openai-bundled",
        "computer-use@openai-bundled",
    ]:
        raise AssertionError("Codex install should install both required bundled plugins")
    run_install(clean_home)
    if read(clean_home / "config.toml") != clean_config:
        raise AssertionError("Codex preference reinstall should be byte-idempotent")


def _assert_conflicting_preferences(root):
    conflict_home = root / "conflict"
    conflict_home.mkdir()
    conflict_config = conflict_home / "config.toml"
    original = (
        'model = "custom"\nmodel_verbosity = "high" # keep comment\n'
        'model_reasoning_summary = "detailed" # keep summary comment\n\n'
        'notify = ["custom-notifier", "turn-ended"]\n'
        'approval_policy = "never"\nsandbox_mode = "danger-full-access"\n\n'
        '[agents]\nmax_threads = 8 # keep agent comment\n\n'
        '[desktop]\nshow-context-window-usage = false # keep desktop comment\n'
        'notifications-turn-mode = "always"\ncomposerEnterBehavior = "cmdIfMultiline"\n\n'
        '[plugins."browser@openai-bundled"]\nenabled = false # keep browser comment\n\n'
        '[plugins."computer-use@openai-bundled"]\nenabled = false # keep computer comment\n\n'
        '[plugins."unrelated@test"]\nenabled = false\n\n'
        '[features]\ngoals = true\n'
    )
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
        'model_reasoning_summary = "detailed"',
        'model_reasoning_summary = "concise"',
        "agents.max_threads = 8",
        "agents.max_threads = 24",
        "desktop.show-context-window-usage = false",
        "desktop.show-context-window-usage = true",
        'plugins."browser@openai-bundled".enabled = false',
        'plugins."browser@openai-bundled".enabled = true',
        'plugins."computer-use@openai-bundled".enabled = false',
        'plugins."computer-use@openai-bundled".enabled = true',
        "--codex-preferences gauntlet",
        "--codex-preferences existing",
    ]:
        assert_contains(result.stderr, marker, "Codex preference conflict report")

    run_install(conflict_home, extra_args=["--codex-preferences", "gauntlet"])
    resolved = conflict_config.read_text()
    for marker, label in [
        ('model = "custom"', "Codex unrelated config preservation"),
        ('model_verbosity = "low"', "Gauntlet verbosity choice"),
        ('personality = "none"', "Gauntlet personality insertion"),
        ('model_reasoning_summary = "concise"', "Gauntlet reasoning summary choice"),
        ("max_threads = 24", "Gauntlet agent thread choice"),
        ("show-context-window-usage = true", "Gauntlet context visibility choice"),
        ("# keep comment", "Codex config trailing-comment preservation"),
        ("# keep agent comment", "Codex agent config trailing-comment preservation"),
        ("# keep summary comment", "Codex summary trailing-comment preservation"),
        ("# keep desktop comment", "Codex desktop trailing-comment preservation"),
        ("# keep browser comment", "Codex Browser trailing-comment preservation"),
        ("# keep computer comment", "Codex Computer Use trailing-comment preservation"),
    ]:
        assert_contains(resolved, marker, label)
    if resolved.count("enabled = true") < 2:
        raise AssertionError("Gauntlet plugin choice should enable both required plugins")
    for preserved in [
        'notify = ["custom-notifier", "turn-ended"]',
        'approval_policy = "never"',
        'sandbox_mode = "danger-full-access"',
        'notifications-turn-mode = "always"',
        'composerEnterBehavior = "cmdIfMultiline"',
        '[plugins."unrelated@test"]\nenabled = false',
    ]:
        assert_contains(resolved, preserved, "unrelated Codex setting preservation")
    assert_contains(resolved, "[features]\ngoals = true", "Codex table preservation")
    if conflict_config.stat().st_mode & 0o777 != 0o600:
        raise AssertionError("Codex config update should preserve permissions")


def _assert_preference_choices(root):
    combined_home = root / "combined-conflict"
    combined_home.mkdir()
    combined_agents = combined_home / "AGENTS.md"
    combined_config = combined_home / "config.toml"
    combined_agents.write_text("# Existing voice\n\nAlways be expansive.\n")
    combined_config.write_text('personality = "friendly"\n')
    combined = run_install(combined_home, check=False)
    if combined.returncode == 0:
        raise AssertionError("combined instruction and preference conflicts should stop installation")
    for marker in [
        "Existing user instructions require conflict review",
        "Codex preference conflict requires a user choice",
    ]:
        assert_contains(combined.stderr, marker, "combined Codex conflict report")
    if (combined_home / "gauntlet").exists():
        raise AssertionError("combined Codex conflicts must stop before payload mutation")

    existing_home = root / "existing"
    existing_home.mkdir()
    existing_config = existing_home / "config.toml"
    existing_original = (
        'model_verbosity = "high"\npersonality = "friendly"\nmodel_reasoning_summary = "detailed"\n\n'
        '[agents]\nmax_threads = 8\n\n'
        '[desktop]\nshow-context-window-usage = false\n\n'
        '[plugins."browser@openai-bundled"]\nenabled = false\n\n'
        '[plugins."computer-use@openai-bundled"]\nenabled = false\n'
    )
    existing_config.write_text(existing_original)
    run_install(existing_home, extra_args=["--codex-preferences", "existing"])
    if existing_config.read_text() != existing_original:
        raise AssertionError("existing Codex preference choice should preserve all values byte-for-byte")
    if (existing_home / "plugin-add.log").exists():
        raise AssertionError("existing Codex plugin choices should not install disabled plugins")

    unavailable_home = root / "plugins-unavailable"
    unavailable_home.mkdir()
    unavailable = run_install(unavailable_home, check=False, plugins_available=False)
    if unavailable.returncode == 0 or "required Codex plugin is unavailable" not in unavailable.stderr:
        raise AssertionError("missing required bundled plugins should fail preflight")
    if any(unavailable_home.iterdir()):
        raise AssertionError("plugin availability preflight must stop before any agent-home mutation")

    unsupported_home = root / "unsupported-agents"
    unsupported_home.mkdir()
    unsupported_config = unsupported_home / "config.toml"
    unsupported_original = "agents.max_threads = 8\n"
    unsupported_config.write_text(unsupported_original)
    unsupported = run_install(unsupported_home, check=False)
    if unsupported.returncode == 0 or "unsupported top-level agents syntax" not in unsupported.stderr:
        raise AssertionError("unsupported Codex agents syntax should fail safely")
    if unsupported_config.read_text() != unsupported_original or (unsupported_home / "gauntlet").exists():
        raise AssertionError("unsupported Codex agents syntax must stop before any mutation")

    agents_home = root / "agents-table"
    agents_home.mkdir()
    agents_config = agents_home / "config.toml"
    agents_config.write_text('[agents]\nmax_depth = 1\n\n[features]\ngoals = true\n')
    run_install(agents_home)
    agents_result = agents_config.read_text()
    assert_contains(agents_result, "[agents]\nmax_depth = 1\nmax_threads = 24", "existing agents table insertion")
    assert_contains(agents_result, "[features]\ngoals = true", "table following agents preservation")

    skip_home = root / "skip"
    skip_home.mkdir()
    skip_config = skip_home / "config.toml"
    skip_original = 'model_verbosity = "high"\n'
    skip_config.write_text(skip_original)
    run_install(skip_home, extra_args=["--codex-preferences", "skip"])
    if skip_config.read_text() != skip_original:
        raise AssertionError("skipped Codex preferences should not modify config.toml")
    if (skip_home / "plugin-add.log").exists():
        raise AssertionError("skipped Codex preferences should not install plugins")


def _assert_preference_file_formats(root):
    linked_home = root / "linked"
    linked_home.mkdir()
    linked_target = root / "shared-config.toml"
    linked_target.write_text(
        'model_verbosity = "low"\npersonality = "none"\nmodel_reasoning_summary = "concise"\n\n'
        '[agents]\nmax_threads = 24\n\n[desktop]\nshow-context-window-usage = true\n\n'
        '[plugins."browser@openai-bundled"]\nenabled = true\n\n'
        '[plugins."computer-use@openai-bundled"]\nenabled = true\n'
    )
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
    for marker in [
        b'personality_notes = "keep"',
        b'model_verbosity = "low"',
        b'personality = "none"',
        b'model_reasoning_summary = "concise"',
        b'[agents]',
        b'max_threads = 24',
        b'[desktop]',
        b'show-context-window-usage = true',
        b'[plugins."browser@openai-bundled"]',
        b'[plugins."computer-use@openai-bundled"]',
    ]:
        if marker not in crlf_result:
            raise AssertionError(f"Codex CRLF config missing preserved or inserted value: {marker!r}")
    if b"\n" in crlf_result.replace(b"\r\n", b""):
        raise AssertionError("Codex config insertion should preserve CRLF newline style")


def test_codex_install_merges_preferences_without_silent_overwrite():
    if not (ROOT / ".git").exists():
        return

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _assert_clean_preferences(root)
        _assert_conflicting_preferences(root)
        _assert_preference_choices(root)
        _assert_preference_file_formats(root)
    test_manifest_install_syncs_runtime_and_preserves_unmanaged_or_modified_stale_files()


def test_manifest_install_syncs_runtime_and_preserves_unmanaged_or_modified_stale_files():
    with tempfile.TemporaryDirectory() as tmp:
        agent_home = Path(tmp) / "agent-home"
        stale = agent_home / "gauntlet" / "scripts" / "test-context-audit.py"
        stale.parent.mkdir(parents=True)
        stale.write_bytes((SCRIPTS / "test-context-audit.py").read_bytes())
        unmanaged = agent_home / "gauntlet" / "scripts" / "user-tool.py"
        unmanaged.write_text("keep me\n")
        modified_stale = agent_home / "gauntlet" / "scripts" / "test-eval-run.py"
        modified_stale.write_text("locally modified\n")

        first = run_install(agent_home)
        if stale.exists():
            raise AssertionError("an unchanged previous-layout development test should be retired")
        if unmanaged.read_text() != "keep me\n":
            raise AssertionError("manifest sync must preserve unmanaged payload paths")
        if modified_stale.read_text() != "locally modified\n":
            raise AssertionError("manifest sync must preserve a modified stale managed file")
        assert_contains(first.stderr, "preserved modified stale managed file", "modified stale finding")

        installed = agent_home / "gauntlet"
        if (installed / "scripts" / "check-gauntlet-workflow.py").exists():
            raise AssertionError("the development workflow checker must not be installed")
        remaining_tests = sorted(
            path.name for path in (installed / "scripts").glob("test-*.py")
        )
        if remaining_tests != ["test-eval-run.py", "test-plan.py"]:
            raise AssertionError("only the production test-plan CLI and preserved modified stale test may remain")
        if not (installed / "scripts" / "test-plan.py").is_file():
            raise AssertionError("the externally referenced test-plan CLI must remain installed")
        for forbidden in [installed / "tests", installed / "ui", installed / "node_modules"]:
            if forbidden.exists():
                raise AssertionError(f"development payload must not be installed: {forbidden}")
        if list(installed.rglob("node_modules")):
            raise AssertionError("nested node_modules must not be installed")
        if not (installed / "scripts" / "thread_titles.py").is_file():
            raise AssertionError("runtime dependency closure must include thread_titles.py")
        source_modules = {
            path.relative_to(SCRIPTS).as_posix()
            for path in (SCRIPTS / "gauntletlib").rglob("*.py")
        }
        installed_modules = {
            path.relative_to(installed / "scripts").as_posix()
            for path in (installed / "scripts" / "gauntletlib").rglob("*.py")
        }
        if installed_modules != source_modules:
            raise AssertionError("installed runtime must include every gauntletlib module")

        receipt_before = (installed / ".install-manifest.json").read_bytes()
        agents_before = (agent_home / "AGENTS.md").read_bytes()
        run_install(agent_home)
        if (installed / ".install-manifest.json").read_bytes() != receipt_before:
            raise AssertionError("manifest ownership receipt should be idempotent")
        if (agent_home / "AGENTS.md").read_bytes() != agents_before:
            raise AssertionError("manifest reinstall should preserve byte-idempotent router output")
        copied_env = os.environ.copy()
        copied_env["AGENT_HOME"] = str(agent_home)
        copied_env["GAUNTLET_SKIP_GIT_HOOKS"] = "1"
        copied_env["GAUNTLET_CODEX_BIN"] = str(fake_codex_plugin_cli(agent_home))
        copied_reinstall = subprocess.run(
            [str(installed / "scripts" / "install.sh"), "--target", "codex"],
            cwd=installed,
            env=copied_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if copied_reinstall.returncode != 0:
            raise AssertionError(
                f"copied-layout reinstall failed:\n{copied_reinstall.stdout}\n{copied_reinstall.stderr}"
            )

        manifest = json.loads((installed / "MANIFEST").read_text())
        for row in manifest["entries"]:
            path = agent_home / row["destination"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
                raise AssertionError(f"installed manifest hash mismatch: {row['destination']}")
        verify = subprocess.run(
            [
                "python3",
                str(installed / "scripts" / "gauntlet.py"),
                "install",
                "verify",
                "--target",
                "codex",
                "--agent-home",
                str(agent_home),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if verify.returncode != 0 or "Install verify: pass" not in verify.stdout:
            raise AssertionError(f"copied-layout verify failed:\n{verify.stdout}\n{verify.stderr}")
        copied_cli = subprocess.run(
            ["python3", str(installed / "scripts" / "gauntlet.py"), "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if copied_cli.returncode != 0:
            raise AssertionError(f"copied-layout CLI smoke failed: {copied_cli.stderr}")
