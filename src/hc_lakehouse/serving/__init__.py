"""Serving-layer helpers: register dashboard SQL paths and validate presence."""

from __future__ import annotations

from pathlib import Path

from hc_lakehouse.utils.config import REPO_ROOT
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)

DASHBOARD_SQL = (
    "dashboard_utilization.sql",
    "dashboard_readmission.sql",
    "dashboard_prom.sql",
    "dashboard_linkage.sql",
)


def dashboard_sql_dir() -> Path:
    return REPO_ROOT / "serving" / "sql"


def list_dashboard_sql() -> list[Path]:
    root = dashboard_sql_dir()
    paths = [root / name for name in DASHBOARD_SQL]
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing dashboard SQL: {missing}")
    logger.info("dashboard_sql_ok", extra={"count": len(paths)})
    return paths
