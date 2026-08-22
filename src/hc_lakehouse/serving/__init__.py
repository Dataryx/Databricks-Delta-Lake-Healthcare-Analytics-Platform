"""Helpers for warehouse SQL under ``dashboards/sql``."""

from __future__ import annotations

from pathlib import Path

from hc_lakehouse.utils.config import REPO_ROOT
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)

DASHBOARD_SQL = (
    "utilization.sql",
    "readmission.sql",
    "prom_scores.sql",
    "clinical_prom_linkage.sql",
)


def dashboard_sql_dir() -> Path:
    return REPO_ROOT / "dashboards" / "sql"


def list_dashboard_sql() -> list[Path]:
    """Return the core dashboard query paths. Raises if any file is missing."""
    root = dashboard_sql_dir()
    paths = [root / name for name in DASHBOARD_SQL]
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing dashboard SQL: {missing}")
    logger.info("dashboard_sql_ok", extra={"count": len(paths)})
    return paths
