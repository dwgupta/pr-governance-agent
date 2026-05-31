# PR Governance Agent (Capstone)

Agentic GitHub PR review for **data engineering migration** workflows (on-prem → BigQuery). Uses **LangGraph**, **ChromaDB RAG**, optional **Semgrep**, and **GitHub** integration (REST + optional MCP bridge).

## Documentation

- [Technical design](docs/pr-governance-agent-technical-design.md)
- [Architecture diagrams](docs/pr-governance-agent-architecture.md)

## Prerequisites

- Python 3.11+ (project `.venv` uses 3.11)
- Optional: [Semgrep](https://semgrep.dev/) for `ENABLE_SAST=true`
- Optional: Node.js if using the GitHub MCP server via `GITHUB_MCP_COMMAND`

## Setup

```bash
cd capstone
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
pip install -e ".[dev]"           # optional: pytest

copy .env.example .env            # edit as needed
python scripts/ingest_docs.py
```

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

```bash
set USE_PR_FIXTURE=true
set HEURISTIC_ONLY=true
python scripts/run_graph_cli.py
python eval/run_eval.py
```

## Run (live GitHub)

```bash
set USE_PR_FIXTURE=false
set GITHUB_TOKEN=ghp_...
python scripts/run_graph_cli.py --pr-url https://github.com/owner/repo/pull/42
```

## Streamlit UI

```bash
streamlit run app/streamlit_app.py
```

## Modes

| Mode | Behavior |
|------|----------|
| **advisory** (default) | Generate review brief; no merge |
| **auto** | Approve/merge only if `ALLOW_WRITE_ACTIONS=true` and `SANDBOX_REPO` matches |

## Project layout

```
src/pr_governance_agent/   # Agent core
app/streamlit_app.py       # UI
scripts/                   # CLI, ingest, MCP bridge
eval/                      # Offline eval cases
data/sample_corpus/        # Policy documents
docs/                      # Design + architecture
```

## Tests

```bash
set USE_PR_FIXTURE=true
set HEURISTIC_ONLY=true
pytest tests/ -q
```

## Capstone planner skill

POC planning rules live under `.cursor/skills/capstone-poc-planner/`. Sync rules after edits:

```bash
python scripts/sync_cursor_rules.py
```
