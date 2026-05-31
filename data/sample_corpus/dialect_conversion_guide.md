# On-Prem Oracle to BigQuery Dialect Guide

## Common replacements

| Oracle | BigQuery |
|--------|----------|
| ROWNUM | ROW_NUMBER() OVER () |
| NVL(a,b) | IFNULL(a,b) |
| SYSDATE | CURRENT_TIMESTAMP() |

## Merge patterns

Use `MERGE` for upserts with explicit join keys. Validate row counts between source and target during cutover weekends.

## Validation

Each converted script should run against a sampled dataset with reconciliation tolerance documented in the migration workbook.
