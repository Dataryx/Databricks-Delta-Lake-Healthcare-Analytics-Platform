"""Silver package — import transforms from submodules to avoid privacy circular imports."""

from __future__ import annotations

__all__ = ["build_silver_core"]


def __getattr__(name: str) -> object:
    if name == "build_silver_core":
        from hc_lakehouse.silver.transform import build_silver_core

        return build_silver_core
    raise AttributeError(name)
