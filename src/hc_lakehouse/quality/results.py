"""Persist DQ results and expose a simple scorecard aggregate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pyspark.sql import Row

from hc_lakehouse.quality.engine import ValidationReport
from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, read_delta, table_exists, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

logger = get_logger(__name__)

DQ_RESULTS_TABLE = "dq_results"
WriteMode = Literal["append", "overwrite"]


def persist_dq_results(
    spark: SparkSession,
    report: ValidationReport,
    *,
    config: PlatformConfig | None = None,
) -> str:
    """Append rule results to ``ops.dq_results``. Returns Delta path."""
    cfg = config or load_config()
    path = delta_table_path(cfg.local_delta_root, "ops", DQ_RESULTS_TABLE)
    rows = [Row(**r) for r in report.to_rows()]
    if not rows:
        logger.info("dq_results_empty", extra={"table": report.table})
        return path
    df = spark.createDataFrame(rows)
    mode: WriteMode = "append" if table_exists(spark, path) else "overwrite"
    write_delta(df, path, mode=mode, enable_cdf=False)
    logger.info(
        "dq_results_persisted",
        extra={"path": path, "rows": len(rows), "run_id": report.run_id},
    )
    return path


def load_dq_results(spark: SparkSession, config: PlatformConfig | None = None) -> DataFrame:
    """Read ``ops.dq_results``; empty frame if missing."""
    cfg = config or load_config()
    path = delta_table_path(cfg.local_delta_root, "ops", DQ_RESULTS_TABLE)
    if not table_exists(spark, path):
        return spark.createDataFrame(
            [],
            schema=(
                "run_id STRING, table STRING, rule_id STRING, category STRING, "
                "severity STRING, owner STRING, rows_scanned LONG, rows_failed LONG, "
                "pass_rate DOUBLE, threshold DOUBLE, status STRING, ts STRING, description STRING"
            ),
        )
    return read_delta(spark, path)


def scorecard_summary(spark: SparkSession, config: PlatformConfig | None = None) -> DataFrame:
    """Latest pass_rate by table and rule for dashboard-style consumption."""
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    df = load_dq_results(spark, config)
    if df.limit(1).count() == 0:
        return df
    w = Window.partitionBy("table", "rule_id").orderBy(F.col("ts").desc())
    return (
        df.withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
        .select(
            "table",
            "rule_id",
            "severity",
            "status",
            "pass_rate",
            "threshold",
            "rows_failed",
            "ts",
            "owner",
        )
    )
