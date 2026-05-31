# PR Governance Agent (Capstone)

Agentic GitHub PR review for **data engineering migration** workflows (on-prem → BigQuery). Uses **LangGraph**, **ChromaDB RAG**, optional **Semgrep**, and **GitHub** integration (REST + optional MCP bridge).

## Documentation

- [Technical design](docs/pr-governance-agent-technical-design.md)
- [Architecture diagrams](docs/pr-governance-agent-architecture.md)

## Prerequisites

- Python 3.11+
- Optional: [Semgrep](https://semgrep.dev/) for `ENABLE_SAST=true`
- Optional: Node.js if using the GitHub MCP server via `GITHUB_MCP_COMMAND`

## Quick start (fresh clone)

One-shot setup (Git Bash, macOS, or Linux):

```bash
git clone https://github.com/dwgupta/pr-governance-agent.git
cd pr-governance-agent
bash scripts/setup.sh
```

Then run the offline demo:

```bash
export USE_PR_FIXTURE=true
export HEURISTIC_ONLY=true
python scripts/run_graph_cli.py
```

## Setup (manual)

```bash
cd capstone
python -m venv .venv

# Activate venv
source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate     # macOS / Linux
# .venv\Scripts\activate        # Windows CMD / PowerShell

pip install -e ".[dev]"
cp .env.example .env            # macOS / Linux / Git Bash
# copy .env.example .env        # Windows CMD
```

### Required: build the RAG index

Policy citations **do not work** until you ingest the sample corpus into Chroma:

```bash
python scripts/ingest_docs.py
```

If you skip this step, the agent still runs (heuristic checks work), but reviews will show warnings and no retrieved policy context. Streamlit and the CLI surface this explicitly.

### Optional: local migration sample data

Seed a SQLite `payments` table aligned with BigQuery partition examples (`event_date`, `payment_id`, `amount_usd`):

```bash
python scripts/seed_sample_db.py
# writes data/sample.db (gitignored)
```

Useful for migration demos; the PR governance agent reads SQL from PR diffs/fixtures, not this database directly.

## LangSmith (tracing + token usage)

1. Sign up at [smith.langchain.com](https://smith.langchain.com).
2. **Settings → API Keys → Create API Key** (value starts with `lsv2_pt_...`).
3. Add to `.env`:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_your_key_here
LANGSMITH_PROJECT=pr-governance-agent
```

4. Run the agent (CLI or Streamlit). Each LLM call appears under your project in the LangSmith UI with **token counts** and latency.

Legacy names `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, and `LANGCHAIN_PROJECT` also work.

Tracing is off when `HEURISTIC_ONLY=true` (no LLM calls). Eval sets that flag by default.

## Run (offline demo)

Uses fixtures under `eval/fixtures/` — no GitHub token required.

**Git Bash / macOS / Linux:**

```bash
export USE_PR_FIXTURE=true
export HEURISTIC_ONLY=true
python scripts/run_graph_cli.py
python eval/run_eval.py
```

**Windows CMD:**

```cmd
set USE_PR_FIXTURE=true
set HEURISTIC_ONLY=true
python scripts/run_graph_cli.py
python eval/run_eval.py
```

## Run (live GitHub)

**Git Bash / macOS / Linux:**

```bash
export USE_PR_FIXTURE=false
export GITHUB_TOKEN=ghp_...
python scripts/run_graph_cli.py --pr-url https://github.com/owner/repo/pull/42
```

**Windows CMD:**

```cmd
set USE_PR_FIXTURE=false
set GITHUB_TOKEN=ghp_...
python scripts/run_graph_cli.py --pr-url https://github.com/owner/repo/pull/42
```

## Streamlit UI

```bash
streamlit run app/streamlit_app.py
```

Set `USE_PR_FIXTURE=true` in `.env` for offline demo without GitHub API calls.

## Modes

| Mode | Behavior |
|------|----------|
| **advisory** (default) | Generate review brief; no merge |
| **auto** | Approve/merge only if `ALLOW_WRITE_ACTIONS=true` and `SANDBOX_REPO` matches |

## Project layout

```
src/pr_governance_agent/   # Agent core
app/streamlit_app.py       # UI
scripts/                   # CLI, ingest, setup, MCP bridge
eval/                      # Offline eval cases
data/sample_corpus/        # Policy documents (ingest into Chroma)
data/sample.db             # Optional SQLite staging (seed script)
docs/                      # Design + architecture
```

## Tests

**Git Bash / macOS / Linux:**

```bash
export USE_PR_FIXTURE=true
export HEURISTIC_ONLY=true
pytest tests/ -q
```

**Windows CMD:**

```cmd
set USE_PR_FIXTURE=true
set HEURISTIC_ONLY=true
pytest tests/ -q
```

CI runs on every push/PR to `main` (`.github/workflows/ci.yml`): install, ingest, pytest, eval.

## Capstone planner skill

POC planning rules live under `.cursor/skills/capstone-poc-planner/`. Sync rules after edits:

```bash
python scripts/sync_cursor_rules.py
```
