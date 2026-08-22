"""Longitudinal patient-reported outcome (PRO) survey simulator.

Instruments: PHQ-9, GAD-7, PROMIS-29 (subset), EQ-5D-5L, SF-36 (domain items simplified).
Includes missingness, dropout, partial completion, straight-lining, and out-of-window responses.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from hc_lakehouse.ingest.synthetic.clinical import GeneratorConfig, _rng, _synth_id

WAVES = [
    ("baseline", 0),
    ("day_30", 30),
    ("day_90", 90),
    ("day_180", 180),
    ("day_365", 365),
]

# Item banks: instrument -> list of (item_id, min, max)
INSTRUMENTS: dict[str, list[tuple[str, int, int]]] = {
    "PHQ-9": [(f"PHQ9_Q{i}", 0, 3) for i in range(1, 10)],
    "GAD-7": [(f"GAD7_Q{i}", 0, 3) for i in range(1, 8)],
    "PROMIS-29": [(f"PROMIS29_Q{i}", 1, 5) for i in range(1, 29)],
    "EQ-5D-5L": [(f"EQ5D_D{i}", 1, 5) for i in range(1, 6)] + [("EQ5D_VAS", 0, 100)],
    "SF-36": [(f"SF36_Q{i}", 1, 5) for i in range(1, 37)],
}

SEVERITY_PHQ9 = [
    (0, 4, "none-minimal"),
    (5, 9, "mild"),
    (10, 14, "moderate"),
    (15, 19, "moderately-severe"),
    (20, 27, "severe"),
]


def _score_phq9(responses: dict[str, int]) -> dict[str, Any]:
    total = sum(responses.values())
    band = "unknown"
    for lo, hi, label in SEVERITY_PHQ9:
        if lo <= total <= hi:
            band = label
            break
    return {"total": total, "severity_band": band, "scoring_version": "PHQ9_v1"}


def _score_gad7(responses: dict[str, int]) -> dict[str, Any]:
    total = sum(responses.values())
    if total <= 4:
        band = "minimal"
    elif total <= 9:
        band = "mild"
    elif total <= 14:
        band = "moderate"
    else:
        band = "severe"
    return {"total": total, "severity_band": band, "scoring_version": "GAD7_v1"}


def _score_sum(_instrument: str, responses: dict[str, int], version: str) -> dict[str, Any]:
    return {
        "total": sum(responses.values()),
        "severity_band": "n/a",
        "scoring_version": version,
    }


def _score_promis29(responses: dict[str, int]) -> dict[str, Any]:
    return _score_sum("PROMIS-29", responses, "PROMIS29_raw_v1")


def _score_eq5d(responses: dict[str, int]) -> dict[str, Any]:
    return _score_sum("EQ-5D-5L", responses, "EQ5D5L_sum_v1")


def _score_sf36(responses: dict[str, int]) -> dict[str, Any]:
    return _score_sum("SF-36", responses, "SF36_raw_v1")


SCORERS: dict[str, Callable[[dict[str, int]], dict[str, Any]]] = {
    "PHQ-9": _score_phq9,
    "GAD-7": _score_gad7,
    "PROMIS-29": _score_promis29,
    "EQ-5D-5L": _score_eq5d,
    "SF-36": _score_sf36,
}


def generate_survey_instruments() -> list[dict[str, Any]]:
    rows = []
    algo = {
        "PHQ-9": "PHQ9_v1",
        "GAD-7": "GAD7_v1",
        "PROMIS-29": "PROMIS29_raw_v1",
        "EQ-5D-5L": "EQ5D5L_sum_v1",
        "SF-36": "SF36_raw_v1",
    }
    for name, items in INSTRUMENTS.items():
        rows.append(
            {
                "instrument_id": f"INSTR-{name.replace('-', '')}",
                "name": name,
                "item_count": len(items),
                "scoring_algorithm": algo[name],
                "source_system": "survey_sim",
            }
        )
    return rows


def generate_survey_items() -> list[dict[str, Any]]:
    rows = []
    for name, items in INSTRUMENTS.items():
        for item_id, lo, hi in items:
            rows.append(
                {
                    "instrument_id": f"INSTR-{name.replace('-', '')}",
                    "item_id": item_id,
                    "min_value": lo,
                    "max_value": hi,
                    "source_system": "survey_sim",
                }
            )
    return rows


def generate_surveys(
    cfg: GeneratorConfig,
    patients: list[dict[str, Any]],
    consents: list[dict[str, Any]],
    instrument_names: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Generate administrations, item responses, and scores with realistic missingness."""
    names = instrument_names or list(INSTRUMENTS.keys())
    consent_by_patient = {c["patient_id"]: c for c in consents}
    administrations: list[dict[str, Any]] = []
    item_responses: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    admin_id = 0
    resp_id = 0
    score_id = 0

    baseline = datetime(2023, 1, 15, tzinfo=timezone.utc)

    for p in patients:
        consent = consent_by_patient.get(p["patient_id"])
        if consent and consent["consent_status"] != "active":
            continue
        # Dropout after a random wave
        dropout_wave = int(_rng(cfg.seed, p["patient_id"], "dropout") * (len(WAVES) + 1))
        for wave_idx, (wave_name, day_offset) in enumerate(WAVES):
            if wave_idx > dropout_wave:
                break
            # Skip wave entirely (~8%)
            if wave_idx > 0 and _rng(cfg.seed, p["patient_id"], wave_name, "skip") < 0.08:
                continue
            # Out-of-window: shift by ±20 days occasionally
            shift = 0
            if _rng(cfg.seed, p["patient_id"], wave_name, "ow") < 0.05:
                shift = int(_rng(cfg.seed, p["patient_id"], wave_name, "ows") * 40) - 20
            administered = baseline + timedelta(days=day_offset + shift)

            for instrument in names:
                admin_id += 1
                aid = _synth_id("ADM", admin_id)
                items = INSTRUMENTS[instrument]
                # Partial completion: answer only a prefix of items
                complete_frac = 1.0
                if _rng(cfg.seed, aid, "partial") < 0.12:
                    complete_frac = 0.4 + _rng(cfg.seed, aid, "pf") * 0.5
                n_answered = max(1, int(len(items) * complete_frac))
                straight = _rng(cfg.seed, aid, "straight") < 0.04
                responses: dict[str, int] = {}
                for item_id, lo, hi in items[:n_answered]:
                    if straight:
                        value = lo
                    else:
                        value = lo + int(_rng(cfg.seed, aid, item_id) * (hi - lo + 1))
                        value = min(max(value, lo), hi)
                    responses[item_id] = value
                    resp_id += 1
                    item_responses.append(
                        {
                            "response_id": _synth_id("RSP", resp_id),
                            "administration_id": aid,
                            "patient_id": p["patient_id"],
                            "instrument_id": f"INSTR-{instrument.replace('-', '')}",
                            "item_id": item_id,
                            "value_num": value,
                            "source_system": "survey_sim",
                        }
                    )

                completion_status = "complete" if n_answered == len(items) else "partial"
                out_of_window = abs(shift) > 14
                administrations.append(
                    {
                        "administration_id": aid,
                        "patient_id": p["patient_id"],
                        "instrument_id": f"INSTR-{instrument.replace('-', '')}",
                        "instrument_name": instrument,
                        "wave": wave_name,
                        "administered_ts": administered.isoformat(),
                        "completion_status": completion_status,
                        "straight_lining_flag": straight,
                        "out_of_window_flag": out_of_window,
                        "irb_protocol_id": "IRB-SYN-2024-001",
                        "source_system": "survey_sim",
                    }
                )

                if completion_status == "complete" or (
                    instrument in {"PHQ-9", "GAD-7"} and n_answered >= len(items) - 1
                ):
                    score_id += 1
                    scored = SCORERS[instrument](responses)
                    scores.append(
                        {
                            "score_id": _synth_id("SCR", score_id),
                            "administration_id": aid,
                            "patient_id": p["patient_id"],
                            "instrument_id": f"INSTR-{instrument.replace('-', '')}",
                            "instrument_name": instrument,
                            "wave": wave_name,
                            "total_score": scored["total"],
                            "severity_band": scored["severity_band"],
                            "scoring_version": scored["scoring_version"],
                            "source_system": "survey_sim",
                        }
                    )

    return {
        "survey_instrument": generate_survey_instruments(),
        "survey_item": generate_survey_items(),
        "survey_administration": administrations,
        "survey_response": item_responses,
        "survey_score": scores,
    }
