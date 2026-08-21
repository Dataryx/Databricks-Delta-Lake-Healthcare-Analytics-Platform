# Healthcare Research Lakehouse — developer targets
# Requires: Python 3.10+, GNU Make, Java 11+ (for local PySpark)

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
PACKAGE := hc_lakehouse
SRC := src/hc_lakehouse
TESTS := tests

.PHONY: help setup install lint typecheck test test-unit test-integration \
	phi-scan demo clean pre-commit-install spark-smoke format windows-hadoop

help:
	@echo "Targets:"
	@echo "  setup            Create venv hint + install editable package with dev extras"
	@echo "  install          pip install -e '.[dev]'"
	@echo "  lint             ruff check + format --check"
	@echo "  format           ruff format + black"
	@echo "  typecheck        mypy on src"
	@echo "  test             Full pytest suite"
	@echo "  test-unit        Unit tests only"
	@echo "  phi-scan         Fail-closed PHI-shaped pattern scan"
	@echo "  spark-smoke      Start local Spark+Delta and write a smoke Delta table"
	@echo "  demo             End-to-end Bronze→Silver→Gold (filled in later phases)"
	@echo "  pre-commit-install  Install git hooks"
	@echo "  clean            Remove local Delta, caches, build artifacts"

setup: install windows-hadoop pre-commit-install
	@echo "Setup complete. Copy .env.example to .env if needed."
	@echo "Ensure JAVA_HOME points to JDK 11 or 17 (not 21+)."

install:
	$(PIP) install -U pip setuptools wheel
	$(PIP) install -e ".[dev]"

windows-hadoop:
	$(PYTHON) scripts/setup_windows_hadoop.py

lint:
	$(PYTHON) -m ruff check $(SRC) $(TESTS) scripts
	$(PYTHON) -m ruff format --check $(SRC) $(TESTS) scripts

format:
	$(PYTHON) -m ruff check --fix $(SRC) $(TESTS) scripts
	$(PYTHON) -m ruff format $(SRC) $(TESTS) scripts
	$(PYTHON) -m black $(SRC) $(TESTS) scripts

typecheck:
	$(PYTHON) -m mypy $(SRC)

test:
	$(PYTHON) -m pytest $(TESTS) --cov=$(PACKAGE) --cov-report=term-missing --cov-report=xml

test-unit:
	$(PYTHON) -m pytest $(TESTS)/unit -q

test-integration:
	$(PYTHON) -m pytest $(TESTS)/integration -q

phi-scan:
	$(PYTHON) -m hc_lakehouse.privacy.phi_scanner .

spark-smoke:
	$(PYTHON) scripts/spark_smoke.py

demo: spark-smoke
	@echo "Phase 0 demo: Spark+Delta smoke only. Full medallion chain arrives in Phases 1–6."

pre-commit-install:
	$(PYTHON) -m pre_commit install || echo "pre-commit not available; skip hooks"

clean:
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['.local_delta','spark-warehouse','htmlcov','.pytest_cache','.mypy_cache','.ruff_cache','dist','build']]"
	@echo "Cleaned local artifacts."
