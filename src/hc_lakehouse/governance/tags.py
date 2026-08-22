"""Apply Unity Catalog-style tags from the access matrix (local: metadata table)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import Row

from hc_lakehouse.governance.matrix import load_access_matrix
from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

logger = get_logger(__name__)


def materialize_tags(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
    schemas: list[str] | None = None,
) -> int:
    """Write ``ops.uc_tags`` snapshot for local/demo (UC TAGS applied in cloud)."""
    cfg = config or load_config()
    matrix = load_access_matrix()
    defaults = matrix.tags.get("defaults", {})
    by_schema = matrix.tags.get("by_schema", {})
    target_schemas = schemas or list(by_schema.keys())
    rows: list[Row] = []
    for schema in target_schemas:
        tags = {**defaults, **by_schema.get(schema, {})}
        for key, value in tags.items():
            rows.append(
                Row(
                    catalog=cfg.catalog,
                    schema=schema,
                    tag_key=str(key),
                    tag_value=str(value),
                    source="access_matrix",
                )
            )
    if not rows:
        return 0
    path = delta_table_path(cfg.local_delta_root, "ops", "uc_tags")
    df = spark.createDataFrame(rows)
    write_delta(df, path, mode="overwrite", enable_cdf=False)
    logger.info("tags_materialized", extra={"rows": len(rows), "path": path})
    return len(rows)
