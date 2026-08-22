"""Appointment no-show prediction (synthetic labels from ambulatory encounters)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier

from hc_lakehouse.ml.cards import render_model_card, write_model_card
from hc_lakehouse.ml.fairness import overall_metrics, subgroup_report
from hc_lakehouse.ml.registry import log_and_register
from hc_lakehouse.ml.splits import (
    DISCLAIMER,
    encode_categoricals,
    numeric_feature_matrix,
    patient_train_test_split,
)
from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, read_delta, table_exists
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

logger = get_logger(__name__)

CAT_COLS = ["sex", "race", "ethnicity", "age_band", "care_setting_key"]
NUM_COLS = ["encounters_90d", "inpatient_90d", "ed_90d", "avg_los_90d", "score_value"]


def _synthetic_noshow(patient_key: str, encounter_key: str) -> int:
    """Deterministic synthetic no-show label (~20% rate) — not real attendance data."""
    import hashlib

    digest = hashlib.sha256(f"{patient_key}:{encounter_key}:noshow".encode()).hexdigest()
    h = int(digest[:8], 16) % 100
    return 1 if h < 20 else 0


def build_noshow_training_frame(spark: SparkSession, config: PlatformConfig) -> pd.DataFrame:
    root = config.local_delta_root

    def _load(schema: str, table: str) -> pd.DataFrame:
        path = delta_table_path(root, schema, table)
        if not table_exists(spark, path):
            raise FileNotFoundError(path)
        return read_delta(spark, path).toPandas()

    enc = _load("gold", "fact_encounter")
    amb = enc[enc["care_setting_key"].isin(["outpatient", "ambulatory"])].copy()
    if amb.empty:
        amb = enc.copy()
    amb["no_show"] = [
        _synthetic_noshow(str(r.patient_key), str(r.encounter_key)) for r in amb.itertuples()
    ]
    amb["feature_as_of"] = pd.to_datetime(amb["admit_ts"]).dt.date.astype(str)

    demo = _load("ml", "ft_patient_demographics")
    util = _load("ml", "ft_utilization_90d")
    prom = _load("ml", "ft_prom_scores")
    demo_u = demo.sort_values("feature_as_of").groupby("patient_key", as_index=False).tail(1)
    prom_u = (
        prom.sort_values("feature_as_of")
        .groupby("patient_key", as_index=False)
        .agg(score_value=("score_value", "mean"))
    )
    util["feature_as_of"] = util["feature_as_of"].astype(str)

    merged = amb.merge(demo_u.drop(columns=["feature_as_of"], errors="ignore"), on="patient_key")
    merged = merged.merge(util, on=["patient_key", "feature_as_of"], how="left")
    merged = merged.merge(prom_u, on="patient_key", how="left")
    merged["payer_group"] = (
        merged["patient_key"]
        .astype(str)
        .str[:1]
        .map(lambda c: ["SYN-PAYER-A", "SYN-PAYER-B", "SYN-PAYER-C"][ord(c[0]) % 3])
    )
    return merged


def train_noshow_model(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
) -> dict[str, Any]:
    cfg = config or load_config()
    frame = build_noshow_training_frame(spark, cfg)
    train_df, test_df = patient_train_test_split(frame, patient_col="patient_key")
    train_e, test_e, _ = encode_categoricals(train_df, test_df, CAT_COLS)
    feature_cols = [c for c in CAT_COLS + NUM_COLS if c in train_e.columns]
    x_train = numeric_feature_matrix(train_e, feature_cols)
    x_test = numeric_feature_matrix(test_e, feature_cols)
    y_train = train_e["no_show"].to_numpy()
    y_test = test_e["no_show"].to_numpy()

    base = HistGradientBoostingClassifier(max_depth=3, max_iter=40, random_state=42)
    model = CalibratedClassifierCV(base, method="sigmoid", cv=2)
    model.fit(x_train, y_train)
    y_prob = model.predict_proba(x_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    metrics = overall_metrics(y_test, y_prob, y_pred)
    fairness = subgroup_report(
        y_test,
        y_prob,
        y_pred,
        test_e.reset_index(drop=True),
        ["age_band", "sex", "race", "ethnicity", "payer_group"],
    )
    card = render_model_card(
        model_name="appointment_noshow",
        version="1.0.0",
        intended_use=(
            "Research prediction of synthetic ambulatory appointment no-show labels. "
            "Labels are simulated for pipeline demonstration only."
        ),
        features=feature_cols,
        metrics=metrics,
        fairness=fairness,
        training_notes=f"Patient-level split; sigmoid-calibrated HGB. {DISCLAIMER}",
    )
    card_path = write_model_card(card, "appointment_noshow")
    run_id = log_and_register(
        model_name="appointment_noshow",
        model=model,
        metrics={k: v for k, v in metrics.items() if isinstance(v, int | float)},
        params={"algorithm": "HistGradientBoosting", "calibration": "sigmoid"},
        artifact_paths=[card_path],
        config=cfg,
    )
    logger.info("noshow_trained", extra={"run_id": run_id, **metrics})
    return {"run_id": run_id, "metrics": metrics, "fairness": fairness, "n_train": len(train_e)}
