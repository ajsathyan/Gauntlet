"""Installer migration and Codex preference workflow cases."""

import os
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from scripts.gauntletlib.install.manifest import (
    preflight_generated_payload,
    preflight_product_cutover,
    sync_payload,
    uninstall_payload,
)
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


def fake_sensor_tools_installer(agent_home):
    path = agent_home.parent / f".fake-sensor-tools-{agent_home.name}.py"
    if path.exists():
        return path
    path.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "home = Path(args[args.index('--agent-home') + 1])\n"
        "home.mkdir(parents=True, exist_ok=True)\n"
        "(home / 'sensor-tools-install.log').write_text(' '.join(args) + '\\n')\n"
    )
    path.chmod(0o755)
    return path


def run_install(
    agent_home,
    target="codex",
    extra_args=None,
    check=True,
    plugins_available=True,
    sensor_tools=False,
):
    env = os.environ.copy()
    env["AGENT_HOME"] = str(agent_home)
    env["GAUNTLET_SKIP_GIT_HOOKS"] = "1"
    if target == "codex":
        env["GAUNTLET_CODEX_BIN"] = str(fake_codex_plugin_cli(agent_home, plugins_available))
    if sensor_tools:
        env["GAUNTLET_SENSOR_TOOLS_INSTALLER"] = str(
            fake_sensor_tools_installer(agent_home)
        )
    args = [str(SCRIPTS / "install.sh"), "--target", target]
    args.extend(extra_args or [])
    if (
        not sensor_tools
        and "--with-sensor-tools" not in args
        and "--without-sensor-tools" not in args
    ):
        args.append("--without-sensor-tools")
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
        personal = "Keep this user-owned instruction exactly.\n"
        (agent_home / "gauntlet" / "AGENTS.md").write_text(legacy)
        (agent_home / "AGENTS.md").write_text(personal + legacy)

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
    test_manifest_sync_rejects_unsafe_paths_symlinks_and_skill_collisions()
    test_manifest_preflight_rejects_bad_ancestors_and_fixed_generated_paths()
    test_product_cutover_guard_has_an_explicit_portable_detection_boundary()
    test_receipt_upgrade_and_uninstall_remove_only_unchanged_owned_files()
    test_manifest_sync_rejects_modified_owned_and_unowned_current_collisions()
    test_generated_router_preflight_preserves_collisions_and_allows_upgrade()
    test_default_install_requests_machine_local_sensor_tools_without_network()
    test_codex_uninstall_preserves_user_bytes_config_and_modified_payload()


