"""Atomic file-writing primitives with explicit durability contracts."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from .serialization import pretty_json


def atomic_write_text(path: Path, content: str) -> None:
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


def atomic_write_json(path: Path, value: Any) -> None:
    """Atomically write canonical pretty JSON using the synced text contract."""

    atomic_write_text(path, pretty_json(value))


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Replace a byte file after flushing and syncing, cleaning up on BaseException."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
