"""Subgroup fairness / performance reporting."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    roc_auc_score,
)


def _safe_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float | None:
    if len(np.unique(y_true)) < 2:
        return None
    try:
        return float(roc_auc_score(y_true, y_prob))
    except ValueError:
        return None


def subgroup_report(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    y_pred: np.ndarray,
    frame: pd.DataFrame,
    slice_cols: list[str],
) -> list[dict[str, Any]]:
    """Compute accuracy/AUC/Brier for each level of each slice column."""
    rows: list[dict[str, Any]] = []
    for col in slice_cols:
        if col not in frame.columns:
            continue
        for level, idx in frame.groupby(col, dropna=False).groups.items():
            mask = frame.index.isin(idx)
            yt = y_true[mask]
            yp = y_prob[mask]
            yd = y_pred[mask]
            if len(yt) == 0:
                continue
            rows.append(
                {
                    "slice_column": col,
                    "slice_value": str(level),
                    "n": int(len(yt)),
                    "positive_rate": float(np.mean(yt)),
                    "accuracy": float(accuracy_score(yt, yd)),
                    "auc": _safe_auc(yt, yp),
                    "brier": float(brier_score_loss(yt, yp)) if len(np.unique(yt)) > 0 else None,
                }
            )
    return rows


def overall_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    return {
        "n": int(len(y_true)),
        "positive_rate": float(np.mean(y_true)) if len(y_true) else 0.0,
        "accuracy": float(accuracy_score(y_true, y_pred)) if len(y_true) else 0.0,
        "auc": _safe_auc(y_true, y_prob),
        "brier": float(brier_score_loss(y_true, y_prob)) if len(y_true) else None,
    }
