#!/usr/bin/env python3
"""Targeted synthetic proof for Gauntlet subagent routing and analytics."""

import json
import sqlite3
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
TOKEN_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


def run(args, *, check=True):
    result = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise AssertionError("command failed: {}\n{}\n{}".format(" ".join(map(str, args)), result.stdout, result.stderr))
    return result


def create_native_state(home):
    connection = sqlite3.connect(str(home / "state_5.sqlite"))
    connection.executescript(
        """
        CREATE TABLE threads (
          id TEXT PRIMARY KEY, rollout_path TEXT, model TEXT, reasoning_effort TEXT,
          agent_role TEXT, sandbox_policy TEXT, approval_mode TEXT,
          agent_nickname TEXT, source TEXT, tokens_used INTEGER, cwd TEXT,
          cli_version TEXT, created_at_ms INTEGER, updated_at_ms INTEGER
        );
        CREATE TABLE thread_spawn_edges (
          parent_thread_id TEXT, child_thread_id TEXT PRIMARY KEY, status TEXT
        );
        """
    )
    return connection


def token_event(total, last):
    return {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {"total_token_usage": total, "last_token_usage": last},
        },
    }


def tokens(input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens):
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def write_lines(path, rows, partial=None):
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    if partial is not None:
        text += partial
    path.write_text(text, encoding="utf-8")


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def route_args(home, version, **overrides):
    fields = {
        "work-class": "implementation",
        "complexity": "standard",
        "risk": "ordinary",
        "authority": "local-write",
        "proof": "integration",
        "context-shape": "bounded",
    }
    fields.update(overrides)
    args = [
        "python3", str(SCRIPTS / "route-codex-agent.py"),
        "--circuit-file", str(home / "gauntlet" / "state" / "routing-circuit.json"),
        "--codex-version", version,
    ]
    for key, value in fields.items():
        args.extend(["--" + key, value])
    args.append("--json")
    return args


def test_cumulative_analytics_are_idempotent_and_partial_safe():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        rollout = home / "private-rollout.jsonl"
        first = tokens(100, 40, 20, 5)
        second_last = tokens(50, 20, 10, 2)
        second_total = {key: first[key] + second_last[key] for key in TOKEN_KEYS}
        rows = [
            {"type": "event_msg", "payload": {"type": "user_message", "message": "PROMPT-SECRET"}},
            token_event(first, first),
            token_event(first, first),
            token_event(second_total, second_last),
        ]
        write_lines(rollout, rows, partial='{"type":"event_msg","payload":{"type":"token_count"')
        connection = create_native_state(home)
        connection.execute(
            "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "child-analytics", str(rollout), "gpt-5.6-sol", "medium", "gauntlet_standard_worker",
                '{"type":"workspace-write","writable_roots":["/Users/private/project"]}', "never", "worker", "subagent", 999,
                "/Users/private/project", "0.144.2", 10, 20,
            ),
        )
        connection.execute("INSERT INTO thread_spawn_edges VALUES (?, ?, ?)", ("parent-1", "child-analytics", "running"))
        connection.commit()
        connection.close()

        audit = SCRIPTS / "subagent-audit.py"
        run(["python3", str(audit), "sync", "--agent-home", str(home)])
        log_dir = home / "gauntlet" / "logs"
        analytics_path = log_dir / "subagent-model-requests.jsonl"
        quarantine_path = log_dir / "subagent-quarantine.jsonl"
        audit_path = log_dir / "subagents.jsonl"
        requests = read_jsonl(analytics_path)
        if len(requests) != 2:
            raise AssertionError("duplicate cumulative snapshots must not become extra model requests: {}".format(requests))
        if [row["tokens"] for row in requests] != [first, second_last]:
            raise AssertionError("analytics must derive per-request deltas from cumulative totals")
        quarantine = read_jsonl(quarantine_path)
        if [row["reason"] for row in quarantine] != ["unterminated-json-line"]:
            raise AssertionError("partial input must be quarantined without being ingested: {}".format(quarantine))
        stored = audit_path.read_text() + analytics_path.read_text() + quarantine_path.read_text()
        for forbidden in ("PROMPT-SECRET", str(rollout), "/Users/private/project"):
            if forbidden in stored:
                raise AssertionError("privacy-bounded outputs leaked {!r}".format(forbidden))
        audit_rows = read_jsonl(audit_path)
        if not audit_rows[0]["cwd"].startswith("sha256:"):
            raise AssertionError("audit cwd must be an opaque fingerprint")

        before = {path: path.read_bytes() for path in (audit_path, analytics_path, quarantine_path)}
        run(["python3", str(audit), "sync", "--agent-home", str(home)])
        if any(path.read_bytes() != content for path, content in before.items()):
            raise AssertionError("repeated synchronization must be byte-idempotent")

        third_last = tokens(25, 10, 5, 1)
        third_total = {key: second_total[key] + third_last[key] for key in TOKEN_KEYS}
        write_lines(rollout, rows + [token_event(third_total, third_last)])
        run(["python3", str(audit), "sync", "--agent-home", str(home)])
        if len(read_jsonl(analytics_path)) != 3 or read_jsonl(quarantine_path):
            raise AssertionError("completed input must leave quarantine and ingest exactly once")
        summary = json.loads(run(["python3", str(audit), "summary", "--agent-home", str(home), "--json"]).stdout)
        if summary["modelRequests"] != 3 or summary["tokens"] != third_total:
            raise AssertionError("summary must report request count and token classes without cumulative double counting")


