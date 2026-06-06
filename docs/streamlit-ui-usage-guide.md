# Streamlit UI Usage Guide

This guide shows how to run and use the **PR Governance Agent** in the browser with Streamlit.

For CLI, eval, and advanced setup, see [PR Governance Agent Usage Guide](pr-governance-agent-usage-guide.md).

---

## What you get in the UI

The Streamlit app (`app/streamlit_app.py`) lets you:

1. Enter a GitHub PR URL
2. Choose **advisory** or **auto** mode
3. Click **Run review** to execute the full agent workflow
4. See pass/fail, risk level, blockers, warnings, and a markdown review

---

## Step 1: One-time setup

Open a terminal in the project folder and run:

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate     # macOS / Linux

pip install -e ".[dev]"
cp .env.example .env
python scripts/ingest_docs.py
```

**Why ingest?** Policy documents must be loaded into Chroma. Without this, the sidebar may show warnings and reviews will have less policy context.

Edit `.env` for how you want to run (see Step 2).

---

## Step 2: Choose how you want to run

You can configure the app in two ways:

1. **Sidebar toggles (recommended)** — change settings in the UI; they apply on the next **Run review** (no restart).
2. **`.env` file** — defaults loaded when Streamlit starts (sidebar can override at runtime).

### Sidebar runtime settings

In the left sidebar, use:

| Toggle / field | Purpose |
|----------------|---------|
| **Use PR fixture (offline)** | Load PR from local JSON instead of GitHub |
| **Heuristic only (no LLM)** | Regex checks only; no OpenAI calls |
| **Allow write actions** | Enable auto approve/merge (with auto mode) |
| **Post PR comments** | Post review as a GitHub comment |
| **Enable SAST (Semgrep)** | Run Semgrep on patches |
| **LangSmith tracing** | Turn tracing on/off (key still from `.env`) |
| **Sandbox repo** | `owner/repo` allowed for auto actions |
| **PR fixture path** | Optional path, e.g. `docs/samples/failed_select_star_pr_fixture.json` |

Optional API key overrides (leave blank to use `.env`).

**Effective status** below the toggles shows what the next run will use.

---

### Or set defaults in `.env` before starting Streamlit

### Option A — Offline demo (no GitHub token)

Good for first-time use and capstone demos.

```env
USE_PR_FIXTURE=true
HEURISTIC_ONLY=true
```

- PR URL in the UI is mostly for display; data comes from local JSON fixtures.
- No OpenAI calls (rule-based checks only).

### Option B — Offline with LLM

```env
USE_PR_FIXTURE=true
HEURISTIC_ONLY=false
OPENAI_API_KEY=sk-...
```

- Still uses fixtures, but evaluation uses OpenAI.

### Option C — Live GitHub PR

```env
USE_PR_FIXTURE=false
GITHUB_TOKEN=ghp_...
HEURISTIC_ONLY=true
```

Or set `HEURISTIC_ONLY=false` and `OPENAI_API_KEY=...` for LLM review.

Use a real PR URL, for example:

`https://github.com/dwgupta/migration-sandbox-capstone/pull/1`

**Note:** If the repo has no open PRs yet, ingest may fail and the review will show **Passed: No** with a blocker about PR ingest.

---

## Step 3: Start Streamlit

From the project root (with venv activated):

```bash
streamlit run app/streamlit_app.py
```

Your browser should open automatically (usually `http://localhost:8501`).

**Terminal noise?** If you see many `ModuleNotFoundError: No module named 'torchvision'` lines, they come from Streamlit’s file watcher scanning optional `transformers` vision models. This project disables that watcher in `.streamlit/config.toml` (not required for PR governance). Restart Streamlit after pulling the latest code.

---

## Step 4: Use the screen

### Left sidebar — Runtime settings + Effective status

Use the toggles to change behavior without editing `.env`. Then check **Effective status**:

