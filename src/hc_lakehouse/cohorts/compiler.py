"""Compile declarative cohorts into Gold tables + registry entries."""

from __future__ import annotations

import getpass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from hc_lakehouse.cohorts.definition import CohortDefinition, Criterion, load_cohort
from hc_lakehouse.reproducibility.manifest import (
    RunManifest,
    checksum_dataframe,
    delta_version,
    write_manifest,
)
from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, read_delta, table_exists, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

logger = get_logger(__name__)
WriteMode = Literal["append", "overwrite"]


def _read(spark: SparkSession, cfg: PlatformConfig, schema: str, table: str) -> DataFrame:
    path = delta_table_path(cfg.local_delta_root, schema, table)
    if not table_exists(spark, path):
        raise FileNotFoundError(f"Missing table for cohort build: {path}")
    return read_delta(spark, path)


def _patients_with_lab(labs: DataFrame, loinc: str) -> DataFrame:
    return (
        labs.filter(F.col("lab_test_key") == loinc)
        .select(F.col("patient_key").alias("patient_sk"))
        .dropDuplicates()
    )


def _patients_with_survey(survey: DataFrame, instrument: str) -> DataFrame:
    return (
        survey.filter(F.col("instrument_key") == instrument)
        .select(F.col("patient_key").alias("patient_sk"))
        .dropDuplicates()
    )


def _patients_min_inpatient(enc: DataFrame, minimum: int) -> DataFrame:
    return (
        enc.filter(F.col("care_setting_key") == "inpatient")
        .groupBy(F.col("patient_key").alias("patient_sk"))
        .agg(F.count("*").alias("n"))
        .filter(F.col("n") >= int(minimum))
        .select("patient_sk")
    )


def _apply_inclusion(
    spark: SparkSession,
    cfg: PlatformConfig,
    criterion: Criterion,
) -> DataFrame:
    if criterion.type == "has_lab_loinc":
        labs = _read(spark, cfg, "gold", "fact_lab_result")
        return _patients_with_lab(labs, str(criterion.value))
    if criterion.type == "has_survey_instrument":
        survey = _read(spark, cfg, "gold", "fact_survey_response")
        return _patients_with_survey(survey, str(criterion.value))
    if criterion.type == "min_inpatient_encounters":
        enc = _read(spark, cfg, "gold", "fact_encounter")
        return _patients_min_inpatient(enc, int(criterion.value))
    raise ValueError(f"Unsupported inclusion criterion: {criterion.type}")


def _apply_exclusion(
    members: DataFrame,
    spark: SparkSession,
    cfg: PlatformConfig,
    criterion: Criterion,
) -> DataFrame:
    if criterion.type == "deceased":
        patients = _read(spark, cfg, "gold", "dim_patient")
        dead = patients.filter(F.col("deceased_flag") == True).select(  # noqa: E712
            F.col("patient_key").alias("patient_sk")
        )
        return members.join(dead, on="patient_sk", how="left_anti")
    raise ValueError(f"Unsupported exclusion criterion: {criterion.type}")


