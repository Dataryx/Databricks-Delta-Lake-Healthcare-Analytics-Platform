"""Governance unit tests."""

from __future__ import annotations

import pytest

from hc_lakehouse.governance.grants import grants_diff_report, render_grants_sql
from hc_lakehouse.governance.lineage import render_mermaid
from hc_lakehouse.governance.matrix import load_access_matrix


def test_access_matrix_groups_only() -> None:
    m = load_access_matrix()
    assert "hc_breakglass_reid" in m.groups
    assert m.grants
    assert all("@" not in g.group for g in m.grants)
    assert all(g.group.lower() != "account users" for g in m.grants)


def test_restricted_only_breakglass() -> None:
    m = load_access_matrix()
    restricted = [g for g in m.grants if "restricted" in g.asset]
    assert restricted
    assert all(g.group == "hc_breakglass_reid" for g in restricted)


def test_render_grants_sql_contains_grant() -> None:
    m = load_access_matrix()
    sql = render_grants_sql(m, "hc_dev")
    assert "GRANT" in sql
    assert "hc_researchers_deid" in sql
    assert "TO `" in sql


def test_grants_diff() -> None:
    added = grants_diff_report(
        "GRANT SELECT ON TABLE a TO `g`;",
        "GRANT SELECT ON TABLE a TO `g`;\nGRANT SELECT ON TABLE b TO `g`;",
    )
    assert any("TABLE b" in line for line in added)


def test_mermaid_lineage() -> None:
    text = render_mermaid()
    assert "flowchart LR" in text
    assert "bronze.patient_raw" in text
    assert "gold.mart_patient_360" in text


def test_forbidden_user_grant(tmp_path) -> None:
    bad = tmp_path / "bad.yml"
    user = "@".join(["someone", "example.com"])
    bad.write_text(
        "version: 1\norg: X\nprinciple: p\ngroups: [g]\n"
        f"grants:\n  - group: {user}\n    asset: '*.gold.*'\n"
        "    privilege: SELECT\n    justification: no\n"
        "masks: []\nrow_filters: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Direct user"):
        load_access_matrix(bad)