def test_codex_hook_install_preserves_user_state_and_fails_closed():
    marker = "Gauntlet repository workflow mode"

    def owned_groups(agent_home):
        payload = json.loads((agent_home / "hooks.json").read_text())
        result = {}
        for event, groups in payload["hooks"].items():
            for group in groups:
                if any(
                    handler.get("statusMessage") == marker
                    for handler in group["hooks"]
                ):
                    result[event] = group
        return result

    def assert_preflight_rejected(agent_home, expected):
        before = {
            path.relative_to(agent_home): path.read_bytes()
            for path in agent_home.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        result = run_install(agent_home, check=False)
        if result.returncode == 0 or expected not in result.stderr:
            raise AssertionError(
                f"unsafe hooks state should fail for {expected}:\n"
                f"{result.stdout}\n{result.stderr}"
            )
        after = {
            path.relative_to(agent_home): path.read_bytes()
            for path in agent_home.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        if after != before or (agent_home / "gauntlet").exists():
            raise AssertionError("hooks preflight rejection must precede payload mutation")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        clean_home = root / "clean"
        clean_home.mkdir()
        run_install(clean_home)
        hooks_path = clean_home / "hooks.json"
        first_bytes = hooks_path.read_bytes()
        groups = owned_groups(clean_home)
        if set(groups) != {"SessionStart", "PreToolUse"}:
            raise AssertionError("install should add exactly two Gauntlet-owned hook groups")
        runtime = str(clean_home / "gauntlet" / "scripts" / "workflow-mode.py")
        for event, matcher in [
            ("SessionStart", "startup|resume|clear|compact"),
            ("PreToolUse", ".*"),
        ]:
            group = groups[event]
            if group["matcher"] != matcher or len(group["hooks"]) != 1:
                raise AssertionError(f"{event} should use the required bounded matcher")
            command = group["hooks"][0]["command"]
            if runtime not in command or str(ROOT) in command:
                raise AssertionError("owned hooks must reference only the installed runtime")
        run_install(clean_home)
        if hooks_path.read_bytes() != first_bytes:
            raise AssertionError("repeat hook installation must be byte-idempotent")

        existing_home = root / "existing"
        existing_home.mkdir()
        original = {
            "custom": {"keep": ["value", 7]},
            "hooks": {
                "SessionStart": [
                    {
                        "matcher": "startup",
                        "customGroup": True,
                        "hooks": [
                            {
                                "type": "command",
                                "command": "/usr/bin/printf user",
                                "async": True,
                                "timeoutSec": 11,
                                "customHandler": "keep",
                            }
                        ],
                    }
                ],
                "PostToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "/usr/bin/true",
                                "async": False,
                            }
                        ],
                    }
                ],
            },
        }
        existing_path = existing_home / "hooks.json"
        existing_path.write_text(json.dumps(original, indent=4) + "\n")
        existing_path.chmod(0o600)
        run_install(existing_home)
        installed = json.loads(existing_path.read_text())
        if installed["custom"] != original["custom"]:
            raise AssertionError("unrelated top-level hook fields must survive")
        if installed["hooks"]["PostToolUse"] != original["hooks"]["PostToolUse"]:
            raise AssertionError("unrelated hook events and handlers must survive")
        if installed["hooks"]["SessionStart"][0] != original["hooks"]["SessionStart"][0]:
            raise AssertionError("existing event groups must survive in order and semantics")
        if existing_path.stat().st_mode & 0o777 != 0o600:
            raise AssertionError("hook installation must preserve file permissions")

        malformed_home = root / "malformed"
        malformed_home.mkdir()
        (malformed_home / "hooks.json").write_text("{bad json")
        assert_preflight_rejected(malformed_home, "malformed JSON")

        unsupported_home = root / "unsupported"
        unsupported_home.mkdir()
        (unsupported_home / "hooks.json").write_text(
            json.dumps({"hooks": {"SessionStart": {"hooks": []}}})
        )
        assert_preflight_rejected(unsupported_home, "must be an array")

        symlink_home = root / "symlink"
        symlink_home.mkdir()
        outside = root / "outside-hooks.json"
        outside.write_text(json.dumps({"hooks": {}}))
        (symlink_home / "hooks.json").symlink_to(outside)
        assert_preflight_rejected(symlink_home, "symbolic link")

        duplicate_home = root / "duplicate"
        duplicate_home.mkdir()
        duplicate_payload = json.loads(
            first_bytes.decode().replace(str(clean_home), str(duplicate_home))
        )
        duplicate_payload["hooks"]["SessionStart"].append(
            duplicate_payload["hooks"]["SessionStart"][-1]
        )
        (duplicate_home / "hooks.json").write_text(json.dumps(duplicate_payload))
        assert_preflight_rejected(duplicate_home, "duplicate")

        drift_home = root / "drift"
        drift_home.mkdir()
        drift_payload = json.loads(first_bytes)
        drift_payload["hooks"]["PreToolUse"][-1]["matcher"] = "Bash"
        (drift_home / "hooks.json").write_text(json.dumps(drift_payload))
        assert_preflight_rejected(drift_home, "modified")

        missing_payload = json.loads(first_bytes)
        missing_payload["hooks"]["SessionStart"].pop()
        hooks_path.write_text(json.dumps(missing_payload))
        missing = subprocess.run(
            [
                "python3",
                str(clean_home / "gauntlet" / "scripts" / "gauntlet.py"),
                "install",
                "verify",
                "--target",
                "codex",
                "--agent-home",
                str(clean_home),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if missing.returncode == 0 or "missing_codex_hook" not in missing.stdout:
            raise AssertionError("installed verification must detect a missing owned hook")

        verification_drift = json.loads(first_bytes)
        verification_drift["hooks"]["PreToolUse"][-1]["hooks"][0][
            "command"
        ] = "python3 /tmp/not-the-installed-runtime.py"
        hooks_path.write_text(json.dumps(verification_drift))
        drifted = subprocess.run(
            [
                "python3",
                str(clean_home / "gauntlet" / "scripts" / "gauntlet.py"),
                "install",
                "verify",
                "--target",
                "codex",
                "--agent-home",
                str(clean_home),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if drifted.returncode == 0 or "invalid_codex_hook" not in drifted.stdout:
            raise AssertionError("installed verification must detect owned hook drift")


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
            [
                str(installed / "scripts" / "install.sh"),
                "--target",
                "codex",
                "--without-sensor-tools",
            ],
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


def test_manifest_sync_rejects_unsafe_paths_symlinks_and_skill_collisions():
    def write_manifest(root, source, destination, payload=b"runtime\n"):
        source_path = root / source
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        (root / "MANIFEST").write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": [
                        {
                            "destination": destination,
                            "executable": False,
                            "sha256": digest,
                            "source": source,
                        }
                    ],
                    "generatedDestinations": [
                        "gauntlet/AGENTS.md",
                        "gauntlet/MANIFEST",
                        "gauntlet/.install-manifest.json",
                    ],
                    "legacyManaged": [],
                }
            )
        )

    def assert_rejected(root, home):
        try:
            sync_payload(root, home)
        except ValueError:
            return
        raise AssertionError("unsafe manifest sync should fail closed")

    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp)

        traversal_root = sandbox / "traversal-root"
        traversal_root.mkdir()
        outside_source = sandbox / "outside-source"
        outside_source.write_bytes(b"runtime\n")
        write_manifest(
            traversal_root,
            "../outside-source",
            "gauntlet/runtime.txt",
        )
        traversal_home = sandbox / "traversal-home"
        assert_rejected(traversal_root, traversal_home)
        if traversal_home.exists():
            raise AssertionError("source traversal rejection must precede agent-home mutation")

        absolute_root = sandbox / "absolute-root"
        absolute_root.mkdir()
        outside_destination = sandbox / "outside-destination"
        write_manifest(
            absolute_root,
            "scripts/runtime.py",
            str(outside_destination),
        )
        absolute_home = sandbox / "absolute-home"
        assert_rejected(absolute_root, absolute_home)
        if outside_destination.exists() or absolute_home.exists():
            raise AssertionError("absolute destination rejection must precede any mutation")

        symlink_root = sandbox / "symlink-root"
        symlink_root.mkdir()
        write_manifest(
            symlink_root,
            "scripts/runtime.py",
            "gauntlet/scripts/runtime.py",
        )
        symlink_home = sandbox / "symlink-home"
        symlink_home.mkdir()
        escaped = sandbox / "escaped"
        escaped.mkdir()
        (symlink_home / "gauntlet").symlink_to(escaped, target_is_directory=True)
        assert_rejected(symlink_root, symlink_home)
        if any(escaped.iterdir()):
            raise AssertionError("redirecting gauntlet parent symlink must not receive writes")

        collision_root = sandbox / "collision-root"
        collision_root.mkdir()
        write_manifest(
            collision_root,
            "skills/example/SKILL.md",
            "skills/example/SKILL.md",
        )
        collision_home = sandbox / "collision-home"
        collision = collision_home / "skills" / "example" / "SKILL.md"
        collision.parent.mkdir(parents=True)
        collision.write_text("user owned\n")
        before = collision.read_bytes()
        assert_rejected(collision_root, collision_home)
        if collision.read_bytes() != before or (collision_home / "gauntlet").exists():
            raise AssertionError("unowned skill collision must abort before any payload mutation")

        receipt_root = sandbox / "receipt-root"
        receipt_root.mkdir()
        write_manifest(
            receipt_root,
            "scripts/runtime.py",
            "gauntlet/scripts/runtime.py",
        )
        receipt_home = sandbox / "receipt-home"
        receipt_collision = receipt_home / "gauntlet" / "scripts" / "runtime.py"
        receipt_collision.parent.mkdir(parents=True)
        receipt_collision.write_text("unowned new destination\n")
        (receipt_home / "gauntlet" / ".install-manifest.json").write_text(
            json.dumps({"schemaVersion": "1.0", "entries": [], "manifestSha256": "0" * 64})
        )
        receipt_before = receipt_collision.read_bytes()
        assert_rejected(receipt_root, receipt_home)
        if receipt_collision.read_bytes() != receipt_before:
            raise AssertionError("a newly added receipt collision must remain untouched")

        invalid_receipt_home = sandbox / "invalid-receipt-home"
        receipt_path = invalid_receipt_home / "gauntlet" / ".install-manifest.json"
        receipt_path.parent.mkdir(parents=True)
        receipt_path.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": [{"destination": "../escape", "sha256": "0" * 64}],
                }
            )
        )
        assert_rejected(receipt_root, invalid_receipt_home)
        if (sandbox / "escape").exists():
            raise AssertionError("receipt traversal must not touch an outside path")


