"""Point-in-time-aware ML feature table builders.

Grain is documented per function. Features are keyed by ``patient_key`` and
``feature_as_of`` so training joins can enforce no look-ahead leakage.

Local Spark uses efficient window/agg builders; Databricks Feature Engineering
in Unity Catalog remains the cloud system of record for online/offline PIT joins.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F
from pyspark.sql.window import Window

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

_CHARLSON_WEIGHTS = {
    "E11": 1,
    "I10": 1,
    "J45": 1,
    "F32": 1,
}


def build_ft_patient_demographics(dim_patient: DataFrame) -> DataFrame:
    """Static demographic features.

    Grain: one row per patient_key (feature_as_of = current snapshot date).
    """
    return dim_patient.select(
        "patient_key",
        F.current_date().alias("feature_as_of"),
        "sex",
        "race",
        "ethnicity",
        "age_band",
        "birth_year",
        "zip3",
        F.col("deceased_flag").cast("int").alias("deceased_flag"),
    )


def build_ft_utilization_90d(fact_encounter: DataFrame) -> DataFrame:
    """Utilization features as of each encounter using a bounded look-back window.

    Grain: one row per patient_key × feature_as_of (admit date).
    Uses range window on unix timestamps (seconds) for 90-day prior history,
    excluding the current row (look-back only).
    """
    base = fact_encounter.select(
        "patient_key",
        F.to_date("admit_ts").alias("feature_as_of"),
        F.unix_timestamp("admit_ts").alias("_ts"),
        "care_setting_key",
        "los_days",
    )
    # 90 days in seconds; rowsBetween on range requires ORDER BY numeric
    w = Window.partitionBy("patient_key").orderBy("_ts").rangeBetween(-90 * 86400, -1)
    return (
        base.withColumn("encounters_90d", F.count("*").over(w))
        .withColumn(
            "inpatient_90d",
            F.sum(F.when(F.col("care_setting_key") == "inpatient", 1).otherwise(0)).over(w),
        )
        .withColumn(
            "ed_90d",
            F.sum(F.when(F.col("care_setting_key") == "emergency", 1).otherwise(0)).over(w),
        )
        .withColumn("avg_los_90d", F.avg("los_days").over(w))
        .select(
            "patient_key",
            "feature_as_of",
            F.coalesce(F.col("encounters_90d"), F.lit(0)).alias("encounters_90d"),
            F.coalesce(F.col("inpatient_90d"), F.lit(0)).alias("inpatient_90d"),
            F.coalesce(F.col("ed_90d"), F.lit(0)).alias("ed_90d"),
            F.coalesce(F.col("avg_los_90d"), F.lit(0.0)).alias("avg_los_90d"),
        )
        .dropDuplicates(["patient_key", "feature_as_of"])
    )


def build_ft_lab_trends(fact_lab: DataFrame) -> DataFrame:
    """Lab trends as of each result using a 180-day look-back window.

    Grain: one row per patient_key × feature_as_of (result date).
    """
    base = fact_lab.select(
        "patient_key",
        F.to_date("resulted_ts").alias("feature_as_of"),
        F.unix_timestamp("resulted_ts").alias("_ts"),
        "lab_test_key",
        "value_num",
    )
    w = Window.partitionBy("patient_key").orderBy("_ts").rangeBetween(-180 * 86400, 0)
    return (
        base.withColumn("lab_count_180d", F.count("*").over(w))
        .withColumn("distinct_labs_180d", F.size(F.collect_set("lab_test_key").over(w)))
        .withColumn("mean_lab_value_180d", F.avg("value_num").over(w))
        .select(
            "patient_key",
            "feature_as_of",
            F.coalesce(F.col("lab_count_180d"), F.lit(0)).alias("lab_count_180d"),
            F.coalesce(F.col("distinct_labs_180d"), F.lit(0)).alias("distinct_labs_180d"),
            F.coalesce(F.col("mean_lab_value_180d"), F.lit(0.0)).alias("mean_lab_value_180d"),
        )
        .dropDuplicates(["patient_key", "feature_as_of"])
    )


def build_ft_prom_scores(fact_survey: DataFrame) -> DataFrame:
    """Latest PRO scores per patient × instrument.

    Grain: one row per patient_key × instrument_key × feature_as_of.
    """
    score_col = "total_score" if "total_score" in fact_survey.columns else "score_value"
    order_col = "administered_ts" if "administered_ts" in fact_survey.columns else "wave"
    w = Window.partitionBy("patient_key", "instrument_key").orderBy(F.col(order_col).desc())
    ranked = fact_survey.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1)
    as_of = (
        F.to_date("administered_ts")
        if "administered_ts" in fact_survey.columns
        else F.current_date()
    )
    return ranked.select(
        "patient_key",
        F.coalesce(as_of, F.current_date()).alias("feature_as_of"),
        "instrument_key",
        F.col(score_col).cast("double").alias("score_value"),
        "wave",
    )


def build_ft_comorbidity_index(
    bronze_condition: DataFrame,
    patient_key_map: DataFrame,
) -> DataFrame:
    """Charlson-like comorbidity score from synthetic ICD-10 codes.

    Grain: one row per patient_key (score as of current snapshot).
    """
    cond = bronze_condition.select(
        F.col("patient_id"),
        F.upper(F.col("icd10_code")).alias("icd10_code"),
        F.to_date("onset_ts").alias("feature_as_of"),
    )
    weighted = cond.withColumn(
        "weight",
        F.when(F.col("icd10_code").startswith("E11"), F.lit(_CHARLSON_WEIGHTS["E11"]))
        .when(F.col("icd10_code").startswith("I10"), F.lit(_CHARLSON_WEIGHTS["I10"]))
        .when(F.col("icd10_code").startswith("J45"), F.lit(_CHARLSON_WEIGHTS["J45"]))
        .when(F.col("icd10_code").startswith("F32"), F.lit(_CHARLSON_WEIGHTS["F32"]))
        .otherwise(F.lit(0)),
    )
    keyed = weighted.join(patient_key_map, on="patient_id", how="inner")
    return keyed.groupBy("patient_key").agg(
        F.max("feature_as_of").alias("feature_as_of"),
        F.sum("weight").alias("charlson_proxy"),
        F.countDistinct("icd10_code").alias("distinct_conditions"),
    )


def build_ft_medication_adherence(
    bronze_med: DataFrame,
    patient_key_map: DataFrame,
) -> DataFrame:
    """Proxy medication adherence (order density) — not true PDC.

    Grain: one row per patient_key.
    """
    med = bronze_med.select("patient_id", F.to_date("ordered_ts").alias("feature_as_of"))
    keyed = med.join(patient_key_map, on="patient_id", how="inner")
    return keyed.groupBy("patient_key").agg(
        F.max("feature_as_of").alias("feature_as_of"),
        F.count("*").alias("med_order_count"),
        F.lit(1.0).alias("adherence_proxy"),
    )
