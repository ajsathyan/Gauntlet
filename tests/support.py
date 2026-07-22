"""Shared paths and loaders for tests moved out of ``scripts/``."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class _ModuleLoader(Protocol):
    def exec_module(self, module: ModuleType) -> None: ...


def load_script_module(module_name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load script module: {filename}")
    module = importlib.util.module_from_spec(spec)
    cast(_ModuleLoader, spec.loader).exec_module(module)
    return module
