# PR Governance Agent — Architecture Diagrams

Visual reference for the capstone application. Implementation lives under [`src/pr_governance_agent/`](../src/pr_governance_agent/).

**Related:** [Technical design](pr-governance-agent-technical-design.md)

---

## 1. System context

Who uses the system and what it connects to.

```mermaid
flowchart LR
  DE[DataEngineer]
  subgraph capstone [PRGovernanceAgent]
    App[StreamlitAndCLI]
  end
  GH[GitHub]
  LLM[OpenAICompatibleAPI]
  Corpus[PolicyCorpus]
  Email[EmailOrLogStub]

  DE -->|PR_URL_and_mode| App
  App -->|read_PR_optional_write| GH
  App -->|evaluate_findings| LLM
  App -->|retrieve_policies| Corpus
  App -->|notify| Email
```

---

## 2. Container view

Major deployable parts inside the repository.

```mermaid
flowchart TB
  subgraph clients [Clients]
    ST[app/streamlit_app.py]
    CLI[scripts/run_graph_cli.py]
    EVAL[eval/run_eval.py]
  end

  subgraph core [src/pr_governance_agent]
    GRAPH[graph/builder.py]
    NODES[graph/nodes.py]
    STATE[state.py]
    CFG[config.py]
  end

  subgraph integrations [Integrations]
    MCP[mcp/github_client.py]
    RAG[rag/chroma_store.py]
    SAST[security/sast_runner.py]
    NOTIFY[notifications/email.py]
  end

  subgraph data [DataLayer]
    CHROMA[(data/chroma)]
    FIXTURES[(eval/fixtures)]
    CORPUS[(data/sample_corpus)]
    LOG[(data/notification.log)]
  end

  ST --> GRAPH
  CLI --> GRAPH
  EVAL --> GRAPH
  GRAPH --> NODES
  NODES --> STATE
  NODES --> CFG
  NODES --> MCP
  NODES --> RAG
  NODES --> SAST
  NODES --> NOTIFY
  RAG --> CHROMA
  MCP --> FIXTURES
  MCP --> GHAPI[GitHubREST_API]
  INGEST[scripts/ingest_docs.py] --> CORPUS
  INGEST --> CHROMA
  NOTIFY --> LOG
```

---

## 3. LangGraph agent pipeline

Linear state machine executed on each review run (`PRReviewState`).

```mermaid
flowchart TD
  start([Start]) --> ingest_pr
  ingest_pr[ingest_pr]
  ingest_pr --> rag_req[rag_requirements]
  rag_req --> rag_sec[rag_security_policies]
  rag_sec --> sast[run_sast_optional]
  sast --> eval_req[evaluate_requirements]
  eval_req --> eval_sec[evaluate_security]
  eval_sec --> synth[synthesize_review]
  synth --> route[route_decision]
  route --> gh_adv[execute_github_advisory]
  gh_adv --> gh_auto[execute_github_auto]
  gh_auto --> notify[notify_team]
  notify --> endNode([End])

  subgraph ingest_detail [ingest_pr_sources]
    FIX[PR_FIXTURE_JSON]
    REST[GitHub_REST]
    MCPCmd[GITHUB_MCP_COMMAND]
  end
  ingest_pr -.-> ingest_detail

  subgraph eval_detail [evaluate_sources]
    HEU[Heuristic_rules]
    BQSQL[BigQuery_syntax_sqlglot]
    OAI[OpenAI_LLM]
  end
  eval_req -.-> eval_detail
  eval_sec -.-> eval_detail
```

| Node | Reads | Writes to state |
|------|--------|-----------------|
| `ingest_pr` | GitHub / fixture | `patches`, `changed_files`, `pr_metadata` |
| `rag_requirements` | Chroma `requirements` | `requirements_chunks` |
| `rag_security_policies` | Chroma `security_policies` | `security_policy_chunks` |
| `run_sast_optional` | Patches, Semgrep CLI | `sast_findings` |
| `evaluate_requirements` | Chunks + patches | `requirements_findings` (incl. `sql_syntax`) |
| `evaluate_security` | Chunks + patches + SAST | `security_findings` |
| `synthesize_review` | All findings | `review_markdown` |
| `route_decision` | Findings | `passed`, `blockers`, `overall_risk` |
| `execute_github_advisory` | Review | `github_actions_taken` |
| `execute_github_auto` | Mode + flags | merge/approve or skip |
| `notify_team` | Review | `notification_sent` |

---

## 4. Sequence — advisory review

Typical path for a data engineer (default mode).

```mermaid
sequenceDiagram
  actor DE as DataEngineer
  participant UI as Streamlit_or_CLI
  participant LG as LangGraph
  participant GH as GitHubClient
  participant CH as ChromaDB
  participant LLM as OpenAI_optional
  participant LOG as NotificationLog

  DE->>UI: Submit PR URL, mode=advisory
  UI->>LG: invoke PRReviewState
  LG->>GH: fetch_pr diff metadata
  GH-->>LG: patches changed_files
  LG->>CH: query requirements retrieve_n=20
  CH-->>LG: candidate chunks
  LG->>LG: CrossEncoder rerank top_k=5
  LG->>CH: query security_policies retrieve_n=20
  CH-->>LG: candidate chunks
  LG->>LG: CrossEncoder rerank top_k=5
  opt ENABLE_SAST
    LG->>LG: Semgrep on patches
  end
  LG->>LLM: evaluate or heuristic
  LLM-->>LG: findings
  LG->>LG: synthesize_review route_decision
  LG->>GH: optional post_comment
  LG->>LOG: append notification
  LG-->>UI: review_markdown passed risk
  UI-->>DE: Display brief and blockers
```

