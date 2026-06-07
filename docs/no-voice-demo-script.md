# No-voice demo script — PR Governance Agent (Streamlit + LLM)

Silent screen recording only. Each **Title card** is a full-screen slide (3–5 seconds). Each **Scene** lists exact UI clicks and what should appear before you cut to the next card.

**Validated against live GitHub (LLM on, advisory unless noted):**

| PR | URL | Expected |
|----|-----|----------|
| Pass | [#11](https://github.com/dwgupta/migration-sandbox-capstone/pull/11) | Passed: **Yes**, risk: **low** |
| Fail (requirements) | [#4](https://github.com/dwgupta/migration-sandbox-capstone/pull/4) | Passed: **No**, risk: **high**, requirements finding |
| Fail (SQL syntax) | [#8](https://github.com/dwgupta/migration-sandbox-capstone/pull/8) | Passed: **No**, risk: **high**, `sql_syntax` finding |
| Already merged | [#9](https://github.com/dwgupta/migration-sandbox-capstone/pull/9) | Advisory: pass review; **Auto**: warning + skip merge |

---

## Before recording (once)

1. Terminal:
   ```bash
   cd "e:/AI Learning/Gaurav Sen cohort/capstone"
   source .venv/Scripts/activate
   python scripts/ingest_docs.py
   streamlit run app/streamlit_app.py
   ```
2. Browser: open `http://localhost:8501` — full window, no bookmarks bar.
3. Confirm `.env` has `GITHUB_TOKEN`, `OPENAI_API_KEY`, `USE_PR_FIXTURE=false`, `HEURISTIC_ONLY=false`.
4. **Warm-up:** run PR #11 once (loads reranker model) before you start recording.

**Sidebar defaults for Scenes 1–4 (LLM + live GitHub):**

| Control | Setting |
|---------|---------|
| Use PR fixture (offline) | **Off** |
| Heuristic only (no LLM) | **Off** |
| Allow write actions | **Off** |
| Post PR comments | **Off** |
| Enable SAST | **Off** |
| LangSmith tracing | Your choice (does not affect UI token counts) |
| Sandbox repo | `dwgupta/migration-sandbox-capstone` |

**Effective status** should show: **LLM enabled: true**, **Offline fixture mode: false**.

---

## Scene 0 — Title card

**Text on slide:**

```
PR Governance Agent
Agentic PR review for data-engineering migrations
LangGraph · RAG · GitHub · LLM
```

**Action:** None (title only).

---

## Scene 1 — Title card

**Text on slide:**

```
Demo setup
Live GitHub · LLM enabled · Advisory mode
Repo: dwgupta/migration-sandbox-capstone
```

**Action:** Cut to Streamlit app.

**Clicks:**

1. Open **sidebar** (expanded).
2. Pause 2s on **Effective status** — show **LLM enabled: true**.
3. Main area: confirm **Mode** = **advisory** (first radio option).

---

## Scene 2 — Title card

**Text on slide:**

```
Scenario 1 — Compliant PR
Pull Request #11
Expected: Passed · Low risk
```

**Clicks:**

1. Click **GitHub PR URL** field → select all → paste:
   ```
   https://github.com/dwgupta/migration-sandbox-capstone/pull/11
   ```
2. Click **Run review**.
3. Wait for **Agent running…** to finish (page auto-refreshes).
4. Scroll to **Results** card.
5. Hold on:
   - **Overall risk:** `low`
   - **Passed:** `Yes`
6. Expand **Review** — scroll to **Requirements findings** → `- None` (or no high items).
7. Expand **Per evaluation step** — show `requirements` and `security` lines with token counts (LLM ran).
8. Click **Clear results**.

---

## Scene 3 — Title card

**Text on slide:**

```
Scenario 2 — Requirements violation
Pull Request #4
Expected: Failed · High risk
```

**Clicks:**

1. **GitHub PR URL** → paste:
   ```
   https://github.com/dwgupta/migration-sandbox-capstone/pull/4
   ```
2. **Mode:** advisory (unchanged).
3. Click **Run review** → wait for completion.
4. Hold on **Results**:
   - **Overall risk:** `high`
   - **Passed:** `No`
5. Show red **Blockers** (if visible): *High or critical findings present*
6. Expand **Review** → **Requirements findings** — show finding (e.g. `SELECT *` / cost control).
7. Expand **Per evaluation step** briefly.
8. Click **Clear results**.

---

## Scene 4 — Title card

**Text on slide:**

```
Scenario 3 — Invalid BigQuery SQL
Pull Request #8
Trailing comma · sql_syntax check
Expected: Failed · High risk
```

**Clicks:**

1. **GitHub PR URL** → paste:
   ```
   https://github.com/dwgupta/migration-sandbox-capstone/pull/8
   ```
2. Click **Run review** → wait.
3. Hold on **Results**:
   - **Passed:** `No`
   - **Overall risk:** `high`
4. Expand **Review** → **Requirements findings** — line containing **`Invalid BigQuery SQL syntax`** or category **`sql_syntax`**.
5. Click **Clear results**.

---

## Scene 5 — Title card

**Text on slide:**

```
Scenario 4 — Already merged PR
Pull Request #9
Advisory: review only (no merge)
```

**Clicks:**

1. Sidebar unchanged: **Allow write actions** = **Off**.
2. **GitHub PR URL** → paste:
   ```
   https://github.com/dwgupta/migration-sandbox-capstone/pull/9
   ```
3. **Mode:** **advisory**.
4. Click **Run review** → wait.
5. Hold on **Passed: Yes** / **low** (governance review can still pass).
6. Expand **GitHub actions taken** → `advisory_review_generated` (no merge).
7. Click **Clear results**.

---

## Scene 6 — Title card

**Text on slide:**

```
Scenario 4b — Auto mode on merged PR
Same PR #9 · Write guard
Expected: Warning · No approve/merge
```

**Clicks:**

1. Sidebar → turn **Allow write actions** → **On**.
2. **Sandbox repo** = `dwgupta/migration-sandbox-capstone`.
3. Main area → **Mode** → select **auto**.
4. **GitHub PR URL** (still #9):
   ```
   https://github.com/dwgupta/migration-sandbox-capstone/pull/9
   ```
5. Click **Run review** → wait.
6. Hold on yellow **Warning**:
   ```
   PR is already merged — please validate your input.
   ```
7. Expand **GitHub actions taken** → show **`auto_skipped_already_merged`** (no `merged` / `approved`).
8. Click **Clear results**.

---

## Scene 7 — Title card

**Text on slide:**

```
Summary
✓ Compliant PR passes (#11)
✗ Policy violations fail (#4)
✗ Invalid SQL fails (#8)
✗ Auto merge blocked on merged PR (#9)

github.com/dwgupta/pr-governance-agent
```

**Action:** End recording.

---

## Recording checklist

- [ ] Hide `.env` and API key override fields (sidebar expander).
- [ ] Each scene: title card → Streamlit → **Clear results** before next PR.
- [ ] Wait for full run completion every time (do not cut during **Agent running…**).
- [ ] Optional: zoom browser to 110% for readability.
- [ ] Total runtime target: **~4–6 minutes** at comfortable pace.

## Optional CLI B-roll (no clicks)

If you want terminal inserts between title cards:

```bash
python scripts/run_graph_cli.py --pr-url https://github.com/dwgupta/migration-sandbox-capstone/pull/8 --mode advisory
```

Show `Passed: False` and requirements findings in terminal output.
