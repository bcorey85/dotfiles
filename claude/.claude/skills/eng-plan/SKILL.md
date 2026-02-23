---
name: eng-plan
description: Plan a feature — auto-detects scope (fe/be/fullstack), runs architect(s), asks questions. Optionally writes plan to disk and/or dispatches coders.
allowed-tools: [Bash, Read, Glob, Grep, Task, AskUserQuestion, Skill]
---

# Engineering Plan

Plan a feature or task. Consumes whatever context is already in the conversation thread (Jira ticket from `/pull-ticket`, user description, product spec, etc.). Does NOT fetch external context itself.

Auto-detects scope and launches the appropriate architect(s). After planning, asks whether to save to disk and/or implement immediately.

## Modifiers

- `be` or `backend` — force backend-only scope
- `fe` or `frontend` — force frontend-only scope
- `fs` or `fullstack` — force fullstack scope

## Instructions

### Phase 1: Gather Context

1. **Check for context already in the thread.** The user may have run `/pull-ticket`, pasted a description, or just described what they want. Use whatever is available. Do NOT independently fetch from Jira or Notion — if the user hasn't run `/pull-ticket` and a Jira ticket is relevant, **suggest they run `/pull-ticket` first** rather than fetching it yourself. This reinforces the workflow loop.

2. **If no context is apparent**, ask the user: "What are we building? Describe the feature or paste a ticket."

3. **Check for an existing eng plan** — Glob `/eng-plan/*.md` for matching files. If found, read it and ask: "Found an existing plan — update it or start fresh?"

### Phase 2: Scope Assessment

5. **Determine scope** (frontend, backend, or fullstack) based on the task description, conversation context, and codebase structure.

5a. **Assess whether architect agents are needed.** Default is YES — run the architects. Only skip Phase 3 if ALL of these are true:
   - The task is pure configuration with zero implementation choices (e.g., installing a package, adding an env var, enabling a flag)
   - No new files are being created
   - No existing service/module signatures are changing
   - No data model, API contract, or state management decisions are involved
   - The entire change could be described in under 5 lines of diff

   **A well-written ticket is NOT a reason to skip the architect.** Tickets describe the PM's intended approach. Architects validate that approach against the actual codebase — catching coupling risks, stale assumptions, and edge cases the ticket cannot see. If the ticket includes an "Approach" section, that is context FOR the architect, not a replacement for one.

   If skipping:
   - Write the plan directly based on existing codebase patterns
   - Ask the user: "This is pure configuration — skip the architect and go lean?" **Wait for explicit confirmation.**
   - **Still dispatch coder subagent(s) in Phase 5 if the user chooses "Implement now."** "Go lean" means skipping the architect, NOT skipping the coder. The coder dispatch is what triggers the auto-review chain — implementing inline breaks that chain.

   If uncertain, run the architect. A 2-minute architect pass that confirms "the approach is sound" is cheap insurance. A skipped architect that misses a coupling risk costs an entire review-fix cycle.

6. **If a scope hint was passed** (`be`, `fe`, `fs`), use it directly.

7. **If scope is ambiguous**, ask the user: "This could be frontend-only, backend-only, or fullstack. What's the scope?"

8. **Present scope to user**: "This is [frontend/backend/fullstack]. I'll spin up [which architects]. Sound right?"

### Phase 3: Architect Analysis

9. **Read existing codebase context** for the affected areas — key files, existing patterns, relevant `eng-arch/` docs. Include this as context when launching architect agents.

10. **Launch architect agents** based on scope. Use the Task tool:

**Backend only:**
- Launch `backend-architect` with the task context. Instruct it to explore the codebase, evaluate tradeoffs, and produce specific design decisions.

**Frontend only:**
- Launch `frontend-architect` with the task context. Same: explore, evaluate, decide.