def test_manifest_preflight_rejects_bad_ancestors_and_fixed_generated_paths():
    def manifest_row(root, name, destination):
        source = root / "scripts" / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(name)
        return {
            "destination": destination,
            "executable": False,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "source": f"scripts/{name}",
        }

    def write_manifest(root, entries, generated=None, legacy=None):
        (root / "MANIFEST").write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": entries,
                    "generatedDestinations": generated
                    if generated is not None
                    else [
                        "gauntlet/AGENTS.md",
                        "gauntlet/MANIFEST",
                        "gauntlet/.install-manifest.json",
                    ],
                    "legacyManaged": legacy or [],
                }
            )
        )

    def assert_rejected(root, home):
        try:
            sync_payload(root, home)
        except (OSError, ValueError):
            return
        raise AssertionError("invalid destination preflight should reject installation")

    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp)
        ancestor_root = sandbox / "ancestor-root"
        ancestor_root.mkdir()
        rows = [
            manifest_row(ancestor_root, "first.py", "gauntlet/first.py"),
            manifest_row(ancestor_root, "second.py", "gauntlet/scripts/second.py"),
        ]
        write_manifest(ancestor_root, rows)
        ancestor_home = sandbox / "ancestor-home"
        ancestor_home.mkdir()
        (ancestor_home / "gauntlet").mkdir()
        (ancestor_home / "gauntlet" / "scripts").write_text("regular ancestor\n")
        assert_rejected(ancestor_root, ancestor_home)
        if (ancestor_home / "gauntlet" / "first.py").exists():
            raise AssertionError("regular-file ancestor must reject before the first payload copy")

        manifest_root = sandbox / "manifest-root"
        manifest_root.mkdir()
        manifest_row_value = manifest_row(
            manifest_root,
            "runtime.py",
            "gauntlet/scripts/runtime.py",
        )
        write_manifest(manifest_root, [manifest_row_value])
        manifest_home = sandbox / "manifest-home"
        (manifest_home / "gauntlet" / "MANIFEST").mkdir(parents=True)
        assert_rejected(manifest_root, manifest_home)
        if (manifest_home / "gauntlet" / "scripts" / "runtime.py").exists():
            raise AssertionError("MANIFEST directory collision must reject before payload mutation")

        metadata_root = sandbox / "metadata-root"
        metadata_root.mkdir()
        metadata_row = manifest_row(
            metadata_root,
            "runtime.py",
            "gauntlet/scripts/runtime.py",
        )
        stale_payload = b"stale managed payload\n"
        stale_sha = hashlib.sha256(stale_payload).hexdigest()
        write_manifest(metadata_root, [metadata_row], generated=[])
        metadata_home = sandbox / "metadata-home"
        stale = metadata_home / "gauntlet" / "scripts" / "stale.py"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(stale_payload)
        outside_receipt = sandbox / "outside-receipt.json"
        outside_receipt.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": [
                        {
                            "destination": "gauntlet/scripts/stale.py",
                            "sha256": stale_sha,
                        }
                    ],
                    "manifestSha256": "0" * 64,
                }
            )
        )
        (metadata_home / "gauntlet" / ".install-manifest.json").symlink_to(
            outside_receipt
        )
        assert_rejected(metadata_root, metadata_home)
        if stale.read_bytes() != stale_payload:
            raise AssertionError("malformed generated metadata must reject before stale deletion")


