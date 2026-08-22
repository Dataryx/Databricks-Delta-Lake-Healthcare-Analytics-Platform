"""Cohort definition loading from ``config/cohorts/*.yml``."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from hc_lakehouse.utils.config import CONF_ROOT
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Criterion:
    type: str
    value: Any


@dataclass(frozen=True)
class CohortDefinition:
    name: str
    version: int
    irb_protocol_id: str
    description: str
    owner: str
    inclusion: tuple[Criterion, ...]
    exclusion: tuple[Criterion, ...]
    index_date_rule: str
    washout_days: int
    follow_up_days: int
    required_instruments: tuple[str, ...]
    raw: dict[str, Any]

    @property
    def definition_hash(self) -> str:
        """Stable hash of the declarative definition (canonical JSON)."""
        payload = json.dumps(self.raw, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def table_name(self) -> str:
        return f"cohort_{self.name}"


def load_cohort(name: str) -> CohortDefinition:
    stem = name.removesuffix(".yml")
    path = CONF_ROOT / "cohorts" / f"{stem}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Cohort definition not found: {path}")
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    inclusion = tuple(
        Criterion(type=c["type"], value=c.get("value")) for c in raw.get("inclusion", [])
    )
    exclusion = tuple(
        Criterion(type=c["type"], value=c.get("value")) for c in raw.get("exclusion", [])
    )
    defn = CohortDefinition(
        name=str(raw["name"]),
        version=int(raw.get("version", 1)),
        irb_protocol_id=str(raw.get("irb_protocol_id", "IRB-UNSPECIFIED")),
        description=str(raw.get("description", "")),
        owner=str(raw.get("owner", "hc_researchers_deid")),
        inclusion=inclusion,
        exclusion=exclusion,
        index_date_rule=str(raw.get("index_date_rule", "first_encounter_admit")),
        washout_days=int(raw.get("washout_days", 0)),
        follow_up_days=int(raw.get("follow_up_days", 0)),
        required_instruments=tuple(raw.get("required_instruments", [])),
        raw=raw,
    )
    logger.info(
        "cohort_loaded",
        extra={"cohort": defn.name, "hash": defn.definition_hash[:12]},
    )
    return defn


def list_cohorts() -> list[str]:
    root = CONF_ROOT / "cohorts"
    return sorted(p.stem for p in Path(root).glob("*.yml") if not p.name.startswith("."))
