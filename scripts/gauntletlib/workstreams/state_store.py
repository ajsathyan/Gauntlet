"""Atomic filesystem persistence for the local workstream queue."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


class StateStoreError(RuntimeError):
    """Locked queue state could not be read or written."""


class _LockedState:
    """Narrow state access that is valid only while its store lock is held."""

    def __init__(self, store, value):
        self._store = store
        self._value = value

    def read(self):
        return self._value

    def write(self, value):
        self._store._write(value)
        self._value = value


class LockedJsonStateStore:
    """Serialize one JSON value with an adjacent inter-process file lock."""

    def __init__(self, state_path):
        self.state_path = Path(state_path).resolve()
        self.lock_path = self.state_path.with_name(self.state_path.name + ".lock")

    @contextmanager
    def locked(self):
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock_path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield _LockedState(self, self._read())
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except StateStoreError:
            raise
        except OSError as error:
            raise StateStoreError(f"queue state access failed: {error}") from error

    def _read(self):
        if not self.state_path.is_file():
            return None
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise StateStoreError(
                f"queue state could not be read: {error}"
            ) from error

    def _write(self, value):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.state_path.name}.",
            dir=self.state_path.parent,
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as stream:
                json.dump(
                    value,
                    stream,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.state_path)
            directory = os.open(self.state_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
