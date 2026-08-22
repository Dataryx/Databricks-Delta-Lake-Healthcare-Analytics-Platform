#!/usr/bin/env python3
"""Build ML feature tables into the local ``ml`` schema."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hc_lakehouse.features.build import build_features  # noqa: E402
from hc_lakehouse.utils.config import load_config  # noqa: E402
from hc_lakehouse.utils.logging import get_logger, setup_logging  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


def main() -> int:
    setup_logging(fmt="text")
    log = get_logger("build_features")
    config = load_config()
    spark = get_spark(config, app_name="hc-features-build")
    try:
        counts = build_features(spark, config=config)
        log.info("features_ok", extra=counts)
        return 0
    finally:
        stop_spark()


if __name__ == "__main__":
    raise SystemExit(main())
