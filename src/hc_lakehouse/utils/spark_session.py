"""Spark session factory with local Delta Lake and graceful cloud degradation."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any, cast

from hc_lakehouse.utils.config import PlatformConfig, load_config
from hc_lakehouse.utils.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

logger = get_logger(__name__)

_SPARK: SparkSession | None = None


def _configure_delta_extensions(builder: Any) -> Any:
    """Attach delta-spark extensions when the package is available."""
    try:
        from delta import configure_spark_with_delta_pip
    except ImportError:
        logger.warning(
            "delta_spark_unavailable",
            extra={
                "detail": "Install delta-spark for local Delta tables. "
                "Proceeding without Delta extensions (cloud-only features degraded)."
            },
        )
        return builder
    return configure_spark_with_delta_pip(builder)


def _ensure_pyspark_python() -> None:
    """Point Spark workers at this interpreter (avoids Windows Store python stub)."""
    exe = sys.executable
    os.environ.setdefault("PYSPARK_PYTHON", exe)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", exe)


def _require_compatible_java() -> None:
    """Warn when JAVA_HOME looks like JDK 21+ (Spark 3.5 needs 11/17)."""
    java_home = os.environ.get("JAVA_HOME", "")
    if any(token in java_home for token in ("jdk-21", "jdk-22", "jdk-23", "jdk-24", "jdk-25")):
        logger.warning(
            "java_version_may_be_incompatible",
            extra={
                "JAVA_HOME": java_home,
                "detail": "PySpark 3.5 expects JDK 11 or 17. Set JAVA_HOME to Temurin 17.",
            },
        )


def _ensure_windows_hadoop_home() -> None:
    """Set HADOOP_HOME to repo tools/hadoop when winutils is present (Windows)."""
    if os.name != "nt":
        return
    from hc_lakehouse.utils.config import REPO_ROOT

    candidate = REPO_ROOT / "tools" / "hadoop"
    bin_dir = candidate / "bin"
    winutils = bin_dir / "winutils.exe"
    if not winutils.exists():
        if not os.environ.get("HADOOP_HOME"):
            logger.warning(
                "winutils_missing",
                extra={
                    "detail": "Run `python scripts/setup_windows_hadoop.py` once on Windows "
                    "before local Spark/Delta demos."
                },
            )
        return

    os.environ.setdefault("HADOOP_HOME", str(candidate))
    # NativeIO loads hadoop.dll from PATH on Windows
    path = os.environ.get("PATH", "")
    bin_str = str(bin_dir)
    if bin_str.lower() not in path.lower():
        os.environ["PATH"] = bin_str + os.pathsep + path
    logger.info("hadoop_home_configured", extra={"HADOOP_HOME": os.environ["HADOOP_HOME"]})


def get_spark(
    config: PlatformConfig | None = None,
    *,
    app_name: str = "hc-lakehouse",
    force_new: bool = False,
) -> SparkSession:
    """Create or reuse a SparkSession suitable for local demo or Databricks.

    Local mode enables Delta Lake extensions, sets a warehouse under
    ``HC_LOCAL_DELTA_ROOT``, and uses a single-worker local master.

    Databricks Connect is attempted only when ``runtime_mode=databricks``; failure
    logs a clear message and falls back to local Spark rather than crashing.
    """
    global _SPARK
    from pyspark.sql import SparkSession

    if _SPARK is not None and not force_new:
        return _SPARK

    cfg = config or load_config()
    warehouse = str(cfg.local_path("spark-warehouse"))
    os.makedirs(warehouse, exist_ok=True)
    os.makedirs(cfg.local_delta_root, exist_ok=True)
    _require_compatible_java()
    _ensure_windows_hadoop_home()
    _ensure_pyspark_python()

    if cfg.runtime_mode.lower() == "databricks":
        spark = _try_databricks_connect(app_name)
        if spark is not None:
            _SPARK = spark
            return spark
        logger.warning(
            "databricks_connect_fallback",
            extra={"detail": "Falling back to local PySpark + delta-spark."},
        )

    builder: Any = (
        SparkSession.builder.appName(app_name)
        .master(os.environ.get("HC_SPARK_MASTER", "local[*]"))
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.warehouse.dir", warehouse)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.driver.memory", os.environ.get("HC_SPARK_DRIVER_MEMORY", "2g"))
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
        .config("spark.databricks.delta.properties.defaults.enableChangeDataFeed", "true")
    )
    builder = _configure_delta_extensions(builder)
    spark = cast("SparkSession", builder.getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    logger.info(
        "spark_session_started",
        extra={
            "runtime_mode": cfg.runtime_mode,
            "warehouse": warehouse,
            "spark_version": spark.version,
        },
    )
    _SPARK = spark
    return spark


def _try_databricks_connect(app_name: str) -> SparkSession | None:
    """Attempt Databricks Connect; return None if unavailable."""
    try:
        from databricks.connect import DatabricksSession
    except ImportError:
        logger.warning(
            "databricks_connect_not_installed",
            extra={"detail": "pip install hc-lakehouse[databricks] to enable cloud connect."},
        )
        return None
    try:
        spark = DatabricksSession.builder.appName(app_name).getOrCreate()
        logger.info("databricks_connect_session_started")
        return cast("SparkSession", spark)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        logger.warning(
            "databricks_connect_failed",
            extra={"error": str(exc)},
        )
        return None


def stop_spark() -> None:
    """Stop the cached SparkSession if present."""
    global _SPARK
    if _SPARK is not None:
        _SPARK.stop()
        _SPARK = None
        logger.info("spark_session_stopped")
