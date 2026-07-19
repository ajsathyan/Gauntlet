"""Generic local workstream serialization."""

from .cli import register
from .queue import QueueError, WorkstreamQueue

__all__ = ["QueueError", "WorkstreamQueue", "register"]
