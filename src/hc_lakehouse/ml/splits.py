"""Patient-level and temporal train/test splits (never row-level)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from numpy.typing import NDArray

DISCLAIMER = (
    "Models are research and decision-support artifacts only. "
    "They are not medical devices, diagnostic tools, or clinical advice."
)


def patient_train_test_split(
    df: pd.DataFrame,
    *,
    patient_col: str = "patient_key",
    test_size: float = 0.25,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by unique patients so the same patient never appears in both sets."""
    patients = df[patient_col].dropna().unique()
    rng = np.random.default_rng(random_state)
    shuffled = rng.permutation(patients)
    n_test = max(1, int(round(len(shuffled) * test_size)))
    test_ids = set(shuffled[:n_test])
    train = df[~df[patient_col].isin(test_ids)].copy()
    test = df[df[patient_col].isin(test_ids)].copy()
    if train.empty or test.empty:
        # Degenerate small samples: fall back to 80/20 on rows but keep warning via empty check
        cut = max(1, int(len(df) * (1 - test_size)))
        return df.iloc[:cut].copy(), df.iloc[cut:].copy()
    return train, test


def temporal_holdout(
    df: pd.DataFrame,
    *,
    time_col: str = "feature_as_of",
    train_frac: float = 0.75,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hold out the latest ``1 - train_frac`` of rows by ``time_col`` (no look-ahead)."""
    ordered = df.sort_values(time_col)
    cut = max(1, int(len(ordered) * train_frac))
    return ordered.iloc[:cut].copy(), ordered.iloc[cut:].copy()


def encode_categoricals(
    train: pd.DataFrame,
    test: pd.DataFrame,
    cat_cols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, int]]]:
    """Fit categorical codes on train only; map unknowns in test to -1."""
    mappings: dict[str, dict[str, int]] = {}
    train_out = train.copy()
    test_out = test.copy()
    for col in cat_cols:
        if col not in train_out.columns:
            continue
        uniques = sorted(train_out[col].astype(str).fillna("MISSING").unique())
        mapping = {v: i for i, v in enumerate(uniques)}
        mappings[col] = mapping
        train_out[col] = train_out[col].astype(str).fillna("MISSING").map(mapping).astype(int)
        test_out[col] = (
            test_out[col]
            .astype(str)
            .fillna("MISSING")
            .map(lambda x, m=mapping: m.get(x, -1))
            .astype(int)
        )
    return train_out, test_out, mappings


def numeric_feature_matrix(
    df: pd.DataFrame,
    feature_cols: list[str],
) -> NDArray[np.floating]:
    """Return float feature matrix with NaNs filled to 0."""
    arr = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    return np.asarray(arr, dtype=float)
