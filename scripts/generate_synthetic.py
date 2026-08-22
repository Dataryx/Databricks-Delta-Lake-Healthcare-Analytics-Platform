#!/usr/bin/env python3
"""CLI: generate synthetic clinical + PRO landing files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hc_lakehouse.ingest.synthetic.generator import generate_and_write  # noqa: E402
from hc_lakehouse.utils.logging import get_logger, setup_logging  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    setup_logging(fmt="text")
    log = get_logger("generate_synthetic")
    parser = argparse.ArgumentParser(description="Generate synthetic healthcare landing data.")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data" / "synthetic",
        help="Output directory (default: data/synthetic)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--patients", type=int, default=100)
    parser.add_argument("--no-sample", action="store_true", help="Skip tiny git sample subset")
    args = parser.parse_args(argv)

    counts = generate_and_write(
        args.output,
        seed=args.seed,
        patient_count=args.patients,
        write_sample_subset=not args.no_sample,
    )
    log.info("done", extra={"entities": len(counts), "patients": args.patients, "seed": args.seed})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
