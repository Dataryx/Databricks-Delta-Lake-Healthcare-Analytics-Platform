-- Dashboard: PRO trajectory mean change from baseline
-- Grain: instrument_key × wave from gold.mart_prom_trajectory

SELECT
  instrument_key,
  wave,
  COUNT(*) AS n_responses,
  AVG(total_score) AS mean_score,
  AVG(change_from_baseline) AS mean_change_from_baseline
FROM gold.mart_prom_trajectory
GROUP BY instrument_key, wave
HAVING COUNT(*) >= 11
ORDER BY instrument_key, wave;
