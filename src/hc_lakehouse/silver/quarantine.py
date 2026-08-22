"""Quarantine path — fail closed, never silently drop bad rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pyspark.sql import functions as F
from pyspark.sql.types import StringType, TimestampType

from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

logger = get_logger(__name__)


def quarantine_rows(
    spark: SparkSession,
    bad: DataFrame,
    *,
    entity: str,
    reason_code: str,
    batch_id: str,
    config: PlatformConfig | None = None,
) -> int:
    """Append rejected rows to ``quarantine.<entity>_<reason>`` with metadata.

    Returns number of quarantined rows. Empty frames are a no-op.
    """
    if bad.limit(1).count() == 0:
        return 0
    cfg = config or load_config()
    table = f"{entity}_{reason_code.lower()}"
    path = delta_table_path(cfg.local_delta_root, "quarantine", table)
    payload = (
        bad.withColumn("_quarantine_ts", F.lit(datetime.now(timezone.utc)).cast(TimestampType()))
        .withColumn("_quarantine_reason", F.lit(reason_code))
        .withColumn("_quarantine_batch_id", F.lit(batch_id))
        .withColumn("_quarantine_entity", F.lit(entity))
    )
    # Collapse business columns to JSON for replayability without schema fights
    biz = [c for c in bad.columns if not c.startswith("_")]
    if biz:
        payload = payload.withColumn(
            "_raw_payload_json",
            F.to_json(F.struct(*[F.col(c) for c in biz])),
        )
    else:
        payload = payload.withColumn("_raw_payload_json", F.lit(None).cast(StringType()))

    write_delta(payload, path, mode="append", enable_cdf=False)
    n = bad.count()
    logger.warning(
        "rows_quarantined",
        extra={"entity": entity, "reason": reason_code, "rows": n, "path": path},
    )
    return n
