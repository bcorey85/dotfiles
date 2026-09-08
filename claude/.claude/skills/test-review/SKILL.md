---
name: test-review
description: Review test suites for coverage gaps, weak assertions, and stale tests — auto-detects scope or accepts be/fe/fs modifier; `branch` reviews only tests added on the current branch and reaps dead/low-value ones. Use for "review the tests", "test suite health", "coverage check", "cull the branch's tests".
allowed-tools: [Agent, Bash, Read, Glob, Grep]
---

# Test Review

Dispatch `test-reviewer`; auto-detects scope or takes a keyword.

## Modifiers

- `be` or `backend` — force backend-only scope
- `fe` or `frontend` — force frontend-only scope
- `fs` or `fullstack` — force fullstack scope (runs both in parallel)
- `branch` — review only branch-added/modified tests + cull check. Ad-hoc/off-pipeline only — a pipeline branch's tests already get this judgment from the Test audit closing phase; never run both.

Any remaining text after the modifier is passed as a focus area (e.g., `/test-review fe useBoard` reviews only frontend tests related to useBoard).

## Instructions

1. **Parse arguments**: Extract the scope modifier (if any) and focus area from `$ARGUMENTS`.

2. **Determine scope** if no modifier: diff + untracked files, classify fe/be per project layout (CLAUDE.md if unclear). Only-fe → frontend; only-be → backend; both → fullstack; ambiguous → ask.

3. **Dispatch** (omit `model` throughout — frontmatter pins Opus): frontend-only → scope `frontend`; backend-only → `backend`; fullstack → TWO in parallel; branch → ONE scope `branch` (agent diffs merge-base itself), ad-hoc use only per above. Include focus area throughout.

4. **Present the report(s)**; ask about dispatching coders for fixes.

## Arguments

$ARGUMENTS
