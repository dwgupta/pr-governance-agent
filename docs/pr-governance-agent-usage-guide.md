# PR Governance Agent Usage Guide

Audience: capstone reviewers and ETL developers

This guide explains how to run the PR Governance Agent for PRs in `dwgupta/migration-sandbox-capstone` in two modes:

- Part A: Heuristic evaluation + RAG (no OpenAI)
- Part B: OpenAI via LangChain (`ChatOpenAI`) + optional LangSmith tracing

It also includes:

- End-to-end setup and run steps
- New sample PR fixtures under `docs/samples/`
- Full live GitHub path
- Connectivity testing for GitHub, OpenAI, LangChain, LangSmith, Chroma, Semgrep, MCP bridge, and SMTP

---

## 1) What the agent does

The workflow is implemented in `src/pr_governance_agent/graph/builder.py` and `src/pr_governance_agent/graph/nodes.py`:

1. Ingest PR (`ingest_pr`)
2. Retrieve policy context from Chroma RAG (`rag_requirements`, `rag_security_policies`)
3. Optional SAST (`run_sast_optional`) when `ENABLE_SAST=true`
4. Evaluate requirements and security (`evaluate_requirements`, `evaluate_security`)
5. Build markdown review (`synthesize_review`)
6. Route decision (`route_decision`)
7. Advisory actions + optional auto actions (`execute_github_advisory`, `execute_github_auto`)
8. Notify team (`notify_team`)

PR URLs and fixtures in this repo are now aligned to:
- `https://github.com/dwgupta/migration-sandbox-capstone/pull/<number>`
- Repo slug `dwgupta/migration-sandbox-capstone`

---

## 2) Prerequisites

- Python 3.11+
- Git Bash / Linux / macOS shell (or equivalent on Windows)
- Optional:
  - Semgrep for SAST checks (`ENABLE_SAST=true`)
  - OpenAI API key for LLM mode
  - LangSmith key for tracing

Install environment:

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"
cp .env.example .env
```

Build RAG index (required for policy retrieval):

```bash
python scripts/ingest_docs.py
```

---

## 3) Sample artifacts for migration PR simulation

Two new fixtures are provided in `docs/samples/`:

1. Success scenario:
   - `docs/samples/success_pr_fixture.json`
   - Uses explicit columns and partition filter (`event_date`)

2. Failure scenario (`SELECT *` violation):
   - `docs/samples/failed_select_star_pr_fixture.json`
   - Adds wildcard query that should be flagged

You can run the agent against either file by setting `PR_FIXTURE_PATH`.

---

## 4) Part A - Run without active LLM (heuristic + RAG)

This mode does not call OpenAI. It uses deterministic regex checks and retrieved policy chunks from Chroma.

### Step A1: Configure `.env`

Set these values:

```env
USE_PR_FIXTURE=true
HEURISTIC_ONLY=true
SANDBOX_REPO=dwgupta/migration-sandbox-capstone
ALLOW_WRITE_ACTIONS=false
```

### Step A2: Run success sample

```bash
export PR_FIXTURE_PATH=docs/samples/success_pr_fixture.json
python scripts/run_graph_cli.py --mode advisory
```

Expected outcome:
- `Passed: True`
- `Risk: low`
- Action contains `advisory_review_generated`

### Step A3: Run failed `SELECT *` sample

```bash
export PR_FIXTURE_PATH=docs/samples/failed_select_star_pr_fixture.json
python scripts/run_graph_cli.py --mode advisory
```

Expected outcome:
- `Passed: False`
- `Risk: high` (or blocked depending on additional findings)
- Requirements findings include `SELECT *` violation signal

### Step A4: Optional full offline eval suite

```bash
python eval/run_eval.py
```

This uses `eval/cases.yaml` in heuristic mode.

---

## 5) Part B - Run with LLM (OpenAI + LangChain) and optional LangSmith

This mode uses `langchain_openai.ChatOpenAI` in `src/pr_governance_agent/graph/llm.py`.

### Step B1: Configure `.env`

```env
USE_PR_FIXTURE=true
HEURISTIC_ONLY=false
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_BASE=
SANDBOX_REPO=dwgupta/migration-sandbox-capstone
ALLOW_WRITE_ACTIONS=false
```

Optional LangSmith tracing:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=pr-governance-agent
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

### Step B2: Run with sample fixtures in LLM mode

```bash
export PR_FIXTURE_PATH=docs/samples/success_pr_fixture.json
python scripts/run_graph_cli.py --mode advisory
```

Then:

```bash
export PR_FIXTURE_PATH=docs/samples/failed_select_star_pr_fixture.json
python scripts/run_graph_cli.py --mode advisory
```

### Step B3: Run LLM eval cases

```bash
python eval/run_eval.py --llm
```

This uses `eval/cases_llm.yaml`.

### Step B4: Optional Streamlit UI

```bash
streamlit run app/streamlit_app.py
```

Use PR URL:
- `https://github.com/dwgupta/migration-sandbox-capstone/pull/1`

