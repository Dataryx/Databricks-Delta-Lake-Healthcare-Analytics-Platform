"""Render and optionally apply Unity Catalog grants from the access matrix."""

from __future__ import annotations

from pathlib import Path

from hc_lakehouse.governance.matrix import AccessMatrix, Grant, load_access_matrix
from hc_lakehouse.utils.config import REPO_ROOT, load_config
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)


def _expand_asset(asset: str, catalog: str) -> str:
    """Replace leading ``*.`` with catalog name for SQL generation."""
    if asset.startswith("*."):
        return f"{catalog}.{asset[2:]}"
    return asset


def grant_to_sql(grant: Grant, catalog: str) -> str:
    target = _expand_asset(grant.asset, catalog)
    # UC: GRANT privilege ON TABLE/SCHEMA/CATALOG — use TABLE for table-like, SCHEMA for schema.*
    if target.endswith(".*"):
        schema = target[: -len(".*")]
        return (
            f"-- {grant.justification}\n"
            f"GRANT {grant.privilege} ON SCHEMA {schema} TO `{grant.group}`;"
        )
    return (
        f"-- {grant.justification}\n"
        f"GRANT {grant.privilege} ON TABLE {target} TO `{grant.group}`;"
    )


def render_grants_sql(matrix: AccessMatrix, catalog: str) -> str:
    lines = [
        f"-- Access matrix v{matrix.version} for {matrix.org} / catalog={catalog}",
        f"-- Principle: {matrix.principle}",
        "-- Groups only — no direct user grants",
        "",
    ]
    for group in matrix.groups:
        lines.append(f"-- ENSURE GROUP EXISTS (SCIM): {group}")
    lines.append("")
    for grant in matrix.grants:
        lines.append(grant_to_sql(grant, catalog))
        lines.append("")
    for mask in matrix.masks:
        table = _expand_asset(mask.table, catalog)
        lines.append(f"-- MASK {mask.name}: {mask.justification}")
        lines.append(
            f"CREATE OR REPLACE FUNCTION {catalog}.ops.{mask.name}(birth_year INT)\n"
            f"RETURNS INT\n"
            f"RETURN {mask.expression};"
        )
        lines.append(
            f"-- ALTER TABLE {table} ALTER COLUMN {mask.column} SET MASK {catalog}.ops.{mask.name};"
        )
        lines.append("")
    for rf in matrix.row_filters:
        table = _expand_asset(rf.table, catalog)
        lines.append(f"-- ROW FILTER {rf.name}: {rf.justification}")
        lines.append(f"-- ALTER TABLE {table} SET ROW FILTER ({rf.function});")
        lines.append("")
    return "\n".join(lines)


def apply_grants(
    *,
    catalog: str | None = None,
    dry_run: bool = True,
    output_dir: Path | None = None,
) -> Path:
    """Generate grant SQL. Live UC apply is cloud-only; local mode writes artifacts.

    Returns path to the generated SQL file.
    """
    cfg = load_config()
    cat = catalog or cfg.catalog
    matrix = load_access_matrix()
    sql = render_grants_sql(matrix, cat)
    out = output_dir or (REPO_ROOT / "artifacts" / "governance")
    out.mkdir(parents=True, exist_ok=True)
    sql_path = out / f"grants_{cat}.sql"
    sql_path.write_text(sql, encoding="utf-8")
    logger.info("grants_sql_written", extra={"path": str(sql_path), "catalog": cat})

    if dry_run or cfg.is_local:
        logger.warning(
            "uc_grants_not_applied",
            extra={
                "detail": "Unity Catalog GRANT requires Databricks workspace; "
                "SQL artifact written for review/apply.",
                "dry_run": dry_run,
                "runtime_mode": cfg.runtime_mode,
            },
        )
        return sql_path

    # Cloud path placeholder — execute via Databricks SQL warehouse / SDK in Phase 10
    logger.warning(
        "uc_apply_deferred",
        extra={"detail": "Wire databricks-sdk statement execution in Phase 10 CD."},
    )
    return sql_path


def grants_diff_report(previous_sql: str, current_sql: str) -> list[str]:
    """Return lines added in current vs previous (simple set diff for CI)."""
    prev = {ln.strip() for ln in previous_sql.splitlines() if ln.strip().startswith("GRANT")}
    curr = {ln.strip() for ln in current_sql.splitlines() if ln.strip().startswith("GRANT")}
    return sorted(curr - prev)
