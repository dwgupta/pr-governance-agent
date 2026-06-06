"""BigQuery SQL syntax validation for added/changed SQL in PR diffs."""

from __future__ import annotations

import re

import sqlglot
from sqlglot.errors import ParseError

from pr_governance_agent.state import Finding, PRReviewState

_SQL_KEYWORDS = re.compile(
    r"\b(SELECT|WITH|INSERT|UPDATE|DELETE|MERGE|CREATE|REPLACE|TRUNCATE)\b",
    re.I,
)
_DBT_JINJA = re.compile(r"\{\{[^}]+\}\}")
_DBT_BLOCKS = re.compile(r"\{%-?[^%]*-?%\}", re.S)
_TRAILING_COMMA_BEFORE_CLAUSE = re.compile(
    r",\s*(?:\n\s*)?"
    r"(FROM|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|UNION|QUALIFY|WINDOW|"
    r"(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN)\b",
    re.I,
)

_HUNK_HEADER = re.compile(r"^@@\s[^@]*@@\s?(.*)$")


SYNTAX_CITATION = "bigquery_migration_requirements.md / BigQuery SQL syntax"


def is_sql_change(filename: str) -> bool:
    """True when the changed file looks like SQL (path or extension)."""
    normalized = filename.replace("\\", "/").lower()
    return normalized.endswith(".sql") or "/sql/" in f"/{normalized}/"


def extract_added_sql_from_patch(patch: str) -> str:
    """Collect added lines from a unified diff as SQL text."""
    lines: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    return "\n".join(lines).strip()


def extract_sql_from_patch(patch: str) -> str:
    """Reconstruct post-change SQL from unified diff context and added lines."""
    lines: list[str] = []
    for line in patch.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("@@"):
            header = _HUNK_HEADER.match(line)
            if header:
                fragment = header.group(1).strip()
                if fragment:
                    lines.append(fragment)
            continue
        if line.startswith("+"):
            lines.append(line[1:])
        elif line.startswith("-"):
            continue
        elif line.startswith(" "):
            lines.append(line[1:])
    return "\n".join(lines).strip()


def _prepare_sql_for_parse(sql: str) -> str:
    """Neutralize dbt/Jinja templating so BigQuery parsing can run on model SQL."""
    prepared = _DBT_BLOCKS.sub("", sql)
    prepared = _DBT_JINJA.sub("placeholder_table", prepared)
    return prepared.strip()


def _trailing_comma_errors(sql: str) -> list[str]:
    """Detect trailing commas before SQL clauses (invalid in BigQuery, missed by sqlglot)."""
    if _TRAILING_COMMA_BEFORE_CLAUSE.search(sql):
        return ["Trailing comma before SQL clause (invalid BigQuery syntax)"]
    return []


def validate_bigquery_sql(sql: str) -> list[str]:
    """Return parse error messages for invalid BigQuery SQL; empty list when valid."""
    prepared = _prepare_sql_for_parse(sql)
    if not prepared:
        return []
    if not _SQL_KEYWORDS.search(prepared):
        return []

    errors = _trailing_comma_errors(prepared)
    if errors:
        return errors

    try:
        statements = sqlglot.parse(prepared, read="bigquery")
    except ParseError as exc:
        return [str(exc).strip() or "BigQuery SQL parse error"]

    if not statements:
        return ["No parseable BigQuery SQL statements found"]

    for statement in statements:
        if statement is None:
            errors.append("Empty SQL statement")
    return errors


def bigquery_syntax_findings(state: PRReviewState) -> list[Finding]:
    """Emit high-severity requirements findings for invalid BigQuery SQL in PR patches."""
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()

    for patch in state.get("patches") or []:
        filename = patch.get("filename") or ""
        if not is_sql_change(filename):
            continue

        patch_text = patch.get("patch") or ""
        candidate_sql = extract_sql_from_patch(patch_text) or extract_added_sql_from_patch(patch_text)
        if not candidate_sql:
            continue

        for error in validate_bigquery_sql(candidate_sql):
            key = (filename, error)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    severity="high",
                    category="sql_syntax",
                    message=f"Invalid BigQuery SQL syntax: {error}",
                    file=filename,
                    citation=SYNTAX_CITATION,
                )
            )

    return findings
