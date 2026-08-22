#!/usr/bin/env python3
"""Apply governance: grants SQL artifact, tags, lineage, access review seed."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hc_lakehouse.governance.audit import (  # noqa: E402
    seed_access_review,
    write_access_audit_daily,
)
from hc_lakehouse.governance.grants import apply_grants  # noqa: E402
from hc_lakehouse.governance.lineage import snapshot_lineage, write_lineage_doc  # noqa: E402
from hc_lakehouse.governance.tags import materialize_tags  # noqa: E402
from hc_lakehouse.utils.config import load_config  # noqa: E402
from hc_lakehouse.utils.logging import get_logger, setup_logging  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    setup_logging(fmt="text")
    log = get_logger("apply_governance")
    parser = argparse.ArgumentParser(description="Apply governance-as-code artifacts.")
    parser.add_argument("--catalog", default=None)
    args = parser.parse_args(argv)

    config = load_config()
    sql_path = apply_grants(catalog=args.catalog or config.catalog, dry_run=True)
    write_lineage_doc()

    spark = get_spark(config, app_name="hc-governance")
    try:
        n_tags = materialize_tags(spark, config=config)
        n_lin = snapshot_lineage(spark, config=config)
        n_audit = write_access_audit_daily(spark, config=config)
        n_review = seed_access_review(spark, config=config)
        log.info(
            "governance_applied",
            extra={
                "grants_sql": str(sql_path),
                "tags": n_tags,
                "lineage_edges": n_lin,
                "audit_rows": n_audit,
                "review_rows": n_review,
            },
        )
        return 0
    finally:
        stop_spark()


if __name__ == "__main__":
    raise SystemExit(main())
