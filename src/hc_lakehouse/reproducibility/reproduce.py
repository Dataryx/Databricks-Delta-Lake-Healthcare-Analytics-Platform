"""Re-derive a published artifact from its research manifest and assert checksum."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hc_lakehouse.cohorts.compiler import compile_cohort
from hc_lakehouse.cohorts.definition import load_cohort
from hc_lakehouse.reproducibility.manifest import checksum_dataframe, load_manifest
from hc_lakehouse.utils.config import load_config
from hc_lakehouse.utils.logging import get_logger, setup_logging
from hc_lakehouse.utils.spark_session import get_spark, stop_spark

logger = get_logger(__name__)


def reproduce_cohort_from_manifest(manifest_path: Path) -> int:
    """Rebuild cohort and assert checksum equals the recorded manifest checksum."""
    setup_logging(fmt="text")
    manifest = load_manifest(manifest_path)
    if manifest.artifact_kind != "cohort":
        logger.error("unsupported_artifact_kind", extra={"kind": manifest.artifact_kind})
        return 2

    cohort_name = (manifest.extra or {}).get("cohort_name") or manifest.artifact.removeprefix(
        "cohort_"
    )
    config = load_config()
    spark = get_spark(config, app_name="hc-reproduce")
    try:
        definition = load_cohort(cohort_name)
        if manifest.definition_hash and definition.definition_hash != manifest.definition_hash:
            logger.error(
                "definition_hash_mismatch",
                extra={
                    "expected": manifest.definition_hash,
                    "actual": definition.definition_hash,
                },
            )
            return 3

        for table_fqn, version in manifest.input_tables.items():
            logger.info(
                "manifest_input_pin",
                extra={"table": table_fqn, "version": version},
            )

        cohort_df, _ = compile_cohort(
            spark,
            definition,
            config=config,
            principal=manifest.creating_principal,
        )
        keys = cohort_df.select("patient_sk", "cohort_name", "definition_hash")
        new_checksum = checksum_dataframe(keys)

        if keys.count() != manifest.row_count:
            logger.error(
                "reproduce_rowcount_mismatch",
                extra={"expected": manifest.row_count, "actual": keys.count()},
            )
            return 4

        if new_checksum != manifest.output_checksum:
            logger.error(
                "reproduce_checksum_mismatch",
                extra={"expected": manifest.output_checksum, "actual": new_checksum},
            )
            return 5

        # Byte-for-byte stability: second compile matches
        again, _ = compile_cohort(spark, definition, config=config, principal="reproduce")
        again_checksum = checksum_dataframe(
            again.select("patient_sk", "cohort_name", "definition_hash")
        )
        if again_checksum != new_checksum:
            logger.error(
                "reproduce_not_deterministic",
                extra={"first": new_checksum, "second": again_checksum},
            )
            return 6

        logger.info(
            "reproduce_ok",
            extra={
                "artifact": manifest.artifact,
                "checksum": new_checksum,
                "rows": manifest.row_count,
            },
        )
        return 0
    finally:
        stop_spark()


def main(argv: list[str] | None = None) -> int:
    setup_logging(fmt="text")
    parser = argparse.ArgumentParser(
        description="Re-derive a Gold artifact from a research manifest.",
    )
    parser.add_argument("--manifest", required=True, help="Path to RESEARCH_MANIFEST.json")
    args = parser.parse_args(argv)
    path = Path(args.manifest)
    if not path.exists():
        logger.error("manifest_missing", extra={"path": str(path)})
        return 1
    return reproduce_cohort_from_manifest(path)


if __name__ == "__main__":
    sys.exit(main())
