"""Unit tests for feature builders and ML splits/fairness (no Spark cluster required for splits)."""

from __future__ import annotations

import pandas as pd

from hc_lakehouse.ml.fairness import overall_metrics, subgroup_report
from hc_lakehouse.ml.propensity import propensity_score_match
from hc_lakehouse.ml.splits import DISCLAIMER, patient_train_test_split, temporal_holdout


def test_disclaimer_present() -> None:
    assert "not medical devices" in DISCLAIMER.lower() or "not" in DISCLAIMER.lower()


def test_patient_level_split_no_leakage() -> None:
    df = pd.DataFrame(
        {
            "patient_key": ["a", "a", "b", "b", "c", "c", "d", "d"],
            "x": range(8),
        }
    )
    train, test = patient_train_test_split(df, test_size=0.25, random_state=0)
    assert set(train["patient_key"]).isdisjoint(set(test["patient_key"]))


def test_temporal_holdout_order() -> None:
    df = pd.DataFrame(
        {
            "feature_as_of": pd.to_datetime(
                ["2022-01-01", "2022-06-01", "2023-01-01", "2023-06-01"]
            ),
            "y": [0, 1, 0, 1],
        }
    )
    train, test = temporal_holdout(df, train_frac=0.5)
    assert train["feature_as_of"].max() <= test["feature_as_of"].min()


def test_fairness_and_psm() -> None:
    import numpy as np

    y = np.array([0, 1, 0, 1, 0, 1])
    p = np.array([0.1, 0.8, 0.2, 0.7, 0.3, 0.6])
    pred = (p >= 0.5).astype(int)
    frame = pd.DataFrame({"sex": ["F", "F", "M", "M", "F", "M"]})
    metrics = overall_metrics(y, p, pred)
    assert metrics["n"] == 6
    report = subgroup_report(y, p, pred, frame, ["sex"])
    assert any(r["slice_column"] == "sex" for r in report)

    ps_frame = pd.DataFrame(
        {
            "treat": [1, 1, 1, 0, 0, 0, 1, 0],
            "f1": [1.0, 1.1, 0.9, 0.2, 0.1, 0.3, 1.2, 0.15],
            "f2": [2.0, 2.1, 1.8, 0.5, 0.4, 0.6, 2.2, 0.45],
        }
    )
    pairs = propensity_score_match(
        ps_frame, treatment_col="treat", feature_cols=["f1", "f2"], caliper=0.5
    )
    assert len(pairs) >= 1
