"""IO helpers for local Delta paths and idempotent writes."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

logger = get_logger(__name__)

WriteMode = Literal["append", "overwrite", "error", "ignore"]


def ensure_dir(path: Path) -> Path:
    """Create directory (and parents) if missing; return path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def delta_table_path(root: Path, schema: str, table: str) -> str:
    """Build a filesystem path for a local Delta table."""
    path = root / schema / table
    ensure_dir(path.parent)
    return str(path)


def write_delta(
    df: DataFrame,
    path: str,
    *,
    mode: WriteMode = "append",
    partition_by: list[str] | None = None,
    enable_cdf: bool = True,
) -> None:
    """Write a DataFrame as Delta with optional CDF and partitioning.

    Idempotent append semantics are the caller's responsibility (e.g. merge or
    partition overwrite). This helper only standardizes options.
    """
    writer = df.write.format("delta").mode(mode)
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    options: dict[str, str] = {}
    if enable_cdf:
        options["delta.enableChangeDataFeed"] = "true"
    if options:
        writer = writer.options(**options)
    writer.save(path)
    logger.info(
        "delta_write_complete",
        extra={"path": path, "mode": mode, "partition_by": partition_by or []},
    )


def read_delta(spark: SparkSession, path: str) -> DataFrame:
    """Read a Delta table from a filesystem path."""
    return spark.read.format("delta").load(path)


def table_exists(spark: SparkSession, path: str) -> bool:
    """Return True if a Delta table exists at ``path``."""
    try:
        from delta.tables import DeltaTable

        return DeltaTable.isDeltaTable(spark, path)
    except Exception:  # noqa: BLE001
        return Path(path).joinpath("_delta_log").exists()
