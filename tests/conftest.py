"""Pytest fixtures shared across suites."""

from __future__ import annotations

import pytest

from hc_lakehouse.utils.config import clear_config_cache
from hc_lakehouse.utils.logging import setup_logging


@pytest.fixture(autouse=True)
def _reset_logging_and_config() -> None:
    setup_logging(level="WARNING", fmt="text", force=True)
    clear_config_cache()
    yield
    clear_config_cache()
