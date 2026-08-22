"""Orchestrate feature-dependent ML train/validate/register steps."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from hc_lakehouse.ml.clustering import cluster_prom_trajectories
from hc_lakehouse.ml.noshow import train_noshow_model
from hc_lakehouse.ml.propensity import propensity_score_match
from hc_lakehouse.ml.readmission import (
    build_readmission_training_frame,
    train_readmission_model,
)
from hc_lakehouse.ml.splits import DISCLAIMER
from hc_lakehouse.utils.config import REPO_ROOT, PlatformConfig, load_config
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

logger = get_logger(__name__)


def load_ml_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or (REPO_ROOT / "conf" / "ml" / "models.yml")
    with cfg_path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)
    return data


def train_all_models(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
) -> dict[str, Any]:
    """Train readmission, no-show, PRO clustering; demo propensity utility."""
    cfg = config or load_config()
    ml_cfg = load_ml_config()
    logger.warning("ml_disclaimer", extra={"disclaimer": ml_cfg.get("disclaimer", DISCLAIMER)})

    results: dict[str, Any] = {
        "disclaimer": DISCLAIMER,
        "readmission_30d": train_readmission_model(spark, config=cfg),
        "appointment_noshow": train_noshow_model(spark, config=cfg),
        "prom_nonresponder_cluster": cluster_prom_trajectories(
            spark,
            config=cfg,
            n_clusters=int(
                ml_cfg.get("models", {}).get("prom_nonresponder_cluster", {}).get("n_clusters", 3)
            ),
        ),
    }

    # Propensity demo: treat high Charlson as "exposure" if present
    try:
        frame = build_readmission_training_frame(spark, cfg)
        if "charlson_proxy" in frame.columns:
            frame = frame.copy()
            frame["high_comorbidity"] = (frame["charlson_proxy"].fillna(0) >= 1).astype(int)
            feat = [
                c
                for c in ["encounters_90d", "inpatient_90d", "ed_90d", "avg_los_90d"]
                if c in frame.columns
            ]
            pairs = propensity_score_match(
                frame, treatment_col="high_comorbidity", feature_cols=feat
            )
            results["propensity_pairs"] = int(len(pairs))
        else:
            results["propensity_pairs"] = 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("propensity_demo_skipped", extra={"error": str(exc)})
        results["propensity_pairs"] = 0

    logger.info("ml_pipeline_complete", extra={"keys": list(results.keys())})
    return results
