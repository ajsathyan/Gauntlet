"""Stable JSON and digest representations shared across Gauntlet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path, *, encoding: Optional[str] = "utf-8") -> Any:
    text = path.read_text() if encoding is None else path.read_text(encoding=encoding)
    return json.loads(text)
