# Streamlit UI Usage Guide

This guide shows how to run and use the **PR Governance Agent** in the browser with Streamlit.

For CLI, eval, and advanced setup, see [PR Governance Agent Usage Guide](pr-governance-agent-usage-guide.md).

---

## What you get in the UI

The Streamlit app (`app/streamlit_app.py`) provides a dashboard with a soft purple theme where you can:

1. Enter a GitHub PR URL
2. Choose **advisory** or **auto** mode
3. Toggle runtime settings in the sidebar (no `.env` edit or restart required)
4. Click **Run review** to execute the full agent workflow
5. See pass/fail, risk level, blockers, warnings, markdown review, and optional LLM usage

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

Edit `.env` for defaults (see Step 2). Sidebar toggles can override most flags at runtime.

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
| **Heuristic only (no LLM)** | Regex + SQL syntax checks only; no OpenAI calls |
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

#### Option A — Offline demo (no GitHub token)

Good for first-time use and capstone demos.

```env
USE_PR_FIXTURE=true
HEURISTIC_ONLY=true
```

- PR URL in the UI is mostly for display; data comes from local JSON fixtures.
- BigQuery SQL syntax checks still run on `.sql` patches in fixtures.

#### Option B — Offline with LLM

```env
USE_PR_FIXTURE=true
HEURISTIC_ONLY=false
OPENAI_API_KEY=sk-...
```

- Still uses fixtures, but policy evaluation uses OpenAI (syntax checks always run).

#### Option C — Live GitHub PR

```env
USE_PR_FIXTURE=false
GITHUB_TOKEN=ghp_...
HEURISTIC_ONLY=true
```

Or set `HEURISTIC_ONLY=false` and `OPENAI_API_KEY=...` for LLM review.

Use a real PR URL, for example:

`https://github.com/dwgupta/migration-sandbox-capstone/pull/2`

**Note:** If ingest fails (404, auth), the review shows **Passed: No** with a fail-closed ingest blocker.

---

## Step 3: Start Streamlit

From the project root (with venv activated):

```bash
streamlit run app/streamlit_app.py
```

Your browser should open automatically (usually `http://localhost:8501`).

Theme and layout are configured in `.streamlit/config.toml` (lavender accent, wide layout).

**Terminal noise?** Optional `transformers` / `torchvision` watcher messages are suppressed via `fileWatcherType = "none"` in `.streamlit/config.toml`.

---

## Step 4: Use the screen

### Header

Header banner with app title and short description.

### Left sidebar — Runtime settings + Effective status

| Item | Meaning |
|------|---------|
| **LLM enabled** | `true` only if OpenAI key is set and **Heuristic only** is off |
| **LangSmith tracing** | `on` if tracing toggle is on and key is in `.env` |
| **Offline fixture mode** | Same as **Use PR fixture** toggle |
| **Write actions allowed** | Same as **Allow write actions** toggle |
| **Yellow warnings** | Often means Chroma index is empty — run `python scripts/ingest_docs.py` |

### Main area — Run review (bordered card)

1. **GitHub PR URL**  
   Default: `https://github.com/dwgupta/migration-sandbox-capstone/pull/1`

2. **Mode**
   - **advisory** (recommended): Generates a review only. Does not merge the PR.
   - **auto**: May approve/merge only if review passes, writes are allowed, sandbox matches, and PR is **not already merged**.

3. **Run review** / **Clear results**  
   The page **auto-refreshes every second** while the workflow runs.

---

## Step 5: Read the results

After a run completes, the **Results** card shows:

| Section | What it tells you |
|---------|-------------------|
| **Overall risk** / **Passed** | Side-by-side summary metrics |
| **Blockers** (red) | Why the PR failed (policy, syntax, ingest failure) |
| **Warnings** (yellow) | Non-fatal issues (empty RAG index, LLM fallback, **already merged PR in auto mode**) |
| **GitHub actions taken** | e.g. `advisory_review_generated`, `auto_skipped_already_merged` |
| **Node timings** | Seconds per workflow step |
| **Review** | Markdown report with requirements/security findings |
| **Per evaluation step** | Collapsed expander with LLM token usage and estimated cost (when LLM ran) |
| **Raw state** | Full JSON for debugging |

### Quick interpretation

- **Passed = Yes, risk = low** → PR looks compliant for the checks run.
- **Passed = No** → Open **Blockers** and **Review** for details.
- **sql_syntax finding** → Invalid BigQuery SQL in a changed `.sql` file (high severity, fails review).
- **Warning: PR is already merged** → Auto mode will not approve/merge again; use an open PR URL.
- **Review shows "Untitled"** → Often means PR ingest failed (check **Raw state** → `errors`).

---

## Step 6: Example workflows

### Offline — passing PR

1. Sidebar: **Use PR fixture** on, **Heuristic only** on
2. Optional: set **PR fixture path** to `docs/samples/success_pr_fixture.json`
3. Mode: **advisory** → **Run review**
4. Expect **Passed: Yes**, **risk: low**

### Offline — failing PR (`SELECT *`)

1. Set **PR fixture path** to `docs/samples/failed_select_star_pr_fixture.json`
2. **Run review** → **Passed: No**, high risk

### Offline — invalid BigQuery SQL

1. Set **PR fixture path** to `eval/fixtures/pr_invalid_bq_syntax.json`
2. **Run review** → **Passed: No**, finding category `sql_syntax`

### Live GitHub — syntax error PR

1. **Use PR fixture** off, valid `GITHUB_TOKEN` in `.env`
2. URL: `https://github.com/dwgupta/migration-sandbox-capstone/pull/8` (trailing comma before `FROM`)
3. **Heuristic only** on is enough to fail syntax checks
4. Expect **Passed: No**, **risk: high**

### Auto mode — already merged PR

1. **Allow write actions** on, mode **auto**
2. URL pointing to a **merged** PR (e.g. pull/1 if merged)
3. Expect warning: **PR is already merged — please validate your input**
4. **GitHub actions taken** includes `auto_skipped_already_merged`

---

## Common issues

| Problem | What to do |
|---------|------------|
| Sidebar warns about empty Chroma | Run `python scripts/ingest_docs.py`, restart Streamlit |
| LLM enabled is **false** | Set `OPENAI_API_KEY` and turn off **Heuristic only** |
| Passed = No, ingest error in Raw state | Fix URL, token, or repo access |
| Auto mode does nothing | Expected if **Allow write actions** is off, review failed, or PR already merged |
| PR passed with medium risk | Medium findings do not fail; only high/critical block |
| Run is slow on first click | Reranker model download; later runs are faster |
| Cost estimate looks wrong | Set `OPENAI_INPUT_COST_PER_1M` / `OPENAI_OUTPUT_COST_PER_1M` in `.env` for your model |

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

- [Full usage guide (CLI, eval, connectivity, SQL syntax)](pr-governance-agent-usage-guide.md)
- [Technical design](pr-governance-agent-technical-design.md)
- [Sample PR fixtures](samples/success_pr_fixture.json)
