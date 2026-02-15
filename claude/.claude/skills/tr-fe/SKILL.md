---
name: tr-fe
description: Dispatch test-reviewer agent to review frontend unit tests for coverage gaps, weak assertions, and stale tests
allowed-tools: [Task, Read, Glob, Grep]
---

# Frontend Test Review

Dispatch the test-reviewer agent to analyze frontend unit tests against their source code.

## Instructions

1. **Launch a test-reviewer agent** (`subagent_type: test-reviewer`, `model: "opus"`):
   - Pass `frontend` as the target scope
   - If the user provided additional arguments below, include them as focus areas (e.g., a specific util module or component)
   - The agent will read all frontend test files and their corresponding source files, then produce a structured report

2. **After the test-reviewer completes**, present the full report to the user

3. **Ask the user** if they want to dispatch the frontend-coder agent to fix any of the findings

## Additional Context

$ARGUMENTS
