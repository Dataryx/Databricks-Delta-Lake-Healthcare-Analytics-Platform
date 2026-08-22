"""30-day readmission risk model (research artifact)."""

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

CAT_COLS = ["sex", "race", "ethnicity", "age_band"]
NUM_COLS = [
    "encounters_90d",
    "inpatient_90d",
    "ed_90d",
    "avg_los_90d",
    "lab_count_180d",
    "distinct_labs_180d",
    "mean_lab_value_180d",
    "charlson_proxy",
    "distinct_conditions",
]


def build_readmission_training_frame(spark: SparkSession, config: PlatformConfig) -> pd.DataFrame:
    """Join gold.fact_readmission with feature tables (patient-level as-of join)."""
    root = config.local_delta_root

    def _load(schema: str, table: str) -> pd.DataFrame:
        path = delta_table_path(root, schema, table)
        if not table_exists(spark, path):
            raise FileNotFoundError(path)
        return read_delta(spark, path).toPandas()

    labels = _load("gold", "fact_readmission")
    enc = _load("gold", "fact_encounter")[
        ["encounter_key", "admit_ts", "discharge_ts", "care_setting_key"]
    ]
    demo = _load("ml", "ft_patient_demographics")
    util = _load("ml", "ft_utilization_90d")
    labs = _load("ml", "ft_lab_trends")
    como = _load("ml", "ft_comorbidity_index")

    base = labels.merge(enc, on="encounter_key", how="left")
    base["readmission_30d"] = base["readmission_30d"].astype(int)
    base["feature_as_of"] = pd.to_datetime(base["admit_ts"]).dt.date.astype(str)

    demo_u = demo.sort_values("feature_as_of").groupby("patient_key", as_index=False).tail(1)
    como_u = como.sort_values("feature_as_of").groupby("patient_key", as_index=False).tail(1)
    util["feature_as_of"] = util["feature_as_of"].astype(str)
    labs["feature_as_of"] = labs["feature_as_of"].astype(str)

    merged = base.merge(demo_u.drop(columns=["feature_as_of"], errors="ignore"), on="patient_key")
    merged = merged.merge(
        como_u.drop(columns=["feature_as_of"], errors="ignore"),
        on="patient_key",
        how="left",
    )
    merged = merged.merge(util, on=["patient_key", "feature_as_of"], how="left")
    merged = merged.merge(labs, on=["patient_key", "feature_as_of"], how="left")
    merged["payer_group"] = (
        merged["patient_key"]
        .astype(str)
        .str[:1]
        .map(lambda c: ["SYN-PAYER-A", "SYN-PAYER-B", "SYN-PAYER-C"][ord(c[0]) % 3])
    )
    return merged


def train_readmission_model(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
) -> dict[str, Any]:
    """Train calibrated HGB readmission model; log to MLflow; write model card."""
    cfg = config or load_config()
    frame = build_readmission_training_frame(spark, cfg)
    train_df, test_df = patient_train_test_split(frame, patient_col="patient_key")
    train_e, test_e, _ = encode_categoricals(train_df, test_df, CAT_COLS)
    feature_cols = [c for c in CAT_COLS + NUM_COLS if c in train_e.columns]
    x_train = numeric_feature_matrix(train_e, feature_cols)
    x_test = numeric_feature_matrix(test_e, feature_cols)
    y_train = train_e["readmission_30d"].to_numpy()
    y_test = test_e["readmission_30d"].to_numpy()

    base = HistGradientBoostingClassifier(max_depth=3, max_iter=50, random_state=42)
    # Small-data safe calibration
    method = "isotonic" if len(train_e) >= 40 else "sigmoid"
    model = CalibratedClassifierCV(base, method=method, cv=2)
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
        model_name="readmission_30d",
        version="1.0.0",
        intended_use=(
            "Research risk stratification for 30-day all-cause readmission among "
            "synthetic inpatient index stays. Not for clinical use."
        ),
        features=feature_cols,
        metrics=metrics,
        fairness=fairness,
        training_notes=(
            f"Patient-level split; calibrated HistGradientBoosting ({method}). {DISCLAIMER}"
        ),
    )
    card_path = write_model_card(card, "readmission_30d")
    run_id = log_and_register(
        model_name="readmission_30d",
        model=model,
        metrics={k: v for k, v in metrics.items() if isinstance(v, int | float)},
        params={"algorithm": "HistGradientBoosting", "calibration": method, "cv": 2},
        artifact_paths=[card_path],
        config=cfg,
    )
    logger.info("readmission_trained", extra={"run_id": run_id, **metrics})
    return {"run_id": run_id, "metrics": metrics, "fairness": fairness, "n_train": len(train_e)}
