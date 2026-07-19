"""Git outbound adapter for exact workflow candidates and evidence locators."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from gauntletlib.core.proc import git


_OBJECT_ID = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?").fullmatch


class GitRepository:
    """Resolve candidate identities and `path:` evidence against a real repository."""

    @staticmethod
    def _run(project_root, arguments, label):
        result = git(arguments, project_root)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"{label} could not be resolved by Git: {detail}")
        return result.stdout.strip()

    def resolve_candidate(self, project_root, commit, tree):
        if _OBJECT_ID(commit) is None or _OBJECT_ID(tree) is None:
            raise RuntimeError("candidate commit and tree must be exact Git object IDs")
        resolved_commit = self._run(
            project_root,
            ["rev-parse", "--verify", f"{commit}^{{commit}}"],
            "candidate commit",
        )
        if resolved_commit != commit:
            raise RuntimeError("candidate commit did not resolve to its exact object ID")
        resolved_tree = self._run(
            project_root,
            ["rev-parse", "--verify", f"{resolved_commit}^{{tree}}"],
            "candidate tree",
        )
        if resolved_tree != tree:
            raise RuntimeError("candidate tree does not match the commit's derived tree")
        return {"commit": resolved_commit, "tree": resolved_tree}

    def resolve_evidence(self, project_root, commit, locator):
        if not isinstance(locator, str) or not locator.startswith("path:"):
            raise RuntimeError(
                "evidence locator must use path:<candidate-relative-file>"
            )
        value = locator.removeprefix("path:")
        path = PurePosixPath(value)
        if (
            not value
            or value.startswith("/")
            or "\\" in value
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise RuntimeError(
                "evidence locator must name a safe candidate-relative file"
            )
        object_type = self._run(
            project_root,
            ["cat-file", "-t", f"{commit}:{path.as_posix()}"],
            f"evidence locator {locator}",
        )
        if object_type != "blob":
            raise RuntimeError(f"evidence locator is not a file: {locator}")
        return f"revision:{commit}#{locator}"
