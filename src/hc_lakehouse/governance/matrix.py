"""Load and validate the access matrix from ``config/governance/access_matrix.yml``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from hc_lakehouse.utils.config import CONF_ROOT
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Grant:
    group: str
    asset: str
    privilege: str
    justification: str


@dataclass(frozen=True)
class MaskSpec:
    name: str
    table: str
    column: str
    expression: str
    justification: str


@dataclass(frozen=True)
class RowFilterSpec:
    name: str
    table: str
    function: str
    justification: str


@dataclass(frozen=True)
class AccessMatrix:
    version: int
    org: str
    principle: str
    groups: tuple[str, ...]
    grants: tuple[Grant, ...]
    masks: tuple[MaskSpec, ...]
    row_filters: tuple[RowFilterSpec, ...]
    deny_defaults: tuple[dict[str, Any], ...]
    tags: dict[str, Any]
    raw: dict[str, Any]


def load_access_matrix(path: Path | None = None) -> AccessMatrix:
    matrix_path = path or (CONF_ROOT / "governance" / "access_matrix.yml")
    with matrix_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    groups_raw = raw.get("groups", [])
    group_ids = tuple(g["id"] if isinstance(g, dict) else str(g) for g in groups_raw)
    grants = tuple(
        Grant(
            group=g["group"],
            asset=g["asset"],
            privilege=g["privilege"],
            justification=str(g.get("justification", "")),
        )
        for g in raw.get("grants", [])
    )
    # Fail closed: never allow account users or bare user principals
    for g in grants:
        if g.group.lower() in {"account users", "users", "all users"}:
            raise ValueError(f"Forbidden principal in access matrix: {g.group}")
        if "@" in g.group:
            raise ValueError(f"Direct user grants are forbidden: {g.group}")

    masks = tuple(
        MaskSpec(
            name=m["name"],
            table=m["table"],
            column=m["column"],
            expression=str(m["expression"]).strip(),
            justification=str(m.get("justification", "")),
        )
        for m in raw.get("masks", [])
    )
    row_filters = tuple(
        RowFilterSpec(
            name=r["name"],
            table=r["table"],
            function=str(r["function"]).strip(),
            justification=str(r.get("justification", "")),
        )
        for r in raw.get("row_filters", [])
    )
    matrix = AccessMatrix(
        version=int(raw.get("version", 1)),
        org=str(raw.get("org", "INDHC")),
        principle=str(raw.get("principle", "least_privilege")),
        groups=group_ids,
        grants=grants,
        masks=masks,
        row_filters=row_filters,
        deny_defaults=tuple(raw.get("deny_defaults", [])),
        tags=raw.get("tags") or {},
        raw=raw,
    )
    logger.info(
        "access_matrix_loaded",
        extra={
            "groups": len(matrix.groups),
            "grants": len(matrix.grants),
            "masks": len(matrix.masks),
        },
    )
    return matrix
