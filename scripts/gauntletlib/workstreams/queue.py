"""A local FIFO workstream queue bound to observable Git identities."""

from __future__ import annotations

import copy
import re
from contextlib import contextmanager
from datetime import datetime, timezone

from .git_client import GitClient, GitClientError
from .state_store import LockedJsonStateStore, StateStoreError


STATE_SCHEMA = "gauntlet.workstream-queue.v1"
TERMINAL_RESULTS = ("merged", "blocked", "failed")
_OBJECT_ID = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?").fullmatch


class QueueError(RuntimeError):
    """The queue state or requested Git transition is invalid."""


class WorkstreamQueue:
    """Serialize generic workstreams through one durable local state file."""

    def __init__(
        self,
        state_path,
        repo,
        *,
        default_ref="main",
        clock=None,
        git_client=None,
        state_store=None,
    ):
        self.default_ref = self._nonempty(default_ref, "default_ref")
        self._clock = clock or self._now
        self._git_client = git_client or GitClient(repo)
        self._state_store = state_store or LockedJsonStateStore(state_path)
        self.repo = getattr(self._git_client, "repo", repo)
        self.state_path = getattr(self._state_store, "state_path", state_path)
        self.lock_path = getattr(self._state_store, "lock_path", None)
        try:
            self._git_client.ensure_repository()
        except GitClientError as error:
            raise QueueError(str(error)) from error

    def snapshot(self):
        """Return a validated copy of current state without changing it."""

        with self._locked_state() as (state, _):
            return copy.deepcopy(state)

    def enqueue(self, workstream_id, source_commit):
        """Append a workstream, preserving FIFO order and replay safety."""

        workstream_id = self._nonempty(workstream_id, "workstream_id")
        source_commit, source_tree = self._revision(source_commit, "source")
        with self._locked_state() as (state, access):
            current = self._entry(state, workstream_id)
            if current is not None and current["status"] in ("queued", "active"):
                if (
                    current["sourceCommit"] != source_commit
                    or current["sourceTree"] != source_tree
                ):
                    raise QueueError(
                        "queued workstream ID is already bound to another source"
                    )
                return copy.deepcopy(state)
            state["sequence"] += 1
            entry = {
                "workstreamId": workstream_id,
                "sourceCommit": source_commit,
                "sourceTree": source_tree,
                "enqueuedSequence": state["sequence"],
                "enqueuedAt": self._timestamp(),
                "status": "queued",
                "attempts": current["attempts"] if current is not None else [],
            }
            if current is None:
                state["entries"].append(entry)
            else:
                state["entries"][state["entries"].index(current)] = entry
            self._save(access, state)
            return copy.deepcopy(state)

    def claim(self):
        """Claim the oldest queued workstream against a fresh default snapshot."""

        with self._locked_state() as (state, access):
            if state["activeAttempt"] is not None:
                return copy.deepcopy(state["activeAttempt"])
            queued = [entry for entry in state["entries"] if entry["status"] == "queued"]
            if not queued:
                raise QueueError("queue has no queued workstream")
            entry = min(queued, key=lambda item: item["enqueuedSequence"])
            base_commit, base_tree = self._revision(self.default_ref, "default head")
            state["sequence"] += 1
            attempt = {
                "attemptId": f"A{state['sequence']:06d}",
                "workstreamId": entry["workstreamId"],
                "baseRef": self.default_ref,
                "baseCommit": base_commit,
                "baseTree": base_tree,
                "candidateCommit": None,
                "candidateTree": None,
                "status": "active",
                "claimedAt": self._timestamp(),
                "finishedAt": None,
                "reason": None,
            }
            entry["status"] = "active"
            entry["attempts"].append(copy.deepcopy(attempt))
            state["activeAttempt"] = attempt
            self._save(access, state)
            return copy.deepcopy(attempt)

    def bind_candidate(self, attempt_id, candidate_commit, candidate_tree):
        """Bind the active attempt to an exact candidate commit and tree."""

        attempt_id = self._nonempty(attempt_id, "attempt_id")
        supplied_tree = self._object_id(candidate_tree, "candidate_tree")
        resolved_commit, resolved_tree = self._revision(
            candidate_commit,
            "candidate",
        )
        if supplied_tree != resolved_tree:
            raise QueueError("candidate tree does not match the candidate commit")
        with self._locked_state() as (state, access):
            attempt = self._active(state, attempt_id)
            if attempt["status"] == "candidate":
                if (
                    attempt["candidateCommit"] == resolved_commit
                    and attempt["candidateTree"] == resolved_tree
                ):
                    return copy.deepcopy(attempt)
                raise QueueError("attempt is already bound to another candidate")
            if attempt["status"] != "active":
                raise QueueError("attempt cannot accept a candidate")
            current_default, _ = self._revision(self.default_ref, "default head")
            if current_default != attempt["baseCommit"]:
                raise QueueError(
                    "default head changed after the attempt was claimed"
                )
            entry = self._entry(state, attempt["workstreamId"])
            if entry is None:
                raise QueueError("active attempt has no owning entry")
            if not self._is_ancestor(entry["sourceCommit"], resolved_commit):
                raise QueueError(
                    "candidate does not contain the queued source commit"
                )
            if not self._is_ancestor(attempt["baseCommit"], resolved_commit):
                raise QueueError("candidate does not contain its claimed default head")
            attempt["candidateCommit"] = resolved_commit
            attempt["candidateTree"] = resolved_tree
            attempt["status"] = "candidate"
            self._copy_attempt_to_entry(state, attempt)
            self._save(access, state)
            return copy.deepcopy(attempt)

    def release(self, attempt_id, result, reason):
        """Record one terminal result and release active ownership."""

        attempt_id = self._nonempty(attempt_id, "attempt_id")
        reason = self._nonempty(reason, "reason")
        if result not in TERMINAL_RESULTS:
            raise QueueError("result must be merged, blocked, or failed")
        with self._locked_state() as (state, access):
            if state["activeAttempt"] is None:
                previous = self._attempt(state, attempt_id)
                if (
                    previous is not None
                    and previous["status"] == result
                    and previous["reason"] == reason
                ):
                    return copy.deepcopy(state)
                raise QueueError("attempt is not active")
            attempt = self._active(state, attempt_id)
            if result == "merged":
                self._require_candidate_identity(attempt)
                default_commit, default_tree = self._revision(
                    self.default_ref,
                    "default head",
                )
                if not self._matches_candidate(
                    attempt,
                    default_commit,
                    default_tree,
                ):
                    raise QueueError(
                        "default head does not match the exact bound candidate tree proof"
                    )
            self._finish(state, attempt, result, reason)
            self._save(access, state)
            return copy.deepcopy(state)

    def reconcile(self):
        """Recover an interrupted active attempt from current Git facts."""

        with self._locked_state() as (state, access):
            attempt = state["activeAttempt"]
            if attempt is None:
                return copy.deepcopy(state)
            default_commit, default_tree = self._revision(
                self.default_ref,
                "default head",
            )
            if attempt["candidateCommit"] is not None:
                self._require_candidate_identity(attempt)
                if self._matches_candidate(
                    attempt,
                    default_commit,
                    default_tree,
                ):
                    self._finish(
                        state,
                        attempt,
                        "merged",
                        "current default head has the exact bound candidate tree",
                    )
                elif default_commit != attempt["baseCommit"]:
                    self._finish(
                        state,
                        attempt,
                        "blocked",
                        "default head changed without the bound candidate tree",
                    )
            elif default_commit != attempt["baseCommit"]:
                self._finish(
                    state,
                    attempt,
                    "blocked",
                    "default head changed during the interrupted attempt",
                )
            self._save(access, state)
            return copy.deepcopy(state)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _timestamp(self):
        value = self._clock()
        return self._nonempty(value, "clock result")

    @staticmethod
    def _nonempty(value, label):
        if not isinstance(value, str) or not value.strip():
            raise QueueError(f"{label} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _object_id(value, label):
        if not isinstance(value, str) or _OBJECT_ID(value) is None:
            raise QueueError(
                f"{label} must be an exact 40- or 64-character Git object ID"
            )
        return value

    def _revision(self, value, label):
        reference = self._nonempty(value, label)
        try:
            object_id, tree_id = self._git_client.revision(reference, label)
        except GitClientError as error:
            raise QueueError(str(error)) from error
        self._object_id(object_id, f"{label} commit")
        self._object_id(tree_id, f"{label} tree")
        return object_id, tree_id

    def _is_ancestor(self, ancestor, descendant):
        try:
            return self._git_client.is_ancestor(ancestor, descendant)
        except GitClientError as error:
            raise QueueError(str(error)) from error

    def _require_candidate_identity(self, attempt):
        candidate = attempt["candidateCommit"]
        expected_tree = attempt["candidateTree"]
        if candidate is None or expected_tree is None:
            raise QueueError("attempt has no bound candidate")
        _, actual_tree = self._revision(candidate, "candidate")
        if actual_tree != expected_tree:
            raise QueueError("bound candidate tree no longer matches its commit")

    def _matches_candidate(self, attempt, default_commit, default_tree):
        if default_tree != attempt["candidateTree"]:
            return False
        if not self._is_ancestor(attempt["baseCommit"], default_commit):
            return False
        if default_commit == attempt["candidateCommit"]:
            return True
        return not self._is_ancestor(
            attempt["candidateCommit"],
            default_commit,
        )

    @contextmanager
    def _locked_state(self):
        try:
            with self._state_store.locked() as access:
                value = access.read()
                state = self._empty() if value is None else value
                self._validate_state(state)
                yield state, access
        except StateStoreError as error:
            raise QueueError(str(error)) from error

    def _empty(self):
        return {
            "schemaVersion": STATE_SCHEMA,
            "defaultRef": self.default_ref,
            "sequence": 0,
            "activeAttempt": None,
            "entries": [],
        }

    def _validate_state(self, state):
        expected = {
            "schemaVersion",
            "defaultRef",
            "sequence",
            "activeAttempt",
            "entries",
        }
        if not isinstance(state, dict) or set(state) != expected:
            raise QueueError("queue state has an unsupported shape")
        if state["schemaVersion"] != STATE_SCHEMA:
            raise QueueError("queue state schema is unsupported")
        if state["defaultRef"] != self.default_ref:
            raise QueueError("queue state is bound to another default ref")
        if (
            not isinstance(state["sequence"], int)
            or isinstance(state["sequence"], bool)
            or state["sequence"] < 0
        ):
            raise QueueError("queue sequence is invalid")
        if not isinstance(state["entries"], list):
            raise QueueError("queue entries must be an array")
        identifiers = set()
        active_count = 0
        attempt_ids = set()
        for entry in state["entries"]:
            self._validate_entry(entry)
            identifier = entry["workstreamId"]
            if identifier in identifiers:
                raise QueueError("queue contains duplicate workstream IDs")
            identifiers.add(identifier)
            if entry["status"] == "active":
                active_count += 1
            for attempt in entry["attempts"]:
                self._validate_attempt(attempt)
                if attempt["attemptId"] in attempt_ids:
                    raise QueueError("queue contains duplicate attempt IDs")
                attempt_ids.add(attempt["attemptId"])
        active = state["activeAttempt"]
        if active is None:
            if active_count:
                raise QueueError("entry is active without an active attempt")
        else:
            self._validate_attempt(active)
            if active["status"] not in ("active", "candidate"):
                raise QueueError("active attempt has a terminal status")
            if active_count != 1:
                raise QueueError("active attempt must have exactly one active entry")
            stored = self._attempt(state, active["attemptId"])
            if stored != active:
                raise QueueError("active attempt differs from its entry history")

    def _validate_entry(self, entry):
        expected = {
            "workstreamId",
            "sourceCommit",
            "sourceTree",
            "enqueuedSequence",
            "enqueuedAt",
            "status",
            "attempts",
        }
        if not isinstance(entry, dict) or set(entry) != expected:
            raise QueueError("queue entry has an unsupported shape")
        self._nonempty(entry["workstreamId"], "workstream ID")
        self._object_id(entry["sourceCommit"], "source commit")
        self._object_id(entry["sourceTree"], "source tree")
        if (
            not isinstance(entry["enqueuedSequence"], int)
            or isinstance(entry["enqueuedSequence"], bool)
            or entry["enqueuedSequence"] < 1
        ):
            raise QueueError("entry sequence is invalid")
        self._nonempty(entry["enqueuedAt"], "enqueue timestamp")
        if entry["status"] not in ("queued", "active", *TERMINAL_RESULTS):
            raise QueueError("entry status is invalid")
        if not isinstance(entry["attempts"], list):
            raise QueueError("entry attempts must be an array")

    def _validate_attempt(self, attempt):
        expected = {
            "attemptId",
            "workstreamId",
            "baseRef",
            "baseCommit",
            "baseTree",
            "candidateCommit",
            "candidateTree",
            "status",
            "claimedAt",
            "finishedAt",
            "reason",
        }
        if not isinstance(attempt, dict) or set(attempt) != expected:
            raise QueueError("attempt has an unsupported shape")
        self._nonempty(attempt["attemptId"], "attempt ID")
        self._nonempty(attempt["workstreamId"], "attempt workstream ID")
        if attempt["baseRef"] != self.default_ref:
            raise QueueError("attempt is bound to another default ref")
        self._object_id(attempt["baseCommit"], "attempt base commit")
        self._object_id(attempt["baseTree"], "attempt base tree")
        candidate_pair = (attempt["candidateCommit"], attempt["candidateTree"])
        if (candidate_pair[0] is None) != (candidate_pair[1] is None):
            raise QueueError("attempt candidate commit and tree must be paired")
        if candidate_pair[0] is not None:
            self._object_id(candidate_pair[0], "attempt candidate commit")
            self._object_id(candidate_pair[1], "attempt candidate tree")
        if attempt["status"] not in ("active", "candidate", *TERMINAL_RESULTS):
            raise QueueError("attempt status is invalid")
        if attempt["status"] == "candidate" and candidate_pair[0] is None:
            raise QueueError("candidate attempt has no candidate identity")
        self._nonempty(attempt["claimedAt"], "claim timestamp")
        terminal = attempt["status"] in TERMINAL_RESULTS
        if terminal:
            self._nonempty(attempt["finishedAt"], "finish timestamp")
            self._nonempty(attempt["reason"], "finish reason")
        elif attempt["finishedAt"] is not None or attempt["reason"] is not None:
            raise QueueError("active attempt contains terminal fields")

    @staticmethod
    def _entry(state, workstream_id):
        return next(
            (
                entry
                for entry in state["entries"]
                if entry["workstreamId"] == workstream_id
            ),
            None,
        )

    @staticmethod
    def _attempt(state, attempt_id):
        return next(
            (
                attempt
                for entry in state["entries"]
                for attempt in entry["attempts"]
                if attempt["attemptId"] == attempt_id
            ),
            None,
        )

    def _active(self, state, attempt_id):
        attempt = state["activeAttempt"]
        if attempt is None or attempt["attemptId"] != attempt_id:
            raise QueueError("attempt is not active")
        return attempt

    def _copy_attempt_to_entry(self, state, attempt):
        entry = self._entry(state, attempt["workstreamId"])
        if entry is None or not entry["attempts"]:
            raise QueueError("active attempt has no owning entry")
        if entry["attempts"][-1]["attemptId"] != attempt["attemptId"]:
            raise QueueError("active attempt is not the latest entry attempt")
        entry["attempts"][-1] = copy.deepcopy(attempt)

    def _finish(self, state, attempt, result, reason):
        attempt["status"] = result
        attempt["finishedAt"] = self._timestamp()
        attempt["reason"] = reason
        entry = self._entry(state, attempt["workstreamId"])
        if entry is None:
            raise QueueError("active attempt has no owning entry")
        entry["status"] = result
        self._copy_attempt_to_entry(state, attempt)
        state["activeAttempt"] = None

    def _save(self, access, state):
        self._validate_state(state)
        try:
            access.write(state)
        except StateStoreError as error:
            raise QueueError(str(error)) from error
