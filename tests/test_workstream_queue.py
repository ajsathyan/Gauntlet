from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests import support as _support  # noqa: F401

from gauntletlib.workstreams import register
from gauntletlib.workstreams.queue import QueueError, WorkstreamQueue


def git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


class WorkstreamQueueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.name", "Queue Test")
        git(self.repo, "config", "user.email", "queue@example.invalid")
        self.base = self.commit("base.txt", "base\n", "base")
        git(self.repo, "switch", "-q", "-c", "work")
        self.source = self.commit("work.txt", "work\n", "work")
        git(self.repo, "switch", "-q", "main")
        self.state_path = self.root / "workstreams.json"
        self.queue = WorkstreamQueue(
            self.state_path,
            self.repo,
            default_ref="main",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def commit(self, name: str, content: str, message: str) -> str:
        (self.repo / name).write_text(content, encoding="utf-8")
        git(self.repo, "add", name)
        git(self.repo, "commit", "-q", "-m", message)
        return git(self.repo, "rev-parse", "HEAD")

    def candidate(self) -> tuple[str, str]:
        git(self.repo, "switch", "-q", "work")
        git(self.repo, "merge", "-q", "--no-edit", "main")
        commit = git(self.repo, "rev-parse", "HEAD")
        tree = git(self.repo, "rev-parse", "HEAD^{tree}")
        git(self.repo, "switch", "-q", "main")
        return commit, tree

    def cli(self, command: str, *arguments: str, check: bool = True):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="family", required=True)
        register(subparsers)
        args = parser.parse_args(
            [
                "workstreams",
                command,
                "--state",
                str(self.state_path),
                "--repo",
                str(self.repo),
                "--json",
                *arguments,
            ]
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            returncode = args.func(args)
        result = SimpleNamespace(
            returncode=returncode,
            stdout=output.getvalue(),
        )
        if check and returncode:
            raise AssertionError(
                f"workstream command failed ({returncode})\n{result.stdout}"
            )
        return result

    def test_fifo_claim_and_one_active_attempt(self):
        self.queue.enqueue("first", self.source)
        self.queue.enqueue("second", self.source)

        first = self.queue.claim()
        replay = self.queue.claim()

        self.assertEqual(first["workstreamId"], "first")
        self.assertEqual(replay["attemptId"], first["attemptId"])
        state = self.queue.snapshot()
        self.assertEqual(state["activeAttempt"]["workstreamId"], "first")
        self.assertEqual(
            [entry["status"] for entry in state["entries"]],
            ["active", "queued"],
        )

    def test_valid_candidate_binds_exact_commit_and_tree(self):
        self.queue.enqueue("valid", self.source)
        attempt = self.queue.claim()
        candidate, tree = self.candidate()

        bound = self.queue.bind_candidate(attempt["attemptId"], candidate, tree)

        self.assertEqual(bound["candidateCommit"], candidate)
        self.assertEqual(bound["candidateTree"], tree)
        self.assertEqual(bound["baseCommit"], self.base)

    def test_default_head_drift_rejects_stale_candidate(self):
        self.queue.enqueue("stale", self.source)
        attempt = self.queue.claim()
        candidate, tree = self.candidate()
        self.commit("drift.txt", "drift\n", "drift")

        with self.assertRaisesRegex(QueueError, "default head changed"):
            self.queue.bind_candidate(attempt["attemptId"], candidate, tree)

    def test_wrong_candidate_tree_is_rejected(self):
        self.queue.enqueue("wrong-tree", self.source)
        attempt = self.queue.claim()
        candidate, _ = self.candidate()

        with self.assertRaisesRegex(QueueError, "tree"):
            self.queue.bind_candidate(
                attempt["attemptId"],
                candidate,
                "f" * 40,
            )

    def test_interrupted_reconcile_observes_candidate_on_default(self):
        self.queue.enqueue("interrupted", self.source)
        attempt = self.queue.claim()
        candidate, tree = self.candidate()
        self.queue.bind_candidate(attempt["attemptId"], candidate, tree)
        git(self.repo, "merge", "-q", "--no-edit", candidate)

        state = self.queue.reconcile()

        self.assertIsNone(state["activeAttempt"])
        self.assertEqual(state["entries"][0]["status"], "merged")

    def test_interrupted_reconcile_accepts_exact_candidate_tree(self):
        self.queue.enqueue("tree-equivalent", self.source)
        attempt = self.queue.claim()
        candidate, tree = self.candidate()
        self.queue.bind_candidate(attempt["attemptId"], candidate, tree)
        equivalent = git(
            self.repo,
            "commit-tree",
            tree,
            "-p",
            self.base,
            "-m",
            "tree-equivalent default",
        )
        git(self.repo, "update-ref", "refs/heads/main", equivalent, self.base)

        state = self.queue.reconcile()

        self.assertIsNone(state["activeAttempt"])
        self.assertEqual(state["entries"][0]["status"], "merged")

    def test_reconcile_blocks_unrepresented_default_drift(self):
        self.queue.enqueue("drift", self.source)
        self.queue.claim()
        self.commit("other.txt", "other\n", "other")

        state = self.queue.reconcile()

        self.assertIsNone(state["activeAttempt"])
        self.assertEqual(state["entries"][0]["status"], "blocked")

    def test_new_attempt_refreshes_the_default_snapshot(self):
        self.queue.enqueue("refresh", self.source)
        first = self.queue.claim()
        advanced = self.commit("new-base.txt", "new base\n", "new base")
        self.queue.reconcile()
        self.queue.enqueue("refresh", self.source)

        second = self.queue.claim()

        self.assertEqual(first["baseCommit"], self.base)
        self.assertEqual(second["baseCommit"], advanced)

    def test_replayed_mutations_are_idempotent(self):
        first = self.queue.enqueue("replay", self.source)
        second = self.queue.enqueue("replay", self.source)
        self.assertEqual(first, second)
        attempt = self.queue.claim()
        candidate, tree = self.candidate()
        first_bound = self.queue.bind_candidate(
            attempt["attemptId"], candidate, tree,
        )
        second_bound = self.queue.bind_candidate(
            attempt["attemptId"], candidate, tree,
        )
        self.assertEqual(first_bound, second_bound)

        git(self.repo, "merge", "-q", "--no-edit", candidate)
        first_release = self.queue.release(
            attempt["attemptId"], "merged", "observed on default",
        )
        second_release = self.queue.release(
            attempt["attemptId"], "merged", "observed on default",
        )
        self.assertEqual(first_release, second_release)

    def test_state_is_one_versioned_json_file_with_adjacent_lock(self):
        self.queue.enqueue("shape", self.source)
        value = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(value["schemaVersion"], "gauntlet.workstream-queue.v1")
        self.assertTrue(self.state_path.with_name("workstreams.json.lock").exists())
        self.assertEqual(
            sorted(path.name for path in self.root.glob("workstreams*")),
            ["workstreams.json", "workstreams.json.lock"],
        )

    def test_git_observation_preserves_unrelated_dirty_work(self):
        dirty = self.repo / "unrelated.txt"
        dirty.write_text("keep me\n", encoding="utf-8")

        self.queue.enqueue("dirty", self.source)
        self.queue.claim()
        self.queue.reconcile()

        self.assertEqual(dirty.read_text(encoding="utf-8"), "keep me\n")
        self.assertIn("?? unrelated.txt", git(self.repo, "status", "--short"))

    def test_cli_claims_fifo_and_emits_closed_json_shape(self):
        for name in ("first-cli", "second-cli"):
            payload = json.loads(
                self.cli(
                    "enqueue",
                    "--workstream",
                    name,
                    "--source-commit",
                    self.source,
                ).stdout
            )
            self.assertEqual(
                set(payload),
                {"schemaVersion", "status", "action", "state"},
            )

        claimed = json.loads(self.cli("claim").stdout)

        self.assertEqual(claimed["status"], "pass")
        self.assertEqual(claimed["action"], "claim")
        self.assertEqual(claimed["result"]["workstreamId"], "first-cli")
        self.assertEqual(
            set(claimed["state"]),
            {
                "schemaVersion",
                "defaultRef",
                "sequence",
                "activeAttempt",
                "entries",
            },
        )

    def test_cli_stale_candidate_failure_is_json_and_keeps_attempt(self):
        self.cli(
            "enqueue",
            "--workstream",
            "stale-cli",
            "--source-commit",
            self.source,
        )
        attempt = json.loads(self.cli("claim").stdout)["result"]
        candidate, tree = self.candidate()
        self.commit("cli-drift.txt", "drift\n", "CLI drift")

        result = self.cli(
            "bind-candidate",
            "--attempt",
            attempt["attemptId"],
            "--candidate-commit",
            candidate,
            "--candidate-tree",
            tree,
            check=False,
        )
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            set(payload),
            {"schemaVersion", "status", "action", "error"},
        )
        self.assertEqual(payload["status"], "fail")
        self.assertIn("default head changed", payload["error"]["message"])
        self.assertEqual(
            self.queue.snapshot()["activeAttempt"]["attemptId"],
            attempt["attemptId"],
        )

    def test_outbound_git_architecture_boundary(self):
        package = _support.SCRIPTS / "gauntletlib"

        def imports(relative):
            tree = ast.parse((package / relative).read_text(encoding="utf-8"))
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    names.add(("." * node.level) + (node.module or ""))
            return names

        contract_imports = imports(Path("workflow/contracts.py"))
        queue_imports = imports(Path("workstreams/queue.py"))
        adapter_imports = imports(Path("workstreams/git_client.py"))

        self.assertFalse(
            {"subprocess", "urllib", ".git_client"} & contract_imports,
        )
        self.assertFalse({"subprocess", "urllib"} & queue_imports)
        self.assertIn("subprocess", adapter_imports)
        self.assertFalse(
            {".queue", "gauntletlib.workflow.contracts"} & adapter_imports,
        )

    def test_queue_observes_git_through_injected_client(self):
        source = "3" * 40
        source_tree = "4" * 40
        base = "5" * 40
        base_tree = "6" * 40

        class ObservedGit:
            def __init__(self):
                self.calls = []

            def ensure_repository(self):
                self.calls.append(("ensure",))

            def revision(self, reference, label):
                self.calls.append(("revision", reference, label))
                return {
                    source: (source, source_tree),
                    "main": (base, base_tree),
                }[reference]

            def is_ancestor(self, ancestor, descendant):
                self.calls.append(("is_ancestor", ancestor, descendant))
                return True

        observed = ObservedGit()
        queue = WorkstreamQueue(
            self.root / "injected.json",
            self.repo,
            git_client=observed,
        )
        queue.enqueue("injected", source)
        attempt = queue.claim()

        self.assertEqual(attempt["baseCommit"], base)
        self.assertEqual(
            observed.calls,
            [
                ("ensure",),
                ("revision", source, "source"),
                ("revision", "main", "default head"),
            ],
        )

    def test_multi_process_enqueue_and_claim_contention(self):
        process_count = 6
        environment = os.environ.copy()
        python_path = str(_support.SCRIPTS)
        if environment.get("PYTHONPATH"):
            python_path += os.pathsep + environment["PYTHONPATH"]
        environment["PYTHONPATH"] = python_path

        def contend(operation, identifiers):
            start = self.root / f"{operation}.start"
            ready_paths = [
                self.root / f"{operation}.{index}.ready"
                for index in range(len(identifiers))
            ]
            program = "\n".join(
                [
                    "import json",
                    "import sys",
                    "import time",
                    "from pathlib import Path",
                    "from gauntletlib.workstreams.queue import WorkstreamQueue",
                    "state, repo, start, ready, operation, identity, source = sys.argv[1:]",
                    "Path(ready).write_text('ready\\n', encoding='utf-8')",
                    "while not Path(start).exists():",
                    "    time.sleep(0.005)",
                    "queue = WorkstreamQueue(Path(state), Path(repo), default_ref='main')",
                    "if operation == 'enqueue':",
                    "    result = queue.enqueue(identity, source)",
                    "else:",
                    "    result = queue.claim()",
                    "print(json.dumps(result, sort_keys=True))",
                ]
            )
            processes = [
                subprocess.Popen(
                    [
                        "python3",
                        "-c",
                        program,
                        str(self.state_path),
                        str(self.repo),
                        str(start),
                        str(ready),
                        operation,
                        identity,
                        self.source,
                    ],
                    cwd=self.repo,
                    env=environment,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for ready, identity in zip(ready_paths, identifiers)
            ]
            outputs = []
            try:
                deadline = time.monotonic() + 5
                while (
                    not all(path.exists() for path in ready_paths)
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.005)
                self.assertTrue(
                    all(path.exists() for path in ready_paths),
                    "subprocess contention barrier did not become ready",
                )
                start.write_text("start\n", encoding="utf-8")
                for process in processes:
                    stdout, stderr = process.communicate(timeout=10)
                    self.assertEqual(process.returncode, 0, stderr)
                    outputs.append(json.loads(stdout))
            finally:
                start.touch(exist_ok=True)
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                for process in processes:
                    if process.poll() is None:
                        process.wait(timeout=2)
            return outputs

        contend(
            "enqueue",
            [f"concurrent-{index}" for index in range(process_count)],
        )
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(len(state["entries"]), process_count)
        sequences = sorted(
            entry["enqueuedSequence"] for entry in state["entries"]
        )
        self.assertEqual(sequences, list(range(1, process_count + 1)))
        self.assertEqual(
            len({entry["workstreamId"] for entry in state["entries"]}),
            process_count,
        )

        claims = contend(
            "claim",
            [f"claimant-{index}" for index in range(process_count)],
        )
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        active = state["activeAttempt"]
        self.assertIsNotNone(active)
        self.assertEqual(
            len(
                [
                    entry
                    for entry in state["entries"]
                    if entry["status"] == "active"
                ]
            ),
            1,
        )
        self.assertEqual(
            {claim["attemptId"] for claim in claims},
            {active["attemptId"]},
        )
        winner = min(
            state["entries"],
            key=lambda entry: entry["enqueuedSequence"],
        )
        self.assertEqual(active["workstreamId"], winner["workstreamId"])


if __name__ == "__main__":
    unittest.main()
