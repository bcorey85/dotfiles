---
name: qrspi-plan
description: Tactical implementation plan from all QRSPI artifacts (QRSPI step 5 of 5)
allowed-tools: [Bash, Read, Glob, Grep, Write, Task]
---

# Write Tactical Plan

Write the detailed implementation plan that an executing agent will follow to build the feature. This is step 5 of the QRSPI workflow. The design discussion and structure outline have already aligned with the user — this plan fills in the tactical details.

## Task Directory & Ticket Detection

```
docs/eng-specs/IQ-XXX-short-description/
├── IQ-XXX-00-ticket.md
├── IQ-XXX-01-questions.md
├── IQ-XXX-02-research.md
├── IQ-XXX-03-design.md
├── IQ-XXX-04-structure.md
└── IQ-XXX-05-plan.md    <-- you create this
```

## Resolving the Task Directory (auto, not paste)

1. If `$ARGUMENTS` is a path under `docs/eng-specs/`, use it.
2. Otherwise infer from branch:
   ```bash
   git rev-parse --abbrev-ref HEAD | grep -oE '^[a-zA-Z]+-[0-9]+' | tr '[:lower:]' '[:upper:]'
   ```
   then glob `docs/eng-specs/IQ-XXX-*/`. Single match → use it. Multiple → ask. None → ask for path.
3. Read `IQ-XXX-00-ticket.md`, `IQ-XXX-02-research.md`, `IQ-XXX-03-design.md`, and `IQ-XXX-04-structure.md` directly. Do NOT ask the user to paste.

## Inputs

You need:
1. The ticket — prefer the snapshot at `IQ-XXX-00-ticket.md` if it exists in the task directory; otherwise accept a path or description from the user.
2. The research document (`IQ-XXX-02-research.md` in the task directory).
3. The design document (`IQ-XXX-03-design.md` in the task directory).
4. The structure outline (`IQ-XXX-04-structure.md` in the task directory).

If any are missing, ask. Read all FULLY (no limit/offset) before proceeding.

## Detect Project Verification Commands

Before writing the plan, determine the project's verification commands:

1. Read `CLAUDE.md` (project root) for commands like `npm run validate`, `make check`, `pnpm test`.
2. Fall back to inspecting `package.json` `scripts` for `validate`, `test`, `lint`, `typecheck`, `build`.
3. If you can't find them, ask the user which commands to reference.

Use the project's actual commands in the Automated Verification checklist — not generic placeholders.

## Process

1. Read all four input documents FULLY.
2. Detect verification commands (above).
3. For each phase in the structure outline, flesh out specific file changes and code.
4. Spawn sub-agents only for tactical lookups — current function signatures, test patterns, import paths. **Every Task call MUST set `model: "haiku"` — these are read-only fact-extractions, exactly what Haiku is for. The agent-model-guard PreToolUse hook will reject any unmodeled or `model: "opus"` call.**
   - Default `subagent_type: "Explore"`. Reach for `general-purpose` only when Explore can't handle the trace; still pin `model: "haiku"`.
5. Write the plan to `docs/eng-specs/IQ-XXX-description/IQ-XXX-05-plan.md`.
6. Present a brief summary — tell the user to spot-check, not deep-review (save that for the code).
7. Print the short footer (below).

## Footer (print this at the end — keep it short, no boxes)

```
Saved → docs/eng-specs/IQ-XXX-description/IQ-XXX-05-plan.md
QRSPI complete. Next: run /clear, then /code docs/eng-specs/IQ-XXX-description/IQ-XXX-05-plan.md
Spot-check the plan now; save deep review for the actual code.
```

Substitute the real path.

## Plan Template

```markdown
# [Feature Name] Implementation Plan

**Ticket**: docs/eng-specs/IQ-XXX-description/IQ-XXX-00-ticket.md (IQ-XXX)
**Research**: docs/eng-specs/IQ-XXX-description/IQ-XXX-02-research.md
**Design**: docs/eng-specs/IQ-XXX-description/IQ-XXX-03-design.md
**Structure**: docs/eng-specs/IQ-XXX-description/IQ-XXX-04-structure.md
**Date**: YYYY-MM-DD

## Overview
[1-2 sentence summary]

## Phase Status

<!-- Updated by /code after each phase completes + peer-review passes. Source of truth for "which phase is next" across /clear boundaries. Do not delete. -->

- [ ] Phase 1: [name from structure outline]
- [ ] Phase 2: [name]
- [ ] Phase 3: [name]
<!-- one line per phase, matching the Phase headers below -->

## Current State Analysis
[Brief — from design doc]

## Desired End State
[Brief — from design doc, with verification criteria]

## What We're NOT Doing
[Scope boundaries from design doc]

## Implementation Approach
[Strategy and key decisions — from design doc]

## Phase 1: [Name from structure outline]

### Overview
[What this phase accomplishes]

### Changes Required:

#### 1. [Component/File]
**File**: `path/to/file.ts`
**Changes**: [specific changes]

`​`​`typescript
// Code to add/modify
`​`​`

#### 2. [Component/File]
**File**: `path/to/file.ts`
**Changes**: [specific changes]

### Success Criteria

Write verification items as TESTABLE assertions, not just descriptions. Each item specifies HOW to verify, not just WHAT.

#### Automated Verification:
- [ ] **Build-verified**: build succeeds with zero errors — `<project build cmd>`
- [ ] **Test-verified**: [specific test name/pattern] passes — `<project test cmd>`
- [ ] **Lint/type-verified**: no new errors — `<project lint/typecheck cmd>`

(For this repo: `npm run validate` covers typecheck + lint + tests + build.)

#### Manual Verification:
- [ ] **Manual-verified**: [scenario] — "hit [endpoint/UI flow], confirm [expected response/behavior]"
- [ ] **Code-verified**: [item] — "grep for [pattern] in [file], confirm [count/shape]" (weakest — flag when it's the only verification)

**Pause for manual verification before proceeding to Phase 2.**

---

## Phase 2: [Name]
[Same structure...]

---

## Testing Strategy
[Unit tests, E2E tests, manual steps]

## References
- Ticket: IQ-XXX
- Research: docs/eng-specs/IQ-XXX-description/IQ-XXX-02-research.md
- Design: docs/eng-specs/IQ-XXX-description/IQ-XXX-03-design.md
- Structure: docs/eng-specs/IQ-XXX-description/IQ-XXX-04-structure.md
```

## Sub-Agent Usage

Spawn sub-agents only for tactical lookups:
- Current function signatures you need to match.
- Existing test patterns to follow.
- Import paths and module structure.
- Do NOT use sub-agents for design decisions — those are already resolved.

**Model and subagent_type are mandatory:**
- `model: "haiku"` always — these are read-only fact-extractions. The agent-model-guard hook rejects unmodeled or `opus` calls.
- `subagent_type: "Explore"` by default. Only use `general-purpose` when Explore can't handle the trace.

## What NOT To Do

- Do NOT re-debate design decisions — they are resolved in the design doc.
- Do NOT restructure the phases — they are set in the structure outline.
- Do NOT skip the References section — link all upstream artifacts.
- Do NOT ask the user to deeply review this plan — tell them to spot-check it and save the deep review for the actual code.
- Do NOT write horizontal phases — the structure outline already enforces vertical slices.

## Arguments

$ARGUMENTS
