"""Stable hashing primitives shared across Gauntlet."""

import hashlib


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


sha256_bytes = sha256
