"""Safe Harbor date shift and geographic transforms."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType

if TYPE_CHECKING:
    from pyspark.sql import Column, DataFrame

# 3-digit ZIPs with population under 20,000 must be nulled (illustrative set)
LOW_POP_ZIP3 = frozenset({"036", "059", "063", "102", "203", "556", "692", "878", "879", "884"})


def patient_day_offset(patient_sk: str, pepper: str, max_days: int = 365) -> int:
    """Deterministic offset in ``[-max_days, +max_days]`` from patient surrogate + pepper."""
    digest = hashlib.sha256(f"{pepper}|shift|{patient_sk}".encode()).hexdigest()
    raw = int(digest[:8], 16)
    span = max_days * 2 + 1
    return (raw % span) - max_days


def make_offset_udf(pepper: str, max_days: int = 365) -> Any:
    def _fn(patient_sk: str | None) -> int | None:
        if not patient_sk:
            return None
        return patient_day_offset(patient_sk, pepper, max_days)

    return F.udf(_fn, IntegerType())


def shift_date_column(
    df: DataFrame,
    date_col: str,
    patient_sk_col: str,
    pepper: str,
    dest_col: str | None = None,
) -> DataFrame:
    """Shift a date/timestamp column by the patient's deterministic offset (days)."""
    target = dest_col or date_col
    offset = make_offset_udf(pepper)
    return (
        df.withColumn("_day_offset", offset(F.col(patient_sk_col)))
        .withColumn(
            target,
            F.date_add(F.to_date(F.col(date_col)), F.col("_day_offset")),
        )
        .drop("_day_offset")
    )


def zip3_safe_harbor(zip_col: str = "postal_code") -> Column:
    """Truncate to ZIP3; null low-population ZIP3s."""
    z3 = F.substring(F.col(zip_col).cast(StringType()), 1, 3)
    return F.when(z3.isin(list(LOW_POP_ZIP3)), F.lit(None).cast(StringType())).otherwise(z3)


def age_band_from_birth_year(birth_year_col: str = "birth_year", as_of_year: int = 2024) -> Column:
    """Bucket ages; ages > 89 → ``90+``."""
    age = F.lit(as_of_year) - F.col(birth_year_col)
    return (
        F.when(age.isNull(), F.lit("unknown"))
        .when(age > 89, F.lit("90+"))
        .when(age < 0, F.lit("unknown"))
        .otherwise(F.concat(F.floor(age / 10).cast(StringType()), F.lit("0s")))
    )


def strip_free_text(df: DataFrame, columns: list[str]) -> DataFrame:
    """Null free-text note columns (Safe Harbor: no free text with identifiers)."""
    out = df
    for col in columns:
        if col in out.columns:
            out = out.withColumn(col, F.lit(None).cast(StringType()))
    return out
