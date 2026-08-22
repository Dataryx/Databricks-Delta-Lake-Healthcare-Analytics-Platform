"""Schema contract loader and drift checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pyspark.sql import DataFrame
from pyspark.sql.types import (
    BooleanType,
    DataType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from hc_lakehouse.utils.config import CONF_ROOT
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)

_TYPE_MAP: dict[str, DataType] = {
    "string": StringType(),
    "integer": IntegerType(),
    "long": LongType(),
    "double": DoubleType(),
    "boolean": BooleanType(),
    "timestamp": TimestampType(),
}


@dataclass(frozen=True)
class ColumnContract:
    name: str
    type_name: str
    nullable: bool
    comment: str | None = None


@dataclass(frozen=True)
class SchemaContract:
    entity: str
    layer: str
    version: int
    columns: tuple[ColumnContract, ...]
    primary_key: tuple[str, ...]
    grain: str = ""
    checks: tuple[dict[str, str], ...] = ()

    def struct_type(self) -> StructType:
        fields = [StructField(c.name, _TYPE_MAP[c.type_name], c.nullable) for c in self.columns]
        return StructType(fields)

    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


def load_contract(entity: str) -> SchemaContract:
    """Load ``config/contracts/<entity>.yml``."""
    path = CONF_ROOT / "contracts" / f"{entity}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Schema contract not found: {path}")
    with path.open(encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle)
    cols = tuple(
        ColumnContract(
            name=c["name"],
            type_name=c["type"],
            nullable=bool(c.get("nullable", True)),
            comment=c.get("comment"),
        )
        for c in raw["columns"]
    )
    return SchemaContract(
        entity=raw["entity"],
        layer=raw.get("layer", "silver"),
        version=int(raw.get("version", 1)),
        columns=cols,
        primary_key=tuple(raw.get("primary_key", [])),
        grain=raw.get("grain", ""),
        checks=tuple(raw.get("checks", [])),
    )


def assert_contract(df: DataFrame, contract: SchemaContract) -> None:
    """Fail closed if required columns are missing (types coerced later)."""
    missing = [c for c in contract.column_names() if c not in df.columns]
    if missing:
        raise ValueError(
            f"Contract drift for {contract.layer}.{contract.entity}: missing {missing}"
        )
    logger.info(
        "contract_ok",
        extra={
            "entity": contract.entity,
            "version": contract.version,
            "cols": len(contract.columns),
        },
    )


def list_contract_entities() -> list[str]:
    root = CONF_ROOT / "contracts"
    return sorted(
        p.stem
        for p in Path(root).glob("*.yml")
        if not p.name.startswith(".") and p.stem != "gitkeep"
    )
