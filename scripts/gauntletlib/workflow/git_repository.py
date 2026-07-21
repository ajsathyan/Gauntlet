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

    def resolve_candidate(self, project_root, commit, tree, base):
        if any(_OBJECT_ID(value) is None for value in (commit, tree, base)):
            raise RuntimeError(
                "candidate commit, tree, and checked base must be exact Git object IDs"
            )
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
        resolved_base = self._run(
            project_root,
            ["rev-parse", "--verify", f"{base}^{{commit}}"],
            "checked base",
        )
        if resolved_base != base:
            raise RuntimeError("checked base did not resolve to its exact object ID")
        return {"commit": resolved_commit, "tree": resolved_tree, "base": resolved_base}

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
