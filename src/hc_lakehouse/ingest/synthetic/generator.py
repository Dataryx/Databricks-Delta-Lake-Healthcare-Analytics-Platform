"""Orchestrate synthetic corpus generation and write landing-zone CSV/JSON files."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from hc_lakehouse.ingest.synthetic.clinical import (
    GeneratorConfig,
    generate_clinical_corpus,
    iter_orphan_lab_candidates,
)
from hc_lakehouse.ingest.synthetic.survey import generate_surveys
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)


def generate_and_write(
    output_dir: Path,
    *,
    seed: int = 42,
    patient_count: int = 100,
    include_orphans: bool = True,
    write_sample_subset: bool = True,
) -> dict[str, int]:
    """Generate clinical + survey datasets and write to ``output_dir``.

    Layout::

        output_dir/
          landing/clinical/*.csv
          landing/survey/*.csv
          sample/  (tiny subset for git, when write_sample_subset)

    Returns entity → row count.
    """
    cfg = GeneratorConfig(seed=seed, patient_count=patient_count)
    clinical = generate_clinical_corpus(cfg)
    if include_orphans:
        orphans = list(iter_orphan_lab_candidates(cfg, clinical["lab_result"]))
        clinical["lab_result"] = clinical["lab_result"] + orphans
        logger.info("orphan_labs_injected", extra={"count": len(orphans)})

    surveys = generate_surveys(cfg, clinical["patient"], clinical["consent"])
    corpus = {**clinical, **surveys}

    clinical_dir = output_dir / "landing" / "clinical"
    survey_dir = output_dir / "landing" / "survey"
    counts: dict[str, int] = {}

    clinical_entities = {
        "patient",
        "encounter",
        "condition",
        "observation",
        "lab_result",
        "medication",
        "procedure",
        "immunization",
        "provider",
        "organization",
        "payer_claim",
        "consent",
    }
    survey_entities = {
        "survey_instrument",
        "survey_item",
        "survey_administration",
        "survey_response",
        "survey_score",
    }

    for name, rows in corpus.items():
        counts[name] = len(rows)
        if name in clinical_entities:
            _write_csv(clinical_dir / f"{name}.csv", rows)
        elif name in survey_entities:
            _write_csv(survey_dir / f"{name}.csv", rows)
        else:
            _write_csv(output_dir / "landing" / "other" / f"{name}.csv", rows)

    meta = {
        "seed": seed,
        "patient_count": patient_count,
        "source": "synthea_sim",
        "survey_source": "survey_sim",
        "counts": counts,
        "note": "SYNTHETIC DATA ONLY — not real PHI",
    }
    _write_json(output_dir / "landing" / "MANIFEST.json", [meta])
    logger.info("synthetic_corpus_written", extra={"output_dir": str(output_dir), **counts})

    if write_sample_subset:
        sample_dir = output_dir / "sample"
        sample_cfg = GeneratorConfig(seed=seed, patient_count=min(5, patient_count))
        sample_clinical = generate_clinical_corpus(sample_cfg)
        sample_surveys = generate_surveys(
            sample_cfg, sample_clinical["patient"], sample_clinical["consent"]
        )
        sample = {**sample_clinical, **sample_surveys}
        for name, rows in sample.items():
            dest = sample_dir / f"{name}.csv"
            _write_csv(dest, rows[:50])
        _write_json(
            sample_dir / "MANIFEST.json",
            [{"seed": seed, "patient_count": sample_cfg.patient_count}],
        )

    return counts
