"""Propensity-score matching utility for observational research comparisons."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors

from hc_lakehouse.ml.splits import DISCLAIMER
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)


def propensity_score_match(
    frame: pd.DataFrame,
    *,
    treatment_col: str,
    feature_cols: list[str],
    caliper: float = 0.2,
) -> pd.DataFrame:
    """1:1 nearest-neighbor matching on propensity scores within ``caliper``.

    Returns a dataframe of matched treated/control pairs with scores.
    Research utility only — not causal identification by itself.
    """
    df = frame.dropna(subset=[treatment_col, *feature_cols]).copy()
    y = df[treatment_col].astype(int).to_numpy()
    x = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy()
    if len(np.unique(y)) < 2 or len(df) < 4:
        logger.warning("psm_insufficient_data", extra={"n": len(df)})
        return pd.DataFrame(columns=["treated_idx", "control_idx", "ps_treated", "ps_control"])

    clf = LogisticRegression(max_iter=500, random_state=42)
    clf.fit(x, y)
    ps = clf.predict_proba(x)[:, 1]
    df = df.assign(_ps=ps, _idx=np.arange(len(df)))
    treated = df[df[treatment_col].astype(int) == 1]
    control = df[df[treatment_col].astype(int) == 0]
    if treated.empty or control.empty:
        return pd.DataFrame(columns=["treated_idx", "control_idx", "ps_treated", "ps_control"])

    nn = NearestNeighbors(n_neighbors=1, algorithm="auto")
    nn.fit(control[["_ps"]].to_numpy())
    dist, ind = nn.kneighbors(treated[["_ps"]].to_numpy())
    pairs: list[dict[str, Any]] = []
    used: set[int] = set()
    for i, (d, j) in enumerate(zip(dist[:, 0], ind[:, 0], strict=True)):
        if d > caliper:
            continue
        ctrl_pos = int(control.iloc[j]["_idx"])
        if ctrl_pos in used:
            continue
        used.add(ctrl_pos)
        pairs.append(
            {
                "treated_idx": int(treated.iloc[i]["_idx"]),
                "control_idx": ctrl_pos,
                "ps_treated": float(treated.iloc[i]["_ps"]),
                "ps_control": float(control.iloc[j]["_ps"]),
                "ps_distance": float(d),
                "disclaimer": DISCLAIMER,
            }
        )
    logger.info("psm_complete", extra={"pairs": len(pairs), "caliper": caliper})
    return pd.DataFrame(pairs)
