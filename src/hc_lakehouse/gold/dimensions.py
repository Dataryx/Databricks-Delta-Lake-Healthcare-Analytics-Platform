"""Gold dimension builders. Grain documented per function."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from pyspark.sql import functions as F

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession


def build_dim_date(
    spark: SparkSession,
    start: date = date(2020, 1, 1),
    end: date = date(2026, 12, 31),
) -> DataFrame:
    """Conformed date dimension.

    Grain: one row per calendar day (date_key = yyyymmdd).
    """
    days = (end - start).days + 1
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        rows.append(
            (
                int(d.strftime("%Y%m%d")),
                d.isoformat(),
                d.year,
                d.month,
                d.day,
                d.isocalendar().week,
                d.strftime("%A"),
                d.month >= 10 or d.month <= 3,
            )
        )
    return spark.createDataFrame(
        rows,
        schema=(
            "date_key INT, full_date STRING, year INT, month INT, day INT, "
            "iso_week INT, day_name STRING, is_flu_season BOOLEAN"
        ),
    ).withColumn("full_date", F.to_date(F.col("full_date")))


def build_dim_patient(silver_patient: DataFrame) -> DataFrame:
    """Patient dimension (current SCD2 rows).

    Grain: one row per patient_sk where is_current.
    """
    return (
        silver_patient.filter(F.col("is_current") == True)  # noqa: E712
        .select(
            F.col("patient_sk").alias("patient_key"),
            "sex",
            "race",
            "ethnicity",
            "birth_year",
            "age_band",
            "zip3",
            "deceased_flag",
            "row_hash",
        )
        .dropDuplicates(["patient_key"])
    )


def build_dim_care_setting(spark: SparkSession) -> DataFrame:
    """Care setting conformed dimension.

    Grain: one row per care_setting_code.
    """
    return spark.createDataFrame(
        [
            ("inpatient", "Inpatient", "acute"),
            ("outpatient", "Outpatient", "ambulatory"),
            ("emergency", "Emergency", "acute"),
            ("ambulatory", "Ambulatory", "ambulatory"),
        ],
        schema="care_setting_key STRING, care_setting_name STRING, setting_class STRING",
    )


def build_dim_lab_test(silver_labs: DataFrame) -> DataFrame:
    """Lab test dimension from distinct LOINC codes.

    Grain: one row per loinc_code.
    """
    return (
        silver_labs.select(
            F.col("loinc_code").alias("lab_test_key"),
            F.col("loinc_code"),
            F.col("unit").alias("default_unit"),
        )
        .dropDuplicates(["lab_test_key"])
        .withColumn("loinc_code", F.col("lab_test_key"))
    )
