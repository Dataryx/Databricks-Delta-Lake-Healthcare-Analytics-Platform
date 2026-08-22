#!/usr/bin/env python3
"""Build Gold dimensional models and research marts (DQ-gated)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hc_lakehouse.gold.build import build_gold  # noqa: E402
from hc_lakehouse.quality.gates import PromotionBlockedError  # noqa: E402
from hc_lakehouse.utils.config import load_config  # noqa: E402
from hc_lakehouse.utils.logging import get_logger, setup_logging  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    setup_logging(fmt="text")
    log = get_logger("build_gold")
    parser = argparse.ArgumentParser(description="Build Gold layer from Silver.")
    parser.add_argument(
        "--skip-dq-gate",
        action="store_true",
        help="Skip Silver DQ promotion gate (not for production)",
    )
    args = parser.parse_args(argv)

    config = load_config()
    spark = get_spark(config, app_name="hc-gold-build")
    try:
        counts = build_gold(spark, config=config, enforce_dq_gate=not args.skip_dq_gate)
        log.info("gold_build_ok", extra=counts)
        return 0
    except PromotionBlockedError as exc:
        log.error("gold_blocked_by_dq", extra={"error": str(exc)})
        return 2
    finally:
        stop_spark()


if __name__ == "__main__":
    raise SystemExit(main())
