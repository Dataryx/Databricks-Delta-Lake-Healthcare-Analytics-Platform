"""Gold package API."""

from __future__ import annotations

__all__ = ["build_gold"]


def __getattr__(name: str) -> object:
    if name == "build_gold":
        from hc_lakehouse.gold.build import build_gold

        return build_gold
    raise AttributeError(name)
