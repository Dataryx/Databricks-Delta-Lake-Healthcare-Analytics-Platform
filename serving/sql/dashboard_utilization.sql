-- Dashboard: Research utilization overview (SQL warehouse)
-- Grain: age_band × sex × care_setting aggregates (k-suppressed in mart)
-- Source: gold.mart_utilization
-- Not clinical advice.

SELECT
  age_band,
  sex,
  care_setting_key,
  n AS encounter_count,
  avg_los_days
FROM gold.mart_utilization
ORDER BY age_band, sex, care_setting_key;
