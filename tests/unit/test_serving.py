"""Unit tests for serving dashboard SQL registry."""

from __future__ import annotations

from hc_lakehouse.serving import list_dashboard_sql


def test_dashboard_sql_present() -> None:
    paths = list_dashboard_sql()
    assert len(paths) == 4
    for p in paths:
        text = p.read_text(encoding="utf-8")
        assert "SELECT" in text.upper()
