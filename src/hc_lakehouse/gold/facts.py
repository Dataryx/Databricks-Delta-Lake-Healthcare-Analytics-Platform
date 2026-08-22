"""Gold fact builders. Grain documented per function."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F
from pyspark.sql.window import Window

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def build_fact_encounter(silver_encounter: DataFrame) -> DataFrame:
    """Encounter fact.

    Grain: one row per encounter_sk.
    """
    return silver_encounter.select(
        F.col("encounter_sk").alias("encounter_key"),
        F.col("patient_sk").alias("patient_key"),
        F.col("provider_sk").alias("provider_key"),
        F.col("organization_sk").alias("organization_key"),
        F.col("care_setting").alias("care_setting_key"),
        F.date_format(F.col("admit_ts"), "yyyyMMdd").cast("int").alias("admit_date_key"),
        F.when(
            F.col("discharge_ts").isNotNull(),
            F.date_format(F.col("discharge_ts"), "yyyyMMdd").cast("int"),
        ).alias("discharge_date_key"),
        "admit_ts",
        "discharge_ts",
        (
            F.when(
                F.col("discharge_ts").isNotNull(),
                (F.unix_timestamp(F.col("discharge_ts")) - F.unix_timestamp(F.col("admit_ts")))
                / 86400.0,
            ).otherwise(F.lit(0.0))
        ).alias("los_days"),
        F.lit(1).alias("encounter_count"),
    )


def build_fact_lab_result(silver_labs: DataFrame) -> DataFrame:
    """Lab result fact.

    Grain: one row per lab_result_sk.
    """
    return silver_labs.select(
        F.col("lab_result_sk").alias("lab_result_key"),
        F.col("patient_sk").alias("patient_key"),
        F.col("encounter_sk").alias("encounter_key"),
        F.col("loinc_code").alias("lab_test_key"),
        "value_num",
        "unit",
        "resulted_ts",
        F.date_format(F.col("resulted_ts"), "yyyyMMdd").cast("int").alias("result_date_key"),
    )


def build_fact_readmission(fact_encounter: DataFrame) -> DataFrame:
    """30-day all-cause readmission fact for inpatient index stays.

    Grain: one row per index inpatient encounter with readmission_30d flag.
    """
    inpatient = fact_encounter.filter(F.col("care_setting_key") == "inpatient")
    w = Window.partitionBy("patient_key").orderBy(F.col("admit_ts").asc())
    ordered = inpatient.withColumn("_next_admit", F.lead("admit_ts").over(w))
    return (
        ordered.withColumn(
            "readmission_30d",
            F.when(
                F.col("_next_admit").isNotNull()
                & (
                    (
                        F.unix_timestamp(F.col("_next_admit"))
                        - F.unix_timestamp(F.coalesce(F.col("discharge_ts"), F.col("admit_ts")))
                    )
                    / 86400.0
                    <= 30
                ),
                F.lit(True),
            ).otherwise(F.lit(False)),
        )
        .drop("_next_admit")
        .select(
            "encounter_key",
            "patient_key",
            "admit_date_key",
            "discharge_date_key",
            "los_days",
            "readmission_30d",
            F.when(F.col("readmission_30d"), 1).otherwise(0).alias("readmission_30d_count"),
        )
    )


def build_fact_survey_response(
    survey_scores: DataFrame,
    patient_sk_col: str = "patient_sk",
) -> DataFrame:
    """Survey score fact (administration × instrument).

    Grain: one row per score_id / administration.
    Expects columns: score_id, patient_sk, instrument_name, wave, total_score,
    severity_band, scoring_version, administered_ts (optional).
    """
    df = survey_scores
    if "administered_ts" not in df.columns and "wave" in df.columns:
        df = df.withColumn("administered_ts", F.lit(None).cast("timestamp"))
    return df.select(
        F.col("score_id").alias("survey_response_key"),
        F.col(patient_sk_col).alias("patient_key"),
        F.col("instrument_name").alias("instrument_key"),
        "wave",
        F.col("total_score").cast("double").alias("total_score"),
        "severity_band",
        "scoring_version",
        F.lit(1).alias("response_count"),
    )
