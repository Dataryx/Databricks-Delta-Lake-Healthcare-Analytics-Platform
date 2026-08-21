"""Unit tests for Phase 0 platform utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from hc_lakehouse.utils.config import clear_config_cache, load_config
from hc_lakehouse.utils.hashing import sha256_hex, stable_record_hash
from hc_lakehouse.utils.logging import get_logger, setup_logging


def test_load_config_from_example_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clear_config_cache()
    monkeypatch.setenv("HC_RUNTIME_MODE", "local")
    monkeypatch.setenv("HC_CATALOG", "hc_dev")
    monkeypatch.setenv("HC_LOCAL_DELTA_ROOT", str(tmp_path / "delta"))
    monkeypatch.setenv("HC_SMALL_CELL_K", "11")
    cfg = load_config()
    assert cfg.is_local
    assert cfg.catalog == "hc_dev"
    assert cfg.small_cell_k == 11
    assert cfg.table_fqn("silver", "patient") == "hc_dev.silver.patient"
    clear_config_cache()


def test_deid_salt_rejects_demo_outside_local(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_config_cache()
    monkeypatch.setenv("HC_RUNTIME_MODE", "databricks")
    monkeypatch.setenv("HC_DEID_SALT", "local-demo-pepper-not-for-production")
    cfg = load_config()
    with pytest.raises(RuntimeError, match="must not be used"):
        cfg.deid_salt()
    clear_config_cache()


def test_stable_record_hash_is_deterministic() -> None:
    a = stable_record_hash(["SYN-PAT-001", "enc-1", None])
    b = stable_record_hash(["SYN-PAT-001", "enc-1", ""])
    assert a == b
    assert len(sha256_hex("x")) == 64


def test_structured_logger_does_not_raise() -> None:
    setup_logging(level="INFO", fmt="json", force=True)
    log = get_logger("test.logger", component="unit")
    log.info("hello", extra={"batch_id": "b1"})


def test_phi_scanner_passes_clean_text(tmp_path: Path) -> None:
    from hc_lakehouse.privacy.phi_scanner import scan_file

    clean = tmp_path / "clean.txt"
    clean.write_text("patient_sk=abc synthetic cohort only\n", encoding="utf-8")
    assert scan_file(clean) == []


def test_phi_scanner_detects_ssn(tmp_path: Path) -> None:
    from hc_lakehouse.privacy.phi_scanner import scan_file

    dirty = tmp_path / "dirty.txt"
    # Build PHI-shaped token at runtime so the source file stays scanner-clean
    shaped = "-".join(["123", "45", "6789"])
    dirty.write_text(f"bad value {shaped} here\n", encoding="utf-8")
    findings = scan_file(dirty)
    assert any(f.pattern_name == "ssn" for f in findings)
