"""Tests for BigQuery SQL syntax validation."""

from __future__ import annotations

from pr_governance_agent.graph.llm import evaluate_with_llm_or_heuristic
from pr_governance_agent.sql.bigquery_validator import (
    bigquery_syntax_findings,
    extract_added_sql_from_patch,
    extract_sql_from_patch,
    validate_bigquery_sql,
)
from pr_governance_agent.state import PRReviewState


def test_extract_added_sql_from_patch():
    patch = "+++ b/models/mart.sql\n+SELECT id\n+FROM payments"
    assert "SELECT id" in extract_added_sql_from_patch(patch)
    assert "+++" not in extract_added_sql_from_patch(patch)


def test_valid_bigquery_sql_passes():
    sql = "SELECT payment_id, event_date FROM payments WHERE event_date = DATE '2024-01-01'"
    assert validate_bigquery_sql(sql) == []


def test_valid_dbt_sql_passes_after_jinja_neutralization():
    sql = "SELECT payment_id\nFROM {{ ref('stg_payments') }}\nWHERE event_date >= DATE('2024-01-01')"
    assert validate_bigquery_sql(sql) == []


def test_invalid_bigquery_sql_fails():
    sql = "SELECT payment_id, event_date FROM payments WHERE (event_date = '2024-01-01'"
    errors = validate_bigquery_sql(sql)
    assert errors


def test_bigquery_syntax_findings_on_invalid_patch():
    state: PRReviewState = {
        "patches": [
            {
                "filename": "sql/broken_extract.sql",
                "patch": (
                    "+++ b/sql/broken_extract.sql\n"
                    "+SELECT payment_id, event_date\n"
                    "+FROM payments\n"
                    "+WHERE (event_date >= DATE '2024-01-01'"
                ),
            }
        ]
    }
    findings = bigquery_syntax_findings(state)
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert findings[0]["category"] == "sql_syntax"
    assert "Invalid BigQuery SQL syntax" in findings[0]["message"]


def test_trailing_comma_before_from_fails():
    sql = """SELECT
  store_loc,
  store_id,
  created_user,
FROM stg_payments
WHERE event_date >= DATE('2025-01-01')"""
    errors = validate_bigquery_sql(sql)
    assert errors
    assert any("Trailing comma" in err for err in errors)


def test_pr8_style_patch_fails():
    patch = """@@ -6,5 +6,6 @@ SELECT
   store_loc,
   store_id,
   store_zipcode,
+  created_user,
 FROM stg_payments
 WHERE event_date >= DATE('2025-01-01')"""
    sql = extract_sql_from_patch(patch)
    assert validate_bigquery_sql(sql)
    state: PRReviewState = {
        "patches": [{"filename": "models/marts/fact_payments.sql", "patch": patch}]
    }
    findings = bigquery_syntax_findings(state)
    assert findings
    assert findings[0]["severity"] == "high"


def test_heuristic_mode_flags_invalid_syntax():
    from unittest.mock import patch

    with patch("pr_governance_agent.graph.llm._get_llm", return_value=None):
        state: PRReviewState = {
            "patches": [
                {
                    "filename": "models/marts/broken.sql",
                    "patch": (
                        "+++ b/models/marts/broken.sql\n"
                        "+SELECT id\n"
                        "+FROM t\n"
                        "+WHERE (id > 1"
                    ),
                }
            ],
            "warnings": [],
            "token_usage": {},
        }
        findings = evaluate_with_llm_or_heuristic(state, "requirements", [])
        assert any(f["category"] == "sql_syntax" for f in findings)
