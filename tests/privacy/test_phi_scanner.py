"""Privacy scanner tests."""

from __future__ import annotations

from pathlib import Path

from hc_lakehouse.privacy.phi_scanner import main, scan_paths


def test_phi_scan_cli_clean(tmp_path: Path) -> None:
    f = tmp_path / "ok.md"
    f.write_text("# synthetic only\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 0


def test_phi_scan_cli_dirty(tmp_path: Path) -> None:
    f = tmp_path / "bad.md"
    # Assemble at runtime — do not commit email-shaped literals in source
    address = "@".join(["me", "example.com"])
    f.write_text(f"contact {address} please\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 1
    findings = scan_paths([tmp_path])
    assert any(x.pattern_name == "email" for x in findings)
