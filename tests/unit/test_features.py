"""Feature table unit tests with Spark (lightweight schemas)."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspark")
pytest.importorskip("delta")

from pyspark.sql import functions as F  # noqa: E402

from hc_lakehouse.features.tables import (  # noqa: E402
    build_ft_patient_demographics,
    build_ft_utilization_90d,
)
from hc_lakehouse.utils.config import clear_config_cache, load_config  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


@pytest.fixture()
def spark_ft(tmp_path, monkeypatch):
    monkeypatch.setenv("HC_RUNTIME_MODE", "local")
    monkeypatch.setenv("HC_LOCAL_DELTA_ROOT", str(tmp_path / "delta"))
    monkeypatch.setenv("HC_DEID_SALT", "local-demo-pepper-not-for-production")
    clear_config_cache()
    cfg = load_config()
    spark = get_spark(cfg, app_name="test-features", force_new=True)
    yield spark
    stop_spark()
    clear_config_cache()


def test_demographics_and_utilization(spark_ft) -> None:
    spark = spark_ft
    dim = spark.createDataFrame(
        [("pk1", "F", "Asian", "Not Hispanic", "45-54", 1975, "021", False)],
        schema=(
            "patient_key STRING, sex STRING, race STRING, ethnicity STRING, "
            "age_band STRING, birth_year INT, zip3 STRING, deceased_flag BOOLEAN"
        ),
    )
    demo = build_ft_patient_demographics(dim)
    assert demo.count() == 1
    assert "feature_as_of" in demo.columns

    enc = spark.createDataFrame(
        [
            ("pk1", "2023-01-10 08:00:00", "inpatient", 3.0),
            ("pk1", "2023-02-01 08:00:00", "emergency", 1.0),
            ("pk1", "2023-03-15 08:00:00", "inpatient", 4.0),
        ],
        schema="patient_key STRING, admit_ts STRING, care_setting_key STRING, los_days DOUBLE",
    ).withColumn("admit_ts", F.to_timestamp("admit_ts"))
    util = build_ft_utilization_90d(enc)
    assert util.count() >= 1
    assert "encounters_90d" in util.columns
