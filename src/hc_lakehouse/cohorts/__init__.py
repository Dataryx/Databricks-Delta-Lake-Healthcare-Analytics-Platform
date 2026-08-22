"""Cohorts package API."""

from __future__ import annotations

__all__ = ["build_cohort", "load_cohort", "list_cohorts"]


def __getattr__(name: str) -> object:
    if name == "build_cohort":
        from hc_lakehouse.cohorts.compiler import build_cohort

        return build_cohort
    if name in {"load_cohort", "list_cohorts"}:
        from hc_lakehouse.cohorts import definition as _def

        return getattr(_def, name)
    raise AttributeError(name)
