---
description: Launch backend-coder to implement backend code directly
allowed-tools: [Task, Read, Glob, Grep]
---

# Backend Code Implementation

Launch the backend-coder agent (Sonnet) to implement backend code directly without architectural planning.

## Instructions

Launch the `backend-coder` agent with the task description below. The agent will:
- Write Django models, serializers, views, migrations, Celery tasks
- Follow existing patterns in the codebase
- Write tests if needed
- Flag any ambiguities or issues

Use this command for:
- Straightforward implementation tasks
- Bug fixes
- Simple feature additions where the approach is clear
- Writing tests for existing code
- Data updates (like sandbox definitions)

For complex features requiring design decisions, use `/be-plan` instead.

## Task

$ARGUMENTS
