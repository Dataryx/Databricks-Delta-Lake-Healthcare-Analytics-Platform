"""PHI-shaped pattern scanner for pre-commit and CI.

Scans text files for patterns that look like real identifiers (MRN, SSN, NPI,
DOB, email, phone, ZIP+4). Synthetic fixtures must use clearly fake tokens that
do not match these patterns (see ``tests/`` and ``data/synthetic/``).

This scanner is intentionally conservative (fail closed): a hit fails the build.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from hc_lakehouse.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

# Binary / generated extensions skipped
SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".parquet",
    ".orc",
    ".avro",
    ".jar",
    ".zip",
    ".gz",
    ".whl",
    ".pyc",
    ".so",
    ".dll",
    ".exe",
    ".ico",
}

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    ".local_delta",
    "spark-warehouse",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
    ".terraform",
    "__pycache__",
    "dist",
    "build",
}


@dataclass(frozen=True)
class PhiPattern:
    name: str
    regex: re.Pattern[str]
    description: str


# Patterns designed to catch PHI-shaped values, not documentation words alone.
PHI_PATTERNS: tuple[PhiPattern, ...] = (
    PhiPattern(
        "ssn",
        re.compile(r"(?<!\d)(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?!\d)"),
        "US Social Security Number shape (AAA-GG-SSSS)",
    ),
    PhiPattern(
        "npi",
        re.compile(r"\bNPI[:\s#-]*[12]\d{9}\b", re.IGNORECASE),
        "NPI label with 10-digit identifier",
    ),
    PhiPattern(
        "mrn",
        re.compile(r"\bMRN[:\s#-]*[A-Z0-9]{6,12}\b", re.IGNORECASE),
        "Medical record number label with identifier",
    ),
    PhiPattern(
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "Email address",
    ),
    PhiPattern(
        "phone",
        re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)"),
        "US phone number",
    ),
    PhiPattern(
        "zip4",
        re.compile(r"(?<!\d)\d{5}-\d{4}(?!\d)"),
        "ZIP+4 postal code",
    ),
    PhiPattern(
        "dob_full",
        re.compile(
            r"\b(?:DOB|date[_\s-]?of[_\s-]?birth)[:\s=]+"
            r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b",
            re.IGNORECASE,
        ),
        "Full date of birth labeled field",
    ),
)

# Allowlisted path fragments (docs explaining patterns, scanner itself, examples)
ALLOWLIST_PATH_FRAGMENTS = (
    "phi_scanner.py",
    "docs/assumptions.md",
    "docs/deidentification",
    "docs/hipaa",
    ".env.example",
)


@dataclass
class Finding:
    path: Path
    line_no: int
    pattern_name: str
    snippet: str


def _is_allowlisted(path: Path) -> bool:
    posix = path.as_posix()
    return any(fragment in posix for fragment in ALLOWLIST_PATH_FRAGMENTS)


def _should_skip(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def iter_text_files(roots: Sequence[Path]) -> Iterable[Path]:
    for root in roots:
        if root.is_file():
            if not _should_skip(root):
                yield root
            continue
        for path in root.rglob("*"):
            if not path.is_file() or _should_skip(path):
                continue
            yield path


def scan_file(path: Path) -> list[Finding]:
    if _is_allowlisted(path):
        return []
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("phi_scan_read_failed", extra={"path": str(path), "error": str(exc)})
        return findings
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in PHI_PATTERNS:
            if pattern.regex.search(line):
                findings.append(
                    Finding(
                        path=path,
                        line_no=line_no,
                        pattern_name=pattern.name,
                        snippet=line.strip()[:120],
                    )
                )
    return findings


def scan_paths(roots: Sequence[Path]) -> list[Finding]:
    all_findings: list[Finding] = []
    for path in iter_text_files(roots):
        all_findings.extend(scan_file(path))
    return all_findings


def main(argv: Sequence[str] | None = None) -> int:
    setup_logging(level="INFO", fmt="text")
    parser = argparse.ArgumentParser(description="Scan for PHI-shaped patterns (fail closed).")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to scan (default: repo root).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    roots = [Path(p).resolve() for p in args.paths]
    findings = scan_paths(roots)
    if findings:
        for hit in findings:
            logger.error(
                "phi_pattern_detected",
                extra={
                    "path": str(hit.path),
                    "line": hit.line_no,
                    "pattern": hit.pattern_name,
                    "snippet": hit.snippet,
                },
            )
        logger.error("phi_scan_failed", extra={"count": len(findings)})
        return 1
    logger.info("phi_scan_passed", extra={"roots": [str(r) for r in roots]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