def test_product_cutover_guard_has_an_explicit_portable_detection_boundary():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agent_home = root / "agent-home"
        receipt = agent_home / "gauntlet" / ".install-manifest.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": [
                        {
                            "destination": "gauntlet/scripts/gauntletlib/run/controller.py",
                            "sha256": "0" * 64,
                        }
                    ],
                    "manifestSha256": "1" * 64,
                }
            )
        )

        try:
            preflight_product_cutover(agent_home, [])
        except ValueError as error:
            assert_contains(
                str(error),
                "local-docs/executions/*/manifest.json",
                "cutover detection boundary",
            )
        else:
            raise AssertionError("controller-era upgrade must require a scan root or confirmation")

        project = root / "project"
        complete = project / "local-docs" / "executions" / "DONE" / "manifest.json"
        complete.parent.mkdir(parents=True)
        complete.write_text(json.dumps({"state": "complete"}))
        if preflight_product_cutover(agent_home, [project]):
            raise AssertionError("complete historical runs should not block product cutover")

        leases = project / "local-docs" / "epic-launches"
        leases.mkdir(parents=True)
        live_lease = leases / "DONE.merge-lease.json"
        live_lease.write_text(
            json.dumps(
                {
                    "schemaVersion": "gauntlet.epic-merge-lease.v1",
                    "coverageSha256": "a" * 64,
                    "epicId": "DONE",
                    "candidateHead": "b" * 40,
                    "baseHead": "c" * 40,
                    "baseRef": "origin/main",
                }
            )
        )
        try:
            preflight_product_cutover(agent_home, [project])
        except ValueError as error:
            assert_contains(str(error), "DONE.merge-lease.json", "live merge lease rejection")
        else:
            raise AssertionError("a live merge lease must block even when its Run is complete")

        live_lease.write_text(
            json.dumps(
                {
                    "schemaVersion": "gauntlet.epic-merge-lease.v1",
                    "status": "released",
                }
            )
        )
        findings = preflight_product_cutover(agent_home, [project])
        if len(findings) != 1 or "released historical controller merge lease" not in findings[0]:
            raise AssertionError("a clearly released historical merge lease should be preserved")

        live_lease.write_text("{malformed")
        try:
            preflight_product_cutover(agent_home, [project])
        except ValueError as error:
            assert_contains(str(error), "Cannot determine controller merge lease state", "malformed lease rejection")
        else:
            raise AssertionError("a malformed merge lease must fail closed")
        live_lease.unlink()

        live = project / "local-docs" / "executions" / "LIVE" / "manifest.json"
        live.parent.mkdir(parents=True)
        live.write_text(json.dumps({"state": "executing"}))
        try:
            preflight_product_cutover(agent_home, [project])
        except ValueError as error:
            assert_contains(str(error), "LIVE (executing)", "live controller run rejection")
        else:
            raise AssertionError("detectable live controller work must block product cutover")
        wired = run_install(
            agent_home,
            extra_args=[
                "--check",
                "--codex-preferences",
                "skip",
                "--cutover-project-root",
                str(project),
            ],
            check=False,
        )
        if wired.returncode == 0:
            raise AssertionError("install.sh must enforce the live controller cutover guard")
        assert_contains(wired.stderr, "LIVE (executing)", "installer cutover guard wiring")

        live.write_text(json.dumps({"state": "prd_verified"}))
        findings = preflight_product_cutover(agent_home, [project])
        if len(findings) != 1 or "preserved historical controller run" not in findings[0]:
            raise AssertionError("legacy controller history should be preserved and reported")


