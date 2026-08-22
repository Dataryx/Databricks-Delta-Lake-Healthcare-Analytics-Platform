-- Dashboard: Clinical–survey linkage coverage
-- Grain: patients with both utilization and PRO scores

SELECT
  COUNT(DISTINCT patient_key) AS patients_with_linkage,
  COUNT(*) AS linkage_rows
FROM gold.mart_clinical_survey_linkage;
