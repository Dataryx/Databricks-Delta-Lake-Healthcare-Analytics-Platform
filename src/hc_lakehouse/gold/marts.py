"""Research marts — wide, purpose-built analytical tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F
from pyspark.sql.window import Window

from hc_lakehouse.gold.privacy_serving import apply_small_cell_suppression

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def build_mart_patient_360(
    dim_patient: DataFrame,
    fact_encounter: DataFrame,
    fact_lab: DataFrame,
) -> DataFrame:
    """Patient 360 mart.

    Grain: one row per patient_key with utilization and lab rollups.
    """
    enc = fact_encounter.groupBy("patient_key").agg(
        F.count("*").alias("encounter_count"),
        F.sum(F.when(F.col("care_setting_key") == "inpatient", 1).otherwise(0)).alias(
            "inpatient_count"
        ),
        F.sum(F.when(F.col("care_setting_key") == "emergency", 1).otherwise(0)).alias("ed_count"),
        F.avg("los_days").alias("avg_los_days"),
        F.min("admit_ts").alias("first_admit_ts"),
        F.max("admit_ts").alias("last_admit_ts"),
    )
    labs = fact_lab.groupBy("patient_key").agg(
        F.count("*").alias("lab_result_count"),
        F.countDistinct("lab_test_key").alias("distinct_lab_tests"),
    )
    return (
        dim_patient.join(enc, on="patient_key", how="left")
        .join(labs, on="patient_key", how="left")
        .fillna(
            {
                "encounter_count": 0,
                "inpatient_count": 0,
                "ed_count": 0,
                "lab_result_count": 0,
                "distinct_lab_tests": 0,
            }
        )
    )


def build_mart_utilization(fact_encounter: DataFrame, dim_patient: DataFrame) -> DataFrame:
    """Utilization by age_band × sex × care_setting with small-cell suppression.

    Grain: one aggregate row per demographic × setting stratum.
    k-anonymity: counts < HC_SMALL_CELL_K masked.
    """
    joined = fact_encounter.join(
        dim_patient.select("patient_key", "age_band", "sex"),
        on="patient_key",
        how="inner",
    )
    agg = joined.groupBy("age_band", "sex", "care_setting_key").agg(
        F.count("*").alias("n"),
        F.avg("los_days").alias("avg_los_days"),
    )
    return apply_small_cell_suppression(agg, "n", mask_cols=["avg_los_days"])


def build_mart_prom_trajectory(fact_survey: DataFrame) -> DataFrame:
    """Longitudinal PRO scores with change from baseline.

    Grain: one row per patient_key × instrument_key × wave.
    """
    w = Window.partitionBy("patient_key", "instrument_key")
    baseline = (
        fact_survey.filter(F.col("wave") == "baseline")
        .select(
            "patient_key",
            "instrument_key",
            F.col("total_score").alias("baseline_score"),
        )
        .dropDuplicates(["patient_key", "instrument_key"])
    )
    return (
        fact_survey.join(baseline, on=["patient_key", "instrument_key"], how="left")
        .withColumn(
            "change_from_baseline",
            F.col("total_score") - F.col("baseline_score"),
        )
        .withColumn(
            "mcid_improved",
            # Illustrative MCID: |change| >= 5 points on common PRO scales
            F.when(
                F.col("change_from_baseline").isNotNull()
                & (F.abs(F.col("change_from_baseline")) >= 5),
                F.lit(True),
            ).otherwise(F.lit(False)),
        )
        .withColumn("wave_count", F.count("*").over(w))
    )


def build_mart_clinical_survey_linkage(
    mart_patient_360: DataFrame,
    fact_survey: DataFrame,
) -> DataFrame:
    """Clinical outcomes aligned to PRO scores on a common patient spine.

    Grain: one row per patient_key × instrument_key × wave (patients with either clinical or PRO).
    """
    survey = fact_survey.select(
        "patient_key",
        "instrument_key",
        "wave",
        "total_score",
        "severity_band",
        "scoring_version",
    )
    return mart_patient_360.join(survey, on="patient_key", how="inner")
