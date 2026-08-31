---
name: eng-spec
description: Spec a feature — goal-blind research first, then architect exploration, then design decisions resolved with you one at a time and logged to a decision ledger as they land, then a finalized plan. Detects scope (frontend/backend/fullstack) from the ticket and codebase. Optionally writes the spec to disk and/or dispatches coders.
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
    Skill,
    mcp__jira__getJiraIssue,
    mcp__claude_ai_Atlassian__getJiraIssue,
  ]
---

# Engineering Spec

The one planning lane. Phase 1 lists the inputs it accepts.

## How to run

**Read the phase file on entering the phase and follow it from disk** — never
from memory, never two ahead. Compacted mid-phase → re-read before anything else.

`~/.claude/skills/eng-spec/phases/<n>-<name>.md`: 1-ticket · 2-research ·
3-scope · 4-explore · 5-decisions · 6-finalize · 7-choice

## The two rules that outrank any phase

**The task directory is the memory; the conversation is not.** Every phase lands
its output on disk before the next starts — `00-ticket.md`, `01-questions.md`,
`02-research.md`, `03-decisions.md`, then `spec.md`. Write first, then continue.

**The order of the first two phases is the point.** Facts land before a goal can
shape which facts get looked for. Never reorder; never let the architect absorb
the research.

## Arguments

$ARGUMENTS
