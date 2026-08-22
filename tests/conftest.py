"""Pytest fixtures shared across suites."""

from __future__ import annotations

from pathlib import Path

import pytest

from hc_lakehouse.utils.config import clear_config_cache
from hc_lakehouse.utils.logging import setup_logging


@pytest.fixture(autouse=True)
def _reset_logging_and_config() -> None:
    setup_logging(level="WARNING", fmt="text", force=True)
    clear_config_cache()
    yield
    clear_config_cache()


@pytest.fixture()
def spark_local_privacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Spark session + config for privacy integration tests."""
    pytest.importorskip("pyspark")
    pytest.importorskip("delta")
    monkeypatch.setenv("HC_RUNTIME_MODE", "local")
    monkeypatch.setenv("HC_LOCAL_DELTA_ROOT", str(tmp_path / "delta"))
    monkeypatch.setenv("HC_DEID_SALT", "local-demo-pepper-not-for-production")
    clear_config_cache()
    from hc_lakehouse.utils.config import load_config
    from hc_lakehouse.utils.spark_session import get_spark, stop_spark

    cfg = load_config()
    spark = get_spark(cfg, app_name="test-privacy", force_new=True)
    yield spark, cfg, tmp_path / "syn"
    stop_spark()
    clear_config_cache()