def compile_cohort(
    spark: SparkSession,
    definition: CohortDefinition,
    *,
    config: PlatformConfig | None = None,
    principal: str | None = None,
) -> tuple[DataFrame, RunManifest]:
    """Materialize cohort members and return (cohort_df, manifest).

    Grain: one row per patient_sk in the cohort, plus provenance columns.
    """
    cfg = config or load_config()
    who = principal or getpass.getuser()

    member_sets = [_apply_inclusion(spark, cfg, c) for c in definition.inclusion]
    if not member_sets:
        raise ValueError(f"Cohort {definition.name} has no inclusion criteria")
    members = member_sets[0]
    for other in member_sets[1:]:
        members = members.join(other, on="patient_sk", how="inner")

    for exc in definition.exclusion:
        members = _apply_exclusion(members, spark, cfg, exc)

    input_tables = {
        "gold.dim_patient": delta_table_path(cfg.local_delta_root, "gold", "dim_patient"),
        "gold.fact_encounter": delta_table_path(cfg.local_delta_root, "gold", "fact_encounter"),
        "gold.fact_lab_result": delta_table_path(cfg.local_delta_root, "gold", "fact_lab_result"),
    }
    if table_exists(spark, delta_table_path(cfg.local_delta_root, "gold", "fact_survey_response")):
        input_tables["gold.fact_survey_response"] = delta_table_path(
            cfg.local_delta_root, "gold", "fact_survey_response"
        )

    versions = {name: delta_version(spark, path) for name, path in input_tables.items()}

    built_at = datetime.now(timezone.utc)
    cohort_df = (
        members.withColumn("cohort_name", F.lit(definition.name))
        .withColumn("cohort_version", F.lit(definition.version))
        .withColumn("definition_hash", F.lit(definition.definition_hash))
        .withColumn("irb_protocol_id", F.lit(definition.irb_protocol_id))
        .withColumn("index_date_rule", F.lit(definition.index_date_rule))
        .withColumn("washout_days", F.lit(definition.washout_days))
        .withColumn("follow_up_days", F.lit(definition.follow_up_days))
        .withColumn("built_at", F.lit(built_at.isoformat()))
        .withColumn("creating_principal", F.lit(who))
        .withColumn(
            "required_instruments",
            F.lit(",".join(definition.required_instruments)).cast(StringType()),
        )
    )

    out_checksum = checksum_dataframe(
        cohort_df.select("patient_sk", "cohort_name", "definition_hash")
    )
    import subprocess

    from hc_lakehouse.utils.config import REPO_ROOT

    try:
        import shutil

        git_bin = shutil.which("git")
        if not git_bin:
            raise FileNotFoundError("git not on PATH")
        git_sha = (
            subprocess.check_output(  # noqa: S603
                [git_bin, "rev-parse", "HEAD"],
                cwd=str(REPO_ROOT),
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        git_sha = "unknown"

    manifest = RunManifest(
        artifact=definition.table_name,
        artifact_kind="cohort",
        created_at=built_at.isoformat(),
        creating_principal=who,
        git_commit_sha=git_sha,
        definition_hash=definition.definition_hash,
        scoring_algorithm_version=None,
        runtime_version=f"spark-{spark.version}",
        input_tables=versions,
        output_checksum=out_checksum,
        irb_protocol_id=definition.irb_protocol_id,
        row_count=cohort_df.count(),
        extra={"cohort_name": definition.name, "cohort_version": definition.version},
    )
    return cohort_df, manifest


def register_cohort(
    spark: SparkSession,
    definition: CohortDefinition,
    manifest: RunManifest,
    *,
    config: PlatformConfig | None = None,
) -> None:
    """Append a row to ``ops.cohort_registry``."""
    cfg = config or load_config()
    path = delta_table_path(cfg.local_delta_root, "ops", "cohort_registry")
    row = spark.createDataFrame(
        [
            (
                definition.name,
                definition.version,
                definition.definition_hash,
                definition.irb_protocol_id,
                manifest.creating_principal,
                manifest.git_commit_sha,
                json_dumps(manifest.input_tables),
                manifest.output_checksum,
                manifest.row_count,
                manifest.created_at,
            )
        ],
        schema=(
            "cohort_name STRING, cohort_version INT, definition_hash STRING, "
            "irb_protocol_id STRING, creating_principal STRING, git_commit_sha STRING, "
            "input_table_versions STRING, output_checksum STRING, row_count LONG, "
            "registered_at STRING"
        ),
    )
    mode: WriteMode = "append" if table_exists(spark, path) else "overwrite"
    write_delta(row, path, mode=mode, enable_cdf=False)
    logger.info("cohort_registered", extra={"name": definition.name, "path": path})


def json_dumps(obj: dict[str, int]) -> str:
    import json

    return json.dumps(obj, sort_keys=True)


def build_cohort(
    spark: SparkSession,
    name: str,
    *,
    config: PlatformConfig | None = None,
    write_research_manifest: bool = True,
) -> RunManifest:
    """Compile, write ``gold.cohort_<name>``, register, and emit manifest."""
    cfg = config or load_config()
    definition = load_cohort(name)
    cohort_df, manifest = compile_cohort(spark, definition, config=cfg)
    gold_path = delta_table_path(cfg.local_delta_root, "gold", definition.table_name)
    write_delta(cohort_df, gold_path, mode="overwrite", enable_cdf=True)
    register_cohort(spark, definition, manifest, config=cfg)
    write_manifest(spark, manifest, config=cfg, emit_sidecar=write_research_manifest)
    logger.info(
        "cohort_built",
        extra={
            "name": definition.name,
            "rows": manifest.row_count,
            "checksum": manifest.output_checksum[:16],
        },
    )
    return manifest
