"""Deterministic synthetic clinical corpus (Synthea-compatible shapes).

Grain: one row per entity instance. Identifiers use ``SYN-*`` tokens that do not
match PHI scanner patterns. Seed controls all randomness for reproducibility.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

# ICD-10 / LOINC / RxNorm / CPT sample codes (public code systems — not PHI)
CONDITIONS = [
    ("E11.9", "Type 2 diabetes mellitus without complications", "SNOMED", "44054006"),
    ("I10", "Essential (primary) hypertension", "SNOMED", "59621000"),
    ("J45.909", "Unspecified asthma, uncomplicated", "SNOMED", "195967001"),
    ("F32.9", "Major depressive disorder, single episode", "SNOMED", "370143000"),
    ("M54.5", "Low back pain", "SNOMED", "279039007"),
]

LABS = [
    ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", "%", 4.5, 14.0),
    ("2339-0", "Glucose [Mass/volume] in Blood", "mg/dL", 70.0, 400.0),
    ("2160-0", "Creatinine [Mass/volume] in Serum or Plasma", "mg/dL", 0.4, 8.0),
    ("2085-9", "Cholesterol in HDL [Mass/volume] in Serum", "mg/dL", 20.0, 100.0),
    ("8480-6", "Systolic blood pressure", "mmHg", 90.0, 200.0),
]

MEDICATIONS = [
    ("860975", "Metformin 500 MG Oral Tablet", "oral"),
    ("197361", "Lisinopril 10 MG Oral Tablet", "oral"),
    ("1049621", "Albuterol 0.083% Inhalation Solution", "inhalation"),
]

PROCEDURES = [
    ("99213", "Office/outpatient visit established", "CPT"),
    ("93000", "Electrocardiogram complete", "CPT"),
    ("71046", "Chest X-ray 2 views", "CPT"),
]

IMMUNIZATIONS = [
    ("140", "Influenza, seasonal, injectable", "CVX"),
    ("208", "COVID-19, mRNA, LNP, PF, 30 mcg", "CVX"),
]

CARE_SETTINGS = ["inpatient", "outpatient", "emergency", "ambulatory"]
PAYERS = ["SYN-PAYER-A", "SYN-PAYER-B", "SYN-PAYER-C"]
RACES = ["white", "black", "asian", "other", "unknown"]
ETHNICITIES = ["hispanic", "nonhispanic", "unknown"]
SEXES = ["female", "male", "other", "unknown"]

# 5-digit ZIPs with population well above 20k (Safe Harbor friendly samples)
ZIP_POOL = ["10001", "60601", "77001", "30301", "94102", "98101", "02108", "85001"]


def _rng(seed: int, *parts: str) -> float:
    """Deterministic float in [0, 1) from seed + parts."""
    material = f"{seed}|" + "|".join(parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(16**12)


def _pick(seed: int, key: str, options: list[Any]) -> Any:
    idx = int(_rng(seed, key) * len(options)) % len(options)
    return options[idx]


def _synth_id(prefix: str, n: int) -> str:
    return f"SYN-{prefix}-{n:06d}"


@dataclass(frozen=True)
class GeneratorConfig:
    """Controls corpus size and seed."""

    seed: int = 42
    patient_count: int = 100
    encounters_per_patient: tuple[int, int] = (1, 8)
    as_of: date = date(2024, 6, 30)


def generate_organizations(cfg: GeneratorConfig) -> list[dict[str, Any]]:
    """Generate synthetic healthcare organizations."""
    names = [
        "North River Medical Center",
        "Cedar Grove Clinic",
        "Lakeside Community Hospital",
        "Summit Ambulatory Care",
    ]
    rows = []
    for i, name in enumerate(names, start=1):
        rows.append(
            {
                "organization_id": _synth_id("ORG", i),
                "name": name,
                "npi_token": f"SYN-ORG-NPI-{i:04d}",
                "zip3": _pick(cfg.seed, f"orgzip{i}", ZIP_POOL)[:3],
                "source_system": "synthea_sim",
            }
        )
    return rows


def generate_providers(
    cfg: GeneratorConfig, organizations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Generate synthetic providers affiliated to organizations."""
    rows = []
    for i in range(1, 21):
        org = organizations[(i - 1) % len(organizations)]
        rows.append(
            {
                "provider_id": _synth_id("PRV", i),
                "organization_id": org["organization_id"],
                "family_name": f"Provider{i:03d}",
                "given_name": f"Clinician{i:03d}",
                "npi_token": f"SYN-PRV-NPI-{i:04d}",
                "specialty": _pick(
                    cfg.seed,
                    f"spec{i}",
                    ["internal medicine", "cardiology", "family", "psychiatry"],
                ),
                "source_system": "synthea_sim",
            }
        )
    return rows


