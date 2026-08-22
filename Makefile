# Healthcare Research Lakehouse — developer targets
# Requires: Python 3.10+, GNU Make, Java 11+ (for local PySpark)

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
PACKAGE := hc_lakehouse
SRC := src/hc_lakehouse
TESTS := tests

.PHONY: help setup install lint typecheck test test-unit test-integration \
	phi-scan demo clean pre-commit-install spark-smoke format windows-hadoop \
	generate-synthetic ingest-bronze build-silver run-dq build-gold

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
	@echo "  generate-synthetic  Build clinical + PRO landing files (seed=42)"
	@echo "  ingest-bronze    Landing CSV → Bronze Delta"
	@echo "  build-silver     Bronze → Silver core (patient/encounter/lab)"
	@echo "  run-dq           Validate Silver; block on error-severity failures"
	@echo "  build-gold       DQ-gated Gold dims/facts/marts"
	@echo "  spark-smoke      Start local Spark+Delta and write a smoke Delta table"
	@echo "  demo             full chain through Gold"
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

generate-synthetic:
	$(PYTHON) scripts/generate_synthetic.py --output data/synthetic --seed 42 --patients 100

ingest-bronze:
	$(PYTHON) scripts/ingest_bronze.py --landing data/synthetic/landing

build-silver:
	$(PYTHON) scripts/build_silver.py

run-dq:
	$(PYTHON) scripts/run_dq.py

build-gold:
	$(PYTHON) scripts/build_gold.py

demo: generate-synthetic ingest-bronze build-silver run-dq build-gold spark-smoke
	@echo "Phases 0–6: synthetic → Bronze → Silver → DQ → Gold complete."

pre-commit-install:
	$(PYTHON) -m pre_commit install || echo "pre-commit not available; skip hooks"

clean:
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['.local_delta','spark-warehouse','htmlcov','.pytest_cache','.mypy_cache','.ruff_cache','dist','build']]"
	@echo "Cleaned local artifacts."
