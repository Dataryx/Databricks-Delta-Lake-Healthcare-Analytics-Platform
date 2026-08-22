"""Pipeline run logging and SLA freshness checks."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

import yaml
from pyspark.sql import Row

from hc_lakehouse.utils.config import REPO_ROOT, PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, table_exists, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

logger = get_logger(__name__)
WriteMode = Literal["append", "overwrite"]


def load_sla_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or (REPO_ROOT / "conf" / "ops" / "sla.yml")
    with cfg_path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)
    return data


def log_pipeline_run(
    spark: SparkSession,
    *,
    pipeline_name: str,
    status: str,
    duration_seconds: float,
    rows_in: int = 0,
    rows_out: int = 0,
    cost_proxy_dbus: float = 0.0,
    config: PlatformConfig | None = None,
) -> str:
    """Append a row to ``ops.pipeline_run_log``."""
    cfg = config or load_config()
    run_id = str(uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    df = spark.createDataFrame(
        [
            (
                run_id,
                pipeline_name,
                status,
                float(duration_seconds),
                int(rows_in),
                int(rows_out),
                float(cost_proxy_dbus),
                ts,
                cfg.catalog,
            )
        ],
        schema=(
            "run_id STRING, pipeline_name STRING, status STRING, duration_seconds DOUBLE, "
            "rows_in LONG, rows_out LONG, cost_proxy_dbus DOUBLE, logged_at STRING, catalog STRING"
        ),
    )
    path = delta_table_path(cfg.local_delta_root, "ops", "pipeline_run_log")
    mode: WriteMode = "append" if table_exists(spark, path) else "overwrite"
    write_delta(df, path, mode=mode, enable_cdf=False)
    logger.info(
        "pipeline_run_logged",
        extra={"run_id": run_id, "pipeline": pipeline_name, "status": status},
    )
    return run_id


def check_freshness(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
) -> list[dict[str, Any]]:
    """Evaluate SLA config; write ``ops.table_freshness`` and return missed SLAs."""
    cfg = config or load_config()
    sla = load_sla_config()
    ts = datetime.now(timezone.utc).isoformat()
    rows: list[Row] = []
    misses: list[dict[str, Any]] = []
    for name, pipe in (sla.get("pipelines") or {}).items():
        for table in pipe.get("tables") or []:
            parts = str(table).split(".", 1)
            if len(parts) != 2:
                continue
            schema, tbl = parts
            path = delta_table_path(cfg.local_delta_root, schema, tbl)
            exists = table_exists(spark, path)
            status = "ok" if exists else "missing"
            if not exists:
                misses.append(
                    {
                        "pipeline": name,
                        "table": table,
                        "sla_hours": pipe.get("sla_hours"),
                        "status": status,
                    }
                )
            rows.append(
                Row(
                    pipeline_name=name,
                    table_name=str(table),
                    sla_hours=int(pipe.get("sla_hours") or 24),
                    status=status,
                    checked_at=ts,
                    owner=str(pipe.get("owner") or "hc-platform"),
                )
            )
    if rows:
        out = delta_table_path(cfg.local_delta_root, "ops", "table_freshness")
        write_delta(spark.createDataFrame(rows), out, mode="overwrite", enable_cdf=False)
    if misses:
        logger.warning("sla_misses", extra={"count": len(misses), "misses": misses})
    return misses
