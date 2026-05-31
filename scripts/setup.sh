#!/usr/bin/env bash
# One-shot setup for fresh clones: venv, install, .env, RAG ingest, sample DB.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python
fi

echo "==> Using Python: $($PYTHON --version)"

if [ ! -d ".venv" ]; then
  echo "==> Creating virtual environment (.venv)"
  "$PYTHON" -m venv .venv
else
  echo "==> Virtual environment already exists (.venv)"
fi

if [ -f ".venv/Scripts/activate" ]; then
  # Windows (Git Bash, MSYS)
  # shellcheck disable=SC1091
  source ".venv/Scripts/activate"
elif [ -f ".venv/bin/activate" ]; then
  # macOS / Linux
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
else
  echo "ERROR: Could not find venv activate script" >&2
  exit 1
fi

echo "==> Installing package (editable) with dev extras"
pip install -U pip
pip install -e ".[dev]"

if [ ! -f ".env" ]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
  echo "    Edit .env before live GitHub or LLM runs."
else
  echo "==> .env already exists (skipped)"
fi

echo "==> Ingesting policy corpus into Chroma (required for RAG citations)"
python scripts/ingest_docs.py

echo "==> Preloading cross-encoder reranker model"
python -c "from pr_governance_agent.rag.reranker import _load_cross_encoder; _load_cross_encoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

echo "==> Seeding local SQLite sample DB (optional migration demo data)"
python scripts/seed_sample_db.py

echo ""
echo "Setup complete."
echo ""
echo "Offline demo (Git Bash / macOS / Linux):"
echo "  export USE_PR_FIXTURE=true"
echo "  export HEURISTIC_ONLY=true"
echo "  python scripts/run_graph_cli.py"
echo ""
echo "Offline demo (Windows CMD):"
echo "  set USE_PR_FIXTURE=true"
echo "  set HEURISTIC_ONLY=true"
echo "  python scripts/run_graph_cli.py"
