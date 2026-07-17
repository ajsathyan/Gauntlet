"""UTC timestamp conventions with named precision."""

from datetime import datetime, timezone


def utc_now_seconds() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
