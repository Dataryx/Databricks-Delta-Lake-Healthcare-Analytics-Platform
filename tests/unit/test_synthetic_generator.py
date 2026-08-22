"""Unit tests for synthetic clinical + survey generators."""

from __future__ import annotations

from hc_lakehouse.ingest.synthetic.clinical import GeneratorConfig, generate_clinical_corpus
from hc_lakehouse.ingest.synthetic.generator import generate_and_write
from hc_lakehouse.ingest.synthetic.survey import generate_surveys


def test_clinical_corpus_deterministic() -> None:
    cfg = GeneratorConfig(seed=42, patient_count=10)
    a = generate_clinical_corpus(cfg)
    b = generate_clinical_corpus(cfg)
    assert a["patient"] == b["patient"]
    assert len(a["patient"]) == 10
    assert len(a["encounter"]) >= 10
    assert all(p["patient_id"].startswith("SYN-PAT-") for p in a["patient"])


def test_encounter_discharge_after_admit() -> None:
    cfg = GeneratorConfig(seed=7, patient_count=5)
    corpus = generate_clinical_corpus(cfg)
    for enc in corpus["encounter"]:
        assert enc["discharge_ts"] >= enc["admit_ts"]


def test_survey_has_waves_and_partials() -> None:
    cfg = GeneratorConfig(seed=42, patient_count=20)
    clinical = generate_clinical_corpus(cfg)
    surveys = generate_surveys(cfg, clinical["patient"], clinical["consent"])
    assert surveys["survey_administration"]
    waves = {a["wave"] for a in surveys["survey_administration"]}
    assert "baseline" in waves
    statuses = {a["completion_status"] for a in surveys["survey_administration"]}
    assert "partial" in statuses or "complete" in statuses
    assert surveys["survey_score"]
    assert all("scoring_version" in s for s in surveys["survey_score"])


def test_generate_and_write(tmp_path) -> None:
    counts = generate_and_write(tmp_path, seed=42, patient_count=5, write_sample_subset=True)
    assert counts["patient"] == 5
    assert (tmp_path / "landing" / "clinical" / "patient.csv").exists()
    assert (tmp_path / "landing" / "survey" / "survey_administration.csv").exists()
    assert (tmp_path / "sample" / "patient.csv").exists()
    assert (tmp_path / "landing" / "MANIFEST.json").exists()
