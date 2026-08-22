"""Reproducibility package."""

from __future__ import annotations

__all__ = ["RunManifest", "checksum_dataframe", "load_manifest"]


def __getattr__(name: str) -> object:
    if name in {"RunManifest", "checksum_dataframe", "load_manifest"}:
        from hc_lakehouse.reproducibility import manifest as _m

        return getattr(_m, name)
    raise AttributeError(name)
