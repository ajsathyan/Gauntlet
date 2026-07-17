#!/usr/bin/env python3
"""Compatibility wrapper for the domain-split development workflow suite."""

import importlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
main = importlib.import_module("tests.workflow.runner").main


if __name__ == "__main__":
    main()
