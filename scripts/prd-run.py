#!/usr/bin/env python3
"""Deterministic, disk-backed execution runs for one accepted Epic."""

from gauntletlib.run.controller import *  # noqa: F403
from gauntletlib.run.controller import main


if __name__ == "__main__":
    raise SystemExit(main())
