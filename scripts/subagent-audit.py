#!/usr/bin/env python3
"""Export privacy-bounded Gauntlet subagent usage from Codex native state."""

import argparse
import json
import os
import sqlite3
import tempfile
from pathlib import Path


QUERY = """
SELECT t.id, e.parent_thread_id, t.agent_role, t.model, t.reasoning_effort,
       t.sandbox_policy, t.approval_mode,
       t.agent_nickname, t.source, t.tokens_used, t.cwd, t.created_at_ms, t.updated_at_ms
FROM threads t
LEFT JOIN thread_spawn_edges e ON e.child_thread_id = t.id
WHERE t.agent_role GLOB 'gauntlet_*'
ORDER BY t.created_at_ms, t.id
"""
EXPECTED = {
    "gauntlet_fast_reader": ("gpt-5.6-luna", "medium"),
    "gauntlet_standard_worker": ("gpt-5.6-sol", "medium"),
    "gauntlet_deep_worker": ("gpt-5.6-sol", "high"),
    "gauntlet_independent_verifier": ("gpt-5.6-sol", "medium"),
    "gauntlet_release_integrator": ("gpt-5.6-terra", "high"),
    "gauntlet_deep_expert_researcher": ("gpt-5.6-sol", "xhigh"),
    "gauntlet_security_reviewer": ("gpt-5.6-sol", "high"),
}


def records(database):
    if not database.is_file():
        raise RuntimeError("Codex native state database is missing: {}".format(database))
    connection = sqlite3.connect("file:{}?mode=ro".format(database), uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(QUERY).fetchall()
    finally:
        connection.close()
    return [
        {
            "agentId": row["id"],
            "parentAgentId": row["parent_thread_id"],
            "profile": row["agent_role"],
            "model": row["model"],
            "reasoningEffort": row["reasoning_effort"],
            "sandboxPolicy": row["sandbox_policy"],
            "approvalMode": row["approval_mode"],
            "nickname": row["agent_nickname"],
            "source": row["source"],
            "tokensUsed": row["tokens_used"],
            "cwd": row["cwd"],
            "createdAtMs": row["created_at_ms"],
            "updatedAtMs": row["updated_at_ms"],
        }
        for row in rows
    ]


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".{}.".format(path.name), dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def existing_records(path):
    if not path.exists():
        return {}
    result = {}
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            row = json.loads(line)
            agent_id = row.get("agentId")
            if not isinstance(agent_id, str) or not agent_id or agent_id in result:
                raise ValueError("invalid or duplicate agentId at line {}".format(line_number))
            result[agent_id] = row
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError("Refusing to replace unreadable existing audit log {}: {}".format(path, exc))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("sync", "list", "summary", "verify"), nargs="?", default="sync")
    parser.add_argument("--agent-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--agent-id")
    parser.add_argument("--requested-profile")
    parser.add_argument("--require-read-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    database = args.agent_home.expanduser() / "state_5.sqlite"
    output = args.agent_home.expanduser() / "gauntlet" / "logs" / "subagents.jsonl"
    try:
        data = records(database)
    except (RuntimeError, sqlite3.Error) as exc:
        parser.error(str(exc))
    if args.action == "sync":
        try:
            merged = existing_records(output)
        except RuntimeError as exc:
            parser.error(str(exc))
        merged.update({row["agentId"]: row for row in data})
        ordered = sorted(merged.values(), key=lambda row: (row.get("createdAtMs") or 0, row["agentId"]))
        rendered = "".join(json.dumps(row, sort_keys=True) + "\n" for row in ordered)
        atomic_write(output, rendered)
    if args.action == "verify":
        if not args.agent_id or not args.requested_profile:
            parser.error("verify requires --agent-id and --requested-profile")
        row = next((item for item in data if item["agentId"] == args.agent_id), None)
        if row is None:
            parser.error("agent ID is not present in Codex native state: {}".format(args.agent_id))
        if row["profile"] != args.requested_profile:
            parser.error("started profile {} does not match requested profile {}".format(row["profile"], args.requested_profile))
        expected = EXPECTED.get(args.requested_profile)
        if expected is None:
            parser.error("requested profile is not a canonical Gauntlet profile: {}".format(args.requested_profile))
        if (row["model"], row["reasoningEffort"]) != expected:
            parser.error("actual model/effort {}/{} does not match required {}/{}".format(row["model"], row["reasoningEffort"], *expected))
        if args.require_read_only:
            try:
                sandbox = json.loads(row["sandboxPolicy"])
            except (TypeError, ValueError):
                parser.error("effective sandbox policy is malformed: {}".format(row["sandboxPolicy"]))
            if not isinstance(sandbox, dict) or sandbox.get("type") != "read-only":
                parser.error("effective sandbox is not read-only: {}".format(row["sandboxPolicy"]))
        payload = {"status": "pass", "agent": row}
    elif args.action == "summary":
        counts = {}
        for row in data:
            counts[row["profile"]] = counts.get(row["profile"], 0) + 1
        payload = {"count": len(data), "profiles": counts, "auditLog": str(output)}
    else:
        payload = data
    if args.json or args.action != "sync":
        print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
