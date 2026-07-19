from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, SCRIPTS


def run(args, *, input_value=None, check=True, env=None):
    result = subprocess.run(
        args,
        cwd=ROOT,
        input=input_value,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if check and result.returncode:
        raise AssertionError(
            "command failed: {}\n{}\n{}".format(
                " ".join(map(str, args)), result.stdout, result.stderr
            )
        )
    return result


def test_security_review_runner_enforces_read_only_codex_exec():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        workspace = root / "workspace"
        workspace.mkdir()
        ticket = root / "ticket.md"
        ticket.write_text("Review commit abc123 for credential leakage.\n", encoding="utf-8")
        capture = root / "capture.json"
        fake = root / "codex"
        fake.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
Path(os.environ["GAUNTLET_TEST_CAPTURE"]).write_text(json.dumps({
    "argv": sys.argv[1:],
    "stdin": sys.stdin.read(),
}), encoding="utf-8")
print('{"type":"turn.completed"}')
""",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        env = dict(os.environ)
        env["GAUNTLET_TEST_CAPTURE"] = str(capture)
        result = run(
            [
                "python3",
                str(SCRIPTS / "security-review.py"),
                "--workspace",
                str(workspace),
                "--ticket-file",
                str(ticket),
                "--codex-bin",
                str(fake),
            ],
            env=env,
        )
        if result.stdout.strip() != '{"type":"turn.completed"}':
            raise AssertionError("runner must stream Codex JSONL output")
        observed = json.loads(capture.read_text(encoding="utf-8"))
        argv = observed["argv"]
        required_pairs = (
            ("--sandbox", "read-only"),
            ("--model", "gpt-5.6-sol"),
            ("--cd", str(workspace.resolve())),
            ("--disable", "multi_agent"),
        )
        for flag, value in required_pairs:
            try:
                index = argv.index(flag)
            except ValueError as error:
                raise AssertionError("missing required Codex CLI flag {}".format(flag)) from error
            if argv[index + 1] != value:
                raise AssertionError("{} must be {}, got {}".format(flag, value, argv[index + 1]))
        for required in (
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            'model_reasoning_effort="high"',
            'approval_policy="never"',
            "-",
        ):
            if required not in argv:
                raise AssertionError("missing required Codex CLI argument {}".format(required))
        prompt = observed["stdin"]
        if "Stay read-only" not in prompt or ticket.read_text(encoding="utf-8") not in prompt:
            raise AssertionError("runner must combine fixed reviewer policy with the bounded ticket")


def test_security_review_runner_rejects_output_inside_reviewed_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        ticket = workspace.parent / "security-ticket.md"
        ticket.write_text("Review the target.\n", encoding="utf-8")
        try:
            result = run(
                [
                    "python3",
                    str(SCRIPTS / "security-review.py"),
                    "--workspace",
                    str(workspace),
                    "--ticket-file",
                    str(ticket),
                    "--output",
                    str(workspace / "review.md"),
                    "--codex-bin",
                    "/bin/true",
                ],
                check=False,
            )
        finally:
            ticket.unlink(missing_ok=True)
        if result.returncode == 0 or "outside the reviewed workspace" not in result.stderr:
            raise AssertionError("review output must not mutate the reviewed workspace")


def security_review_tests():
    return (
        test_security_review_runner_enforces_read_only_codex_exec,
        test_security_review_runner_rejects_output_inside_reviewed_workspace,
    )


def load_tests(loader, standard_tests, pattern):
    del loader, standard_tests, pattern
    suite = unittest.TestSuite()
    for test in security_review_tests():
        suite.addTest(unittest.FunctionTestCase(test, description=test.__name__))
    return suite


if __name__ == "__main__":
    for case in security_review_tests():
        case()
        print("PASS {}".format(case.__name__))
