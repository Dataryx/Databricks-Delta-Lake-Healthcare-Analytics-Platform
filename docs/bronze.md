# Bronze layer

Append-only capture of landing files into Delta with technical metadata only.

## Contract

| Column | Meaning |
|--------|---------|
| `_ingest_ts` | UTC ingest timestamp |
| `_source_system` | `synthea_sim` or `survey_sim` |
| `_source_file` | Landing path |
| `_file_modification_time` | Source file mtime |
| `_batch_id` | Replayable batch id |
| `_record_hash` | SHA-256 of business payload |
| `_rescued_data` | Auto Loader rescued column (null in local batch) |
| `_ingest_pipeline_version` | Pipeline code version |

## Local demo

```bash
make generate-synthetic
make ingest-bronze
```

Re-running `ingest-bronze` is a no-op for unchanged rows (hash anti-join).

## Cloud

`try_autoloader_stream` uses `cloudFiles` with `schemaEvolutionMode=addNewColumns`
and `rescuedDataColumn`. On local Spark it logs and returns `None` (see ADR 0003).
