"""Research run manifests and dataframe checksums."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from hc_lakehouse.utils.config import REPO_ROOT, PlatformConfig, load_config
from hc_lakehouse.utils.io import delta_table_path, table_exists, write_delta
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

logger = get_logger(__name__)
WriteMode = Literal["append", "overwrite"]


@dataclass
class RunManifest:
    """Provenance for a published research artifact."""

    artifact: str
    artifact_kind: str
    created_at: str
    creating_principal: str
    git_commit_sha: str
    definition_hash: str | None
    scoring_algorithm_version: str | None
    runtime_version: str
    input_tables: dict[str, int]
    output_checksum: str
    irb_protocol_id: str | None = None
    row_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunManifest:
        return cls(
            artifact=data["artifact"],
            artifact_kind=data["artifact_kind"],
            created_at=data["created_at"],
            creating_principal=data["creating_principal"],
            git_commit_sha=data["git_commit_sha"],
            definition_hash=data.get("definition_hash"),
            scoring_algorithm_version=data.get("scoring_algorithm_version"),
            runtime_version=data["runtime_version"],
            input_tables={k: int(v) for k, v in data["input_tables"].items()},
            output_checksum=data["output_checksum"],
            irb_protocol_id=data.get("irb_protocol_id"),
            row_count=int(data.get("row_count", 0)),
            extra=data.get("extra") or {},
        )


def delta_version(spark: SparkSession, path: str) -> int:
    """Return current Delta table version (0 if empty/new)."""
    if not table_exists(spark, path):
        return -1
    try:
        from delta.tables import DeltaTable

        hist = DeltaTable.forPath(spark, path).history(1).select("version").collect()
        if not hist:
            return 0
        return int(hist[0]["version"])
    except Exception:  # noqa: BLE001
        logger.warning("delta_version_unavailable", extra={"path": path})
        return 0


def checksum_dataframe(df: DataFrame) -> str:
    """Stable SHA-256 over sorted row payloads (order-independent)."""
    from pyspark.sql import functions as F

    cols = sorted(df.columns)
    # Collect sorted hashes of each row then hash the concatenation
    row_hashes = (
        df.select(
            F.sha2(
                F.concat_ws(
                    "\u241f",
                    *[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in cols],
                ),
                256,
            ).alias("rh")
        )
        .orderBy("rh")
        .collect()
    )
    material = "|".join(r["rh"] for r in row_hashes)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def write_manifest(
    spark: SparkSession,
    manifest: RunManifest,
    *,
    config: PlatformConfig | None = None,
    emit_sidecar: bool = True,
) -> Path:
    """Persist to ``ops.run_manifest`` and optional ``RESEARCH_MANIFEST.json`` sidecar."""
    cfg = config or load_config()
    path = delta_table_path(cfg.local_delta_root, "ops", "run_manifest")
    row = spark.createDataFrame(
        [
            (
                manifest.artifact,
                manifest.artifact_kind,
                manifest.created_at,
                manifest.creating_principal,
                manifest.git_commit_sha,
                manifest.definition_hash,
                manifest.scoring_algorithm_version,
                manifest.runtime_version,
                json.dumps(manifest.input_tables, sort_keys=True),
                manifest.output_checksum,
                manifest.irb_protocol_id,
                manifest.row_count,
                json.dumps(manifest.extra, sort_keys=True),
            )
        ],
        schema=(
            "artifact STRING, artifact_kind STRING, created_at STRING, "
            "creating_principal STRING, git_commit_sha STRING, definition_hash STRING, "
            "scoring_algorithm_version STRING, runtime_version STRING, "
            "input_tables_json STRING, output_checksum STRING, irb_protocol_id STRING, "
            "row_count LONG, extra_json STRING"
        ),
    )
    mode: WriteMode = "append" if table_exists(spark, path) else "overwrite"
    write_delta(row, path, mode=mode, enable_cdf=False)

    sidecar = REPO_ROOT / "artifacts" / manifest.artifact / "RESEARCH_MANIFEST.json"
    if emit_sidecar:
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
        logger.info("manifest_sidecar_written", extra={"path": str(sidecar)})
    return sidecar


def load_manifest(path: Path) -> RunManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return RunManifest.from_dict(data)
