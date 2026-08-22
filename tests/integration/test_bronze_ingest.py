"""Bronze transform and ingest tests."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspark")
pytest.importorskip("delta")

from hc_lakehouse.bronze.transform import (  # noqa: E402
    TECH_COLUMNS,
    add_technical_columns,
    anti_join_existing_hashes,
    dedupe_by_record_hash,
)
from hc_lakehouse.ingest.synthetic.generator import generate_and_write  # noqa: E402
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
    spark = get_spark(cfg, app_name="test-bronze", force_new=True)
    yield spark, cfg
    stop_spark()
    clear_config_cache()


def test_add_technical_columns(spark_local) -> None:
    spark, _ = spark_local
    df = spark.createDataFrame([("SYN-PAT-000001", "A")], "patient_id STRING, label STRING")
    out = add_technical_columns(
        df,
        source_system="synthea_sim",
        source_file="patient.csv",
        batch_id="b1",
    )
    for col in TECH_COLUMNS:
        assert col in out.columns
    assert out.filter(out._record_hash.isNotNull()).count() == 1


def test_idempotent_bronze_ingest(spark_local, tmp_path) -> None:
    spark, cfg = spark_local
    landing_root = tmp_path / "syn"
    generate_and_write(landing_root, seed=42, patient_count=3, write_sample_subset=False)

    from hc_lakehouse.bronze.ingest import ingest_landing_directory

    first = ingest_landing_directory(
        spark, landing_root / "landing", config=cfg, entities=["patient"]
    )
    second = ingest_landing_directory(
        spark, landing_root / "landing", config=cfg, entities=["patient"]
    )
    assert first["patient"] == 3
    assert second["patient"] == 0  # replay is a no-op
    path = delta_table_path(cfg.local_delta_root, "bronze", "patient_raw")
    assert read_delta(spark, path).count() == 3


def test_dedupe_and_anti_join(spark_local) -> None:
    spark, _ = spark_local
    df = spark.createDataFrame(
        [("a",), ("a",), ("b",)],
        "_record_hash STRING",
    )
    deduped = dedupe_by_record_hash(df)
    assert deduped.count() == 2
    existing = spark.createDataFrame([("a",)], "_record_hash STRING")
    fresh = anti_join_existing_hashes(deduped, existing)
    assert fresh.count() == 1
