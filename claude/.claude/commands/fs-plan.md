---
description: Plan and implement a fullstack feature. Backend architect defines the API contract, frontend architect plans against it, then both coders implement in parallel.
allowed-tools: [Task, Read, Glob, Grep, AskUserQuestion]
---

# Fullstack Plan & Implement

Coordinate backend and frontend architects sequentially to produce an aligned fullstack plan, then dispatch both coders in parallel for implementation.

## Instructions

1. **Launch the backend-architect agent** (`subagent_type: backend-architect`):
   - Pass the task description below
   - Instruct it to explore the codebase, search for existing patterns, and produce a detailed implementation plan
   - The plan MUST include a clearly defined **API contract** section specifying: endpoint URLs, HTTP methods, request body shapes, response shapes, status codes, and any query parameters or pagination
   - Also include: data models with field types/indexes/constraints, serializer definitions, viewset structure, Celery tasks if needed, and migration strategy

2. **Extract the API contract** from the backend architect's plan

3. **Launch the frontend-architect agent** (`subagent_type: frontend-architect`):
   - Pass the task description below AND the backend architect's API contract
   - Instruct it to design the frontend implementation **against the defined API contract** — it must not invent its own endpoint shapes
   - The plan should include: component hierarchy, props/emits interfaces, state management approach, styling approach, API integration points using the exact contract from step 2, and existing components to reuse

4. **Present the unified plan** to the user:
   - Show the API contract as the bridge between both plans
   - Summarize the backend plan
   - Summarize the frontend plan
   - Highlight any concerns or tradeoffs

5. **Ask the user** if they want to proceed with implementation

6. **If the user approves**, launch both coder agents **in parallel** using a single message with multiple Task tool calls:

   **Backend Coder** (`subagent_type: backend-coder`):
   - Pass the full backend architect plan as context
   - Instruct it to follow the plan exactly and flag any ambiguities
   - If the plan has independent pieces, launch parallel backend-coder subagents for each piece

   **Frontend Coder** (`subagent_type: frontend-coder`):
   - Pass the full frontend architect plan AND the API contract as context
   - Instruct it to follow the plan exactly, using the exact API contract shapes
   - If the plan has independent pieces, launch parallel frontend-coder subagents for each piece

7. **After both coders complete**, summarize:
   - What was implemented on the backend
   - What was implemented on the frontend
   - Any issues flagged by either coder
   - Any mismatches or integration concerns to verify

## Task

$ARGUMENTS
