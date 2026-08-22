"""Reproducibility and cohort integration tests."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspark")
pytest.importorskip("delta")

from hc_lakehouse.bronze.ingest import ingest_landing_directory  # noqa: E402
from hc_lakehouse.cohorts.compiler import build_cohort  # noqa: E402
from hc_lakehouse.gold.build import build_gold  # noqa: E402
from hc_lakehouse.ingest.synthetic.generator import generate_and_write  # noqa: E402
from hc_lakehouse.reproducibility.manifest import load_manifest  # noqa: E402
from hc_lakehouse.reproducibility.reproduce import reproduce_cohort_from_manifest  # noqa: E402
from hc_lakehouse.silver.transform import build_silver_core  # noqa: E402
from hc_lakehouse.utils.config import clear_config_cache, load_config  # noqa: E402
from hc_lakehouse.utils.io import delta_table_path, read_delta  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


@pytest.fixture()
def spark_repro(tmp_path, monkeypatch):
    monkeypatch.setenv("HC_RUNTIME_MODE", "local")
    monkeypatch.setenv("HC_LOCAL_DELTA_ROOT", str(tmp_path / "delta"))
    monkeypatch.setenv("HC_DEID_SALT", "local-demo-pepper-not-for-production")
    clear_config_cache()
    cfg = load_config()
    spark = get_spark(cfg, app_name="test-repro", force_new=True)
    yield spark, cfg, tmp_path
    stop_spark()
    clear_config_cache()


@pytest.mark.reproducibility
def test_cohort_build_and_reproduce(spark_repro, monkeypatch) -> None:
    spark, cfg, tmp_path = spark_repro
    # Sidecar under tmp artifacts
    monkeypatch.setattr(
        "hc_lakehouse.reproducibility.manifest.REPO_ROOT",
        tmp_path,
    )
    root = tmp_path / "syn"
    generate_and_write(root, seed=42, patient_count=12, write_sample_subset=False)
    ingest_landing_directory(spark, root / "landing", config=cfg)
    build_silver_core(spark, config=cfg)
    build_gold(spark, config=cfg, enforce_dq_gate=True)

    manifest = build_cohort(spark, "inpatient_utilizers", config=cfg)
    assert manifest.row_count >= 1
    assert manifest.output_checksum

    cohort = read_delta(
        spark, delta_table_path(cfg.local_delta_root, "gold", "cohort_inpatient_utilizers")
    )
    assert cohort.count() == manifest.row_count
    assert "patient_id" not in cohort.columns

    sidecar = tmp_path / "artifacts" / "cohort_inpatient_utilizers" / "RESEARCH_MANIFEST.json"
    assert sidecar.exists()
    loaded = load_manifest(sidecar)
    assert loaded.output_checksum == manifest.output_checksum

    rc = reproduce_cohort_from_manifest(sidecar)
    assert rc == 0
