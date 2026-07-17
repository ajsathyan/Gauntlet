"""Stable JSON representations shared across Gauntlet."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def read_json(path: Path, *, encoding: Optional[str] = "utf-8") -> Any:
    text = path.read_text() if encoding is None else path.read_text(encoding=encoding)
    return json.loads(text)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
