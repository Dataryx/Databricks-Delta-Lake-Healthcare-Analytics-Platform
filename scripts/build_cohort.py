#!/usr/bin/env python3
"""Build a declarative cohort into Gold and emit a research manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hc_lakehouse.cohorts.compiler import build_cohort  # noqa: E402
from hc_lakehouse.cohorts.definition import list_cohorts  # noqa: E402
from hc_lakehouse.utils.config import load_config  # noqa: E402
from hc_lakehouse.utils.logging import get_logger, setup_logging  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    setup_logging(fmt="text")
    log = get_logger("build_cohort")
    parser = argparse.ArgumentParser(description="Materialize a YAML cohort definition.")
    parser.add_argument(
        "--name",
        default="inpatient_utilizers",
        help=f"Cohort name ({', '.join(list_cohorts())})",
    )
    args = parser.parse_args(argv)

    config = load_config()
    spark = get_spark(config, app_name="hc-cohort")
    try:
        manifest = build_cohort(spark, args.name, config=config)
        log.info(
            "cohort_ok",
            extra={
                "name": args.name,
                "rows": manifest.row_count,
                "checksum": manifest.output_checksum[:16],
            },
        )
        return 0
    finally:
        stop_spark()


if __name__ == "__main__":
    raise SystemExit(main())
