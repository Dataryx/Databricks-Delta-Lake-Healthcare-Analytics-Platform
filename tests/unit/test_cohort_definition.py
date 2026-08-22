"""Unit tests for cohort definitions."""

from __future__ import annotations

from hc_lakehouse.cohorts.definition import list_cohorts, load_cohort


def test_load_inpatient_cohort() -> None:
    c = load_cohort("inpatient_utilizers")
    assert c.name == "inpatient_utilizers"
    assert c.definition_hash
    assert len(c.definition_hash) == 64
    assert c.table_name == "cohort_inpatient_utilizers"
    assert "inpatient_utilizers" in list_cohorts()


def test_definition_hash_stable() -> None:
    a = load_cohort("t2dm_phq9")
    b = load_cohort("t2dm_phq9")
    assert a.definition_hash == b.definition_hash
