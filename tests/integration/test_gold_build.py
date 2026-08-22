"""Gold layer integration tests."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspark")
pytest.importorskip("delta")

from hc_lakehouse.bronze.ingest import ingest_landing_directory  # noqa: E402
from hc_lakehouse.gold.build import build_gold  # noqa: E402
from hc_lakehouse.gold.privacy_serving import apply_small_cell_suppression  # noqa: E402
from hc_lakehouse.ingest.synthetic.generator import generate_and_write  # noqa: E402
from hc_lakehouse.silver.transform import build_silver_core  # noqa: E402
from hc_lakehouse.utils.config import clear_config_cache, load_config  # noqa: E402
from hc_lakehouse.utils.io import delta_table_path, read_delta  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


@pytest.fixture()
def spark_gold(tmp_path, monkeypatch):
    monkeypatch.setenv("HC_RUNTIME_MODE", "local")
    monkeypatch.setenv("HC_LOCAL_DELTA_ROOT", str(tmp_path / "delta"))
    monkeypatch.setenv("HC_DEID_SALT", "local-demo-pepper-not-for-production")
    monkeypatch.setenv("HC_SMALL_CELL_K", "11")
    clear_config_cache()
    cfg = load_config()
    spark = get_spark(cfg, app_name="test-gold", force_new=True)
    yield spark, cfg, tmp_path
    stop_spark()
    clear_config_cache()


def test_small_cell_suppression(spark_gold) -> None:
    spark, _, _ = spark_gold
    df = spark.createDataFrame([(5, 1.2), (20, 2.4)], "n INT, avg_los_days DOUBLE")
    out = apply_small_cell_suppression(df, "n", k=11, mask_cols=["avg_los_days"]).collect()
    assert any(r.n is None for r in out)
    assert any(r.n == 20 for r in out)


@pytest.mark.integration
def test_gold_build_end_to_end(spark_gold) -> None:
    spark, cfg, tmp_path = spark_gold
    root = tmp_path / "syn"
    generate_and_write(root, seed=42, patient_count=8, write_sample_subset=False)
    ingest_landing_directory(spark, root / "landing", config=cfg)
    build_silver_core(spark, config=cfg)
    counts = build_gold(spark, config=cfg, enforce_dq_gate=True)
    assert counts["dim_patient"] == 8
    assert counts["fact_encounter"] >= 8
    assert counts["mart_patient_360"] == 8
    assert "mart_clinical_survey_linkage" in counts
    # No direct ids in gold patient dim
    dim = read_delta(spark, delta_table_path(cfg.local_delta_root, "gold", "dim_patient"))
    assert "patient_id" not in dim.columns
    assert "family_name" not in dim.columns
