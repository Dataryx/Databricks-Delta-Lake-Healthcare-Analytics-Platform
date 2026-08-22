#!/usr/bin/env python3
"""Log a pipeline run and evaluate SLA freshness (local/demo)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hc_lakehouse.ops.cost import write_cost_report_artifact  # noqa: E402
from hc_lakehouse.ops.run_log import check_freshness, log_pipeline_run  # noqa: E402
from hc_lakehouse.utils.config import load_config  # noqa: E402
from hc_lakehouse.utils.logging import get_logger, setup_logging  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    setup_logging(fmt="text")
    log = get_logger("ops_report")
    parser = argparse.ArgumentParser(description="Write ops run log + freshness + cost SQL")
    parser.add_argument("--pipeline", default="local_demo")
    parser.add_argument("--status", default="success")
    args = parser.parse_args(argv)

    write_cost_report_artifact()
    config = load_config()
    spark = get_spark(config, app_name="hc-ops-report")
    try:
        started = time.perf_counter()
        run_id = log_pipeline_run(
            spark,
            pipeline_name=args.pipeline,
            status=args.status,
            duration_seconds=time.perf_counter() - started,
            config=config,
        )
        misses = check_freshness(spark, config=config)
        log.info("ops_report_ok", extra={"run_id": run_id, "sla_misses": len(misses)})
        return 0
    finally:
        stop_spark()


if __name__ == "__main__":
    raise SystemExit(main())