def test_receipt_upgrade_and_uninstall_remove_only_unchanged_owned_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source_root = root / "source"
        source = source_root / "scripts" / "new.py"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"new runtime\n")
        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        (source_root / "MANIFEST").write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": [
                        {
                            "destination": "gauntlet/scripts/new.py",
                            "executable": False,
                            "sha256": source_sha,
                            "source": "scripts/new.py",
                        }
                    ],
                    "generatedDestinations": [
                        "gauntlet/AGENTS.md",
                        "gauntlet/MANIFEST",
                        "gauntlet/.install-manifest.json",
                    ],
                    "legacyManaged": [],
                }
            )
        )
        upgrade_home = root / "upgrade-home"
        upgrade_scripts = upgrade_home / "gauntlet" / "scripts"
        upgrade_scripts.mkdir(parents=True)
        exact_stale = upgrade_scripts / "old.py"
        exact_stale.write_bytes(b"old owned\n")
        modified_stale = upgrade_scripts / "changed.py"
        modified_stale.write_bytes(b"user edit\n")
        (upgrade_home / "gauntlet" / ".install-manifest.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": [
                        {
                            "destination": "gauntlet/scripts/old.py",
                            "sha256": hashlib.sha256(b"old owned\n").hexdigest(),
                        },
                        {
                            "destination": "gauntlet/scripts/changed.py",
                            "sha256": hashlib.sha256(b"old changed\n").hexdigest(),
                        },
                    ],
                    "manifestSha256": "0" * 64,
                }
            )
        )
        upgrade_findings = sync_payload(source_root, upgrade_home)
        if exact_stale.exists():
            raise AssertionError("upgrade must retire byte-identical files from the prior receipt")
        if modified_stale.read_bytes() != b"user edit\n":
            raise AssertionError("upgrade must preserve modified files from the prior receipt")
        if (upgrade_scripts / "new.py").read_bytes() != b"new runtime\n":
            raise AssertionError("upgrade must install the current payload")
        if (
            len(upgrade_findings) != 1
            or "preserved modified stale managed file" not in upgrade_findings[0]
        ):
            raise AssertionError("upgrade must report modified stale preservation")

        agent_home = root / "agent-home"
        gauntlet = agent_home / "gauntlet"
        scripts = gauntlet / "scripts"
        scripts.mkdir(parents=True)
        unchanged = scripts / "retired.py"
        unchanged.write_bytes(b"owned unchanged\n")
        modified = scripts / "modified.py"
        modified.write_bytes(b"user changed this\n")
        unmanaged = scripts / "user-tool.py"
        unmanaged.write_bytes(b"user owned\n")
        generated_router = gauntlet / "AGENTS.md"
        generated_router.write_bytes(b"rendered router\n")
        installed_manifest = gauntlet / "MANIFEST"
        installed_manifest.write_bytes(b"old manifest\n")

        def sha(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()

        receipt = gauntlet / ".install-manifest.json"
        receipt.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": [
                        {
                            "destination": "gauntlet/scripts/retired.py",
                            "sha256": sha(unchanged),
                        },
                        {
                            "destination": "gauntlet/scripts/modified.py",
                            "sha256": hashlib.sha256(b"owned original\n").hexdigest(),
                        },
                    ],
                    "generatedEntries": [
                        {
                            "destination": "gauntlet/AGENTS.md",
                            "sha256": sha(generated_router),
                        }
                    ],
                    "manifestSha256": sha(installed_manifest),
                }
            )
        )
        findings = uninstall_payload(agent_home)
        if unchanged.exists() or generated_router.exists() or installed_manifest.exists():
            raise AssertionError("uninstall should remove unchanged receipt-owned files")
        if modified.read_bytes() != b"user changed this\n":
            raise AssertionError("uninstall must preserve a modified formerly managed file")
        if unmanaged.read_bytes() != b"user owned\n":
            raise AssertionError("uninstall must preserve unowned payload paths")
        if receipt.exists():
            raise AssertionError("uninstall should retire the ownership receipt")
        if len(findings) != 1 or "preserved modified stale managed file" not in findings[0]:
            raise AssertionError("modified managed preservation must be explicit")


