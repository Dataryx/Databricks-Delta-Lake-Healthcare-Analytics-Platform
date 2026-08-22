"""Break-glass and governance integration tests."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspark")
pytest.importorskip("delta")

from hc_lakehouse.governance.audit import (  # noqa: E402
    BreakGlassError,
    assert_reid_justified,
    request_reid,
    seed_access_review,
    write_access_audit_daily,
)
from hc_lakehouse.governance.grants import apply_grants  # noqa: E402
from hc_lakehouse.governance.lineage import snapshot_lineage, write_lineage_doc  # noqa: E402
from hc_lakehouse.governance.tags import materialize_tags  # noqa: E402
from hc_lakehouse.utils.config import clear_config_cache, load_config  # noqa: E402
from hc_lakehouse.utils.io import delta_table_path, read_delta  # noqa: E402
from hc_lakehouse.utils.spark_session import get_spark, stop_spark  # noqa: E402


@pytest.fixture()
def spark_gov(tmp_path, monkeypatch):
    monkeypatch.setenv("HC_RUNTIME_MODE", "local")
    monkeypatch.setenv("HC_LOCAL_DELTA_ROOT", str(tmp_path / "delta"))
    monkeypatch.setenv("HC_DEID_SALT", "local-demo-pepper-not-for-production")
    clear_config_cache()
    cfg = load_config()
    spark = get_spark(cfg, app_name="test-gov", force_new=True)
    yield spark, cfg, tmp_path
    stop_spark()
    clear_config_cache()


def test_apply_grants_writes_sql(tmp_path) -> None:
    path = apply_grants(catalog="hc_dev", dry_run=True, output_dir=tmp_path)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "GRANT" in text


def test_governance_ops_tables(spark_gov, tmp_path) -> None:
    spark, cfg, _ = spark_gov
    assert materialize_tags(spark, config=cfg) > 0
    assert snapshot_lineage(spark, config=cfg) > 0
    assert write_access_audit_daily(spark, config=cfg) >= 1
    assert seed_access_review(spark, config=cfg) > 0
    doc = write_lineage_doc(tmp_path / "lineage.md")
    assert "mermaid" in doc.read_text(encoding="utf-8")

    rid = request_reid(
        spark,
        principal="hc_breakglass_reid",
        patient_sk="a" * 64,
        justification="Court order reference SYN-CASE-001 for limited disclosure",
        privacy_officer="privacy.officer",
        config=cfg,
    )
    assert_reid_justified(spark, rid, config=cfg)
    with pytest.raises(BreakGlassError):
        assert_reid_justified(spark, "missing-id", config=cfg)

    log = read_delta(spark, delta_table_path(cfg.local_delta_root, "ops", "reid_request_log"))
    assert log.filter(f"request_id = '{rid}'").count() == 1
