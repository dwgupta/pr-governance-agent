# Data Security and PII Policy

## Prohibited raw fields

Production datasets must not store raw government identifiers (SSN), full payment card numbers, or unmasked email addresses in analytics marts. Use salted hashing or tokenization approved by InfoSec.

## Secrets management

API keys, database passwords, and private keys must not appear in source code, workflow YAML, or SQL files. Use Secret Manager references in Composer and GitHub Actions secrets.

## Logging

Application and pipeline logs must redact PII. Structured logs may include internal customer tokens only when documented in the data catalog.

## PR declarations

If a pull request description claims "no PII changes", the diff must not introduce new PII-classified columns. Contradictions require security review before merge.
