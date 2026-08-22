"""Orchestrate Silver → Gold build with DQ promotion gate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

from hc_lakehouse.gold.dimensions import (
    build_dim_care_setting,
    build_dim_date,
    build_dim_lab_test,
    build_dim_patient,
)
from hc_lakehouse.gold.facts import (
    build_fact_encounter,
    build_fact_lab_result,
    build_fact_readmission,
    build_fact_survey_response,
)
from hc_lakehouse.gold.marts import (
    build_mart_clinical_survey_linkage,
    build_mart_patient_360,
    build_mart_prom_trajectory,
    build_mart_utilization,
)
from hc_lakehouse.privacy.hashing import attach_surrogate_key
from hc_lakehouse.quality.runner import validate_all_silver
from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, read_delta, table_exists, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

logger = get_logger(__name__)


def _read_silver(spark: SparkSession, cfg: PlatformConfig, table: str) -> DataFrame:
    path = delta_table_path(cfg.local_delta_root, "silver", table)
    if not table_exists(spark, path):
        raise FileNotFoundError(f"Silver required for Gold: {path}")
    return read_delta(spark, path)


def _load_survey_scores_for_gold(
    spark: SparkSession,
    cfg: PlatformConfig,
    pepper: str,
) -> DataFrame | None:
    """Load bronze survey scores and attach HMAC patient_sk for Gold facts."""
    path = delta_table_path(cfg.local_delta_root, "bronze", "survey_score_raw")
    if not table_exists(spark, path):
        logger.warning("survey_scores_missing", extra={"path": path})
        return None
    raw = read_delta(spark, path)
    raw = attach_surrogate_key(raw, "patient_id", "patient_sk", pepper)
    return raw.withColumn("total_score", F.col("total_score").cast("double"))


def _write_gold(cfg: PlatformConfig, name: str, df: DataFrame) -> int:
    path = delta_table_path(cfg.local_delta_root, "gold", name)
    write_delta(df, path, mode="overwrite", enable_cdf=True)
    n = df.count()
    logger.info("gold_table_written", extra={"table": name, "rows": n, "path": path})
    return n


def build_gold(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
    enforce_dq_gate: bool = True,
) -> dict[str, int]:
    """Build Gold dims, facts, and marts. Refuses to run if Silver DQ errors failed."""
    cfg = config or load_config()
    pepper = cfg.deid_salt()

    if enforce_dq_gate:
        validate_all_silver(spark, config=cfg, enforce_gate=True)

    patients = _read_silver(spark, cfg, "patient")
    encounters = _read_silver(spark, cfg, "encounter")
    labs = _read_silver(spark, cfg, "lab_result")

    counts: dict[str, int] = {}

    counts["dim_date"] = _write_gold(cfg, "dim_date", build_dim_date(spark))
    dim_patient = build_dim_patient(patients)
    counts["dim_patient"] = _write_gold(cfg, "dim_patient", dim_patient)
    counts["dim_care_setting"] = _write_gold(cfg, "dim_care_setting", build_dim_care_setting(spark))
    counts["dim_lab_test"] = _write_gold(cfg, "dim_lab_test", build_dim_lab_test(labs))

    fact_enc = build_fact_encounter(encounters)
    counts["fact_encounter"] = _write_gold(cfg, "fact_encounter", fact_enc)
    fact_lab = build_fact_lab_result(labs)
    counts["fact_lab_result"] = _write_gold(cfg, "fact_lab_result", fact_lab)
    counts["fact_readmission"] = _write_gold(
        cfg, "fact_readmission", build_fact_readmission(fact_enc)
    )

    fact_survey = None
    survey_raw = _load_survey_scores_for_gold(spark, cfg, pepper)
    if survey_raw is not None:
        fact_survey = build_fact_survey_response(survey_raw)
        counts["fact_survey_response"] = _write_gold(cfg, "fact_survey_response", fact_survey)
        counts["mart_prom_trajectory"] = _write_gold(
            cfg, "mart_prom_trajectory", build_mart_prom_trajectory(fact_survey)
        )

    mart_360 = build_mart_patient_360(dim_patient, fact_enc, fact_lab)
    counts["mart_patient_360"] = _write_gold(cfg, "mart_patient_360", mart_360)
    counts["mart_utilization"] = _write_gold(
        cfg, "mart_utilization", build_mart_utilization(fact_enc, dim_patient)
    )

    if fact_survey is not None:
        counts["mart_clinical_survey_linkage"] = _write_gold(
            cfg,
            "mart_clinical_survey_linkage",
            build_mart_clinical_survey_linkage(mart_360, fact_survey),
        )

    logger.info("gold_build_complete", extra=counts)
    return counts
