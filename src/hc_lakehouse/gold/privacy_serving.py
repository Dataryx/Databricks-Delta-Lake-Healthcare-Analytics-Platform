"""Small-cell suppression for aggregate Gold serving views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

from hc_lakehouse.utils.config import load_config
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

logger = get_logger(__name__)


def apply_small_cell_suppression(
    df: DataFrame,
    count_col: str = "n",
    *,
    k: int | None = None,
    mask_cols: list[str] | None = None,
) -> DataFrame:
    """Mask aggregate rows where ``count_col`` < k (default HC_SMALL_CELL_K).

    Count column is set to null when suppressed; optional measure columns nulled.
    Documents k-anonymity posture for broad-access aggregates.
    """
    threshold = k if k is not None else load_config().small_cell_k
    measures = mask_cols or []
    suppressed = F.col(count_col) < F.lit(threshold)
    out = df.withColumn(
        count_col,
        F.when(suppressed, F.lit(None).cast(df.schema[count_col].dataType)).otherwise(
            F.col(count_col)
        ),
    ).withColumn("_suppressed", suppressed)
    for col in measures:
        if col in out.columns and col != count_col:
            out = out.withColumn(
                col,
                F.when(F.col("_suppressed"), F.lit(None)).otherwise(F.col(col)),
            )
    logger.info(
        "small_cell_applied",
        extra={"k": threshold, "count_col": count_col, "mask_cols": measures},
    )
    return out.drop("_suppressed")
