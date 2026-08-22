"""Governance package API."""

from __future__ import annotations

__all__ = [
    "apply_grants",
    "load_access_matrix",
    "request_reid",
    "snapshot_lineage",
    "write_lineage_doc",
]


def __getattr__(name: str) -> object:
    if name == "apply_grants":
        from hc_lakehouse.governance.grants import apply_grants

        return apply_grants
    if name == "load_access_matrix":
        from hc_lakehouse.governance.matrix import load_access_matrix

        return load_access_matrix
    if name in {"request_reid", "assert_reid_justified"}:
        from hc_lakehouse.governance import audit as _a

        return getattr(_a, name)
    if name in {"snapshot_lineage", "write_lineage_doc"}:
        from hc_lakehouse.governance import lineage as _l

        return getattr(_l, name)
    raise AttributeError(name)
