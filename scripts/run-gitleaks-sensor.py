#!/usr/bin/env python3
"""Scan changed Git content with Gitleaks without copying findings into context."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def git(root, *arguments):
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def base_ref(root):
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    for candidate in ("origin/HEAD", "origin/main", "main", "origin/master", "master"):
        value = git(root, "rev-parse", "--verify", f"{candidate}^{{commit}}")
        if value.returncode == 0 and value.stdout.strip() != head:
            return candidate
    return None


def changed_content(root):
    chunks = []
    base = base_ref(root)
    if base:
        merge_base = git(root, "merge-base", "HEAD", base)
        if merge_base.returncode == 0:
            chunks.append(
                git(
                    root,
                    "diff",
                    "--binary",
                    merge_base.stdout.decode("ascii").strip(),
                    "HEAD",
                ).stdout
            )
    chunks.append(git(root, "diff", "--binary").stdout)
    chunks.append(git(root, "diff", "--binary", "--cached").stdout)
    untracked = git(
        root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    )
    for value in untracked.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
        if not value or value.startswith((".git/", ".gauntlet/")):
            continue
        path = root / value
        if path.is_file() and path.stat().st_size <= 2 * 1024 * 1024:
            chunks.extend(
                [
                    f"\n--- /dev/null\n+++ b/{value}\n".encode(),
                    path.read_bytes(),
                    b"\n",
                ]
            )
    return b"".join(chunks)


def main():
    root = Path(__file__).resolve().parents[1]
    gitleaks = shutil.which("gitleaks")
    if not gitleaks:
        print("gitleaks executable is unavailable")
        return 2
    content = changed_content(root)
    if not content.strip():
        print("No changed content to scan.")
        return 0
    result = subprocess.run(
        [
            gitleaks,
            "stdin",
            "--no-banner",
            "--redact",
            "--exit-code",
            "1",
        ],
        cwd=root,
        input=content,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
