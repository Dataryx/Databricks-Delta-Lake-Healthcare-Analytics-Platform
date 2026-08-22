"""Delta Live Tables entrypoint: Bronze → Silver (Databricks cloud).

Local demo uses ``scripts/ingest_bronze.py`` + ``scripts/build_silver.py``.
This module is deployed via Asset Bundles and expects Auto Loader paths under
Unity Catalog Volumes. De-id HMAC pepper must come from a secret scope.
"""

from __future__ import annotations

import dlt  # type: ignore
from pyspark.sql import functions as F


def _spark():
    from pyspark.sql import SparkSession

    return SparkSession.getActiveSession()


def _catalog() -> str:
    spark = _spark()
    assert spark is not None
    return spark.conf.get("hc.catalog", "hc_dev")


@dlt.table(
    name="patient_raw",
    comment="Bronze patients (Auto Loader) with technical columns",
    table_properties={"quality": "bronze"},
)
@dlt.expect_or_drop("patient_id_present", "patient_id IS NOT NULL")
def patient_raw():
    spark = _spark()
    assert spark is not None
    cat = _catalog()
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .option("cloudFiles.inferColumnTypes", "false")
        .load(f"/Volumes/{cat}/landing/clinical/patient")
        .withColumn("_ingest_ts", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )


@dlt.table(
    name="encounter_raw",
    comment="Bronze encounters (Auto Loader)",
    table_properties={"quality": "bronze"},
)
@dlt.expect_or_drop("encounter_id_present", "encounter_id IS NOT NULL")
def encounter_raw():
    spark = _spark()
    assert spark is not None
    cat = _catalog()
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .option("cloudFiles.inferColumnTypes", "false")
        .load(f"/Volumes/{cat}/landing/clinical/encounter")
        .withColumn("_ingest_ts", F.current_timestamp())
    )


@dlt.table(
    name="patient",
    comment="Silver patient stub; production wires hc_lakehouse.silver wheel",
    table_properties={"quality": "silver"},
)
@dlt.expect_or_fail("patient_sk_present", "patient_sk IS NOT NULL")
def silver_patient():
    return dlt.read("patient_raw").select(
        F.col("patient_id").alias("patient_sk"),
        F.lit("unknown").alias("sex"),
        F.current_timestamp().alias("effective_start_ts"),
        F.lit(True).alias("is_current"),
    )
