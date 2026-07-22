#!/usr/bin/env python3
"""Run a bounded Gauntlet security review through read-only Codex CLI."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import NoReturn


MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "high"
MAX_TICKET_BYTES = 1024 * 1024
REVIEW_POLICY = """\
You are Gauntlet's independent security reviewer.

Review only the bounded security-sensitive ticket below. Stay read-only. Examine
trust boundaries, authentication, authorization, secrets, privacy, data loss,
migrations, destructive operations, abuse cases, recovery, and relevant current
standards where applicable. Distinguish exploitable findings from hardening
suggestions and include reproducible evidence or a concrete attack path.

Do not modify files, fix findings, expand scope, dispatch other agents, merge,
release, operate external applications, or perform production actions. Return
compact prioritized findings with evidence and affected surfaces. If there are
no findings, say so and name the material limits of the review.

--- BEGIN BOUNDED SECURITY TICKET ---
{ticket}
--- END BOUNDED SECURITY TICKET ---
"""


def fail(parser: argparse.ArgumentParser, message: str) -> NoReturn:
    parser.error(message)


def existing_file(parser: argparse.ArgumentParser, value: Path, label: str) -> Path:
    if value.is_symlink() or not value.is_file():
        fail(parser, "{} must be a regular file: {}".format(label, value))
    return value.resolve()


def existing_directory(parser: argparse.ArgumentParser, value: Path, label: str) -> Path:
    if value.is_symlink() or not value.is_dir():
        fail(parser, "{} must be a real directory: {}".format(label, value))
    return value.resolve()


def resolve_codex(parser: argparse.ArgumentParser, value: str | None) -> str:
    candidate = value or os.environ.get("GAUNTLET_CODEX_BIN") or shutil.which("codex")
    if not candidate:
        fail(parser, "Codex CLI was not found; pass --codex-bin or set GAUNTLET_CODEX_BIN")
    resolved = Path(candidate).expanduser()
    if not resolved.is_absolute():
        discovered = shutil.which(candidate)
        if not discovered:
            fail(parser, "Codex CLI is not executable: {}".format(candidate))
        resolved = Path(discovered)
    if resolved.is_symlink():
        resolved = resolved.resolve()
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        fail(parser, "Codex CLI is not executable: {}".format(resolved))
    return str(resolved)


def validate_output(
    parser: argparse.ArgumentParser, output: Path | None, workspace: Path
) -> Path | None:
    if output is None:
        return None
    resolved = output.expanduser().resolve(strict=False)
    if resolved == workspace or workspace in resolved.parents:
        fail(parser, "--output must be outside the reviewed workspace")
    if output.is_symlink() or resolved.exists():
        fail(parser, "--output must be a new regular file")
    if not resolved.parent.is_dir():
        fail(parser, "--output parent directory does not exist: {}".format(resolved.parent))
    return resolved


def build_command(
    codex_bin: str, workspace: Path, output: Path | None
) -> list[str]:
    command = [
        codex_bin,
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--disable",
        "multi_agent",
        "--model",
        MODEL,
        "--sandbox",
        "read-only",
        "--cd",
        str(workspace),
        "-c",
        'model_reasoning_effort="{}"'.format(REASONING_EFFORT),
        "-c",
        'approval_policy="never"',
        "-c",
        'shell_environment_policy.inherit="core"',
    ]
    if output is not None:
        command.extend(["--output-last-message", str(output)])
    command.append("-")
    return command


def run(command: list[str], prompt: str, timeout: float) -> int:
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        process.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        print("security review timed out after {} seconds".format(timeout), file=sys.stderr)
        return 124
    return process.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--ticket-file", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--codex-bin")
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args(argv)

    if args.timeout <= 0:
        fail(parser, "--timeout must be greater than zero")
    workspace = existing_directory(parser, args.workspace.expanduser(), "--workspace")
    ticket_file = existing_file(parser, args.ticket_file.expanduser(), "--ticket-file")
    if ticket_file.stat().st_size > MAX_TICKET_BYTES:
        fail(parser, "--ticket-file exceeds the 1 MiB bounded-context limit")
    try:
        ticket = ticket_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        fail(parser, "cannot read --ticket-file: {}".format(error))
    if not ticket.strip():
        fail(parser, "--ticket-file must not be empty")

    output = validate_output(parser, args.output, workspace)
    codex_bin = resolve_codex(parser, args.codex_bin)
    command = build_command(codex_bin, workspace, output)
    return run(command, REVIEW_POLICY.format(ticket=ticket.rstrip()), args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
