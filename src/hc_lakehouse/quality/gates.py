"""Promotion gates and alerting — fail closed on error-severity DQ failures."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from hc_lakehouse.quality.engine import ValidationReport
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class PromotionBlockedError(RuntimeError):
    """Raised when Silver → Gold (or any gated step) must not proceed."""


def assert_promotable(report: ValidationReport) -> None:
    """Fail closed: any ``error`` severity failure blocks promotion."""
    failures = report.error_failures
    if not failures:
        logger.info("promotion_allowed", extra={"table": report.table, "run_id": report.run_id})
        return
    detail = ", ".join(f"{f.rule_id}(pass_rate={f.pass_rate}<{f.threshold})" for f in failures)
    msg = f"Promotion blocked for {report.table}: error-severity DQ failures: {detail}"
    logger.error(
        "promotion_blocked",
        extra={
            "table": report.table,
            "run_id": report.run_id,
            "failures": [f.rule_id for f in failures],
        },
    )
    raise PromotionBlockedError(msg)


def emit_dq_alert(report: ValidationReport) -> None:
    """Emit actionable alert for failed error rules.

    Tries Teams/email webhooks from env; otherwise logs a structured alert
    (cloud-only features degrade gracefully).
    """
    failures = [r for r in report.results if r.status == "fail"]
    if not failures:
        return
    payload = {
        "title": f"DQ alert: {report.table}",
        "run_id": report.run_id,
        "table": report.table,
        "failed_rules": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity,
                "pass_rate": f.pass_rate,
                "threshold": f.threshold,
                "rows_failed": f.rows_failed,
                "owner": f.owner,
            }
            for f in failures
        ],
    }
    logger.warning("dq_alert", extra=payload)
    for env_key in ("HC_ALERT_TEAMS_WEBHOOK", "HC_ALERT_EMAIL_WEBHOOK"):
        url = os.environ.get(env_key)
        if not url:
            continue
        try:
            if not url.startswith("https://"):
                logger.warning(
                    "dq_alert_webhook_skipped",
                    extra={"webhook": env_key, "detail": "only https webhooks allowed"},
                )
                continue
            req = urllib.request.Request(  # noqa: S310
                url,
                data=json.dumps({"text": json.dumps(payload)}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
                logger.info(
                    "dq_alert_webhook_sent",
                    extra={"webhook": env_key, "status": getattr(resp, "status", None)},
                )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning(
                "dq_alert_webhook_failed",
                extra={"webhook": env_key, "error": str(exc)},
            )


def gate_promotion(report: ValidationReport) -> None:
    """Alert on any failure, then block if error-severity rules failed."""
    emit_dq_alert(report)
    assert_promotable(report)
