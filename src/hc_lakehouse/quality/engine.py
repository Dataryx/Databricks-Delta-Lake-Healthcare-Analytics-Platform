"""Reusable ``validate(df, ruleset)`` engine (DLT-parity expectations for local Spark)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from pyspark.sql import functions as F

from hc_lakehouse.quality.rules import QualityRule, QualityRuleset
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

logger = get_logger(__name__)


@dataclass(frozen=True)
class RuleResult:
    run_id: str
    table: str
    rule_id: str
    category: str
    severity: str
    owner: str
    rows_scanned: int
    rows_failed: int
    pass_rate: float
    threshold: float
    status: str  # pass | fail
    ts: datetime
    description: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "pass"


@dataclass(frozen=True)
class ValidationReport:
    run_id: str
    table: str
    results: tuple[RuleResult, ...]
    ts: datetime

    @property
    def error_failures(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.results if r.severity == "error" and not r.passed)

    @property
    def passed(self) -> bool:
        return len(self.error_failures) == 0

    def to_rows(self) -> list[dict[str, object]]:
        return [
            {
                "run_id": r.run_id,
                "table": r.table,
                "rule_id": r.rule_id,
                "category": r.category,
                "severity": r.severity,
                "owner": r.owner,
                "rows_scanned": r.rows_scanned,
                "rows_failed": r.rows_failed,
                "pass_rate": r.pass_rate,
                "threshold": r.threshold,
                "status": r.status,
                "ts": r.ts.isoformat(),
                "description": r.description,
            }
            for r in self.results
        ]


def _scoped(df: DataFrame, rule: QualityRule) -> DataFrame:
    if rule.filter:
        return df.filter(rule.filter)
    return df


def _eval_not_null(df: DataFrame, rule: QualityRule) -> tuple[int, int]:
    assert rule.column is not None
    scoped = _scoped(df, rule)
    scanned = scoped.count()
    failed = scoped.filter(F.col(rule.column).isNull()).count()
    return scanned, failed


def _eval_unique(df: DataFrame, rule: QualityRule) -> tuple[int, int]:
    cols = list(rule.columns) or ([rule.column] if rule.column else [])
    if not cols:
        raise ValueError(f"Rule {rule.id}: unique requires columns")
    scoped = _scoped(df, rule)
    scanned = scoped.count()
    distinct = scoped.select(*cols).dropDuplicates().count()
    failed = scanned - distinct
    return scanned, failed


def _eval_allowed_values(df: DataFrame, rule: QualityRule) -> tuple[int, int]:
    assert rule.column is not None
    scoped = _scoped(df, rule).filter(F.col(rule.column).isNotNull())
    scanned = scoped.count()
    failed = scoped.filter(~F.col(rule.column).isin(list(rule.values))).count()
    return scanned, failed


def _eval_between(df: DataFrame, rule: QualityRule) -> tuple[int, int]:
    assert rule.column is not None and rule.min is not None and rule.max is not None
    scoped = _scoped(df, rule).filter(F.col(rule.column).isNotNull())
    scanned = scoped.count()
    failed = scoped.filter(
        (F.col(rule.column) < F.lit(rule.min)) | (F.col(rule.column) > F.lit(rule.max))
    ).count()
    return scanned, failed


def _eval_regex(df: DataFrame, rule: QualityRule) -> tuple[int, int]:
    assert rule.column is not None and rule.pattern is not None
    scoped = _scoped(df, rule).filter(F.col(rule.column).isNotNull())
    scanned = scoped.count()
    failed = scoped.filter(~F.col(rule.column).rlike(rule.pattern)).count()
    return scanned, failed


def _eval_expression(df: DataFrame, rule: QualityRule) -> tuple[int, int]:
    assert rule.expression is not None
    scoped = _scoped(df, rule)
    scanned = scoped.count()
    failed = scoped.filter(f"NOT ({rule.expression})").count()
    return scanned, failed


def _eval_row_count_min(df: DataFrame, rule: QualityRule) -> tuple[int, int]:
    assert rule.min_rows is not None
    scanned = df.count()
    failed = 0 if scanned >= rule.min_rows else 1
    return scanned, failed


_EVALUATORS = {
    "not_null": _eval_not_null,
    "unique": _eval_unique,
    "allowed_values": _eval_allowed_values,
    "between": _eval_between,
    "regex": _eval_regex,
    "expression": _eval_expression,
    "row_count_min": _eval_row_count_min,
}


def evaluate_rule(
    df: DataFrame,
    rule: QualityRule,
    *,
    table: str,
    run_id: str,
    ts: datetime | None = None,
) -> RuleResult:
    """Evaluate one rule; ``status=fail`` when pass_rate < threshold (fail closed for gates)."""
    evaluator = _EVALUATORS.get(rule.type)
    if evaluator is None:
        raise ValueError(f"Unsupported rule type: {rule.type}")
    scanned, failed = evaluator(df, rule)
    pass_rate = 1.0 if scanned == 0 else (scanned - failed) / scanned
    # Empty table: completeness/uniqueness rules pass vacuously except row_count_min
    if scanned == 0 and rule.type != "row_count_min":
        pass_rate = 1.0
        failed = 0
    status = "pass" if pass_rate >= rule.threshold else "fail"
    when = ts or datetime.now(timezone.utc)
    result = RuleResult(
        run_id=run_id,
        table=table,
        rule_id=rule.id,
        category=rule.category,
        severity=rule.severity,
        owner=rule.owner,
        rows_scanned=scanned,
        rows_failed=failed,
        pass_rate=round(pass_rate, 6),
        threshold=rule.threshold,
        status=status,
        ts=when,
        description=rule.description,
    )
    logger.info(
        "dq_rule_evaluated",
        extra={
            "rule_id": rule.id,
            "status": status,
            "pass_rate": result.pass_rate,
            "severity": rule.severity,
        },
    )
    return result


def validate(
    df: DataFrame,
    ruleset: QualityRuleset,
    *,
    run_id: str | None = None,
) -> ValidationReport:
    """Run all rules in ``ruleset`` against ``df`` and return a report.

    Does not raise on failure — callers use ``assert_promotable`` / ``gate_promotion``.
    """
    rid = run_id or f"dq-{uuid4().hex[:12]}"
    ts = datetime.now(timezone.utc)
    results = tuple(
        evaluate_rule(df, rule, table=ruleset.table, run_id=rid, ts=ts) for rule in ruleset.rules
    )
    report = ValidationReport(run_id=rid, table=ruleset.table, results=results, ts=ts)
    logger.info(
        "dq_validation_complete",
        extra={
            "table": ruleset.table,
            "run_id": rid,
            "rules": len(results),
            "error_failures": len(report.error_failures),
            "passed": report.passed,
        },
    )
    return report
