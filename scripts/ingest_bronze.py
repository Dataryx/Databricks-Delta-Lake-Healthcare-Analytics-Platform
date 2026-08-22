#!/usr/bin/env python3
"""Ingest synthetic landing CSVs into local Bronze Delta tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hc_lakehouse.bronze.ingest import ingest_landing_directory  # noqa: E402
from hc_lakehouse.utils.config import load_config  # noqa: E402
from hc_lakehouse.utils.logging import get_logger, setup_logging  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    setup_logging(fmt="text")
    log = get_logger("ingest_bronze")
    parser = argparse.ArgumentParser(description="Bronze batch ingest from landing CSVs.")
    parser.add_argument(
        "--landing",
        type=Path,
        default=REPO_ROOT / "data" / "synthetic" / "landing",
        help="Landing root containing clinical/ and survey/",
    )
    args = parser.parse_args(argv)

    if not args.landing.exists():
        log.error(
            "landing_missing",
            extra={
                "path": str(args.landing),
                "hint": "Run scripts/generate_synthetic.py first",
            },
        )
        return 1

    config = load_config()
    spark = get_spark(config, app_name="hc-bronze-ingest")
    try:
        counts = ingest_landing_directory(spark, args.landing, config=config)
        total = sum(counts.values())
        log.info("bronze_ingest_complete", extra={"tables": len(counts), "rows": total})
        return 0 if total >= 0 else 1
    finally:
        stop_spark()


if __name__ == "__main__":
    raise SystemExit(main())
