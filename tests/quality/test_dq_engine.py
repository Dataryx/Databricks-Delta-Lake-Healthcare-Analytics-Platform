"""Integration tests for DQ engine against Silver tables."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspark")
pytest.importorskip("delta")

from hc_lakehouse.bronze.ingest import ingest_landing_directory  # noqa: E402
from hc_lakehouse.ingest.synthetic.generator import generate_and_write  # noqa: E402
from hc_lakehouse.quality.results import load_dq_results, scorecard_summary  # noqa: E402
from hc_lakehouse.quality.runner import validate_all_silver  # noqa: E402
from hc_lakehouse.silver.transform import build_silver_core  # noqa: E402
from hc_lakehouse.utils.config import clear_config_cache, load_config  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


@pytest.fixture()
def spark_dq(tmp_path, monkeypatch):
    monkeypatch.setenv("HC_RUNTIME_MODE", "local")
    monkeypatch.setenv("HC_LOCAL_DELTA_ROOT", str(tmp_path / "delta"))
    monkeypatch.setenv("HC_DEID_SALT", "local-demo-pepper-not-for-production")
    clear_config_cache()
    cfg = load_config()
    spark = get_spark(cfg, app_name="test-dq", force_new=True)
    yield spark, cfg, tmp_path
    stop_spark()
    clear_config_cache()


@pytest.mark.quality
def test_dq_persists_and_passes_on_synthetic(spark_dq) -> None:
    spark, cfg, tmp_path = spark_dq
    root = tmp_path / "syn"
    generate_and_write(root, seed=42, patient_count=5, write_sample_subset=False)
    ingest_landing_directory(
        spark,
        root / "landing",
        config=cfg,
        entities=["patient", "encounter", "lab_result"],
    )
    build_silver_core(spark, config=cfg)
    reports = validate_all_silver(spark, config=cfg, enforce_gate=True)
    assert all(r.passed for r in reports.values())
    results = load_dq_results(spark, cfg)
    assert results.count() >= 10
    card = scorecard_summary(spark, cfg)
    assert card.count() >= 5
