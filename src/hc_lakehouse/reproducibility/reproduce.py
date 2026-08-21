"""Reproduce CLI stub — fully implemented in Phase 7."""

from __future__ import annotations

import argparse
import sys

from hc_lakehouse.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    setup_logging(fmt="text")
    parser = argparse.ArgumentParser(
        description="Re-derive a Gold artifact from a research manifest."
    )
    parser.add_argument("--manifest", required=True, help="Path to RESEARCH_MANIFEST.json")
    args = parser.parse_args(argv)
    logger.error(
        "reproduce_not_implemented",
        extra={
            "manifest": args.manifest,
            "detail": "Phase 7 implements Delta time-travel reproduction.",
        },
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
