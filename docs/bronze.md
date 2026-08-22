# Bronze

Landing files land here first. We keep the payload close to source shape, add
technical columns (ingest time, source file, row hash), and turn on change data
feed so downstream rebuilds can be incremental.

Local path: batch CSV load via scripts/ingest_bronze.py.
Cloud path: Auto Loader / DLT under pipelines/dlt/.
