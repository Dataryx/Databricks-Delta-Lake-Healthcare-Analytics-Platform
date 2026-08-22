"""Silver cleansing utilities — pure DataFrame transforms."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

NULL_TOKENS = ("", "NULL", "UNK", "NA", "N/A", "-9", "999", "null", "None")


def normalize_null_tokens(df: DataFrame, columns: list[str] | None = None) -> DataFrame:
    """Replace common null tokens with SQL null."""
    cols = columns or [c for c in df.columns if not c.startswith("_")]
    out = df
    for col in cols:
        if col not in out.columns:
            continue
        out = out.withColumn(
            col,
            F.when(
                F.upper(F.trim(F.col(col).cast(StringType()))).isin(
                    [t.upper() for t in NULL_TOKENS]
                ),
                F.lit(None),
            ).otherwise(F.col(col)),
        )
    return out


def trim_strings(df: DataFrame, columns: list[str] | None = None) -> DataFrame:
    """Trim whitespace on string-like columns."""
    cols = columns or [c for c in df.columns if not c.startswith("_")]
    out = df
    for col in cols:
        if col not in out.columns:
            continue
        out = out.withColumn(col, F.trim(F.col(col).cast(StringType())))
    return out


def canonical_lower(df: DataFrame, columns: list[str]) -> DataFrame:
    """Lowercase selected categorical columns."""
    out = df
    for col in columns:
        if col in out.columns:
            out = out.withColumn(col, F.lower(F.col(col)))
    return out


def parse_ts(df: DataFrame, column: str, dest: str | None = None) -> DataFrame:
    """Parse ISO-8601 / common timestamp strings to TimestampType (UTC session)."""
    target = dest or column
    return df.withColumn(
        target,
        F.to_timestamp(F.col(column)),
    )


def dedupe_latest(
    df: DataFrame,
    key_cols: list[str],
    order_col: str,
) -> DataFrame:
    """Keep latest row per natural key by ``order_col``."""
    from pyspark.sql.window import Window

    w = Window.partitionBy(*key_cols).orderBy(F.col(order_col).desc_nulls_last())
    return df.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1).drop("_rn")