---

## 5. Sequence — auto mode (sandbox)

Write actions only when explicitly enabled.

```mermaid
sequenceDiagram
  participant LG as LangGraph
  participant CFG as Settings
  participant GH as GitHubClient

  LG->>CFG: writes_allowed repo mode
  alt PR already merged
    LG->>LG: auto_skipped_already_merged plus warning
  else passed and auto and ALLOW_WRITE_ACTIONS and SANDBOX_REPO match
    CFG-->>LG: true
    LG->>GH: approve_pr optional skip self-author
    LG->>GH: merge_pr
  else advisory or failed or flags off
    CFG-->>LG: false
    LG->>LG: auto_skipped_writes_not_allowed or auto_skipped_failed_checks
  end
```

---

## 6. RAG ingestion (offline)

How policy documents enter the vector store.

```mermaid
flowchart TD
  MD[data/sample_corpus/*.md]
  PDF[data/sample_corpus/*.pdf]
  INGEST[scripts/ingest_docs.py]
  H1[Extract H1 title]
  SPLIT[Split on ## headings]
  CHECK{Section > 512 tokens?}
  TABLE{Contains table?}
  ATOMIC[Single section chunk]
  FALLBACK[Token window split overlap 100]
  TABLEKEEP[Keep table section up to 1024 tokens]
  PREFIX[Prepend doc_title > section]
  CHROMA[(ChromaDB HNSW cosine)]
  REQ[requirements collection]
  SEC[security_policies collection]

  MD --> INGEST
  PDF --> INGEST
  INGEST --> H1
  INGEST --> SPLIT
  SPLIT --> TABLE
  TABLE -->|yes| TABLEKEEP
  TABLE -->|no| CHECK
  CHECK -->|no| ATOMIC
  CHECK -->|yes| FALLBACK
  H1 --> PREFIX
  ATOMIC --> PREFIX
  FALLBACK --> PREFIX
  TABLEKEEP --> PREFIX
  PREFIX --> REQ
  PREFIX --> SEC
  REQ --> CHROMA
  SEC --> CHROMA
```

**Chunking rationale:** Sample corpus files are short policy markdown with one rule per `##` section. Section-first chunking preserves rule boundaries and keeps the dialect conversion table intact. Token-bounded fallback handles future long Confluence exports.

---

## 7. Repository layout (implementation map)

```
capstone/
├── app/streamlit_app.py          # GUI entry
├── scripts/
│   ├── run_graph_cli.py          # CLI entry
│   └── ingest_docs.py            # RAG bootstrap
├── eval/                         # Offline test cases
├── src/pr_governance_agent/
│   ├── graph/                    # LangGraph builder + nodes
│   ├── sql/bigquery_validator.py # BigQuery SQL syntax on PR diffs
│   ├── mcp/github_client.py      # GitHub REST / fixture / MCP hook
│   ├── rag/chroma_store.py       # HNSW retrieval + rerank orchestration
│   ├── rag/reranker.py           # CrossEncoder reranking
│   ├── rag/ingest_markdown.py    # Section-first chunking
│   ├── security/sast_runner.py   # Optional Semgrep
│   └── notifications/email.py    # SMTP or log stub
└── data/
    ├── chroma/                   # Persisted embeddings
    └── sample_corpus/            # Source policies
```

---

## 8. RAG retrieval (online)

Two-stage pipeline used by `rag_requirements` and `rag_security_policies` nodes.

```mermaid
sequenceDiagram
  participant Node as rag_node
  participant Chroma as ChromaDB_HNSW
  participant Rerank as CrossEncoder
  participant Eval as evaluate_node

  Node->>Chroma: query retrieve_n=20 cosine
  Chroma-->>Node: candidate chunks with vector scores
  Node->>Rerank: score query vs each candidate
  Rerank-->>Node: reranked by relevance
  Node->>Eval: top_k=5 chunks with citations
```

**Why HNSW:** Small policy corpus (tens to hundreds of chunks), sub-ms latency, cosine matches default embeddings. Wide recall (N=20) compensates for approximate search; cross-encoder reranking improves precision before LLM eval.

**Fallback:** If reranker model fails to load, return vector-order top-k.

---

## 9. Configuration gates

```mermaid
flowchart TD
  mode{mode}
  merged{PR_already_merged}
  passed{passed}
  writes{ALLOW_WRITE_ACTIONS}
  sandbox{SANDBOX_REPO_match}

  mode -->|advisory| A[Generate review only]
  mode -->|auto| merged
  merged -->|yes| F[auto_skipped_already_merged plus warning]
  merged -->|no| B{passed}
  B -->|no| C[Block merge notify failures]
  B -->|yes| writes
  writes -->|false| D[auto_skipped_writes_not_allowed]
  writes -->|true| sandbox
  sandbox -->|yes| E[approve optional skip self-author then merge]
  sandbox -->|no| D
```

---

## Viewing these diagrams

- **Cursor / VS Code:** Markdown preview renders Mermaid.
- **GitHub:** Mermaid blocks render in this file when pushed.
- **Export PNG:** Use [Mermaid Live Editor](https://mermaid.live) and paste a diagram block.

---

*Last updated: June 2026 — aligned with implemented codebase in `src/pr_governance_agent/`.*
