"""Privacy and de-identification package."""

from __future__ import annotations

__all__ = [
    "build_deid_patient_layer",
    "deidentify_patients",
    "hmac_sha256_hex",
]


def __getattr__(name: str) -> object:
    if name in {"build_deid_patient_layer", "deidentify_patients"}:
        from hc_lakehouse.privacy import deid as _deid

        return getattr(_deid, name)
    if name == "hmac_sha256_hex":
        from hc_lakehouse.privacy.hashing import hmac_sha256_hex

        return hmac_sha256_hex
    raise AttributeError(name)
