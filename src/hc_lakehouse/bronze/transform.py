"""Bronze-layer technical metadata and append-only ingest helpers.

Bronze stores the payload exactly as received plus technical columns only.
No business logic, filtering, or updates. Change Data Feed is enabled on write.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, TimestampType

from hc_lakehouse.utils.hashing import sha256_hex
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)

TECH_COLUMNS: tuple[str, ...] = (
    "_ingest_ts",
    "_source_system",
    "_source_file",
    "_file_modification_time",
    "_batch_id",
    "_record_hash",
    "_rescued_data",
    "_ingest_pipeline_version",
)

PIPELINE_VERSION = "0.2.0"

# Landing entity → bronze table name
BRONZE_TABLES: dict[str, str] = {
    "patient": "patient_raw",
    "encounter": "encounter_raw",
    "condition": "condition_raw",
    "observation": "observation_raw",
    "lab_result": "lab_result_raw",
    "medication": "medication_raw",
    "procedure": "procedure_raw",
    "immunization": "immunization_raw",
    "provider": "provider_raw",
    "organization": "organization_raw",
    "payer_claim": "payer_claim_raw",
    "survey_instrument": "survey_instrument_raw",
    "survey_item": "survey_item_raw",
    "survey_administration": "survey_administration_raw",
    "survey_response": "survey_response_raw",
    "consent": "consent_raw",
}


def business_columns(df: DataFrame) -> list[str]:
    """Return non-technical column names in stable order."""
    return [c for c in df.columns if not c.startswith("_")]


def add_technical_columns(
    df: DataFrame,
    *,
    source_system: str,
    source_file: str,
    batch_id: str,
    pipeline_version: str = PIPELINE_VERSION,
    file_modification_time: datetime | None = None,
) -> DataFrame:
    """Attach Bronze technical columns; compute ``_record_hash`` over business payload.

    Grain: one output row per input row. Does not drop or transform business fields.
    """
    mod_ts = file_modification_time or datetime.now(timezone.utc)
    biz = business_columns(df)
    # Hash = sha2 of concatenated business values (null → empty)
    if biz:
        concat_cols = [F.coalesce(F.col(c).cast(StringType()), F.lit("")) for c in biz]
        payload = F.concat_ws("\u241f", *concat_cols)
        record_hash = F.sha2(payload, 256)
    else:
        record_hash = F.lit(sha256_hex(""))

    return (
        df.withColumn("_ingest_ts", F.lit(datetime.now(timezone.utc)).cast(TimestampType()))
        .withColumn("_source_system", F.lit(source_system))
        .withColumn("_source_file", F.lit(source_file))
        .withColumn(
            "_file_modification_time",
            F.lit(mod_ts).cast(TimestampType()),
        )
        .withColumn("_batch_id", F.lit(batch_id))
        .withColumn("_record_hash", record_hash)
        .withColumn("_rescued_data", F.lit(None).cast(StringType()))
        .withColumn("_ingest_pipeline_version", F.lit(pipeline_version))
    )


def dedupe_by_record_hash(df: DataFrame) -> DataFrame:
    """Idempotent helper: keep first row per ``_record_hash`` within a batch.

    Used when replaying the same landing file so appends do not duplicate.
    Across batches, callers should anti-join existing Bronze hashes (see ingest).
    """
    if "_record_hash" not in df.columns:
        raise ValueError("_record_hash required before dedupe")
    return df.dropDuplicates(["_record_hash"])


def anti_join_existing_hashes(new_df: DataFrame, existing: DataFrame | None) -> DataFrame:
    """Return rows in ``new_df`` whose ``_record_hash`` is not already in Bronze."""
    if existing is None or existing.limit(1).count() == 0:
        return new_df
    existing_hashes = existing.select("_record_hash").distinct()
    return new_df.join(existing_hashes, on="_record_hash", how="left_anti")


def validate_tech_columns(df: DataFrame) -> None:
    """Fail closed if required technical columns are missing."""
    missing = [c for c in TECH_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Bronze frame missing technical columns: {missing}")


def list_bronze_entities() -> Sequence[str]:
    """Return landing entity keys that map to Bronze tables."""
    return tuple(BRONZE_TABLES.keys())