| Item | Meaning |
|------|---------|
| **LLM enabled** | `true` only if OpenAI key is set and **Heuristic only** is off |
| **LangSmith tracing** | `on` if tracing toggle is on and key is in `.env` |
| **Offline fixture mode** | Same as **Use PR fixture** toggle |
| **Write actions allowed** | Same as **Allow write actions** toggle |
| **Yellow warnings** | Often means Chroma index is empty — run `python scripts/ingest_docs.py` |

### Main area — Inputs

1. **GitHub PR URL**  
   Default: `https://github.com/dwgupta/migration-sandbox-capstone/pull/1`  
   Change this when using live GitHub mode.

2. **Mode**
   - **advisory** (recommended): Generates a review only. Does not merge the PR.
   - **auto**: May approve/merge only if review passes **and** `ALLOW_WRITE_ACTIONS=true` **and** the PR repo matches `SANDBOX_REPO`.

3. **Run review**  
   Starts the agent. The page **auto-refreshes every second** until the workflow finishes (you should see **Agent running…**, then results).

4. **Clear results**  
   Clears the last review from the page.

---

## Step 5: Read the results

After a run completes, you will see:

| Section | What it tells you |
|---------|-------------------|
| **Overall risk** | `low`, `medium`, `high`, or `blocked` |
| **Passed** | `Yes` / `No` — final governance decision |
| **Blockers** (red) | Why the PR failed (e.g. policy violations, ingest failure) |
| **Warnings** (yellow) | Non-fatal issues (empty RAG index, LLM fallback, etc.) |
| **GitHub actions taken** | What the agent did (e.g. `advisory_review_generated`) |
| **Node timings** | How long each workflow step took (seconds) |
| **Review** | Full markdown report with requirements/security findings |
| **Raw state** | Complete JSON state for debugging |

### Quick interpretation

- **Passed = Yes, risk = low** → PR looks compliant for the checks run.
- **Passed = No** → Open **Blockers** and **Review** for details.
- **Review shows "Untitled"** → Often means PR ingest failed (check **Raw state** → `errors`).

---

## Step 6: Example workflow (offline)

1. In `.env`: `USE_PR_FIXTURE=true`, `HEURISTIC_ONLY=true`
2. Run: `streamlit run app/streamlit_app.py`
3. Keep the default PR URL (or any valid GitHub PR URL format)
4. Mode: **advisory**
5. Click **Run review**
6. Read **Passed**, **Overall risk**, and the **Review** section

To test a failing case offline, point the fixture env var before starting Streamlit:

```bash
export PR_FIXTURE_PATH=docs/samples/failed_select_star_pr_fixture.json
streamlit run app/streamlit_app.py
```

---

## Step 7: Example workflow (live GitHub)

1. In `.env`: `USE_PR_FIXTURE=false`, set `GITHUB_TOKEN`
2. Restart Streamlit (so it reloads `.env`)
3. Enter your real PR URL, e.g. `https://github.com/dwgupta/migration-sandbox-capstone/pull/2`
4. Mode: **advisory**
5. Click **Run review**

---

## Common issues

| Problem | What to do |
|---------|------------|
| Sidebar warns about empty Chroma | Run `python scripts/ingest_docs.py`, restart Streamlit |
| LLM enabled is **false** | Set `OPENAI_API_KEY` and `HEURISTIC_ONLY=false` in `.env`, restart |
| Passed = No, ingest error in Raw state | PR/repo missing or token lacks access; fix URL or token |
| Auto mode does nothing | Expected if `ALLOW_WRITE_ACTIONS=false` (default) |
| Run is slow on first click | Reranker model download; later runs are faster |

---

## Optional: post review as a GitHub comment

In `.env`:

```env
POST_PR_COMMENTS=true
USE_PR_FIXTURE=false
GITHUB_TOKEN=ghp_...
```

Requires a valid token with permission to comment on the PR.

---

## Related docs

- [Full usage guide (CLI, eval, connectivity)](pr-governance-agent-usage-guide.md)
- [Sample PR fixtures](samples/success_pr_fixture.json)
