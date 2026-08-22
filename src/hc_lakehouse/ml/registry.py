"""MLflow tracking + Unity Catalog model registry (local file store / cloud UC)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hc_lakehouse.utils.config import REPO_ROOT, PlatformConfig, load_config
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)


def configure_mlflow(config: PlatformConfig | None = None) -> str:
    """Set tracking URI. Local: ``artifacts/mlruns``. Cloud: workspace MLflow."""
    import mlflow

    cfg = config or load_config()
    if cfg.is_local:
        uri = str((REPO_ROOT / "artifacts" / "mlruns").resolve())
        Path(uri).mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(uri)
        logger.info("mlflow_tracking_local", extra={"uri": uri})
        return uri
    # Cloud: rely on Databricks-hosted MLflow; UC models via models:/catalog.schema.name
    logger.info("mlflow_tracking_databricks", extra={"detail": "Using workspace default URI"})
    return "databricks"


def log_and_register(
    *,
    model_name: str,
    model: Any,
    metrics: dict[str, Any],
    params: dict[str, Any],
    artifact_paths: list[Path] | None = None,
    config: PlatformConfig | None = None,
) -> str:
    """Fit already done — log sklearn model to MLflow and register locally.

    Returns run_id. UC three-level naming is recorded as a tag for Phase 10 CD.
    """
    import mlflow
    import mlflow.sklearn

    cfg = config or load_config()
    configure_mlflow(cfg)
    uc_name = f"{cfg.catalog}.ml.{model_name}"
    mlflow.set_experiment(f"/hc_lakehouse/{model_name}")
    with mlflow.start_run(run_name=model_name) as run:
        mlflow.log_params({k: str(v) for k, v in params.items()})
        for k, v in metrics.items():
            if v is None:
                continue
            try:
                mlflow.log_metric(k, float(v))
            except (TypeError, ValueError):
                mlflow.log_param(f"metric_{k}", str(v))
        mlflow.set_tag("uc_model_name", uc_name)
        mlflow.set_tag("disclaimer", "research_decision_support_not_clinical_device")
        mlflow.sklearn.log_model(model, artifact_path="model")
        for path in artifact_paths or []:
            if path.exists():
                mlflow.log_artifact(str(path))
        # Local Model Registry (file store); cloud uses UC Models
        try:
            mlflow.register_model(f"runs:/{run.info.run_id}/model", model_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("model_registry_skipped", extra={"error": str(exc)})
        logger.info(
            "model_logged",
            extra={"run_id": run.info.run_id, "uc_model_name": uc_name},
        )
        run_id: str = run.info.run_id
        return run_id
