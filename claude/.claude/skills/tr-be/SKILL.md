---
name: tr-be
description: Dispatch test-reviewer agent to review backend unit tests for coverage gaps, weak assertions, and stale tests
allowed-tools: [Task, Read, Glob, Grep]
---

# Backend Test Review

Dispatch the test-reviewer agent to analyze backend unit tests against their source code.

## Instructions

1. **Launch a test-reviewer agent** (`subagent_type: test-reviewer`, `model: "opus"`):
   - Pass `backend` as the target scope
   - If the user provided additional arguments below, include them as focus areas (e.g., a specific Django app like "engine" or "workflow")
   - The agent will read all backend test files and their corresponding source modules, then produce a structured report

2. **After the test-reviewer completes**, present the full report to the user

3. **Ask the user** if they want to dispatch the backend-coder agent to fix any of the findings

## Additional Context

$ARGUMENTS
