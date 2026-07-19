"""Small, source-bound workflow contracts."""

from .application import (
    authorize_candidate,
    build_entry,
    completion_check,
    record_verification_verdict,
    validate_prebuild_reviews,
    verify_entry,
)
from .cli import register
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
    "authorize_candidate",
    "bind_candidate_revision",
    "build_entry",
    "completion_check",
    "completion_status",
    "register",
    "record_verdict",
    "record_verification_verdict",
    "validate_prebuild_reviews",
    "verify_entry",
]
