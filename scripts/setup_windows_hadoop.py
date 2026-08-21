#!/usr/bin/env python3
"""Provision a minimal HADOOP_HOME with winutils for local Spark on Windows.

PySpark on Windows requires ``winutils.exe`` when Delta packages are resolved.
This script downloads a well-known winutils build into ``tools/hadoop/`` and is
idempotent. Non-Windows platforms are a no-op.
"""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HADOOP_HOME = REPO_ROOT / "tools" / "hadoop"
# Hadoop 3.3.x aligns with Spark 3.5 client jars
WINUTILS_URL = (
    "https://raw.githubusercontent.com/cdarlint/winutils/master/hadoop-3.3.5/bin/winutils.exe"
)
HADOOP_DLL_URL = (
    "https://raw.githubusercontent.com/cdarlint/winutils/master/hadoop-3.3.5/bin/hadoop.dll"
)


def main() -> int:
    if os.name != "nt":
        print("setup_windows_hadoop: skipped (not Windows)")
        return 0

    bin_dir = HADOOP_HOME / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    targets = {
        bin_dir / "winutils.exe": WINUTILS_URL,
        bin_dir / "hadoop.dll": HADOOP_DLL_URL,
    }
    for path, url in targets.items():
        if path.exists() and path.stat().st_size > 0:
            print(f"exists: {path}")
            continue
        print(f"downloading: {url}")
        try:
            urllib.request.urlretrieve(url, path)  # noqa: S310 — fixed HTTPS URL
        except OSError as exc:
            print(f"ERROR: failed to download {url}: {exc}", file=sys.stderr)
            return 1
        print(f"wrote: {path}")

    print(f"HADOOP_HOME={HADOOP_HOME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
