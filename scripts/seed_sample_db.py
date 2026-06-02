#!/usr/bin/env python3
"""Seed local SQLite sample DB with a payments staging table.

Simulates on-prem Oracle staging for BigQuery migration demos. Columns align
with eval/fixtures/sample_pr.json (fact_payments mart) and
data/sample_corpus/bigquery_migration_requirements.md (event_date partitioning).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "sample.db"

CREATE_PAYMENTS = """
CREATE TABLE payments (
    payment_id   INTEGER PRIMARY KEY,
    event_date   TEXT NOT NULL,
    amount_usd   REAL NOT NULL,
    customer_id  INTEGER NOT NULL,
    currency     TEXT NOT NULL DEFAULT 'USD',
    status       TEXT NOT NULL DEFAULT 'completed'
)
"""

# ISO dates span multiple months so partition-filter queries are meaningful.
SEED_ROWS: list[tuple[int, str, float, int, str, str]] = [
    (1001, "2024-01-05", 49.99, 501, "USD", "completed"),
    (1002, "2024-01-12", 120.00, 502, "USD", "completed"),
    (1003, "2024-01-18", 8.50, 503, "USD", "refunded"),
    (1004, "2024-02-03", 250.00, 504, "USD", "completed"),
    (1005, "2024-02-14", 19.99, 505, "EUR", "completed"),
    (1006, "2024-02-28", 75.25, 506, "USD", "completed"),
    (1007, "2024-03-10", 300.00, 507, "USD", "completed"),
    (1008, "2024-03-22", 42.00, 508, "USD", "completed"),
    (1009, "2024-04-01", 15.75, 509, "USD", "completed"),
    (1010, "2024-04-15", 999.00, 510, "USD", "completed"),
    (1011, "2024-05-01", 33.33, 511, "USD", "completed"),
    (1012, "2024-05-20", 61.00, 512, "USD", "completed"),
    (1013, "2024-06-08", 88.88, 513, "USD", "completed"),
    (1014, "2024-06-30", 5.00, 514, "USD", "completed"),
    (1015, "2024-07-04", 177.60, 515, "USD", "completed"),
    (1016, "2024-08-11", 220.00, 516, "USD", "completed"),
    (1017, "2024-09-02", 14.99, 517, "USD", "completed"),
    (1018, "2024-10-19", 430.50, 518, "USD", "completed"),
    (1019, "2024-11-27", 67.00, 519, "USD", "completed"),
    (1020, "2024-12-31", 1500.00, 520, "USD", "completed"),
    (1021, "2025-01-08", 29.99, 521, "USD", "completed"),
    (1022, "2025-02-14", 45.00, 522, "USD", "completed"),
    (1023, "2025-03-21", 112.00, 523, "USD", "completed"),
    (1024, "2025-04-30", 78.25, 524, "USD", "completed"),
    (1025, "2025-05-15", 199.99, 525, "USD", "completed"),
    (1026, "2025-06-01", 55.55, 526, "USD", "completed"),
    (1027, "2025-07-19", 90.00, 527, "USD", "completed"),
    (1028, "2025-08-08", 12.00, 528, "USD", "refunded"),
    (1029, "2025-09-09", 340.00, 529, "USD", "completed"),
    (1030, "2025-10-31", 21.50, 530, "USD", "completed"),
    (1031, "2025-11-11", 64.00, 531, "USD", "completed"),
    (1032, "2025-12-25", 500.00, 532, "USD", "completed"),
    (1033, "2026-01-03", 38.00, 533, "USD", "completed"),
    (1034, "2026-02-18", 72.00, 534, "USD", "completed"),
    (1035, "2026-03-07", 156.40, 535, "USD", "completed"),
    (1036, "2026-04-12", 44.44, 536, "USD", "completed"),
    (1037, "2026-05-01", 99.99, 537, "USD", "completed"),
    (1038, "2026-05-15", 18.00, 538, "USD", "completed"),
    (1039, "2026-05-22", 210.00, 539, "USD", "completed"),
    (1040, "2026-05-30", 33.00, 540, "USD", "completed"),
]

INSERT_PAYMENTS = """
INSERT INTO payments (payment_id, event_date, amount_usd, customer_id, currency, status)
VALUES (?, ?, ?, ?, ?, ?)
"""

PARTITION_FILTER_QUERY = """
SELECT payment_id, event_date, amount_usd
FROM payments
WHERE event_date >= '2024-01-01'
ORDER BY event_date, payment_id
"""


def seed(db_path: Path) -> int:
    """Create payments table, indexes, and demo rows; return row count."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DROP TABLE IF EXISTS payments")
        conn.execute(CREATE_PAYMENTS)
        conn.executemany(INSERT_PAYMENTS, SEED_ROWS)
        conn.execute(
            "CREATE INDEX idx_payments_event_date ON payments (event_date)"
        )
        conn.execute(
            "CREATE INDEX idx_payments_customer_id ON payments (customer_id)"
        )
        conn.commit()

        row_count = conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        date_range = conn.execute(
            "SELECT MIN(event_date), MAX(event_date) FROM payments"
        ).fetchone()
        partition_rows = conn.execute(PARTITION_FILTER_QUERY).fetchall()
    finally:
        conn.close()

    print(f"Wrote {db_path}")
    print(f"  table: payments ({row_count} rows)")
    print(f"  event_date range: {date_range[0]} .. {date_range[1]}")
    print(f"  partition-filter demo (event_date >= '2024-01-01'): {len(partition_rows)} rows")
    return row_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite file path (default: {DEFAULT_DB_PATH.relative_to(ROOT)})",
    )
    args = parser.parse_args()
    try:
        seed(args.db_path.resolve())
    except sqlite3.Error as exc:
        print(f"Failed to seed database: {exc}", file=sys.stderr)
        return 1
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
