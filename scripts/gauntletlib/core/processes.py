"""Subprocess conventions shared by Gauntlet command-line tools."""

from __future__ import annotations

import os
import subprocess
from typing import Mapping, Optional, Sequence


def run_command(
    args: Sequence[str],
    cwd=None,
    env: Optional[Mapping[str, str]] = None,
    check: bool = False,
):
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"{args} failed with {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def git(args, cwd):
    return run_command(["git", *args], cwd=cwd)


def gh_binary():
    return os.environ.get("GAUNTLET_GH", "gh")


def gh(args, cwd):
    return run_command([gh_binary(), *args], cwd=cwd, env=os.environ.copy())