def test_manifest_sync_rejects_modified_owned_and_unowned_current_collisions():
    def fixture(root, payload):
        source_root = root / "source"
        source = source_root / "scripts" / "runtime.py"
        source.parent.mkdir(parents=True)
        source.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        (source_root / "MANIFEST").write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": [
                        {
                            "destination": "gauntlet/scripts/runtime.py",
                            "executable": False,
                            "sha256": digest,
                            "source": "scripts/runtime.py",
                        }
                    ],
                    "generatedDestinations": [
                        "gauntlet/AGENTS.md",
                        "gauntlet/MANIFEST",
                        "gauntlet/.install-manifest.json",
                    ],
                    "legacyManaged": [],
                }
            )
        )
        return source_root

    def receipt(home, digest):
        path = home / "gauntlet" / ".install-manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": [
                        {
                            "destination": "gauntlet/scripts/runtime.py",
                            "sha256": digest,
                        }
                    ],
                    "manifestSha256": "0" * 64,
                }
            )
        )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source_root = fixture(root, b"new runtime\n")

        modified_home = root / "modified-home"
        modified = modified_home / "gauntlet" / "scripts" / "runtime.py"
        modified.parent.mkdir(parents=True)
        modified.write_bytes(b"user modified runtime\n")
        receipt(
            modified_home,
            hashlib.sha256(b"old runtime\n").hexdigest(),
        )
        try:
            sync_payload(source_root, modified_home)
        except ValueError as error:
            assert_contains(str(error), "modified prior-receipt-owned", "owned collision")
        else:
            raise AssertionError("modified receipt-owned current payload must fail closed")
        if modified.read_bytes() != b"user modified runtime\n":
            raise AssertionError("modified receipt-owned current payload must be preserved")

        unowned_home = root / "unowned-home"
        unowned = unowned_home / "gauntlet" / "scripts" / "runtime.py"
        unowned.parent.mkdir(parents=True)
        unowned.write_bytes(b"user-owned runtime\n")
        try:
            sync_payload(source_root, unowned_home)
        except ValueError as error:
            assert_contains(str(error), "unowned manifest destination", "unowned collision")
        else:
            raise AssertionError("unowned gauntlet payload collision must fail closed")
        if unowned.read_bytes() != b"user-owned runtime\n":
            raise AssertionError("unowned gauntlet payload collision must be preserved")

        upgrade_home = root / "upgrade-home-current"
        upgrade = upgrade_home / "gauntlet" / "scripts" / "runtime.py"
        upgrade.parent.mkdir(parents=True)
        upgrade.write_bytes(b"old runtime\n")
        receipt(upgrade_home, hashlib.sha256(upgrade.read_bytes()).hexdigest())
        sync_payload(source_root, upgrade_home)
        if upgrade.read_bytes() != b"new runtime\n":
            raise AssertionError("byte-identical receipt-owned payload should upgrade")


