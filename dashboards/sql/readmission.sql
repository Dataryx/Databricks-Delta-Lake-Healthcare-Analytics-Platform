-- Dashboard: 30-day readmission rate by age band
-- Grain: age_band aggregate from gold.fact_readmission × dim_patient
-- Apply small-cell suppression in serving views when n < small_cell_k.

WITH base AS (
  SELECT
    p.age_band,
    r.readmission_30d,
    r.patient_key
  FROM gold.fact_readmission r
  INNER JOIN gold.dim_patient p
    ON r.patient_key = p.patient_key
)
SELECT
  age_band,
  COUNT(*) AS index_stays,
  SUM(CASE WHEN readmission_30d THEN 1 ELSE 0 END) AS readmissions_30d,
  ROUND(
    SUM(CASE WHEN readmission_30d THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(*), 0),
    4
  ) AS readmission_rate
FROM base
GROUP BY age_band
HAVING COUNT(*) >= 11
ORDER BY age_band;
