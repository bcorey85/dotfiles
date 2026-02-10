---
description: Launch frontend-architect to plan, then hand off to frontend-coder for implementation
allowed-tools: [Task, Read, Glob, Grep, AskUserQuestion]
---

# Frontend Plan & Implement

Use the frontend-architect (Opus) to design a plan, then hand off to frontend-coder (Sonnet) for implementation.

## Instructions

1. **Launch the frontend-architect agent** (`subagent_type: frontend-architect`):
   - Pass the task description below
   - Instruct it to explore the codebase, search for existing patterns, and produce a detailed implementation plan
   - The plan should include: component hierarchy, props/emits interfaces, state management approach, styling approach, API integration points, and existing components to reuse

2. **Present the architect's plan** to the user clearly and concisely

3. **Ask the user** if they want to proceed with implementation using the frontend-coder agent

4. **If the user approves**, launch one or more frontend-coder agents (`subagent_type: frontend-coder`):
   - Pass the full architect plan as context
   - If the plan has independent pieces (e.g., a composable + a component + a page), launch parallel frontend-coder subagents for each piece
   - If the pieces depend on each other, launch them sequentially
   - Each coder should be told to follow the plan exactly and flag any ambiguities

5. **After coders complete**, summarize what was implemented and any issues flagged

## Task

$ARGUMENTS
