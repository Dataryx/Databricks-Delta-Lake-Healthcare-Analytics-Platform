#!/usr/bin/env python3
"""Local Spark + Delta smoke test for Phase 0.

Creates a tiny Delta table under ``.local_delta/ops/smoke`` to prove the
developer machine can run the medallion stack without Azure.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is importable when run without editable install
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hc_lakehouse.utils.config import load_config  # noqa: E402
from hc_lakehouse.utils.io import delta_table_path, read_delta, write_delta  # noqa: E402
from hc_lakehouse.utils.logging import get_logger, setup_logging  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


def main() -> int:
    setup_logging(fmt="text")
    log = get_logger("spark_smoke")
    config = load_config()
    spark = get_spark(config, app_name="hc-lakehouse-smoke")
    try:
        df = spark.createDataFrame(
            [(1, "bronze"), (2, "silver"), (3, "gold")],
            schema="layer_id INT, layer_name STRING",
        )
        path = delta_table_path(config.local_delta_root, "ops", "smoke")
        write_delta(df, path, mode="overwrite", enable_cdf=True)
        roundtrip = read_delta(spark, path)
        count = roundtrip.count()
        log.info("smoke_ok", extra={"path": path, "rows": count})
        if count != 3:
            log.error("smoke_rowcount_mismatch", extra={"expected": 3, "actual": count})
            return 1
        return 0
    finally:
        stop_spark()


if __name__ == "__main__":
    raise SystemExit(main())
