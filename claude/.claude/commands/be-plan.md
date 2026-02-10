---
description: Launch backend-architect to plan, then hand off to backend-coder for implementation
allowed-tools: [Task, Read, Glob, Grep, AskUserQuestion]
---

# Backend Plan & Implement

Use the backend-architect (Opus) to design a plan, then hand off to backend-coder (Sonnet) for implementation.

## Instructions

1. **Launch the backend-architect agent** (`subagent_type: backend-architect`):
   - Pass the task description below
   - Instruct it to explore the codebase, search for existing patterns, and produce a detailed implementation plan
   - The plan should include: data models with field types/indexes/constraints, API endpoints with URLs/methods/request-response shapes, serializer definitions, viewset structure, Celery tasks if needed, and migration strategy

2. **Present the architect's plan** to the user clearly and concisely

3. **Ask the user** if they want to proceed with implementation using the backend-coder agent

4. **If the user approves**, launch one or more backend-coder agents (`subagent_type: backend-coder`):
   - Pass the full architect plan as context
   - If the plan has independent pieces (e.g., models + serializers + views for separate apps), launch parallel backend-coder subagents for each piece
   - If the pieces depend on each other (e.g., models must exist before serializers), launch them sequentially
   - Each coder should be told to follow the plan exactly and flag any ambiguities

5. **After coders complete**, summarize what was implemented and any issues flagged

## Task

$ARGUMENTS
