---
name: eng-spec
description: Spec a feature — goal-blind research, architect exploration, then design decisions resolved with you and recorded as they land. Always saves the spec to disk, runs planning checks and fresh-eyes review, then hands off to /code in a cleared conversation. Never implements.
allowed-tools:
  [
    Bash,
    Read,
    Write,
    Edit,
    Glob,
    Grep,
    Agent,
    AskUserQuestion,
    SendMessage,
    mcp__jira__getJiraIssue,
    mcp__claude_ai_Atlassian__getJiraIssue,
  ]
---

# Engineering Spec

Planning only. Phase 1 resolves the input; Phase 7 hands the saved plan to the
user for implementation in a cleared conversation.

## Phase dispatch

Read each phase file on entry, not ahead. After compaction, re-read the current
phase before continuing.

`~/.claude/skills/eng-spec/phases/<n>-<name>.md`: 1-ticket · 2-research ·
3-scope · 4-explore · 5-decisions · 6-finalize · 6b-review · 7-handoff

All agent dispatches are pinned — omit `model`; frontmatter pins it.

## Persistence and order

The task directory is the memory. Persist each phase's output before advancing:
`00-ticket.md`, `01-questions.md`, `02-research.md`, `03-decisions.md`, then
`spec.md`. The spec is written before finalization checks and kept current through
review. Never ask for save approval or delete the artifacts at handoff.

Research precedes design. Never reorder the first two phases or let the architect
absorb the goal-blind research step.

## Arguments

$ARGUMENTS