def test_start_reconciliation_opens_a_version_scoped_circuit():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        connection = create_native_state(home)
        connection.execute(
            "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "child-mismatch", None, "gpt-5.6-sol", "high", "gauntlet_deep_worker",
                '{"type":"workspace-write"}', "never", "worker", "subagent", 0, "/repo", "0.144.2", 10, 20,
            ),
        )
        connection.execute("INSERT INTO thread_spawn_edges VALUES (?, ?, ?)", ("parent-1", "child-mismatch", "running"))
        connection.commit()
        connection.close()
        audit = SCRIPTS / "subagent-audit.py"

        healthy = json.loads(run(route_args(home, "0.144.2")).stdout)
        if healthy["status"] != "delegate" or healthy["profile"] != "gauntlet_standard_worker":
            raise AssertionError("healthy optimistic dispatch must remain available before a mismatch is observed")
        reconciled = run([
            "python3", str(audit), "reconcile", "--agent-home", str(home),
            "--agent-id", "child-mismatch", "--requested-profile", "gauntlet_standard_worker",
            "--requested-risk", "ordinary", "--json",
        ])
        payload = json.loads(reconciled.stdout)
        if payload["status"] != "mismatch-observed" or payload["failClosed"]:
            raise AssertionError("ordinary equivalent-authority mismatch must remain auditable without killing current work")
        blocked = run(route_args(home, "0.144.2"), check=False)
        if blocked.returncode != 3 or json.loads(blocked.stdout)["status"] != "circuit-open":
            raise AssertionError("the first mismatch must prevent the next affected dispatch")
        other_version = json.loads(run(route_args(home, "0.145.0")).stdout)
        if other_version["status"] != "delegate":
            raise AssertionError("routing circuits must be version scoped")
        consequential = run([
            "python3", str(audit), "reconcile", "--agent-home", str(home),
            "--agent-id", "child-mismatch", "--requested-profile", "gauntlet_standard_worker",
            "--requested-risk", "consequential", "--json",
        ], check=False)
        if consequential.returncode != 4 or not json.loads(consequential.stdout)["failClosed"]:
            raise AssertionError("consequential substitution must fail closed")


