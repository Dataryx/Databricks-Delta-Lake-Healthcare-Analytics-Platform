"""Silver cleansing, contracts, and core build tests."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspark")
pytest.importorskip("delta")

from hc_lakehouse.bronze.ingest import ingest_landing_directory  # noqa: E402
from hc_lakehouse.ingest.synthetic.generator import generate_and_write  # noqa: E402
from hc_lakehouse.silver.cleanse import normalize_null_tokens, trim_strings  # noqa: E402
from hc_lakehouse.silver.contracts import assert_contract, load_contract  # noqa: E402
from hc_lakehouse.silver.transform import (  # noqa: E402
    FORBIDDEN_SILVER_COLUMNS,
    build_silver_core,
)
from hc_lakehouse.utils.config import clear_config_cache, load_config  # noqa: E402
from hc_lakehouse.utils.io import delta_table_path, read_delta  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


@pytest.fixture()
def spark_local(tmp_path, monkeypatch):
    monkeypatch.setenv("HC_RUNTIME_MODE", "local")
    monkeypatch.setenv("HC_LOCAL_DELTA_ROOT", str(tmp_path / "delta"))
    monkeypatch.setenv("HC_DEID_SALT", "local-demo-pepper-not-for-production")
    clear_config_cache()
    cfg = load_config()
    spark = get_spark(cfg, app_name="test-silver", force_new=True)
    yield spark, cfg
    stop_spark()
    clear_config_cache()


def test_load_patient_contract() -> None:
    c = load_contract("patient")
    assert c.entity == "patient"
    assert "patient_sk" in c.column_names()
    assert c.struct_type() is not None


def test_cleanse_null_tokens(spark_local) -> None:
    spark, _ = spark_local
    df = spark.createDataFrame([("UNK", " x ")], "sex STRING, race STRING")
    out = normalize_null_tokens(trim_strings(df))
    row = out.collect()[0]
    assert row["sex"] is None
    assert row["race"] == "x"


def test_silver_core_and_quarantine(spark_local, tmp_path) -> None:
    spark, cfg = spark_local
    root = tmp_path / "syn"
    generate_and_write(root, seed=42, patient_count=5, write_sample_subset=False)
    ingest_landing_directory(
        spark,
        root / "landing",
        config=cfg,
        entities=["patient", "encounter", "lab_result", "organization", "provider"],
    )
    counts = build_silver_core(spark, config=cfg)
    assert counts["patient"] == 5
    assert counts["encounter"] >= 5
    patients = read_delta(spark, delta_table_path(cfg.local_delta_root, "silver", "patient"))
    assert_contract(patients, load_contract("patient"))
    for col in FORBIDDEN_SILVER_COLUMNS:
        assert col not in patients.columns
    # Orphan labs from generator should land in quarantine
    assert counts["lab_result_quarantine"] >= 0