def test_generated_router_preflight_preserves_collisions_and_allows_upgrade():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        candidate = root / "candidate-router.md"
        candidate.write_bytes(b"new generated router\n")

        owned_home = root / "owned-home"
        installed = owned_home / "gauntlet" / "AGENTS.md"
        installed.parent.mkdir(parents=True)
        installed.write_bytes(b"old generated router\n")
        receipt = owned_home / "gauntlet" / ".install-manifest.json"
        receipt.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": [],
                    "generatedEntries": [
                        {
                            "destination": "gauntlet/AGENTS.md",
                            "sha256": hashlib.sha256(installed.read_bytes()).hexdigest(),
                        }
                    ],
                    "manifestSha256": "0" * 64,
                }
            )
        )
        preflight_generated_payload(
            owned_home,
            "gauntlet/AGENTS.md",
            candidate,
        )

        installed.write_bytes(b"user modified generated router\n")
        before = installed.read_bytes()
        try:
            preflight_generated_payload(
                owned_home,
                "gauntlet/AGENTS.md",
                candidate,
            )
        except ValueError as error:
            assert_contains(
                str(error),
                "modified prior-receipt-owned generated destination",
                "modified generated router collision",
            )
        else:
            raise AssertionError("modified owned generated router must fail closed")
        if installed.read_bytes() != before:
            raise AssertionError("modified owned generated router must be preserved")

        unowned_home = root / "unowned-home"
        unowned = unowned_home / "gauntlet" / "AGENTS.md"
        unowned.parent.mkdir(parents=True)
        unowned.write_bytes(b"user-owned generated router\n")
        before = unowned.read_bytes()
        try:
            preflight_generated_payload(
                unowned_home,
                "gauntlet/AGENTS.md",
                candidate,
            )
        except ValueError as error:
            assert_contains(
                str(error),
                "unowned generated destination collision",
                "unowned generated router collision",
            )
        else:
            raise AssertionError("unowned generated router must fail closed")
        if unowned.read_bytes() != before:
            raise AssertionError("unowned generated router must be preserved")

        legacy_home = root / "legacy-home"
        legacy_router = legacy_home / "gauntlet" / "AGENTS.md"
        legacy_router.parent.mkdir(parents=True)
        legacy_router.write_bytes(b"exact historical router\n")
        legacy_container = legacy_home / "AGENTS.md"
        legacy_container.write_bytes(
            b"personal instructions\n" + legacy_router.read_bytes()
        )
        preflight_generated_payload(
            legacy_home,
            "gauntlet/AGENTS.md",
            candidate,
            legacy_container=legacy_container,
        )
        legacy_container.write_bytes(
            b"user-owned prefix\n"
            b"<!-- BEGIN GAUNTLET MANAGED BLOCK -->\n"
            + legacy_router.read_bytes()
            + b"<!-- END GAUNTLET MANAGED BLOCK -->\n"
            b"user-owned suffix\n"
        )
        (legacy_home / "gauntlet" / ".install-manifest.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "entries": [],
                    "generatedEntries": [],
                    "manifestSha256": "0" * 64,
                }
            )
        )
        preflight_generated_payload(
            legacy_home,
            "gauntlet/AGENTS.md",
            candidate,
            legacy_container=legacy_container,
        )
        legacy_container.write_bytes(
            legacy_router.read_bytes()
            + b"<!-- BEGIN GAUNTLET MANAGED BLOCK -->\n"
            b"different managed bytes\n"
            b"<!-- END GAUNTLET MANAGED BLOCK -->\n"
        )
        try:
            preflight_generated_payload(
                legacy_home,
                "gauntlet/AGENTS.md",
                candidate,
                legacy_container=legacy_container,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "router bytes outside a managed block are not managed evidence"
            )
        legacy_container.write_bytes(b"personal instructions only\n")
        try:
            preflight_generated_payload(
                legacy_home,
                "gauntlet/AGENTS.md",
                candidate,
                legacy_container=legacy_container,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "unowned router without exact legacy-container evidence must fail"
            )

        wired = run_install(
            unowned_home,
            extra_args=["--check", "--codex-preferences", "skip"],
            check=False,
        )
        if wired.returncode == 0:
            raise AssertionError("install.sh must enforce generated router ownership")
        assert_contains(
            wired.stderr,
            "unowned generated destination collision",
            "generated router preflight wiring",
        )


