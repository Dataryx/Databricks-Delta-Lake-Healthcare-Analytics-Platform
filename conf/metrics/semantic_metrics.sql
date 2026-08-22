-- Semantic metrics (versioned SQL) — single source of truth for measure definitions
-- Owner: hc_data_stewards | Version: 1.0.0

-- Metric: 30-day all-cause readmission rate
-- Numerator: index inpatient encounters with readmission_30d = true
-- Denominator: inpatient index encounters
-- Exclusions: none in v1 (deaths excluded when deceased_flag available on index)
-- Owner: hc_data_stewards
CREATE OR REPLACE VIEW gold.metric_readmission_30d AS
SELECT
  COUNT(*) AS denominator,
  SUM(readmission_30d_count) AS numerator,
  CAST(SUM(readmission_30d_count) AS DOUBLE) / NULLIF(COUNT(*), 0) AS rate
FROM gold.fact_readmission;

-- Metric: average length of stay (inpatient)
-- Numerator: sum(los_days)
-- Denominator: inpatient encounter count
CREATE OR REPLACE VIEW gold.metric_avg_los AS
SELECT
  AVG(los_days) AS avg_los_days,
  COUNT(*) AS encounters
FROM gold.fact_encounter
WHERE care_setting_key = 'inpatient';

-- Metric: ED revisit count proxy (ED encounters per patient in mart)
CREATE OR REPLACE VIEW gold.metric_ed_utilization AS
SELECT
  AVG(ed_count) AS mean_ed_encounters,
  SUM(ed_count) AS total_ed_encounters,
  COUNT(*) AS patients
FROM gold.mart_patient_360;

-- Metric: PRO response rate (administrations with scores / patients)
CREATE OR REPLACE VIEW gold.metric_pro_response_rate AS
SELECT
  COUNT(DISTINCT patient_key) AS patients_with_pro,
  COUNT(*) AS scored_responses
FROM gold.fact_survey_response;

-- Metric: mean change from baseline (PHQ-9)
CREATE OR REPLACE VIEW gold.metric_phq9_mean_change AS
SELECT
  AVG(change_from_baseline) AS mean_change,
  SUM(CASE WHEN mcid_improved THEN 1 ELSE 0 END) AS mcid_count,
  COUNT(*) AS rows_n
FROM gold.mart_prom_trajectory
WHERE instrument_key = 'PHQ-9'
  AND wave <> 'baseline'
  AND change_from_baseline IS NOT NULL;
