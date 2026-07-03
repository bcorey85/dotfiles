---
name: q-orchestrator
description: Run the full QRSPI pipeline (Questions → leak-check → Research → Design → Structure → Plan) in one orchestrated session. Routes artifact file paths between subagents; preserves Q→R isolation structurally instead of relying on /clear discipline.
allowed-tools: [Bash, Read, Glob, Agent, AskUserQuestion, Edit, Write]
---

# QRSPI Orchestrator

You are a router. Until Phase D begins, you NEVER read, summarize, or paraphrase the ticket, the questions, or any artifact — you move file paths between subagents. If you are about to read one before Phase D: stop, pass the path instead. Naming the goal in your own output before research completes contaminates every downstream step.

## Phase 0 — Resolve

1. Run `bash ~/.claude/scripts/qrspi-resolve-dir.sh "$ARGUMENTS"`. Exit 0 → that is `DIR`. Exit 3 → ask the user which. Exit 4 → no `DIR` yet; get the ticket onto disk, then hand its path to Phase Q (which creates `DIR` if absent). **Never pre-copy the ticket into `DIR`** — Phase Q snapshots the source to `<KEY>-00-ticket.md`, so a stray sibling there becomes a duplicate. If the user has a ticket file, pass that path **as-is**. If they only have a Jira key/URL, fetch it (`/pull-ticket` or the Jira tools — neither persists a file on its own) and `Write` it verbatim straight to the canonical path `docs/eng-specs/<KEY>-<slug>/<KEY>-00-ticket.md`: raw fields only, no paraphrase or goal words in your context.
2. Glob `DIR/*.md` (filenames only — do not read). If artifacts already exist, ask which phase to resume from and skip completed phases.

## Phase Q — Questions (subagent)

Dispatch `qrspi-questions` (omit `model`) with ONLY: the ticket path and the task directory (or slug). No other context. It returns the questions file path.

## Leak-check (subagent)

Dispatch `qrspi-leak-check` (omit `model`) with ONLY the questions file path. It returns `PASS` or a flagged list with intent-free rewrites. Relay the verdict verbatim — no commentary of your own about what flagged items imply.

If flagged: ask the user whether to apply the rewrites. On approval, re-dispatch `qrspi-questions` with the flagged items + rewrites (still no ticket content in your prompt beyond the path), then leak-check again. Max 2 rounds, then hand the file to the user to edit directly.

## Gate — human (MANDATORY)

Stop. Say: "Questions written → `<path>`. Leak-check: `<verdict>`. Open the file, edit freely, and confirm to start research." Do NOT proceed without explicit confirmation. All course corrections route back through Q — never inject context into R directly.

## Phase R — Research (subagent)

Dispatch `qrspi-research` (omit `model`) with ONLY the questions file path and the task directory. The dispatch prompt must not mention the ticket, its path, or anything goal-shaped. It returns the research file path.

## Phase D — Design (inline, interactive)

Research is on disk; isolation no longer applies — you become a participant. Read `${CLAUDE_SKILL_DIR}/design-phase.md` and follow it.

## Phase S — Structure (inline, interactive)

Read `${CLAUDE_SKILL_DIR}/structure-phase.md` and follow it.

## Phase P — Plan (subagent)

Dispatch `qrspi-plan` (omit `model`) with ONLY the task directory. It reads the artifacts itself and returns the plan path.

## Footer

```
Saved → <plan path>
QRSPI complete. Next: /clear, then /code <plan path>
Spot-check the plan; save deep review for the actual code. After the code ships: /q-verify confirms the plan was fully built, then /pr, then /q-finalize collapses the folder into an ADR.
```

## Hard Rules

- This file stays ≤80 lines. If an edit pushes past, the addition belongs in a phase file or an agent — not here.
- No reading artifact contents before Phase D. No goal words in the Q, leak-check, or R dispatch prompts.
- Every dispatch omits `model` — all four `qrspi-*` agents pin their own.

## Arguments

$ARGUMENTS