**Fullstack:**
- Launch `backend-architect` first — instruct it to include a clearly defined **API contract** (endpoint URLs, methods, request/response shapes, status codes).
- Extract the API contract from the backend architect's output.
- Launch `frontend-architect` with the task context AND the API contract — instruct it to design against the defined contract, not invent its own.

11. **Synthesize architect outputs** — identify key decisions, tradeoffs, and open questions.

### Phase 4: Human Input (REQUIRED)

12. **Present decisions and questions to the user.** Never skip this step. Examples:
    - Tradeoff choices the architects identified
    - Ambiguities in the task description
    - Convention questions (naming, patterns, structure)
    - Scope questions (do X now or defer?)

13. **Wait for answers.** Incorporate them into the plan.

### Phase 5: User Choice

14. **HARD STOP — DO NOT WRITE ANY FILES OR DISPATCH ANY AGENTS UNTIL THE USER ANSWERS THESE QUESTIONS.**

    This has been a recurring failure point. The user has corrected this behavior TWICE.
    You MUST present these questions and WAIT for explicit answers before taking any action.
    Presenting the plan in the conversation is fine. Writing files or dispatching coders is NOT.

    **Save to disk?**
    - Yes → Write to `eng-plan/` using the template below. File naming:
      - If a Jira ticket was mentioned in context: `eng-plan/JIRAPROJECT-TICKETNUMBER-description.md`
      - Otherwise: `eng-plan/<feature-name>.md` (kebab-case from description)
    - No → Plan stays in the conversation only

    **Implement now?**
    - Yes → Dispatch coder agent(s) based on scope:
      - Backend only: launch `backend-coder` with the architect's plan
      - Frontend only: launch `frontend-coder` with the architect's plan
      - Fullstack: launch BOTH `backend-coder` and `frontend-coder` in parallel — frontend-coder also gets the API contract
      **IMPORTANT: Always dispatch a coder subagent. Do NOT implement code changes yourself.** The coder dispatch is what triggers the auto-review chain. Implementing inline bypasses peer review.
    - Later → Stop here

15. **Present summary**:
    - Key decisions made (and who made them)
    - File written (if saved)
    - What was implemented (if coded)
    - Remind to check Figma if frontend work is involved
    - **If any code was changed during this session** (whether by dispatched coders OR by you directly), tell the user: "Auto-dispatching `/peer-review` to check the implementation before committing." Then invoke the `/peer-review` skill using the Skill tool (`skill: "peer-review"`). This runs AFTER all implementation is complete and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing. **Never skip peer review just because no coder subagent was dispatched** — the review is triggered by code changes, not by how those changes were made.

## Template (for saving to disk)

```markdown
# Title
> Jira: JIRAPROJECT-TICKETNUMBER (if applicable)
> Context sources: Jira ticket, Figma mockups (sourced via MCP)
> Date: YYYY-MM-DD

## Summary
One paragraph on what this accomplishes.

## Decisions
Key decisions made during planning, with rationale.

## Approach
- Breakdown by area (backend, frontend, etc.)
- Specific patterns to follow

## File Changes
| File | Action | Description |
|------|--------|-------------|
| path | Create/Modify/Delete | What and why |

## Sequence
1. Step-by-step implementation order with dependencies noted

## Dependencies
- External packages to install
- Internal modules to build on

## Verification
Write verification items as TESTABLE assertions, not just descriptions. Each item should specify HOW to verify, not just WHAT to verify.

- [ ] **Test-verified**: [item] — "run tests, confirm [specific test name/pattern] passes"
- [ ] **Build-verified**: [item] — "build succeeds with zero errors"
- [ ] **Code-verified**: [item] — "grep for [pattern] in [file], confirm [count/shape]" (weakest — flag when this is the only verification)
- [ ] **Manual-verified**: [item] — "hit [endpoint], confirm [expected response]"

Prefer test-verified items. If an AC item has no existing test, note whether one should be written.

Integration checks: route ordering, validator edge cases, no-op handling, caller compatibility.
```

## Arguments

$ARGUMENTS
