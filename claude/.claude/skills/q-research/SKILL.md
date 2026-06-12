---
name: q-research
description: Objective codebase research from questions only — no ticket context (QRSPI step 2 of 5)
allowed-tools: [Bash, Read, Glob, Grep, Write, Task]
---

# Objective Codebase Research

Answer research questions by exploring the codebase and documenting what you find. This is step 2 of the QRSPI workflow.

## Critical Rule

You have NO knowledge of what is being built. You only have questions to answer. Your output must be 100% factual — what exists, how it works, where it lives. Zero opinions, zero suggestions, zero implementation ideas.

If the user offers the ticket or describes what they're building, politely decline: "I need to stay objective — just the questions please."

**Do NOT read `*-00-ticket.md`** — the task directory contains a ticket snapshot at `IQ-XXX-00-ticket.md`. Skip it. Reading it defeats the purpose of this step (objectivity comes from not knowing the goal). Only read `IQ-XXX-01-questions.md`.

## Task Directory & Ticket Detection

All QRSPI artifacts live together under `docs/eng-specs/`:

```
docs/eng-specs/IQ-XXX-short-description/
├── IQ-XXX-00-ticket.md       <-- DO NOT READ — ticket snapshot, off-limits to research
├── IQ-XXX-01-questions.md
├── IQ-XXX-02-research.md    <-- you create this
├── IQ-XXX-03-design.md
├── IQ-XXX-04-structure.md
└── IQ-XXX-05-plan.md
```

## Resolving the Task Directory (auto, not paste)

The user should NOT paste the questions. Read them from disk.

1. Run the shared resolver:
   ```bash
   bash ~/.claude/scripts/qrspi-resolve-dir.sh "$ARGUMENTS"
   ```
   Exit 0 → use the printed directory. Exit 3 → multiple matches printed; ask the user which. Exit 4 → ask for the path.
2. Read `IQ-XXX-01-questions.md` directly. **Do NOT read `IQ-XXX-00-ticket.md`** — it's off-limits.
3. Do NOT ask what is being built. Do NOT ask the user to paste questions.

## Process

1. Resolve the task directory and read `IQ-XXX-01-questions.md` (above).
2. For each question (or cluster of 2-3 related questions), spawn a focused sub-agent via the Task tool. **Every Task call MUST set `model: "haiku"` — this is read-only research, exactly what Haiku is for. The agent-model-guard PreToolUse hook will reject any unmodeled or `model: "opus"` call.**
   - Default to `subagent_type: "Explore"` — research is fundamentally lookup work ("where is X", "what does this file do", "find every place Y is called"). Explore is read-only and cheaper.
   - Use `subagent_type: "general-purpose"` only when a question genuinely requires tracing across many files in a way Explore can't handle (rare). Still pin `model: "haiku"`.
   - Never use `general-purpose` as the default. Never omit `model`. Never set `model: "opus"`.
3. Tell every sub-agent: "Document what exists. No opinions. No suggestions. Include `file_path:line_number` references."
4. Run sub-agents in parallel.
5. Synthesize findings into a research document.
6. Save to `docs/eng-specs/IQ-XXX-description/IQ-XXX-02-research.md`.
7. Print the short footer (below).

### Example Task invocation

```
Task({
  description: "Router config and gate components",
  subagent_type: "Explore",
  model: "haiku",
  prompt: "..."
})
```

## Footer (print this at the end — keep it short, no boxes)

```
Saved → docs/eng-specs/IQ-XXX-description/IQ-XXX-02-research.md
Next: run /clear, then /q-design docs/eng-specs/IQ-XXX-description/
```

Substitute the real path.

## Research Document Format

```markdown
---
date: [ISO timestamp]
git_commit: [current hash]
branch: [current branch]
topic: "[Derived from questions, not from any ticket]"
tags: [research, codebase, relevant-component-names]
status: complete
---

# Research: [Topic]

**Date**: [today]
**Git Commit**: [hash]

## Findings

### [Question 1 topic]

[Factual answer with file_path:line_number references]
[Code snippets where helpful]

### [Question 2 topic]

[Factual answer with file_path:line_number references]

...

## Code References

- `path/to/file.ts:123` - Description of what's there
- `path/to/file.ts:456` - Description of what's there

## Patterns Found

[Existing patterns discovered, documented without judgment]
```

## What NOT To Do

- Do NOT ask what is being built — you don't need to know.
- Do NOT suggest improvements or changes to existing code.
- Do NOT critique existing code quality or patterns.
- Do NOT add implementation recommendations.
- Do NOT include the ticket in your context.
- Do NOT editorialize ("this could be improved by...") — just document.
- Do NOT spawn `general-purpose` agents on Opus or without a model — the hook will block you and you should never have tried.

## Arguments

$ARGUMENTS
