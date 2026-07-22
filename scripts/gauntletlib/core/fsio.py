"""File-writing primitives with explicit creation, mode, and durability contracts."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from .jsonio import pretty_json


def atomic_write_synced_text(path: Path, content: str) -> None:
    """Replace a UTF-8 text file after flushing and syncing its temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_synced_json(path: Path, value: Any) -> None:
    """Atomically write canonical pretty JSON using the synced text contract."""

    atomic_write_synced_text(path, pretty_json(value))
