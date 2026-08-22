"""Bronze ingestion: local batch (demo) and Auto Loader (cloud) with graceful degrade."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from hc_lakehouse.bronze.transform import (
    BRONZE_TABLES,
    PIPELINE_VERSION,
    add_technical_columns,
    anti_join_existing_hashes,
    dedupe_by_record_hash,
    validate_tech_columns,
)
from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, read_delta, table_exists, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

logger = get_logger(__name__)


def _entity_source_system(entity: str) -> str:
    if entity.startswith("survey_"):
        return "survey_sim"
    return "synthea_sim"


def _is_empty(df: DataFrame) -> bool:
    """True if the frame has no rows. Stays on the JVM (avoids Windows timestamp pickle)."""
    return df.limit(1).count() == 0


def read_landing_csv(spark: SparkSession, path: Path) -> DataFrame:
    """Read a landing CSV as strings — Bronze stores the payload as received."""
    return (
        spark.read.option("header", True)
        .option("inferSchema", False)
        .option("mode", "PERMISSIVE")
        .csv(str(path))
    )


def ingest_entity_batch(
    spark: SparkSession,
    entity: str,
    landing_file: Path,
    *,
    config: PlatformConfig | None = None,
    batch_id: str | None = None,
) -> int:
    """Ingest one landing CSV into the corresponding Bronze Delta table.

    Idempotent: rows whose ``_record_hash`` already exist in Bronze are skipped.
    Returns count of newly appended rows.
    """
    if entity not in BRONZE_TABLES:
        raise KeyError(f"Unknown bronze entity: {entity}")
    cfg = config or load_config()
    table = BRONZE_TABLES[entity]
    target = delta_table_path(cfg.local_delta_root, "bronze", table)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bid = batch_id or f"batch-{stamp}-{uuid.uuid4().hex[:8]}"

    raw = read_landing_csv(spark, landing_file)
    if _is_empty(raw):
        logger.info("bronze_skip_empty", extra={"entity": entity, "file": str(landing_file)})
        return 0

    mod_ts = datetime.fromtimestamp(landing_file.stat().st_mtime, tz=timezone.utc)
    bronze_df = add_technical_columns(
        raw,
        source_system=_entity_source_system(entity),
        source_file=str(landing_file.as_posix()),
        batch_id=bid,
        pipeline_version=PIPELINE_VERSION,
        file_modification_time=mod_ts,
    )
    bronze_df = dedupe_by_record_hash(bronze_df)
    validate_tech_columns(bronze_df)

    existing = None
    if table_exists(spark, target):
        existing = read_delta(spark, target)
    to_write = anti_join_existing_hashes(bronze_df, existing)
    new_count = to_write.count()
    if new_count == 0:
        logger.info(
            "bronze_idempotent_noop",
            extra={"entity": entity, "table": table, "batch_id": bid},
        )
        return 0

    write_delta(to_write, target, mode="append", enable_cdf=True)
    logger.info(
        "bronze_append",
        extra={
            "entity": entity,
            "table": table,
            "rows": new_count,
            "batch_id": bid,
            "path": target,
        },
    )
    return new_count


def ingest_landing_directory(
    spark: SparkSession,
    landing_root: Path,
    *,
    config: PlatformConfig | None = None,
    entities: list[str] | None = None,
) -> dict[str, int]:
    """Batch-ingest all known entities from ``landing/clinical`` and ``landing/survey``.

    Cloud Auto Loader is not required for local demo; see ``try_autoloader_stream``.
    """
    cfg = config or load_config()
    selected = entities or list(BRONZE_TABLES.keys())
    results: dict[str, int] = {}
    clinical = landing_root / "clinical"
    survey = landing_root / "survey"

    for entity in selected:
        candidates = [
            clinical / f"{entity}.csv",
            survey / f"{entity}.csv",
            landing_root / f"{entity}.csv",
        ]
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            logger.warning("landing_file_missing", extra={"entity": entity})
            results[entity] = 0
            continue
        results[entity] = ingest_entity_batch(spark, entity, path, config=cfg)
    return results


def try_autoloader_stream(
    spark: SparkSession,
    source_path: str,
    checkpoint_path: str,
    *,
    schema_location: str,
) -> DataFrame | None:
    """Attempt Databricks Auto Loader (``cloudFiles``); degrade gracefully if unavailable.

    Local Spark does not support ``cloudFiles``. Returns ``None`` after logging.
    """
    try:
        stream = (
            spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "csv")
            .option("cloudFiles.schemaLocation", schema_location)
            .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
            .option("cloudFiles.inferColumnTypes", "true")
            .option("rescuedDataColumn", "_rescued_data")
            .load(source_path)
        )
        logger.info(
            "autoloader_stream_ready",
            extra={"source": source_path, "checkpoint": checkpoint_path},
        )
        return stream
    except Exception as exc:  # noqa: BLE001 — expected on local
        logger.warning(
            "autoloader_unavailable",
            extra={
                "detail": "cloudFiles requires Databricks runtime; using local batch ingest.",
                "error": str(exc),
            },
        )
        return None
