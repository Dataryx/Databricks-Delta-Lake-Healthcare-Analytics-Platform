"""Unit tests for DQ rules loading and gate logic."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hc_lakehouse.quality.engine import RuleResult, ValidationReport
from hc_lakehouse.quality.gates import PromotionBlockedError, assert_promotable, gate_promotion
from hc_lakehouse.quality.rules import list_rulesets, load_ruleset


def test_load_patient_ruleset() -> None:
    rs = load_ruleset("silver_patient")
    assert rs.table == "silver.patient"
    assert any(r.id == "pat_pk_not_null" for r in rs.rules)
    assert rs.error_rules
    assert "silver_patient" in list_rulesets()


def test_promotion_blocked_on_error() -> None:
    ts = datetime.now(timezone.utc)
    fail = RuleResult(
        run_id="r1",
        table="silver.patient",
        rule_id="pat_pk_not_null",
        category="completeness",
        severity="error",
        owner="steward",
        rows_scanned=10,
        rows_failed=2,
        pass_rate=0.8,
        threshold=1.0,
        status="fail",
        ts=ts,
    )
    warn = RuleResult(
        run_id="r1",
        table="silver.patient",
        rule_id="pat_sex_enum",
        category="validity",
        severity="warn",
        owner="steward",
        rows_scanned=10,
        rows_failed=1,
        pass_rate=0.9,
        threshold=0.99,
        status="fail",
        ts=ts,
    )
    report = ValidationReport(run_id="r1", table="silver.patient", results=(fail, warn), ts=ts)
    assert not report.passed
    with pytest.raises(PromotionBlockedError):
        assert_promotable(report)
    with pytest.raises(PromotionBlockedError):
        gate_promotion(report)


def test_promotion_allows_warn_only() -> None:
    ts = datetime.now(timezone.utc)
    warn = RuleResult(
        run_id="r2",
        table="silver.encounter",
        rule_id="enc_care_setting_enum",
        category="validity",
        severity="warn",
        owner="steward",
        rows_scanned=100,
        rows_failed=2,
        pass_rate=0.98,
        threshold=0.95,
        status="pass",
        ts=ts,
    )
    report = ValidationReport(run_id="r2", table="silver.encounter", results=(warn,), ts=ts)
    assert report.passed
    assert_promotable(report)