def generate_patients(cfg: GeneratorConfig) -> list[dict[str, Any]]:
    """Generate synthetic patients (direct identifiers are synthetic tokens only)."""
    rows = []
    for i in range(1, cfg.patient_count + 1):
        age = 18 + int(_rng(cfg.seed, f"age{i}") * 70)
        # Cap displayed ages for demo; real de-id bucketing happens in Silver
        birth = date(cfg.as_of.year - age, 1 + int(_rng(cfg.seed, f"bm{i}") * 12), 1)
        rows.append(
            {
                "patient_id": _synth_id("PAT", i),
                "source_patient_token": f"SYNTOK{i:08d}",
                "family_name": f"Person{i:04d}",
                "given_name": f"Pat{i:04d}",
                "birth_date": birth.isoformat(),
                "sex": _pick(cfg.seed, f"sex{i}", SEXES),
                "race": _pick(cfg.seed, f"race{i}", RACES),
                "ethnicity": _pick(cfg.seed, f"eth{i}", ETHNICITIES),
                "postal_code": _pick(cfg.seed, f"zip{i}", ZIP_POOL),
                "deceased_flag": _rng(cfg.seed, f"dead{i}") < 0.03,
                "source_system": "synthea_sim",
            }
        )
    return rows


def generate_encounters(
    cfg: GeneratorConfig,
    patients: list[dict[str, Any]],
    providers: list[dict[str, Any]],
    organizations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate encounters with admit/discharge windows."""
    rows: list[dict[str, Any]] = []
    eid = 0
    for p in patients:
        lo, hi = cfg.encounters_per_patient
        n = lo + int(_rng(cfg.seed, p["patient_id"], "nenc") * (hi - lo + 1))
        n = min(max(n, lo), hi)
        for j in range(n):
            eid += 1
            setting = _pick(cfg.seed, f"{p['patient_id']}-set{j}", CARE_SETTINGS)
            day_offset = int(_rng(cfg.seed, f"{p['patient_id']}-day{j}") * 700)
            admit = datetime(2022, 1, 1, tzinfo=timezone.utc) + timedelta(days=day_offset, hours=8)
            los_hours = 2 + int(_rng(cfg.seed, f"{p['patient_id']}-los{j}") * 120)
            discharge = admit + timedelta(hours=los_hours) if setting != "outpatient" else admit
            prv = _pick(cfg.seed, f"{p['patient_id']}-prv{j}", providers)
            org = _pick(cfg.seed, f"{p['patient_id']}-org{j}", organizations)
            rows.append(
                {
                    "encounter_id": _synth_id("ENC", eid),
                    "patient_id": p["patient_id"],
                    "provider_id": prv["provider_id"],
                    "organization_id": org["organization_id"],
                    "care_setting": setting,
                    "admit_ts": admit.isoformat(),
                    "discharge_ts": discharge.isoformat(),
                    "encounter_class": setting,
                    "source_system": "synthea_sim",
                }
            )
    return rows


def generate_conditions(
    cfg: GeneratorConfig, encounters: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    cid = 0
    for enc in encounters:
        if _rng(cfg.seed, enc["encounter_id"], "cond") < 0.7:
            cid += 1
            code, display, system, snomed = _pick(cfg.seed, enc["encounter_id"], CONDITIONS)
            rows.append(
                {
                    "condition_id": _synth_id("COND", cid),
                    "patient_id": enc["patient_id"],
                    "encounter_id": enc["encounter_id"],
                    "icd10_code": code,
                    "snomed_code": snomed,
                    "display": display,
                    "onset_ts": enc["admit_ts"],
                    "clinical_status": "active",
                    "source_system": "synthea_sim",
                }
            )
    return rows


def generate_lab_results(
    cfg: GeneratorConfig, encounters: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    lid = 0
    for enc in encounters:
        if enc["care_setting"] == "emergency" and _rng(cfg.seed, enc["encounter_id"], "lab") < 0.3:
            continue
        n_labs = 1 + int(_rng(cfg.seed, enc["encounter_id"], "nl") * 3)
        for k in range(n_labs):
            lid += 1
            loinc, display, unit, lo, hi = _pick(cfg.seed, f"{enc['encounter_id']}-lab{k}", LABS)
            value = lo + _rng(cfg.seed, f"{enc['encounter_id']}-v{k}") * (hi - lo)
            # Occasional out-of-range for DQ tests later
            if _rng(cfg.seed, f"{enc['encounter_id']}-oor{k}") < 0.02:
                value = hi * 1.5
            rows.append(
                {
                    "lab_result_id": _synth_id("LAB", lid),
                    "patient_id": enc["patient_id"],
                    "encounter_id": enc["encounter_id"],
                    "loinc_code": loinc,
                    "display": display,
                    "value_num": round(value, 2),
                    "unit": unit,
                    "resulted_ts": enc["discharge_ts"],
                    "source_system": "synthea_sim",
                }
            )
    return rows


def generate_observations(
    cfg: GeneratorConfig, encounters: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Vitals / observations (subset of labs as vital signs)."""
    rows = []
    for oid, enc in enumerate(encounters, start=1):
        sys_bp = 100 + int(_rng(cfg.seed, enc["encounter_id"], "sys") * 60)
        rows.append(
            {
                "observation_id": _synth_id("OBS", oid),
                "patient_id": enc["patient_id"],
                "encounter_id": enc["encounter_id"],
                "loinc_code": "8480-6",
                "display": "Systolic blood pressure",
                "value_num": float(sys_bp),
                "unit": "mmHg",
                "observed_ts": enc["admit_ts"],
                "source_system": "synthea_sim",
            }
        )
    return rows


def generate_medications(
    cfg: GeneratorConfig, encounters: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    mid = 0
    for enc in encounters:
        if _rng(cfg.seed, enc["encounter_id"], "med") < 0.5:
            continue
        mid += 1
        rx, display, route = _pick(cfg.seed, enc["encounter_id"], MEDICATIONS)
        rows.append(
            {
                "medication_id": _synth_id("MED", mid),
                "patient_id": enc["patient_id"],
                "encounter_id": enc["encounter_id"],
                "rxnorm_code": rx,
                "display": display,
                "route": route,
                "ordered_ts": enc["admit_ts"],
                "source_system": "synthea_sim",
            }
        )
    return rows


def generate_procedures(
    cfg: GeneratorConfig, encounters: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    pid = 0
    for enc in encounters:
        if _rng(cfg.seed, enc["encounter_id"], "proc") < 0.4:
            continue
        pid += 1
        code, display, system = _pick(cfg.seed, enc["encounter_id"], PROCEDURES)
        rows.append(
            {
                "procedure_id": _synth_id("PROC", pid),
                "patient_id": enc["patient_id"],
                "encounter_id": enc["encounter_id"],
                "code": code,
                "code_system": system,
                "display": display,
                "performed_ts": enc["admit_ts"],
                "source_system": "synthea_sim",
            }
        )
    return rows


def generate_immunizations(
    cfg: GeneratorConfig, patients: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    iid = 0
    for p in patients:
        if _rng(cfg.seed, p["patient_id"], "imm") < 0.4:
            continue
        iid += 1
        cvx, display, system = _pick(cfg.seed, p["patient_id"], IMMUNIZATIONS)
        day = int(_rng(cfg.seed, p["patient_id"], "immd") * 600)
        ts = datetime(2022, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)
        rows.append(
            {
                "immunization_id": _synth_id("IMM", iid),
                "patient_id": p["patient_id"],
                "cvx_code": cvx,
                "display": display,
                "code_system": system,
                "administered_ts": ts.isoformat(),
                "source_system": "synthea_sim",
            }
        )
    return rows


def generate_payer_claims(
    cfg: GeneratorConfig, encounters: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    cid = 0
    for enc in encounters:
        if _rng(cfg.seed, enc["encounter_id"], "claim") < 0.35:
            continue
        cid += 1
        amount = round(50 + _rng(cfg.seed, enc["encounter_id"], "amt") * 20000, 2)
        rows.append(
            {
                "claim_line_id": _synth_id("CLM", cid),
                "patient_id": enc["patient_id"],
                "encounter_id": enc["encounter_id"],
                "payer_id": _pick(cfg.seed, enc["encounter_id"], PAYERS),
                "allowed_amount": amount,
                "paid_amount": round(
                    amount * (0.6 + _rng(cfg.seed, enc["encounter_id"], "paid") * 0.4), 2
                ),
                "service_ts": enc["admit_ts"],
                "source_system": "synthea_sim",
            }
        )
    return rows


def generate_consents(cfg: GeneratorConfig, patients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for i, p in enumerate(patients, start=1):
        status = "active" if _rng(cfg.seed, p["patient_id"], "consent") > 0.08 else "revoked"
        rows.append(
            {
                "consent_id": _synth_id("CNS", i),
                "patient_id": p["patient_id"],
                "irb_protocol_id": "IRB-SYN-2024-001",
                "consent_status": status,
                "consent_ts": "2022-01-15T00:00:00+00:00",
                "source_system": "synthea_sim",
            }
        )
    return rows


def generate_clinical_corpus(cfg: GeneratorConfig) -> dict[str, list[dict[str, Any]]]:
    """Build the full clinical entity set keyed by landing entity name."""
    orgs = generate_organizations(cfg)
    providers = generate_providers(cfg, orgs)
    patients = generate_patients(cfg)
    encounters = generate_encounters(cfg, patients, providers, orgs)
    return {
        "organization": orgs,
        "provider": providers,
        "patient": patients,
        "encounter": encounters,
        "condition": generate_conditions(cfg, encounters),
        "observation": generate_observations(cfg, encounters),
        "lab_result": generate_lab_results(cfg, encounters),
        "medication": generate_medications(cfg, encounters),
        "procedure": generate_procedures(cfg, encounters),
        "immunization": generate_immunizations(cfg, patients),
        "payer_claim": generate_payer_claims(cfg, encounters),
        "consent": generate_consents(cfg, patients),
    }


def iter_orphan_lab_candidates(
    cfg: GeneratorConfig, labs: list[dict[str, Any]]
) -> Iterator[dict[str, Any]]:
    """Yield a few intentionally orphan labs for quarantine testing (~1%)."""
    for lab in labs:
        if _rng(cfg.seed, lab["lab_result_id"], "orphan") < 0.01:
            dirty = dict(lab)
            dirty["encounter_id"] = "SYN-ENC-MISSING"
            dirty["patient_id"] = "SYN-PAT-MISSING"
            yield dirty
