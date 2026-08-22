"""Run DQ validation for Silver tables and gate Gold promotion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hc_lakehouse.quality.engine import ValidationReport, validate
from hc_lakehouse.quality.gates import gate_promotion
from hc_lakehouse.quality.results import persist_dq_results
from hc_lakehouse.quality.rules import load_ruleset
from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, read_delta, table_exists
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

logger = get_logger(__name__)

# ruleset file stem → local silver table name
SILVER_DQ_TARGETS: dict[str, str] = {
    "silver_patient": "patient",
    "silver_encounter": "encounter",
    "silver_lab_result": "lab_result",
}


def validate_silver_table(
    spark: SparkSession,
    ruleset_name: str,
    *,
    config: PlatformConfig | None = None,
    persist: bool = True,
    enforce_gate: bool = False,
) -> ValidationReport:
    """Validate one Silver table against its YAML ruleset."""
    cfg = config or load_config()
    ruleset = load_ruleset(ruleset_name)
    table = SILVER_DQ_TARGETS[ruleset_name]
    path = delta_table_path(cfg.local_delta_root, "silver", table)
    if not table_exists(spark, path):
        raise FileNotFoundError(f"Silver table missing for DQ: {path}")
    df = read_delta(spark, path)
    report = validate(df, ruleset)
    if persist:
        persist_dq_results(spark, report, config=cfg)
    if enforce_gate:
        gate_promotion(report)
    return report


def validate_all_silver(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
    enforce_gate: bool = True,
) -> dict[str, ValidationReport]:
    """Run DQ for all registered Silver tables; optionally block on errors."""
    cfg = config or load_config()
    reports: dict[str, ValidationReport] = {}
    blocked: list[str] = []
    for name in SILVER_DQ_TARGETS:
        report = validate_silver_table(spark, name, config=cfg, persist=True, enforce_gate=False)
        reports[name] = report
        if not report.passed:
            from hc_lakehouse.quality.gates import emit_dq_alert

            emit_dq_alert(report)
            blocked.append(name)
    if enforce_gate and blocked:
        from hc_lakehouse.quality.gates import PromotionBlockedError

        raise PromotionBlockedError(f"Silver→Gold promotion blocked; failing rulesets: {blocked}")
    logger.info(
        "silver_dq_complete",
        extra={"tables": list(reports), "blocked": blocked, "enforce_gate": enforce_gate},
    )
    return reports
