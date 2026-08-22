"""Ops unit tests (no Spark required for SLA/cost helpers)."""

from __future__ import annotations

from hc_lakehouse.ops.cost import monthly_cost_report_sql, write_cost_report_artifact
from hc_lakehouse.ops.run_log import load_sla_config


def test_sla_config_loads() -> None:
    sla = load_sla_config()
    assert "pipelines" in sla
    assert "gold_cohort_ml" in sla["pipelines"]


def test_cost_sql_and_artifact(tmp_path) -> None:
    sql = monthly_cost_report_sql()
    assert "system.billing.usage" in sql
    path = write_cost_report_artifact(tmp_path / "cost.sql")
    assert path.exists()
    assert "dbus" in path.read_text(encoding="utf-8")
