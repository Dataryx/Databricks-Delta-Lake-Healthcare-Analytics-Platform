"""Spark + Delta integration smoke (requires Java + PySpark)."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspark")
pytest.importorskip("delta")


@pytest.mark.integration
def test_local_delta_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("HC_RUNTIME_MODE", "local")
    monkeypatch.setenv("HC_LOCAL_DELTA_ROOT", str(tmp_path / "delta"))
    monkeypatch.setenv("HC_DEID_SALT", "local-demo-pepper-not-for-production")

    from hc_lakehouse.utils.config import clear_config_cache, load_config
    from hc_lakehouse.utils.io import delta_table_path, read_delta, write_delta
    from hc_lakehouse.utils.spark_session import get_spark, stop_spark

    clear_config_cache()
    config = load_config()
    spark = get_spark(config, app_name="test-delta", force_new=True)
    try:
        df = spark.createDataFrame([(1, "a")], "id INT, label STRING")
        path = delta_table_path(config.local_delta_root, "ops", "test_smoke")
        write_delta(df, path, mode="overwrite")
        assert read_delta(spark, path).count() == 1
    finally:
        stop_spark()
        clear_config_cache()
