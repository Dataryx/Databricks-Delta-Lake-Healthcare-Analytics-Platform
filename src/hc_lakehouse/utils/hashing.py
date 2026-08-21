"""Hashing and record-identity helpers (no PHI in logs)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable


def sha256_hex(value: str) -> str:
    """Return hex SHA-256 digest of a UTF-8 string."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_record_hash(parts: Iterable[str | None]) -> str:
    """Compute a stable hash over ordered business-payload parts.

    ``None`` and empty strings are normalized to the token ``<NULL>`` so that
    missing fields do not silently collide with empty strings inconsistently.
    """
    normalized = [(p if p not in (None, "") else "<NULL>") for p in parts]
    payload = "\u241f".join(normalized)  # unit separator
    return sha256_hex(payload)
