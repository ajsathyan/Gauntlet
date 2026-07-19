"""Repository-owned sensor command configuration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from .planner import SENSOR_IDS


CONFIG_SCHEMA = "gauntlet.sensor-config/v1"
DEFAULT_CONFIG = "gauntlet-sensors.json"


def _string_list(value, label, *, allow_empty=False):
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise RuntimeError(f"{label} must be a non-empty string array")
    return [item.strip() for item in value]


def load_sensor_config(project_root: Path, supplied: Optional[Path] = None):
    project_root = project_root.resolve()
    path = supplied or project_root / DEFAULT_CONFIG
    if not path.is_absolute():
        path = project_root / path
    path = path.resolve()
    try:
        path.relative_to(project_root)
    except ValueError as error:
        raise RuntimeError("sensor config must be inside the project root") from error
    if not path.is_file():
        return {
            "path": path,
            "sha256": None,
            "commands": {},
        }
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"sensor config could not be read: {error}") from error
    if not isinstance(value, dict) or value.get("schema") != CONFIG_SCHEMA:
        raise RuntimeError(f"sensor config schema must be {CONFIG_SCHEMA}")
    raw_commands = value.get("commands")
    if not isinstance(raw_commands, dict):
        raise RuntimeError("sensor config commands must be an object")

    commands = {}
    for sensor, entry in raw_commands.items():
        if sensor not in SENSOR_IDS:
            raise RuntimeError(f"sensor config contains unknown sensor: {sensor}")
        if not isinstance(entry, dict):
            raise RuntimeError(f"sensor config command {sensor} must be an object")
        argv = _string_list(entry.get("argv"), f"sensor config command {sensor}.argv")
        required = entry.get("required", True)
        if not isinstance(required, bool):
            raise RuntimeError(f"sensor config command {sensor}.required must be boolean")
        covers = entry.get("covers", [])
        if covers:
            covers = _string_list(
                covers,
                f"sensor config command {sensor}.covers",
            )
            unknown = sorted(set(covers) - set(SENSOR_IDS))
            if unknown:
                raise RuntimeError(
                    f"sensor config command {sensor}.covers has unknown sensors: "
                    + ", ".join(unknown)
                )
        timeout = entry.get("timeoutSeconds", 600)
        if (
            not isinstance(timeout, int)
            or isinstance(timeout, bool)
            or timeout < 1
            or timeout > 7200
        ):
            raise RuntimeError(
                f"sensor config command {sensor}.timeoutSeconds must be 1..7200"
            )
        commands[sensor] = {
            "sensor": sensor,
            "argv": argv,
            "required": required,
            "covers": sorted(set(covers)),
            "timeoutSeconds": timeout,
        }
    return {
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "commands": commands,
    }
