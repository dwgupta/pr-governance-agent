# BigQuery Migration Engineering Requirements

## Partitioning and clustering

All fact tables larger than 10 GB must partition on `event_date` (DATE type). Clustering should include high-cardinality filter columns used in WHERE clauses. Every query against partitioned tables must include a partition filter in production jobs.

## SQL dialect conversion

Migrated SQL must not contain Oracle-specific syntax: `ROWNUM`, `(+)` outer-join notation, or `NVL` without approval. Use `IFNULL`, `COALESCE`, and standard ANSI joins. `SELECT *` is discouraged on production marts; explicit column lists are required.

## dbt and testing

Every new mart model must include schema tests for `not_null` on primary keys and `unique` where applicable. Documentation blocks in `schema.yml` are required for exposure to downstream consumers.

## Cost controls

Avoid full-table scans without partition predicates. Staging tables should expire after 30 days unless tagged `retain=true` in model config.
