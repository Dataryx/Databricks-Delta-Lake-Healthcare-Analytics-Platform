#!/usr/bin/env python3
"""Train research ML models (readmission, no-show, PRO clusters) and register via MLflow."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hc_lakehouse.ml.pipeline import train_all_models  # noqa: E402
from hc_lakehouse.ml.splits import DISCLAIMER  # noqa: E402
from hc_lakehouse.utils.config import load_config  # noqa: E402
from hc_lakehouse.utils.logging import get_logger, setup_logging  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


def main() -> int:
    setup_logging(fmt="text")
    log = get_logger("train_ml")
    log.warning("ml_disclaimer", extra={"disclaimer": DISCLAIMER})
    config = load_config()
    spark = get_spark(config, app_name="hc-ml-train")
    try:
        results = train_all_models(spark, config=config)
        log.info(
            "ml_train_ok",
            extra={
                "readmission_run": results.get("readmission_30d", {}).get("run_id"),
                "noshow_run": results.get("appointment_noshow", {}).get("run_id"),
                "propensity_pairs": results.get("propensity_pairs"),
            },
        )
        return 0
    finally:
        stop_spark()


if __name__ == "__main__":
    raise SystemExit(main())
