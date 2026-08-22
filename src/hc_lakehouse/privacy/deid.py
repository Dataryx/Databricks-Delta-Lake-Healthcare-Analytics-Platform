"""De-identification pipeline: Bronze patient → restricted xref + de-id Silver patient."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pyspark.sql import functions as F
from pyspark.sql.types import BooleanType, StringType, TimestampType

from hc_lakehouse.privacy.hashing import attach_surrogate_key, write_patient_crosswalk
from hc_lakehouse.privacy.safe_harbor import age_band_from_birth_year, zip3_safe_harbor
from hc_lakehouse.silver.cleanse import (
    canonical_lower,
    dedupe_latest,
    normalize_null_tokens,
    trim_strings,
)
from hc_lakehouse.silver.contracts import assert_contract, load_contract
from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, read_delta, table_exists, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

logger = get_logger(__name__)

DIRECT_ID_COLUMNS = frozenset(
    {
        "patient_id",
        "family_name",
        "given_name",
        "source_patient_token",
        "birth_date",
        "postal_code",
        "npi_token",
    }
)


def deidentify_patients(
    bronze_patients: DataFrame,
    pepper: str,
    batch_id: str,
) -> DataFrame:
    """Apply Safe Harbor-oriented transforms; output has no direct identifiers.

    Grain: one current SCD2 row per patient_sk.
    """
    df = trim_strings(bronze_patients)
    df = normalize_null_tokens(df)
    df = canonical_lower(df, ["sex", "race", "ethnicity"])
    df = attach_surrogate_key(df, "patient_id", "patient_sk", pepper)
    df = (
        df.withColumn("birth_year", F.year(F.to_date(F.col("birth_date"))))
        .withColumn("age_band", age_band_from_birth_year("birth_year"))
        .withColumn("zip3", zip3_safe_harbor("postal_code"))
        .withColumn(
            "deceased_flag",
            F.when(F.lower(F.col("deceased_flag").cast(StringType())).isin("true", "1"), True)
            .when(F.lower(F.col("deceased_flag").cast(StringType())).isin("false", "0"), False)
            .otherwise(F.lit(False).cast(BooleanType())),
        )
        .withColumn("valid_from", F.lit(datetime(1900, 1, 1, tzinfo=timezone.utc)))
        .withColumn("valid_to", F.lit(None).cast(TimestampType()))
        .withColumn("is_current", F.lit(True))
        .withColumn(
            "row_hash",
            F.sha2(
                F.concat_ws(
                    "|",
                    F.col("patient_sk"),
                    F.col("sex"),
                    F.col("race"),
                    F.col("ethnicity"),
                    F.col("zip3"),
                    F.col("age_band"),
                ),
                256,
            ),
        )
        .withColumn("_batch_id", F.lit(batch_id))
    )
    df = dedupe_latest(df, ["patient_sk"], "_ingest_ts")
    out = df.select(
        "patient_sk",
        "sex",
        "race",
        "ethnicity",
        "birth_year",
        "age_band",
        "zip3",
        "deceased_flag",
        "valid_from",
        "valid_to",
        "is_current",
        "row_hash",
        "_batch_id",
    )
    leaked = DIRECT_ID_COLUMNS.intersection(out.columns)
    if leaked:
        raise ValueError(f"Direct identifiers leaked into de-id patient frame: {leaked}")
    return out


def build_deid_patient_layer(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
    batch_id: str | None = None,
) -> dict[str, int]:
    """Write restricted crosswalk + overwrite silver.patient with de-identified rows."""
    cfg = config or load_config()
    bid = batch_id or datetime.now(timezone.utc).strftime("deid-%Y%m%dT%H%M%SZ")
    bronze_path = delta_table_path(cfg.local_delta_root, "bronze", "patient_raw")
    if not table_exists(spark, bronze_path):
        raise FileNotFoundError(f"Missing bronze patients at {bronze_path}")
    bronze = read_delta(spark, bronze_path)
    xref = write_patient_crosswalk(spark, bronze, config=cfg)
    pepper = cfg.deid_salt()
    silver = deidentify_patients(bronze, pepper, bid)
    assert_contract(silver, load_contract("patient"))
    write_delta(
        silver,
        delta_table_path(cfg.local_delta_root, "silver", "patient"),
        mode="overwrite",
        enable_cdf=True,
    )
    counts = {"patient_xref": xref.count(), "silver_patient": silver.count()}
    logger.info("deid_patient_layer_complete", extra=counts)
    return counts
