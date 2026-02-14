---
description: Launch frontend-coder to implement frontend code directly
allowed-tools: [Task, Read, Glob, Grep]
---

# Frontend Code Implementation

Launch the frontend-coder agent (Sonnet) to implement frontend code directly without architectural planning.

## Instructions

Launch the `frontend-coder` agent with the task description below. The agent will:
- Write Vue 3 components, TypeScript, SCSS, Pinia stores, composables
- Follow existing patterns in the codebase
- Write tests if needed
- Flag any ambiguities or issues

Use this command for:
- Straightforward implementation tasks
- Bug fixes
- Simple feature additions where the approach is clear
- Writing tests for existing code

For complex features requiring design decisions, use `/fe-plan` instead.

## Task

$ARGUMENTS
