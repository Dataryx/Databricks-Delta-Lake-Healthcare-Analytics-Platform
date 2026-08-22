#!/usr/bin/env python3
"""Run Silver data-quality rules and optionally gate Gold promotion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hc_lakehouse.quality.results import scorecard_summary  # noqa: E402
from hc_lakehouse.quality.runner import validate_all_silver  # noqa: E402
from hc_lakehouse.utils.config import load_config  # noqa: E402
from hc_lakehouse.utils.logging import get_logger, setup_logging  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    setup_logging(fmt="text")
    log = get_logger("run_dq")
    parser = argparse.ArgumentParser(description="Validate Silver tables (fail closed).")
    parser.add_argument(
        "--no-gate",
        action="store_true",
        help="Persist results and alert but do not raise on error failures",
    )
    args = parser.parse_args(argv)

    config = load_config()
    spark = get_spark(config, app_name="hc-dq")
    try:
        reports = validate_all_silver(spark, config=config, enforce_gate=not args.no_gate)
        for name, report in reports.items():
            log.info(
                "dq_table_status",
                extra={
                    "ruleset": name,
                    "passed": report.passed,
                    "error_failures": [f.rule_id for f in report.error_failures],
                },
            )
        card = scorecard_summary(spark, config)
        log.info("dq_scorecard_rows", extra={"rows": card.count()})
        return 0
    except Exception as exc:  # noqa: BLE001 — CLI exit
        from hc_lakehouse.quality.gates import PromotionBlockedError

        if isinstance(exc, PromotionBlockedError):
            log.error("dq_gate_blocked", extra={"error": str(exc)})
            return 2
        raise
    finally:
        stop_spark()


if __name__ == "__main__":
    raise SystemExit(main())
