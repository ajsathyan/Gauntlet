#!/usr/bin/env python3
"""Compatibility entry point for tests/test_doc_lifecycle.py."""

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "tests" / "test_doc_lifecycle.py"), run_name="__main__")
