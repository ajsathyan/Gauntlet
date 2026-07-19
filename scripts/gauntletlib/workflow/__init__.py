"""Small, source-bound workflow contracts."""

from .contracts import (
    ContractError,
    accept_design,
    bind_candidate_revision,
    completion_status,
    record_verdict,
)

__all__ = [
    "ContractError",
    "accept_design",
    "bind_candidate_revision",
    "completion_status",
    "record_verdict",
]
