"""Lineage snapshot and Mermaid diagram generation (CI-refreshable)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from pyspark.sql import Row

from hc_lakehouse.utils.config import REPO_ROOT, PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

logger = get_logger(__name__)

# Static medallion edges for local/demo; cloud enriches from UC system.access.table_lineage
LINEAGE_EDGES: tuple[tuple[str, str, str], ...] = (
    ("landing/clinical/patient.csv", "bronze.patient_raw", "ingest"),
    ("landing/clinical/encounter.csv", "bronze.encounter_raw", "ingest"),
    ("landing/clinical/lab_result.csv", "bronze.lab_result_raw", "ingest"),
    ("landing/survey/survey_score.csv", "bronze.survey_score_raw", "ingest"),
    ("bronze.patient_raw", "restricted.patient_xref", "deid_crosswalk"),
    ("bronze.patient_raw", "silver.patient", "deid_conform"),
    ("bronze.encounter_raw", "silver.encounter", "conform"),
    ("bronze.lab_result_raw", "silver.lab_result", "conform"),
    ("silver.patient", "gold.dim_patient", "publish"),
    ("silver.encounter", "gold.fact_encounter", "publish"),
    ("silver.lab_result", "gold.fact_lab_result", "publish"),
    ("gold.fact_encounter", "gold.fact_readmission", "derive"),
    ("gold.dim_patient", "gold.mart_patient_360", "mart"),
    ("gold.fact_encounter", "gold.mart_patient_360", "mart"),
    ("gold.fact_lab_result", "gold.mart_patient_360", "mart"),
    ("gold.fact_encounter", "gold.mart_utilization", "mart"),
    ("bronze.survey_score_raw", "gold.fact_survey_response", "publish"),
    ("gold.fact_survey_response", "gold.mart_prom_trajectory", "mart"),
    ("gold.mart_patient_360", "gold.mart_clinical_survey_linkage", "mart"),
    ("gold.fact_survey_response", "gold.mart_clinical_survey_linkage", "mart"),
    ("gold.fact_encounter", "gold.cohort_inpatient_utilizers", "cohort"),
    ("gold.fact_lab_result", "gold.cohort_t2dm_phq9", "cohort"),
    ("gold.fact_survey_response", "gold.cohort_t2dm_phq9", "cohort"),
)


def snapshot_lineage(
    spark: SparkSession,
    *,
    config: PlatformConfig | None = None,
) -> int:
    """Persist ``ops.lineage_snapshot`` from the medallion edge list (UC in cloud)."""
    cfg = config or load_config()
    ts = datetime.now(timezone.utc).isoformat()
    rows = [
        Row(
            source=src,
            target=tgt,
            transform=xform,
            catalog=cfg.catalog,
            captured_at=ts,
            source_system="local_medallion_graph",
        )
        for src, tgt, xform in LINEAGE_EDGES
    ]
    path = delta_table_path(cfg.local_delta_root, "ops", "lineage_snapshot")
    write_delta(spark.createDataFrame(rows), path, mode="overwrite", enable_cdf=False)
    logger.info("lineage_snapshot_written", extra={"edges": len(rows), "path": path})
    return len(rows)


def render_mermaid(edges: Iterable[tuple[str, str, str]] | None = None) -> str:
    """Render a Mermaid flowchart from lineage edges."""
    use = list(edges) if edges is not None else list(LINEAGE_EDGES)
    lines = ["```mermaid", "flowchart LR"]
    # Simplify node ids
    seen: dict[str, str] = {}

    def nid(name: str) -> str:
        if name not in seen:
            safe = name.replace("/", "_").replace(".", "_").replace("-", "_").replace("*", "x")
            seen[name] = f"n{len(seen)}_{safe[:40]}"
            lines.append(f'  {seen[name]}["{name}"]')
        return seen[name]

    for src, tgt, _xform in use:
        lines.append(f"  {nid(src)} --> {nid(tgt)}")
    lines.append("```")
    return "\n".join(lines)


def write_lineage_doc(path: Path | None = None) -> Path:
    """Write ``docs/lineage.md`` with regenerated Mermaid (CI-safe)."""
    out = path or (REPO_ROOT / "docs" / "lineage.md")
    body = (
        "# Lineage\n\n"
        "Auto-generated from `hc_lakehouse.governance.lineage.LINEAGE_EDGES`.\n"
        "CI regenerates this file so the diagram cannot go stale.\n\n"
        "Unity Catalog table/column lineage is the system of record in Azure; "
        "this graph is the local/demo snapshot mirrored into `ops.lineage_snapshot`.\n\n"
        f"{render_mermaid()}\n"
    )
    out.write_text(body, encoding="utf-8")
    logger.info("lineage_doc_written", extra={"path": str(out)})
    return out