def test_security_authority_is_attested_and_runtime_enforced_per_version():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        home = root / "home"
        installer = SCRIPTS / "install-codex-agents.py"
        run(["python3", str(installer), "apply", "--source", str(ROOT / "agents" / "codex"), "--agent-home", str(home)])
        run(["python3", str(installer), "verify", "--source", str(ROOT / "agents" / "codex"), "--agent-home", str(home)])
        manifest = json.loads((home / "gauntlet" / "install-agents-codex.json").read_text())
        authority = manifest.get("securityReviewerAuthority", {})
        if authority.get("sandboxMode") != "read-only" or authority.get("profileSetVersion") != manifest.get("profileSetVersion"):
            raise AssertionError("the installed security reviewer authority must be attested for its profile-set version")
        manifest["securityReviewerAuthority"]["sandboxMode"] = "workspace-write"
        (home / "gauntlet" / "install-agents-codex.json").write_text(json.dumps(manifest))
        tampered = run([
            "python3", str(installer), "verify", "--source", str(ROOT / "agents" / "codex"), "--agent-home", str(home),
        ], check=False)
        if tampered.returncode == 0:
            raise AssertionError("verify must reject authority attestation drift within a profile-set version")
        run(["python3", str(installer), "apply", "--source", str(ROOT / "agents" / "codex"), "--agent-home", str(home)])

        connection = create_native_state(home)
        connection.execute(
            "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "security-bad", None, "gpt-5.6-sol", "high", "gauntlet_security_reviewer",
                '{"type":"workspace-write"}', "never", "security", "subagent", 0, "/repo", "0.144.2", 10, 20,
            ),
        )
        connection.execute("INSERT INTO thread_spawn_edges VALUES (?, ?, ?)", ("parent-1", "security-bad", "running"))
        connection.execute(
            "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "security-good", None, "gpt-5.6-sol", "high", "gauntlet_security_reviewer",
                '{"type":"read-only"}', "never", "security", "subagent", 0, "/repo", "0.145.0", 11, 21,
            ),
        )
        connection.execute("INSERT INTO thread_spawn_edges VALUES (?, ?, ?)", ("parent-1", "security-good", "running"))
        connection.commit()
        connection.close()
        audit = SCRIPTS / "subagent-audit.py"
        result = run([
            "python3", str(audit), "reconcile", "--agent-home", str(home),
            "--agent-id", "security-bad", "--requested-profile", "gauntlet_security_reviewer",
            "--requested-risk", "ordinary", "--json",
        ], check=False)
        payload = json.loads(result.stdout)
        if result.returncode != 4 or "security_sandbox_violation" not in payload["taxonomy"]:
            raise AssertionError("a non-read-only security reviewer must fail closed")
        security_route = route_args(
            home, "0.144.2", **{
                "work-class": "verification", "complexity": "deep", "authority": "read-only",
                "proof": "security",
            }
        )
        if run(security_route, check=False).returncode != 3:
            raise AssertionError("security sandbox violation must block future reviewers on the affected version")
        validated = json.loads(run([
            "python3", str(audit), "reconcile", "--agent-home", str(home),
            "--agent-id", "security-good", "--requested-profile", "gauntlet_security_reviewer",
            "--requested-risk", "ordinary", "--json",
        ]).stdout)
        if validated["status"] != "pass":
            raise AssertionError("a read-only security reviewer must reconcile successfully")
        circuit = json.loads((home / "gauntlet" / "state" / "routing-circuit.json").read_text())
        runtime_authority = circuit["versions"]["0.145.0"]["validatedAuthorities"]["gauntlet_security_reviewer"]
        if runtime_authority["sandboxMode"] != "read-only":
            raise AssertionError("runtime security authority must be recorded by Codex version")


def main():
    tests = [
        test_cumulative_analytics_are_idempotent_and_partial_safe,
        test_start_reconciliation_opens_a_version_scoped_circuit,
        test_security_authority_is_attested_and_runtime_enforced_per_version,
    ]
    for test in tests:
        test()
        print("PASS {}".format(test.__name__))


if __name__ == "__main__":
    main()
