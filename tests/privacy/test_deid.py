"""Privacy / de-identification unit and Spark tests."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from hc_lakehouse.privacy.hashing import hmac_sha256_hex
from hc_lakehouse.privacy.safe_harbor import patient_day_offset


def test_hmac_deterministic() -> None:
    a = hmac_sha256_hex("SYN-PAT-000001", "pepper-a")
    b = hmac_sha256_hex("SYN-PAT-000001", "pepper-a")
    c = hmac_sha256_hex("SYN-PAT-000001", "pepper-b")
    assert a == b
    assert a != c
    assert len(a) == 64


def test_date_shift_preserves_intervals() -> None:
    pepper = "test-pepper"
    sk = "abc123"
    off = patient_day_offset(sk, pepper, max_days=365)
    assert -365 <= off <= 365
    d1 = date(2020, 1, 15)
    d2 = date(2020, 3, 15)
    assert (d2 + timedelta(days=off)) - (d1 + timedelta(days=off)) == (d2 - d1)


@pytest.mark.privacy
def test_silver_has_no_direct_ids(spark_local_privacy) -> None:
    spark, cfg, root = spark_local_privacy
    from hc_lakehouse.bronze.ingest import ingest_landing_directory
    from hc_lakehouse.ingest.synthetic.generator import generate_and_write
    from hc_lakehouse.privacy.safe_harbor import LOW_POP_ZIP3
    from hc_lakehouse.silver.transform import FORBIDDEN_SILVER_COLUMNS, build_silver_core
    from hc_lakehouse.utils.io import delta_table_path, read_delta

    generate_and_write(root, seed=42, patient_count=5, write_sample_subset=False)
    ingest_landing_directory(
        spark,
        root / "landing",
        config=cfg,
        entities=["patient", "encounter", "lab_result"],
    )
    build_silver_core(spark, config=cfg)
    patients = read_delta(spark, delta_table_path(cfg.local_delta_root, "silver", "patient"))
    for col in FORBIDDEN_SILVER_COLUMNS:
        assert col not in patients.columns
    # patient_sk is 64-char hex HMAC, not SYN-PAT
    sk = patients.select("patient_sk").first()[0]
    assert len(sk) == 64
    assert not str(sk).startswith("SYN-")
    xref = read_delta(spark, delta_table_path(cfg.local_delta_root, "restricted", "patient_xref"))
    assert "source_patient_id" in xref.columns
    assert xref.count() == 5
    # zip3 never a low-pop code when present
    zips = [r.zip3 for r in patients.select("zip3").collect() if r.zip3]
    assert all(z not in LOW_POP_ZIP3 for z in zips)
