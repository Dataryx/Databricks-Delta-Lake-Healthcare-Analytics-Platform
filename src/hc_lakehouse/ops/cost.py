"""Monthly cost report SQL against system.billing.usage."""

from __future__ import annotations

from pathlib import Path

from hc_lakehouse.utils.config import REPO_ROOT
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)


def monthly_cost_report_sql() -> str:
    """SQL against ``system.billing.usage`` for cloud cost by pipeline tag."""
    return """
SELECT
  date_trunc('month', usage_date) AS usage_month,
  COALESCE(get_json_object(usage_metadata, '$.job_name'), 'untagged') AS pipeline,
  COALESCE(get_json_object(custom_tags, '$.Owner'), 'unknown') AS owner,
  SUM(usage_quantity) AS dbus,
  SUM(usage_quantity) * 0.55 AS cost_proxy_usd
FROM system.billing.usage
WHERE usage_date >= add_months(current_date(), -1)
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 4 DESC
""".strip()


def write_cost_report_artifact(path: Path | None = None) -> Path:
    """Write cost report SQL to artifacts for warehouse execution."""
    out = path or (REPO_ROOT / "artifacts" / "ops" / "monthly_cost_report.sql")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(monthly_cost_report_sql() + "\n", encoding="utf-8")
    logger.info("cost_report_sql_written", extra={"path": str(out)})
    return out
