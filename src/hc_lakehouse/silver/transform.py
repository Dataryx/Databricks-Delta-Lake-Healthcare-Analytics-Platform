"""Silver transforms for core clinical entities (pre–full Safe Harbor in Phase 4).

Phase 3 establishes conformed keys as ``SYN-*`` surrogate stand-ins and drops
direct name columns from published Silver tables. HMAC crosswalk + date shift
land in Phase 4; until then ``patient_sk`` equals the synthetic source id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType, TimestampType

from hc_lakehouse.silver.cleanse import (
    canonical_lower,
    dedupe_latest,
    normalize_null_tokens,
    parse_ts,
    trim_strings,
)
from hc_lakehouse.silver.contracts import assert_contract, load_contract
from hc_lakehouse.silver.quarantine import quarantine_rows
from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, read_delta, table_exists, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

logger = get_logger(__name__)

# Columns that must never appear in Silver (direct identifiers)
FORBIDDEN_SILVER_COLUMNS = frozenset(
    {
        "family_name",
        "given_name",
        "source_patient_token",
        "npi_token",
        "birth_date",
        "postal_code",
    }
)


def _read_bronze(spark: SparkSession, cfg: PlatformConfig, table: str) -> DataFrame:
    path = delta_table_path(cfg.local_delta_root, "bronze", table)
    if not table_exists(spark, path):
        raise FileNotFoundError(f"Bronze table missing: {path}")
    return read_delta(spark, path)


def transform_patient(bronze: DataFrame, batch_id: str) -> DataFrame:
    """Conformed patient demographics (SCD2 current snapshot).

    Grain: one current row per patient_sk.
    """
    df = trim_strings(bronze)
    df = normalize_null_tokens(df)
    df = canonical_lower(df, ["sex", "race", "ethnicity"])
    df = (
        df.withColumn("patient_sk", F.col("patient_id"))
        .withColumn("birth_year", F.year(F.to_date(F.col("birth_date"))))
        .withColumn(
            "age_band",
            F.when(F.col("birth_year").isNull(), F.lit("unknown")).otherwise(
                F.concat(
                    F.floor((F.lit(2024) - F.col("birth_year")) / 10).cast(StringType()),
                    F.lit("0s"),
                )
            ),
        )
        .withColumn("zip3", F.substring(F.col("postal_code"), 1, 3))
        .withColumn(
            "deceased_flag",
            F.when(F.lower(F.col("deceased_flag").cast(StringType())).isin("true", "1"), True)
            .when(F.lower(F.col("deceased_flag").cast(StringType())).isin("false", "0"), False)
            .otherwise(F.lit(False)),
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
    for forbidden in FORBIDDEN_SILVER_COLUMNS:
        if forbidden in out.columns:
            raise ValueError(f"Forbidden identifier column in silver.patient: {forbidden}")
    return out


def transform_encounter(
    bronze: DataFrame,
    patients: DataFrame,
    batch_id: str,
) -> tuple[DataFrame, DataFrame, DataFrame]:
    """Conformed encounters; orphans and window violators returned for quarantine.

    Grain: one row per encounter_sk.
    Returns ``(good, patient_orphans, window_violations)``.
    """
    df = trim_strings(bronze)
    df = normalize_null_tokens(df)
    df = canonical_lower(df, ["care_setting", "encounter_class"])
    df = parse_ts(df, "admit_ts")
    df = parse_ts(df, "discharge_ts")
    df = (
        df.withColumn("encounter_sk", F.col("encounter_id"))
        .withColumn("patient_sk", F.col("patient_id"))
        .withColumn("provider_sk", F.col("provider_id"))
        .withColumn("organization_sk", F.col("organization_id"))
        .withColumn("_batch_id", F.lit(batch_id))
    )
    df = dedupe_latest(df, ["encounter_sk"], "_ingest_ts")
    patient_keys = patients.select("patient_sk").distinct()
    good = df.join(patient_keys, on="patient_sk", how="inner")
    orphan = df.join(patient_keys, on="patient_sk", how="left_anti")
    out = good.select(
        "encounter_sk",
        "patient_sk",
        "provider_sk",
        "organization_sk",
        "care_setting",
        "admit_ts",
        "discharge_ts",
        "_batch_id",
    )
    bad_window = out.filter(
        F.col("discharge_ts").isNotNull() & (F.col("discharge_ts") < F.col("admit_ts"))
    )
    out = out.filter(F.col("discharge_ts").isNull() | (F.col("discharge_ts") >= F.col("admit_ts")))
    return out, orphan, bad_window


def transform_lab_result(
    bronze: DataFrame,
    patients: DataFrame,
    encounters: DataFrame,
    batch_id: str,
) -> tuple[DataFrame, DataFrame]:
    """Conformed labs; unresolved patient/encounter rows go to quarantine."""
    df = trim_strings(bronze)
    df = normalize_null_tokens(df)
    df = parse_ts(df, "resulted_ts")
    df = (
        df.withColumn("lab_result_sk", F.col("lab_result_id"))
        .withColumn("patient_sk", F.col("patient_id"))
        .withColumn("encounter_sk", F.col("encounter_id"))
        .withColumn("value_num", F.col("value_num").cast(DoubleType()))
        .withColumn("_batch_id", F.lit(batch_id))
    )
    df = dedupe_latest(df, ["lab_result_sk"], "_ingest_ts")
    patient_keys = patients.select("patient_sk").distinct()
    enc_keys = encounters.select("encounter_sk").distinct()

    no_patient = df.join(patient_keys, on="patient_sk", how="left_anti")
    with_patient = df.join(patient_keys, on="patient_sk", how="inner")
    has_enc = with_patient.filter(F.col("encounter_sk").isNotNull())
    no_enc_needed = with_patient.filter(F.col("encounter_sk").isNull())
    enc_ok = has_enc.join(enc_keys, on="encounter_sk", how="inner")
    enc_bad = has_enc.join(enc_keys, on="encounter_sk", how="left_anti")
    orphan = no_patient.unionByName(enc_bad, allowMissingColumns=True)
    good = no_enc_needed.unionByName(enc_ok, allowMissingColumns=True)
    out = good.select(
        "lab_result_sk",
        "patient_sk",
        "encounter_sk",
        "loinc_code",
        "value_num",
        "unit",
        "resulted_ts",
        "_batch_id",
    )
    return out, orphan


def build_silver_core(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
    batch_id: str | None = None,
) -> dict[str, int]:
    """Build silver.patient, silver.encounter, silver.lab_result from Bronze."""
    cfg = config or load_config()
    bid = batch_id or datetime.now(timezone.utc).strftime("silver-%Y%m%dT%H%M%SZ")
    counts: dict[str, int] = {}

    patient_bronze = _read_bronze(spark, cfg, "patient_raw")
    patients = transform_patient(patient_bronze, bid)
    assert_contract(patients, load_contract("patient"))
    write_delta(
        patients,
        delta_table_path(cfg.local_delta_root, "silver", "patient"),
        mode="overwrite",
        enable_cdf=True,
    )
    counts["patient"] = patients.count()

    enc_bronze = _read_bronze(spark, cfg, "encounter_raw")
    encounters, enc_orphans, enc_window = transform_encounter(enc_bronze, patients, bid)
    assert_contract(encounters, load_contract("encounter"))
    quarantine_rows(
        spark, enc_orphans, entity="encounter", reason_code="orphan", batch_id=bid, config=cfg
    )
    quarantine_rows(
        spark,
        enc_window,
        entity="encounter",
        reason_code="window",
        batch_id=bid,
        config=cfg,
    )
    write_delta(
        encounters,
        delta_table_path(cfg.local_delta_root, "silver", "encounter"),
        mode="overwrite",
        enable_cdf=True,
    )
    counts["encounter"] = encounters.count()

    lab_bronze = _read_bronze(spark, cfg, "lab_result_raw")
    labs, lab_orphans = transform_lab_result(lab_bronze, patients, encounters, bid)
    assert_contract(labs, load_contract("lab_result"))
    quarantine_rows(
        spark, lab_orphans, entity="lab_result", reason_code="orphan", batch_id=bid, config=cfg
    )
    write_delta(
        labs,
        delta_table_path(cfg.local_delta_root, "silver", "lab_result"),
        mode="overwrite",
        enable_cdf=True,
    )
    counts["lab_result"] = labs.count()
    counts["lab_result_quarantine"] = lab_orphans.count() if lab_orphans.limit(1).count() else 0

    logger.info("silver_core_complete", extra=counts)
    return counts
