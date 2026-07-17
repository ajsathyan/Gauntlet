"""Installed-runtime verification command and parser registration."""

import json
import subprocess
import sys
from pathlib import Path

from gauntletlib.cli_support import EXIT_CODES
from gauntletlib.core.findings import status_for
from gauntletlib.install.manifest import verify_payload


def _missing(findings, path, code):
    if not path.exists():
        findings.append(
            {"code": code, "severity": "fail", "message": f"Missing {path}"}
        )


def _required_runtime_paths(agent_home):
    root = agent_home / "gauntlet"
    return [
        (root / "AGENTS.md", "missing_installed_agents"),
    ]


def _verify_router(agent_home, findings):
    installed_router = agent_home / "gauntlet" / "AGENTS.md"
    if not installed_router.exists():
        return
    router_text = installed_router.read_text(encoding="utf-8")
    expected_root = str(agent_home / "gauntlet")
    expected_skills = str(agent_home / "skills")
    placeholders = ["{{GAUNTLET_ROOT}}", "{{AGENT_HOME}}", "{{RESPONSE_STYLE}}"]
    if any(placeholder in router_text for placeholder in placeholders):
        findings.append({"code": "unresolved_router_placeholder", "severity": "fail", "message": "Installed router contains an unresolved path placeholder."})
    if expected_root not in router_text:
        findings.append({"code": "missing_installed_root_path", "severity": "fail", "message": "Installed router lacks the rendered Gauntlet root."})
    if expected_skills not in router_text:
        findings.append({"code": "missing_installed_skills_path", "severity": "fail", "message": "Installed router lacks the rendered skills root."})
    if len(router_text.encode("utf-8")) >= 32768:
        findings.append({"code": "installed_router_too_large", "severity": "fail", "message": "Installed router exceeds the 32 KiB default instruction budget."})


def _verify_codex(agent_home, findings):
    codex_agents = agent_home / "AGENTS.md"
    _missing(findings, codex_agents, "missing_codex_agents")
    if codex_agents.exists():
        text = codex_agents.read_text(encoding="utf-8")
        if text.count("BEGIN GAUNTLET MANAGED BLOCK") != 1 or text.count("END GAUNTLET MANAGED BLOCK") != 1:
            findings.append({"code": "invalid_codex_managed_block", "severity": "fail", "message": "Codex AGENTS.md must contain exactly one complete Gauntlet managed block."})
        if "Gauntlet Workflow Router" not in text:
            findings.append({"code": "missing_codex_router", "severity": "fail", "message": "Codex AGENTS.md lacks the installed Gauntlet router."})
    source = agent_home / "gauntlet" / "agents" / "codex"
    verifier = agent_home / "gauntlet" / "scripts" / "install-codex-agents.py"
    if source.is_dir() and verifier.is_file():
        result = subprocess.run(
            [sys.executable, str(verifier), "verify", "--source", str(source), "--agent-home", str(agent_home)],
            text=True,
            capture_output=True,
        )
        if result.returncode:
            findings.append({"code": "invalid_codex_custom_agents", "severity": "fail", "message": result.stderr.strip() or result.stdout.strip()})


def _verify_claude(agent_home, findings):
    claude_md = agent_home / "CLAUDE.md"
    _missing(findings, claude_md, "missing_claude_md")
    if not claude_md.exists():
        return
    text = claude_md.read_text(encoding="utf-8")
    expected_import = f"@{agent_home}/gauntlet/AGENTS.md"
    if "BEGIN GAUNTLET MANAGED BLOCK" not in text:
        findings.append({"code": "missing_claude_managed_block", "severity": "fail", "message": "CLAUDE.md lacks Gauntlet managed block."})
    if expected_import not in text:
        findings.append({"code": "missing_claude_agents_import", "severity": "fail", "message": "CLAUDE.md does not import installed AGENTS.md."})


def command_verify(args):
    agent_home = Path(args.agent_home).expanduser()
    if not agent_home.is_absolute():
        agent_home = (Path.cwd() / agent_home).absolute()
    findings = []
    for path, code in _required_runtime_paths(agent_home):
        _missing(findings, path, code)
    installed_root = agent_home / "gauntlet"
    for message in verify_payload(installed_root, agent_home):
        findings.append({"code": "invalid_manifest_payload", "severity": "fail", "message": message})
    if (installed_root / "ui").exists() or list(installed_root.rglob("node_modules")):
        findings.append({"code": "development_ui_installed", "severity": "fail", "message": "Installed runtime must not contain ui/ or node_modules/."})
    _verify_router(agent_home, findings)
    if args.target == "codex":
        _verify_codex(agent_home, findings)
    if args.target == "claude":
        _verify_claude(agent_home, findings)
    payload = {"schemaVersion": "1.0", "status": "pass", "target": args.target, "agentHome": str(agent_home), "findings": findings}
    payload["status"] = status_for(findings)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Install verify: {payload['status']}")
        for finding in findings:
            print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    return EXIT_CODES[payload["status"]]


def register(subcommands, *, command):
    install = subcommands.add_parser("install", help="Installed-layout helpers.")
    commands = install.add_subparsers(dest="install_command", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--target", choices=["codex", "claude"], required=True)
    verify.add_argument("--agent-home", required=True)
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=command)
