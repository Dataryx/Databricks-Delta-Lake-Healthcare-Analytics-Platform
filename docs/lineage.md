# Lineage

Auto-generated from `hc_lakehouse.governance.lineage.LINEAGE_EDGES`.
CI regenerates this file so the diagram cannot go stale.

Unity Catalog table/column lineage is the system of record in Azure; this graph is the local/demo snapshot mirrored into `ops.lineage_snapshot`.

```mermaid
flowchart LR
  n0_landing_clinical_patient_csv["landing/clinical/patient.csv"]
  n1_bronze_patient_raw["bronze.patient_raw"]
  n0_landing_clinical_patient_csv --> n1_bronze_patient_raw
  n2_landing_clinical_encounter_csv["landing/clinical/encounter.csv"]
  n3_bronze_encounter_raw["bronze.encounter_raw"]
  n2_landing_clinical_encounter_csv --> n3_bronze_encounter_raw
  n4_landing_clinical_lab_result_csv["landing/clinical/lab_result.csv"]
  n5_bronze_lab_result_raw["bronze.lab_result_raw"]
  n4_landing_clinical_lab_result_csv --> n5_bronze_lab_result_raw
  n6_landing_survey_survey_score_csv["landing/survey/survey_score.csv"]
  n7_bronze_survey_score_raw["bronze.survey_score_raw"]
  n6_landing_survey_survey_score_csv --> n7_bronze_survey_score_raw
  n8_restricted_patient_xref["restricted.patient_xref"]
  n1_bronze_patient_raw --> n8_restricted_patient_xref
  n9_silver_patient["silver.patient"]
  n1_bronze_patient_raw --> n9_silver_patient
  n10_silver_encounter["silver.encounter"]
  n3_bronze_encounter_raw --> n10_silver_encounter
  n11_silver_lab_result["silver.lab_result"]
  n5_bronze_lab_result_raw --> n11_silver_lab_result
  n12_gold_dim_patient["gold.dim_patient"]
  n9_silver_patient --> n12_gold_dim_patient
  n13_gold_fact_encounter["gold.fact_encounter"]
  n10_silver_encounter --> n13_gold_fact_encounter
  n14_gold_fact_lab_result["gold.fact_lab_result"]
  n11_silver_lab_result --> n14_gold_fact_lab_result
  n15_gold_fact_readmission["gold.fact_readmission"]
  n13_gold_fact_encounter --> n15_gold_fact_readmission
  n16_gold_mart_patient_360["gold.mart_patient_360"]
  n12_gold_dim_patient --> n16_gold_mart_patient_360
  n13_gold_fact_encounter --> n16_gold_mart_patient_360
  n14_gold_fact_lab_result --> n16_gold_mart_patient_360
  n17_gold_mart_utilization["gold.mart_utilization"]
  n13_gold_fact_encounter --> n17_gold_mart_utilization
  n18_gold_fact_survey_response["gold.fact_survey_response"]
  n7_bronze_survey_score_raw --> n18_gold_fact_survey_response
  n19_gold_mart_prom_trajectory["gold.mart_prom_trajectory"]
  n18_gold_fact_survey_response --> n19_gold_mart_prom_trajectory
  n20_gold_mart_clinical_survey_linkage["gold.mart_clinical_survey_linkage"]
  n16_gold_mart_patient_360 --> n20_gold_mart_clinical_survey_linkage
  n18_gold_fact_survey_response --> n20_gold_mart_clinical_survey_linkage
  n21_gold_cohort_inpatient_utilizers["gold.cohort_inpatient_utilizers"]
  n13_gold_fact_encounter --> n21_gold_cohort_inpatient_utilizers
  n22_gold_cohort_t2dm_phq9["gold.cohort_t2dm_phq9"]
  n14_gold_fact_lab_result --> n22_gold_cohort_t2dm_phq9
  n18_gold_fact_survey_response --> n22_gold_cohort_t2dm_phq9
```
