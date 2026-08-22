"""Access audit summaries, quarterly access review, and break-glass re-id workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, table_exists, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

logger = get_logger(__name__)
WriteMode = Literal["append", "overwrite"]


def write_access_audit_daily(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
    sample_events: list[dict[str, str]] | None = None,
) -> int:
    """Build ``ops.access_audit_daily`` (from UC system.access.audit in cloud).

    Local mode accepts synthetic sample events for demo/tests.
    """
    cfg = config or load_config()
    events = sample_events or [
        {
            "principal": "hc_researchers_deid",
            "action": "SELECT",
            "asset": f"{cfg.catalog}.gold.mart_patient_360",
            "classification": "sensitive",
        },
        {
            "principal": "hc_analysts",
            "action": "SELECT",
            "asset": f"{cfg.catalog}.gold.mart_utilization",
            "classification": "sensitive",
        },
    ]
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = [
        (
            day,
            e["principal"],
            e["action"],
            e["asset"],
            e.get("classification", "sensitive"),
            1,
            cfg.retention_years,
        )
        for e in events
    ]
    path = delta_table_path(cfg.local_delta_root, "ops", "access_audit_daily")
    mode: WriteMode = "append" if table_exists(spark, path) else "overwrite"
    df = spark.createDataFrame(
        rows,
        schema=(
            "audit_date STRING, principal STRING, action STRING, asset STRING, "
            "classification STRING, query_count INT, retained_until_years INT"
        ),
    )
    write_delta(df, path, mode=mode, enable_cdf=False)
    logger.info("access_audit_daily_written", extra={"rows": len(rows)})
    return len(rows)


def seed_access_review(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
) -> int:
    """Populate ``ops.access_review`` for quarterly recertification."""
    cfg = config or load_config()
    from hc_lakehouse.governance.matrix import load_access_matrix

    matrix = load_access_matrix()
    ts = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            str(uuid4()),
            g.group,
            g.asset,
            g.privilege,
            g.justification,
            "pending_recert",
            "",
            ts,
            "Q_next",
        )
        for g in matrix.grants
    ]
    path = delta_table_path(cfg.local_delta_root, "ops", "access_review")
    df = spark.createDataFrame(
        rows,
        schema=(
            "review_id STRING, group_name STRING, asset STRING, privilege STRING, "
            "justification STRING, status STRING, reviewer STRING, created_at STRING, "
            "due_quarter STRING"
        ),
    )
    write_delta(df, path, mode="overwrite", enable_cdf=False)
    logger.info("access_review_seeded", extra={"rows": len(rows)})
    return len(rows)


class BreakGlassError(RuntimeError):
    """Raised when re-id is attempted without a justification log entry."""


def request_reid(
    spark: SparkSession,
    *,
    principal: str,
    patient_sk: str,
    justification: str,
    privacy_officer: str,
    config: PlatformConfig | None = None,
) -> str:
    """Write break-glass justification to ``ops.reid_request_log`` before crosswalk read.

    Returns request_id. Does not return source identifiers — caller must be in
    ``hc_breakglass_reid`` and read ``restricted.patient_xref`` separately.
    """
    if not justification or len(justification.strip()) < 20:
        raise BreakGlassError("Justification must be at least 20 characters.")
    cfg = config or load_config()
    request_id = str(uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    row = spark.createDataFrame(
        [
            (
                request_id,
                principal,
                patient_sk,
                justification.strip(),
                privacy_officer,
                ts,
                "requested",
                "alert_emitted",
            )
        ],
        schema=(
            "request_id STRING, principal STRING, patient_sk STRING, justification STRING, "
            "privacy_officer STRING, requested_at STRING, status STRING, alert_status STRING"
        ),
    )
    path = delta_table_path(cfg.local_delta_root, "ops", "reid_request_log")
    mode: WriteMode = "append" if table_exists(spark, path) else "overwrite"
    write_delta(row, path, mode=mode, enable_cdf=False)
    logger.warning(
        "reid_breakglass_requested",
        extra={
            "request_id": request_id,
            "principal": principal,
            "privacy_officer": privacy_officer,
            "patient_sk_prefix": patient_sk[:8],
        },
    )
    return request_id


def assert_reid_justified(
    spark: SparkSession,
    request_id: str,
    *,
    config: PlatformConfig | None = None,
) -> None:
    """Fail closed if request_id is missing from the reid log."""
    cfg = config or load_config()
    path = delta_table_path(cfg.local_delta_root, "ops", "reid_request_log")
    if not table_exists(spark, path):
        raise BreakGlassError("No reid_request_log table; cannot authorize crosswalk read.")
    from hc_lakehouse.utils.io import read_delta

    hits = read_delta(spark, path).filter(f"request_id = '{request_id}'")
    if hits.limit(1).count() == 0:
        raise BreakGlassError(f"No justification logged for request_id={request_id}")
