---
name: test-review
description: Review test suites for coverage gaps, weak assertions, and stale tests — auto-detects scope or accepts be/fe/fs modifier
allowed-tools: [Task, Read, Glob, Grep]
---

# Test Review

Dispatch the test-reviewer agent to analyze test suites against their source code. Auto-detects scope or accepts a keyword hint.

## Modifiers

- `be` or `backend` — force backend-only scope
- `fe` or `frontend` — force frontend-only scope
- `fs` or `fullstack` — force fullstack scope (runs both in parallel)

Any remaining text after the modifier is passed as a focus area (e.g., `/test-review fe useBoard` reviews only frontend tests related to useBoard).

## Instructions

1. **Parse arguments**: Extract the scope modifier (if any) and focus area from `$ARGUMENTS`.

2. **Determine scope** if no modifier was provided:
   - Check `git diff --name-only HEAD` and untracked files for recent changes
   - If only `packages/web/` or frontend-like files changed → frontend
   - If only `packages/api/` or backend-like files changed → backend
   - If both → fullstack
   - If ambiguous, ask the user: "Frontend, backend, or both?"

3. **Dispatch test-reviewer agent(s)** based on scope:

   **Frontend only:**
   - Launch `test-reviewer` (`model: "opus"`) with scope `frontend`
   - Include focus area if provided

   **Backend only:**
   - Launch `test-reviewer` (`model: "opus"`) with scope `backend`
   - Include focus area if provided

   **Fullstack:**
   - Launch TWO `test-reviewer` agents in parallel (single message, multiple Task calls):
     - One with scope `frontend`
     - One with scope `backend`
   - Include focus area for both if provided

4. **Present the report(s)** to the user

5. **Ask the user** if they want to dispatch coder agent(s) to fix any of the findings

## Arguments

$ARGUMENTS
