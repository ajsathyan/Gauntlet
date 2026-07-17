#!/usr/bin/env python3
"""Compatibility shim for the packaged live-progress projection."""

from gauntletlib.progress.projection import *  # noqa: F403
from gauntletlib.progress.projection import main


if __name__ == "__main__":
    raise SystemExit(main())
