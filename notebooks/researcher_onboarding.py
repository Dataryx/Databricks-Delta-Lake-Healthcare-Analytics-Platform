# Databricks notebook source
# Researcher onboarding for INDHC
# Uses synthetic / de-identified data only.

# COMMAND ----------

# MAGIC %md
# MAGIC # Researcher onboarding
# MAGIC
# MAGIC This notebook shows how to:
# MAGIC 1. Pull a governed cohort
# MAGIC 2. Join clinical Gold to PRO scores
# MAGIC 3. Export a de-identified extract with a research manifest
# MAGIC
# MAGIC Stay out of the restricted crosswalk unless break-glass is approved.
# MAGIC Do not print source identifiers. Model scores are research artifacts, not clinical advice.

# COMMAND ----------

from pathlib import Path

from hc_lakehouse.utils.config import load_config
from hc_lakehouse.utils.io import delta_table_path, read_delta, table_exists
from hc_lakehouse.utils.spark_session import get_spark

config = load_config()
spark = get_spark(config, app_name="researcher-onboarding")
print(f"catalog={config.catalog} mode={config.runtime_mode}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Load a cohort

# COMMAND ----------

cohort_path = delta_table_path(config.local_delta_root, "gold", "cohort_inpatient_utilizers")
if table_exists(spark, cohort_path):
    cohort = read_delta(spark, cohort_path)
else:
    cohort = read_delta(spark, delta_table_path(config.local_delta_root, "gold", "dim_patient"))
display(cohort.limit(20))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Join clinical + PRO (de-identified keys only)

# COMMAND ----------

p360 = read_delta(spark, delta_table_path(config.local_delta_root, "gold", "mart_patient_360"))
prom = read_delta(spark, delta_table_path(config.local_delta_root, "gold", "mart_prom_trajectory"))
patient_col = "patient_sk" if "patient_sk" in cohort.columns else "patient_key"
cohort_keys = cohort.select(patient_col).withColumnRenamed(patient_col, "patient_key")
joined = (
    cohort_keys.join(p360, on="patient_key", how="left").join(prom, on="patient_key", how="left")
)
display(joined.limit(20))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Export extract + tip for manifests
# MAGIC
# MAGIC Use `make build-cohort` / `hc-reproduce` for checksummed `RESEARCH_MANIFEST.json`.
# MAGIC Sandbox schema per user is provisioned in Unity Catalog (`sandbox`) with quotas.

# COMMAND ----------

out = Path("artifacts") / "extracts" / "onboarding_sample"
out.mkdir(parents=True, exist_ok=True)
joined.limit(100).toPandas().to_csv(out / "sample_deid_extract.csv", index=False)
print(f"wrote {out / 'sample_deid_extract.csv'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Done
# MAGIC Next: read `docs/governance.md`, `docs/reproducibility.md`, and request group membership
# MAGIC (`hc_researchers_deid`) via your access review channel.
