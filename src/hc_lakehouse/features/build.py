"""Orchestrate ML feature table materialization into the ``ml`` schema."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hc_lakehouse.features.tables import (
    build_ft_comorbidity_index,
    build_ft_lab_trends,
    build_ft_medication_adherence,
    build_ft_patient_demographics,
    build_ft_prom_scores,
    build_ft_utilization_90d,
)
from hc_lakehouse.privacy.hashing import attach_surrogate_key
from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, read_delta, table_exists, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

logger = get_logger(__name__)

FEATURE_TABLES = (
    "ft_patient_demographics",
    "ft_utilization_90d",
    "ft_lab_trends",
    "ft_prom_scores",
    "ft_comorbidity_index",
    "ft_medication_adherence",
)


def _require(spark: SparkSession, cfg: PlatformConfig, schema: str, table: str) -> Any:
    path = delta_table_path(cfg.local_delta_root, schema, table)
    if not table_exists(spark, path):
        raise FileNotFoundError(f"Missing prerequisite Delta table: {schema}.{table} at {path}")
    return read_delta(spark, path)


def build_features(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
) -> dict[str, int]:
    """Build and write all ``ml.ft_*`` feature tables. Returns row counts."""
    cfg = config or load_config()
    dim_patient = _require(spark, cfg, "gold", "dim_patient")
    fact_enc = _require(spark, cfg, "gold", "fact_encounter")
    fact_lab = _require(spark, cfg, "gold", "fact_lab_result")
    fact_survey = _require(spark, cfg, "gold", "fact_survey_response")

    bronze_cond_path = delta_table_path(cfg.local_delta_root, "bronze", "condition_raw")
    bronze_med_path = delta_table_path(cfg.local_delta_root, "bronze", "medication_raw")
    if not table_exists(spark, bronze_cond_path):
        raise FileNotFoundError(f"Missing bronze.condition_raw at {bronze_cond_path}")
    bronze_cond = read_delta(spark, bronze_cond_path)
    bronze_med = (
        read_delta(spark, bronze_med_path)
        if table_exists(spark, bronze_med_path)
        else spark.createDataFrame([], "patient_id STRING, ordered_ts STRING")
    )

    # Map source patient_id → patient_key via same HMAC used in Silver
    bronze_pat = _require(spark, cfg, "bronze", "patient_raw")
    keyed = attach_surrogate_key(bronze_pat, "patient_id", "patient_key", cfg.deid_salt())
    patient_map = keyed.select("patient_id", "patient_key").dropDuplicates(["patient_id"])

    builders: dict[str, Any] = {
        "ft_patient_demographics": build_ft_patient_demographics(dim_patient),
        "ft_utilization_90d": build_ft_utilization_90d(fact_enc),
        "ft_lab_trends": build_ft_lab_trends(fact_lab),
        "ft_prom_scores": build_ft_prom_scores(fact_survey),
        "ft_comorbidity_index": build_ft_comorbidity_index(bronze_cond, patient_map),
        "ft_medication_adherence": build_ft_medication_adherence(bronze_med, patient_map),
    }

    counts: dict[str, int] = {}
    for name, df in builders.items():
        path = delta_table_path(cfg.local_delta_root, "ml", name)
        # Materialize once: cache for count, then write
        cached = df.cache()
        n = cached.count()
        write_delta(cached, path, mode="overwrite", enable_cdf=False)
        cached.unpersist()
        counts[name] = n
        logger.info("feature_table_written", extra={"table": f"ml.{name}", "rows": n})
    return counts
