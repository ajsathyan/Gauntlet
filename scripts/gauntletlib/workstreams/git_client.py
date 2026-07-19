"""Read-only local Git observations for the workstream queue."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitClientError(RuntimeError):
    """A local Git observation could not be completed."""


class GitClient:
    """Observe exact revisions and ancestry without changing repository state."""

    def __init__(self, repo):
        self.repo = Path(repo).resolve()

    def ensure_repository(self):
        if not self.repo.is_dir():
            raise GitClientError("repo must be an existing directory")
        self._run("rev-parse", "--git-dir")

    def revision(self, reference, label):
        commit = self._run(
            "rev-parse",
            "--verify",
            f"{reference}^{{commit}}",
        ).stdout.strip()
        tree = self._run(
            "rev-parse",
            "--verify",
            f"{commit}^{{tree}}",
        ).stdout.strip()
        if not commit or not tree:
            raise GitClientError(f"cannot resolve {label} revision")
        return commit, tree

    def is_ancestor(self, ancestor, descendant):
        result = self._run(
            "merge-base",
            "--is-ancestor",
            ancestor,
            descendant,
            check=False,
        )
        if result.returncode not in (0, 1):
            raise GitClientError(
                result.stderr.strip() or "cannot compare Git ancestry"
            )
        return result.returncode == 0

    def _run(self, *arguments, check=True):
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if check and result.returncode:
            raise GitClientError(
                result.stderr.strip()
                or result.stdout.strip()
                or f"git {' '.join(arguments)} failed"
            )
        return result
