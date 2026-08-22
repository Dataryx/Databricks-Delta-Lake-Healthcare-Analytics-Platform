"""HMAC surrogate keys and restricted crosswalk writers."""

from __future__ import annotations

import hashlib
import hmac
from typing import TYPE_CHECKING, Any

from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

logger = get_logger(__name__)


def hmac_sha256_hex(value: str, pepper: str) -> str:
    """Return hex HMAC-SHA256 of ``value`` using environment pepper."""
    return hmac.new(
        pepper.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def make_hmac_udf(pepper: str) -> Any:
    """Spark UDF: string → HMAC hex (pepper closed over; never logged)."""

    def _fn(value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return hmac_sha256_hex(value, pepper)

    return F.udf(_fn, StringType())


def attach_surrogate_key(
    df: DataFrame,
    source_col: str,
    sk_col: str,
    pepper: str,
) -> DataFrame:
    """Add surrogate key column from HMAC of source identifier."""
    udf = make_hmac_udf(pepper)
    return df.withColumn(sk_col, udf(F.col(source_col).cast(StringType())))


def write_patient_crosswalk(
    spark: SparkSession,
    bronze_patients: DataFrame,
    *,
    config: PlatformConfig | None = None,
) -> DataFrame:
    """Write ``restricted.patient_xref`` keyed by HMAC; source id only here.

    Grain: one row per source patient_id. Never grant outside break-glass group.
    """
    cfg = config or load_config()
    pepper = cfg.deid_salt()
    udf = make_hmac_udf(pepper)
    xref = (
        bronze_patients.select(
            F.col("patient_id").alias("source_patient_id"),
            F.col("_record_hash"),
            F.col("_batch_id"),
        )
        .dropDuplicates(["source_patient_id"])
        .withColumn("patient_sk", udf(F.col("source_patient_id")))
        .select("patient_sk", "source_patient_id", "_record_hash", "_batch_id")
    )
    path = delta_table_path(cfg.local_delta_root, "restricted", "patient_xref")
    write_delta(xref, path, mode="overwrite", enable_cdf=False)
    logger.info("patient_crosswalk_written", extra={"path": path, "rows": xref.count()})
    return xref
