"""PRO trajectory clustering to identify synthetic non-responder patterns."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from hc_lakehouse.ml.cards import render_model_card, write_model_card
from hc_lakehouse.ml.registry import log_and_register
from hc_lakehouse.ml.splits import DISCLAIMER
from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, read_delta, table_exists, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

logger = get_logger(__name__)


def cluster_prom_trajectories(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
    n_clusters: int = 3,
) -> dict[str, Any]:
    """KMeans on wide PRO scores; write ``ml.prom_cluster_assignment``."""
    cfg = config or load_config()
    path = delta_table_path(cfg.local_delta_root, "ml", "ft_prom_scores")
    if not table_exists(spark, path):
        raise FileNotFoundError(path)
    prom_pdf: pd.DataFrame = read_delta(spark, path).toPandas()
    if len(prom_pdf) == 0:
        return {"n": 0, "clusters": 0}

    wide = prom_pdf.pivot_table(
        index="patient_key",
        columns="instrument_key",
        values="score_value",
        aggfunc="mean",
    ).fillna(0.0)
    scaler = StandardScaler()
    x = scaler.fit_transform(wide.to_numpy())
    k = min(n_clusters, max(1, len(wide)))
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(x)
    assign = pd.DataFrame(
        {
            "patient_key": wide.index.astype(str),
            "cluster_id": labels.astype(int),
            "n_instruments": (wide != 0).sum(axis=1).to_numpy(),
        }
    )
    # Heuristic: lowest mean score cluster tagged as non_responder_pattern
    means = assign.merge(
        wide.mean(axis=1).rename("mean_score").reset_index(),
        on="patient_key",
    )
    cluster_means = means.groupby("cluster_id")["mean_score"].mean()
    non_resp = int(cluster_means.idxmin()) if len(cluster_means) else 0
    assign["is_nonresponder_pattern"] = (assign["cluster_id"] == non_resp).astype(int)

    out_path = delta_table_path(cfg.local_delta_root, "ml", "prom_cluster_assignment")
    write_delta(spark.createDataFrame(assign), out_path, mode="overwrite", enable_cdf=False)

    card = render_model_card(
        model_name="prom_nonresponder_cluster",
        version="1.0.0",
        intended_use=(
            "Exploratory clustering of synthetic PRO scores to surface non-responder-like "
            "patterns for research hypothesis generation."
        ),
        features=list(wide.columns.astype(str)),
        metrics={"n_patients": len(assign), "n_clusters": k, "nonresponder_cluster": non_resp},
        fairness=[],
        training_notes=f"KMeans k={k} on standardized instrument means. {DISCLAIMER}",
    )
    card_path = write_model_card(card, "prom_nonresponder_cluster")
    run_id = log_and_register(
        model_name="prom_nonresponder_cluster",
        model=km,
        metrics={"n_patients": float(len(assign)), "n_clusters": float(k)},
        params={"algorithm": "KMeans", "n_clusters": k},
        artifact_paths=[card_path],
        config=cfg,
    )
    logger.info("prom_clustered", extra={"run_id": run_id, "n": len(assign), "k": k})
    return {"run_id": run_id, "n": len(assign), "clusters": k, "nonresponder_cluster": non_resp}
