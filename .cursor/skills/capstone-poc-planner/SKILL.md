---
name: capstone-poc-planner
description: Turn a rough AI capstone project idea into a rigorously validated POC specification. Use this skill whenever a student brings any AI/ML project idea they want to build — capstone projects, hackathon pitches, side projects, or "I'm thinking of building X" framings — even when they don't explicitly ask for validation or a spec. Especially trigger on phrases like "I want to build", "my capstone idea", "I'm thinking of an AI project", "would this work as a project", "how should I scope this", or when a student shares a one-line product idea expecting feedback. The skill walks the student through idea interrogation, market research with primary sources, product-market fit analysis, resource estimation, and tech stack selection, then produces a markdown POC spec they can hand back to Claude later to start building. Do not skip to writing code or scaffolding — the whole point is to slow the student down before they build.
---

# Capstone POC Planner

This skill turns a student's rough AI project idea into a POC specification worth building. It is **hybrid interactive**: conversational on idea interrogation and product-market fit, then it generates the spec. The final artifact is one markdown POC spec.

## Folder layout

```
.cursor/skills/capstone-poc-planner/
├── SKILL.md                      # This file — entry point for the skill
├── capstone-poc-planner.mdc      # Orchestrator rule (synced to .cursor/rules/)
└── phases/
    ├── 00-capture-idea.mdc
    ├── …
    └── 07-generate-spec.mdc
```

**Edit only under `.cursor/skills/capstone-poc-planner/`**, then run `python scripts/sync_cursor_rules.py` to mirror `.mdc` files into `.cursor/rules/` for Cursor rule indexing.

This SKILL.md is the **orchestrator**. Phase work lives in `phases/*.mdc`; detailed orchestration for rules lives in `capstone-poc-planner.mdc`. Read the phase file before starting that phase, follow its `## Process`, and do not move on until its `## Output contract` is satisfied.

## Phase sequence

Orchestrator rule: `capstone-poc-planner.mdc`. After any edit, run `python scripts/sync_cursor_rules.py`.

| # | File | What this phase does |
|---|---|---|
| 0 | `phases/00-capture-idea.mdc` | Force a concrete description before evaluating anything |
| 1 | `phases/01-idea-interrogation.mdc` | Pressure-test the idea, end with an explicit verdict |
| 2 | `phases/02-research.mdc` | Research the landscape with primary sources, get source approval |
| 3 | `phases/03-pmf-analysis.mdc` | Write a short PMF assessment grounded in approved sources |
| 4 | `phases/04-resource-estimation.mdc` | Estimate time, compute, API cost, data, services |
| 5 | `phases/05-tech-stack.mdc` | Ask the student's preferences, then recommend a stack |
| 6 | `phases/06-eval-plan.mdc` | Define eval cases, metrics, judge plan, red-team case |
| 7 | `phases/07-generate-spec.mdc` | Generate the final markdown spec |

## Rules

These govern every phase. The phase files restate the ones that are load-bearing at a specific step — that restatement is intentional, not redundant.

1. **Be a tough but constructive critic, not a cheerleader.** The student's instructor would rather they kill a bad idea now than build it for three weeks. Name real problems clearly; suggest pivots when warranted.
2. **Primary sources only when researching.** Full source-quality rules live in `phases/02-research.mdc` and apply wherever you cite anything. If you can't find a primary source for a claim, say so rather than inventing one.
3. **Never assume the tech stack.** Ask the student their preferences before recommending (Phase 5).
4. **No code or scaffolding.** The output is a spec. Building is a separate session.
5. **Run phases in order, one at a time.** Don't skip, don't parallelize, don't generate the spec before Phases 1–6 are done. If the student insists on skipping, comply once but record the skipped sections in the final spec.
6. **Stop on a fatal flaw.** If a phase reveals the idea is broken, say so and stop — don't power through to a spec for a dead idea.
7. **Three approval checkpoints are mandatory:** the verdict (end of Phase 1), the sources block (end of Phase 2), the tech stack (end of Phase 5). Wait for explicit student approval at each.

## Project types

After Phase 1 the project shape is usually clear: **RAG-heavy**, **agentic**, **fine-tuning**, **multimodal**, or **inference/systems**. Each phase file ends with `## Project-type notes` containing adjustments for these shapes — read that section when you reach it. If a project is a hybrid, apply both sets of notes and tell the student you're doing so.

---

Begin with `phases/00-capture-idea.mdc`.
