"""Integration: materialize ml.ft_* from stub Gold/Bronze tables."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspark")
pytest.importorskip("delta")

from pyspark.sql import functions as F  # noqa: E402

from hc_lakehouse.features.build import FEATURE_TABLES, build_features  # noqa: E402
from hc_lakehouse.utils.config import clear_config_cache, load_config  # noqa: E402
from hc_lakehouse.utils.io import delta_table_path, table_exists, write_delta  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


@pytest.fixture()
def spark_ml(tmp_path, monkeypatch):
    monkeypatch.setenv("HC_RUNTIME_MODE", "local")
    monkeypatch.setenv("HC_LOCAL_DELTA_ROOT", str(tmp_path / "delta"))
    monkeypatch.setenv("HC_DEID_SALT", "local-demo-pepper-not-for-production")
    clear_config_cache()
    cfg = load_config()
    spark = get_spark(cfg, app_name="test-ml-features", force_new=True)
    yield spark, cfg
    stop_spark()
    clear_config_cache()


def _seed_prereqs(spark, cfg) -> None:
    root = cfg.local_delta_root
    dim = spark.createDataFrame(
        [
            ("pk1", "F", "Asian", "Not Hispanic", "45-54", 1975, "021", False),
            ("pk2", "M", "White", "Not Hispanic", "55-64", 1965, "100", False),
        ],
        schema=(
            "patient_key STRING, sex STRING, race STRING, ethnicity STRING, "
            "age_band STRING, birth_year INT, zip3 STRING, deceased_flag BOOLEAN"
        ),
    )
    write_delta(
        dim, delta_table_path(root, "gold", "dim_patient"), mode="overwrite", enable_cdf=False
    )

    enc = (
        spark.createDataFrame(
            [
                ("e1", "pk1", "2023-01-10 08:00:00", "2023-01-12 08:00:00", "inpatient", 2.0),
                ("e2", "pk1", "2023-02-01 08:00:00", "2023-02-01 12:00:00", "emergency", 0.2),
                ("e3", "pk2", "2023-01-15 08:00:00", "2023-01-18 08:00:00", "inpatient", 3.0),
                ("e4", "pk2", "2023-03-01 08:00:00", "2023-03-01 09:00:00", "outpatient", 0.0),
            ],
            schema=(
                "encounter_key STRING, patient_key STRING, admit_ts STRING, discharge_ts STRING, "
                "care_setting_key STRING, los_days DOUBLE"
            ),
        )
        .withColumn("admit_ts", F.to_timestamp("admit_ts"))
        .withColumn("discharge_ts", F.to_timestamp("discharge_ts"))
    )
    write_delta(
        enc, delta_table_path(root, "gold", "fact_encounter"), mode="overwrite", enable_cdf=False
    )

    labs = spark.createDataFrame(
        [
            ("l1", "pk1", "e1", "4548-4", 7.2, "2023-01-11 10:00:00"),
            ("l2", "pk2", "e3", "4548-4", 6.1, "2023-01-16 10:00:00"),
        ],
        schema=(
            "lab_result_key STRING, patient_key STRING, encounter_key STRING, "
            "lab_test_key STRING, value_num DOUBLE, resulted_ts STRING"
        ),
    ).withColumn("resulted_ts", F.to_timestamp("resulted_ts"))
    write_delta(
        labs, delta_table_path(root, "gold", "fact_lab_result"), mode="overwrite", enable_cdf=False
    )

    survey = spark.createDataFrame(
        [
            ("s1", "pk1", "PHQ-9", "baseline", 12.0),
            ("s2", "pk2", "PHQ-9", "baseline", 8.0),
        ],
        schema=(
            "survey_response_key STRING, patient_key STRING, instrument_key STRING, "
            "wave STRING, total_score DOUBLE"
        ),
    )
    write_delta(
        survey,
        delta_table_path(root, "gold", "fact_survey_response"),
        mode="overwrite",
        enable_cdf=False,
    )

    bronze_pat = spark.createDataFrame(
        [("SYN-PAT-00000001",), ("SYN-PAT-00000002",)],
        schema="patient_id STRING",
    )
    # Align HMAC keys with dim patient keys for this stub: write xref-style map via known keys
    # build_features HMAC-hashes patient_id; for stub, also write conditions with those ids
    # and overwrite dim patient_key after build is not needed — comorbidity joins on HMAC.
    # Simpler: put patient_id tokens and accept comorbidity may be empty if keys diverge.
    write_delta(
        bronze_pat,
        delta_table_path(root, "bronze", "patient_raw"),
        mode="overwrite",
        enable_cdf=False,
    )
    cond = spark.createDataFrame(
        [
            ("SYN-PAT-00000001", "E11.9", "2023-01-01"),
            ("SYN-PAT-00000002", "I10", "2023-01-01"),
        ],
        schema="patient_id STRING, icd10_code STRING, onset_ts STRING",
    )
    write_delta(
        cond, delta_table_path(root, "bronze", "condition_raw"), mode="overwrite", enable_cdf=False
    )
    med = spark.createDataFrame(
        [("SYN-PAT-00000001", "2023-01-10")],
        schema="patient_id STRING, ordered_ts STRING",
    )
    write_delta(
        med, delta_table_path(root, "bronze", "medication_raw"), mode="overwrite", enable_cdf=False
    )


def test_build_features_writes_ml_tables(spark_ml) -> None:
    spark, cfg = spark_ml
    _seed_prereqs(spark, cfg)
    counts = build_features(spark, config=cfg)
    assert counts["ft_patient_demographics"] == 2
    assert counts["ft_utilization_90d"] >= 1
    for name in FEATURE_TABLES:
        path = delta_table_path(cfg.local_delta_root, "ml", name)
        assert table_exists(spark, path), name
