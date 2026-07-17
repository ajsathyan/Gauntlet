"""Stable hashing primitives shared across Gauntlet."""

import hashlib


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