def test_default_install_requests_machine_local_sensor_tools_without_network():
    if not (ROOT / ".git").exists():
        return
    with tempfile.TemporaryDirectory() as tmp:
        agent_home = Path(tmp) / "agent-home"
        run_install(agent_home, sensor_tools=True)
        log = read(agent_home / "sensor-tools-install.log")
        assert_contains(log, "install --agent-home", "default sensor tool installation")


def test_codex_uninstall_preserves_user_bytes_config_and_modified_payload():
    if not (ROOT / ".git").exists():
        return
    with tempfile.TemporaryDirectory() as tmp:
        agent_home = Path(tmp) / "agent-home"
        agent_home.mkdir()
        agents_path = agent_home / "AGENTS.md"
        agents_path.write_bytes(b"User-owned instruction.\r\n")
        config_path = agent_home / "config.toml"
        config_path.write_text('[features]\nunknown_future_key = "keep"\n')
        run_install(agent_home, extra_args=["--instructions-reviewed"])

        installed = agents_path.read_bytes()
        begin = b"<!-- BEGIN GAUNTLET MANAGED BLOCK -->"
        end = b"<!-- END GAUNTLET MANAGED BLOCK -->"
        start = installed.index(begin)
        finish = installed.index(end, start) + len(end)
        outside_before = installed[:start] + installed[finish:]

        modified_payload = agent_home / "gauntlet" / "README.md"
        modified_payload.write_text("user-modified installed file\n")
        result = run_install(
            agent_home,
            extra_args=["--uninstall"],
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"Codex uninstall failed:\n{result.stdout}\n{result.stderr}"
            )
        if agents_path.read_bytes() != outside_before:
            raise AssertionError("uninstall must preserve every byte outside the managed block")
        assert_contains(
            config_path.read_text(),
            'unknown_future_key = "keep"',
            "unknown Codex config preservation",
        )
        if modified_payload.read_text() != "user-modified installed file\n":
            raise AssertionError("uninstall must preserve modified receipt-owned payload")
        if (agent_home / "gauntlet" / ".install-manifest.json").exists():
            raise AssertionError("uninstall should remove the payload ownership receipt")
