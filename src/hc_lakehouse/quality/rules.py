"""Data-quality rule definitions loaded from ``config/quality/*.yml``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml

from hc_lakehouse.utils.config import CONF_ROOT
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)

Severity = Literal["info", "warn", "error"]
RuleType = Literal[
    "not_null",
    "unique",
    "allowed_values",
    "between",
    "regex",
    "expression",
    "row_count_min",
]


@dataclass(frozen=True)
class QualityRule:
    id: str
    category: str
    severity: Severity
    owner: str
    type: RuleType
    threshold: float
    description: str = ""
    column: str | None = None
    columns: tuple[str, ...] = ()
    values: tuple[str, ...] = ()
    min: float | None = None
    max: float | None = None
    pattern: str | None = None
    expression: str | None = None
    filter: str | None = None
    min_rows: int | None = None


@dataclass(frozen=True)
class QualityRuleset:
    table: str
    owner: str
    version: int
    rules: tuple[QualityRule, ...]

    @property
    def error_rules(self) -> tuple[QualityRule, ...]:
        return tuple(r for r in self.rules if r.severity == "error")


def _parse_rule(raw: dict[str, Any]) -> QualityRule:
    return QualityRule(
        id=str(raw["id"]),
        category=str(raw.get("category", "validity")),
        severity=cast(Severity, str(raw.get("severity", "error"))),
        owner=str(raw.get("owner", "hc_data_stewards")),
        type=cast(RuleType, str(raw["type"])),
        threshold=float(raw.get("threshold", 1.0)),
        description=str(raw.get("description", "")),
        column=raw.get("column"),
        columns=tuple(raw.get("columns", [])),
        values=tuple(str(v) for v in raw.get("values", [])),
        min=float(raw["min"]) if raw.get("min") is not None else None,
        max=float(raw["max"]) if raw.get("max") is not None else None,
        pattern=raw.get("pattern"),
        expression=raw.get("expression"),
        filter=raw.get("filter"),
        min_rows=int(raw["min_rows"]) if raw.get("min_rows") is not None else None,
    )


def load_ruleset(name: str) -> QualityRuleset:
    """Load ``config/quality/<name>.yml`` (with or without ``.yml``)."""
    stem = name.removesuffix(".yml")
    path = CONF_ROOT / "quality" / f"{stem}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Quality ruleset not found: {path}")
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    rules = tuple(_parse_rule(r) for r in raw.get("rules", []))
    rs = QualityRuleset(
        table=str(raw["table"]),
        owner=str(raw.get("owner", "hc_data_stewards")),
        version=int(raw.get("version", 1)),
        rules=rules,
    )
    logger.info(
        "ruleset_loaded",
        extra={"ruleset": stem, "table": rs.table, "rules": len(rs.rules)},
    )
    return rs


def list_rulesets() -> list[str]:
    root = CONF_ROOT / "quality"
    return sorted(p.stem for p in Path(root).glob("*.yml") if not p.name.startswith("."))