---

## 6) Full live GitHub path for `dwgupta/migration-sandbox-capstone`

Use this when reviewing an actual PR from GitHub API (not fixture JSON).

### Step L1: Configure `.env`

```env
USE_PR_FIXTURE=false
GITHUB_TOKEN=ghp_...
SANDBOX_REPO=dwgupta/migration-sandbox-capstone
ALLOW_WRITE_ACTIONS=false
HEURISTIC_ONLY=true   # set false if running with OpenAI
```

### Step L2: Run advisory review on live PR

```bash
python scripts/run_graph_cli.py --pr-url https://github.com/dwgupta/migration-sandbox-capstone/pull/1 --mode advisory
```

### Step L3: Optional auto mode (guarded)

Auto approve/merge executes only if all are true:
- `--mode auto`
- `ALLOW_WRITE_ACTIONS=true`
- PR repo exactly matches `SANDBOX_REPO`
- Review passed (`passed=true`)

Command:

```bash
python scripts/run_graph_cli.py --pr-url https://github.com/dwgupta/migration-sandbox-capstone/pull/1 --mode auto
```

If safeguards do not match, action records include `auto_skipped_writes_not_allowed`.

---

## 7) Connectivity checks for all integrations

A new script is added:
- `scripts/check_connectivity.py`

Run all checks:

```bash
python scripts/check_connectivity.py
```

Run selected checks:

```bash
python scripts/check_connectivity.py --only github openai langchain langsmith chroma semgrep mcp smtp
```

### What each check validates

1. `github`
   - Calls `https://api.github.com/user` with `GITHUB_TOKEN`
   - Pass means token and network are valid

2. `openai`
   - Calls `<OPENAI_API_BASE or https://api.openai.com/v1>/models`
   - Pass means key and API reachability are valid

3. `langchain`
   - Instantiates `ChatOpenAI` and does a minimal invoke
   - Pass means LangChain-to-OpenAI path works

4. `langsmith`
   - Calls `<LANGSMITH_ENDPOINT>/projects` with `LANGSMITH_API_KEY`
   - Pass means tracing backend is reachable

5. `chroma`
   - Instantiates `ChromaStore` and reads collection counts
   - Warns if index is empty (run `scripts/ingest_docs.py`)

6. `semgrep`
   - Checks Semgrep executable on PATH

7. `mcp`
   - Runs command from `GITHUB_MCP_COMMAND` with JSON input
   - Expects PR payload keys: `repo`, `pr_number`, `patches`

8. `smtp`
   - Tries TCP connection to `SMTP_HOST:SMTP_PORT`

Exit code behavior:
- `0` if all checks are PASS/WARN (no hard failure)
- `1` if any check returns FAIL

---

## 8) Quick troubleshooting

- Missing policy citations or empty retrieval:
  - Run `python scripts/ingest_docs.py`

- LLM mode silently using fallback heuristics:
  - Check warnings for `LLM review fallback`
  - Verify `OPENAI_API_KEY` and `HEURISTIC_ONLY=false`

- Live GitHub not working:
  - Confirm `USE_PR_FIXTURE=false`
  - Confirm `GITHUB_TOKEN` scope and repo visibility

- Auto mode not approving/merging:
  - Ensure `ALLOW_WRITE_ACTIONS=true`
  - Ensure `SANDBOX_REPO=dwgupta/migration-sandbox-capstone`
  - Ensure mode is `auto` and review passed

---

## 9) Recommended execution order

1. `python scripts/ingest_docs.py`
2. `python scripts/check_connectivity.py`
3. Part A run (`HEURISTIC_ONLY=true`) with `docs/samples/` fixtures
4. Part B run (`HEURISTIC_ONLY=false`) with OpenAI key
5. Switch to live PR URL in `dwgupta/migration-sandbox-capstone`

