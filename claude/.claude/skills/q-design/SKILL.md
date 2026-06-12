---
name: q-design
description: Interactive design discussion — align on what we're building before plan (QRSPI step 3 of 6)
allowed-tools: [Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion]
---

# Design Discussion

Facilitate an interactive design discussion to build a shared understanding of what we're building. This is step 3 of the QRSPI workflow and produces the highest-leverage artifact: a ~200 line design document that captures every decision before a single line of code is written.

## Why This Matters

This is the agent's chance to "brain dump" everything it thinks, everything it found, and everything it's unsure about — so the user can do surgery on the understanding before 2,000 lines of code get written. Do not outsource the thinking. Force every decision to be explicit.

## Task Directory & Ticket Detection

```
docs/eng-specs/IQ-XXX-short-description/
├── IQ-XXX-00-ticket.md       <-- ticket snapshot (read this for ticket context)
├── IQ-XXX-01-questions.md
├── IQ-XXX-02-research.md
├── IQ-XXX-03-design.md    <-- you create this
├── IQ-XXX-04-structure.md
└── IQ-XXX-05-plan.md
```

## Resolving the Task Directory (auto, not paste)

1. Run the shared resolver:
   ```bash
   bash ~/.claude/scripts/qrspi-resolve-dir.sh "$ARGUMENTS"
   ```
   Exit 0 → use the printed directory. Exit 3 → multiple matches printed; ask the user which. Exit 4 → ask for the path.
2. Read `IQ-XXX-00-ticket.md` and `IQ-XXX-02-research.md` directly. Do NOT ask the user to paste.

## Inputs

You need two things:

1. The ticket — prefer the snapshot at `IQ-XXX-00-ticket.md` if it exists in the task directory; otherwise accept a path or description from the user.
2. The research document (`IQ-XXX-02-research.md` in the task directory).

If either is missing, ask. Read both FULLY (no limit/offset) before proceeding.

## Process

1. Read the ticket and research document FULLY.
2. Analyze the research for relevant patterns, constraints, and existing approaches.
3. Present your initial understanding with open questions — DO NOT write the design doc yet.
4. Iterate with the user: ask questions, present options, resolve decisions one by one.
5. Only after ALL questions are resolved, write the design document.
6. Save to `docs/eng-specs/IQ-XXX-description/IQ-XXX-03-design.md`.
7. Print the NEXT STEP block (below).

## Footer (print this at the end — keep it short, no boxes)

```
Saved → docs/eng-specs/IQ-XXX-description/IQ-XXX-03-design.md
Next: run /clear, then /q-structure docs/eng-specs/IQ-XXX-description/
```

Substitute the real path.

## Initial Presentation (MANDATORY — do this BEFORE writing anything)

```
Based on the ticket and research, here's my understanding:

**Current State**: [what exists today, from research, with file_path:line_number refs]

**Desired End State**: [what the system looks like after we're done]

**Patterns I found** (confirm these are the RIGHT ones to follow):
- [Pattern A] — `file:line` — [brief description]
- [Pattern B] — `file:line` — [brief description]

**Patterns to AVOID** (ones I found that look wrong or outdated):
- [Anti-pattern] — `file:line` — [why I think we should avoid this]

**Design Questions** (need your input before I can proceed):

1. [Question about approach/tradeoff]
   - A: [description + pros/cons]
   - B: [description + pros/cons]
   - Recommended: [your pick + why]

2. [Another question]
   - A: ...
   - B: ...
```

Wait for user responses. Ask follow-ups. Do NOT proceed until every question is answered and you have confirmed understanding.

## Design Document Template

Only write this AFTER all questions are resolved:

```markdown
# Design: [Feature Name]

**Ticket**: docs/eng-specs/IQ-XXX-description/IQ-XXX-00-ticket.md (IQ-XXX)
**Research**: docs/eng-specs/IQ-XXX-description/IQ-XXX-02-research.md
**Date**: YYYY-MM-DD
**Status**: draft

## Current State

[What exists today — from research, with file_path:line_number refs]

## Desired End State

[What the system looks like after implementation]
[How to verify we're done]

## Patterns to Follow

- [Pattern with file_path:line_number reference and brief description]

## Patterns to AVOID

- [Anti-pattern with explanation of why to avoid]

## Design Decisions

### 1. [Topic]

**Choice**: [what was decided]
**Reasoning**: [why, referencing user's input]
**Alternatives rejected**: [what was considered and why not]

### 2. [Topic]

...

## Constraints

- [Technical constraint from research]
- [Business constraint from ticket]

## Open Risks

- [Risk that implementation might surface]
```

## What NOT To Do

- Do NOT write the design doc without asking questions first — this is the whole point.
- Do NOT make design decisions unilaterally — present options, get user input.
- Do NOT include implementation details (phases, specific file changes) — that is `/q-structure`.
- Do NOT produce more than ~200 lines — concise alignment, not exhaustive spec.
- Do NOT skip presenting patterns for confirmation — the user needs to catch bad patterns before they propagate.

## Arguments

$ARGUMENTS
