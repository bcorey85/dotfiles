---
name: feature-plan
description: Full product-to-architecture feature planning pipeline. Runs product spec, UX research, and backend/frontend architects to produce a comprehensive feature spec.
allowed-tools: [Task, Read, Write, Glob, Grep, AskUserQuestion, WebSearch, WebFetch]
---

# Feature Plan Pipeline

Run a full product-to-architecture planning pipeline for a new feature. This produces a comprehensive feature spec document without writing any implementation code.

## Pipeline Flow

```
1. Product Spec Agent → defines WHAT to build and WHY
2. USER CHECKPOINT → approve the product spec before continuing
3. UX Researcher + Backend Architect → run in PARALLEL
   (UX recommends patterns/flows, Backend defines API contract)
4. Frontend Architect → designs UI against UX recommendations + API contract
5. Write FEATURE_SPEC.md → unified spec document
```

## Instructions

### Step 1: Product Specification

Launch the product-spec-manager agent (`subagent_type: product-spec-manager`):
- Pass the feature description below
- Instruct it to define: problem statement, user stories, success criteria, scope boundaries, and priority
- Instruct it to examine the existing codebase and any existing product specs in `product-specs/` for context
- Tell it to NOT create or write any files — just return the analysis as text output
- The output should follow its standard spec format but returned as text, not written to disk

### Step 1b: Research Phase (MANDATORY)

Before presenting the product spec for approval, identify and research the pivotal technical and product questions that could change the approach.

1. **Extract open questions.** From the product spec output, identify 3-5 pivotal questions where current best practices, official documentation, or community consensus could change the design. Focus on:
   - Architecture patterns (how should this type of system be structured?)
   - Integration patterns (what does the official documentation recommend?)
   - Technology choices (what are the current best practices and pitfalls?)
   - Common failure modes (what do teams who built similar things wish they knew?)

2. **Web research.** For each question, use `WebSearch` to find current guidance:
   - Official documentation and architecture guides
   - Community best practices and lessons learned
   - Common anti-patterns to avoid
   - Search with the current year to avoid outdated advice

3. **Synthesize findings.** Produce a concise research summary:
   - For each question: what you searched, what you found, how it affects the spec
   - Flag any findings that contradict the product spec's initial assumptions
   - Include source URLs for traceability

4. **Update the product spec.** Revise to incorporate research findings before presenting to the user. Highlight any contradicted assumptions prominently.

**Do NOT skip this step.** Planning without research leads to rework. A 5-minute search can prevent 10 bad tickets.

### Step 2: User Checkpoint

Present the product spec AND the research findings to the user clearly and concisely. Ask if they want to:
- **Approve** and continue to UX + architecture planning
- **Modify** the scope or direction before continuing

Do NOT proceed past this point without user approval.

### Step 3: UX Research + Backend Architecture (PARALLEL)

Launch BOTH agents in parallel using a single message with multiple Task tool calls:

**UX Research Analyst** (`subagent_type: ux-research-analyst`):
- Pass the approved product spec
- Pass any UX-relevant research findings from Step 1b
- Instruct it to recommend UX patterns, user flows, interaction design, and information architecture for this feature
- If there is an existing frontend codebase, instruct it to analyze existing patterns and recommend consistency
- If this is greenfield, instruct it to recommend best practices for the feature type
- Tell it to focus on: component patterns, user flow steps, feedback/loading states, error handling UX, accessibility considerations, and responsive behavior

**Backend Architect** (`subagent_type: backend-architect`):
- Pass the approved product spec
- Pass the research findings from Step 1b (technology questions and best-practice guidance)
- Instruct it to explore the codebase, search for existing patterns, and produce a detailed implementation plan
- Instruct it to explicitly address how its design aligns with (or intentionally deviates from) the researched best practices
- The plan MUST include a clearly defined **API contract** section specifying: endpoint URLs, HTTP methods, request body shapes, response shapes, status codes, and any query parameters or pagination
- Also include: data models with field types/indexes/constraints, API layer structure (read the project to learn the conventions), async/background tasks if needed, and migration strategy

### Step 4: Frontend Architecture

Launch the frontend-architect agent (`subagent_type: frontend-architect`):
- Pass the feature description, the UX researcher's recommendations, AND the backend API contract
- Pass any frontend-relevant research findings from Step 1b
- Instruct it to design the frontend implementation that:
  - Follows the UX researcher's recommended patterns and flows
  - Integrates against the exact API contract from the backend architect
  - Must NOT invent its own endpoint shapes
- The plan should include: component hierarchy, props/emits interfaces, state management approach, styling approach, API integration points, and existing components to reuse

### Step 5: Write the Feature Spec

Derive a filename from the feature name (kebab-case, e.g., `user-notifications.md`).

Write a unified spec document to `product-specs/FEATURE_NAME.md` with these sections, sourced from the respective agents:

1. **Product Specification** — Problem Statement, User Stories, Success Criteria, Scope (from product-spec-manager)
2. **UX Design** — Recommended User Flows, Interaction Patterns, Accessibility & Responsive Notes (from UX researcher)
3. **API Contract** — full contract from backend architect (bridge between backend and frontend)
4. **Backend Architecture** — Data Models, API Layer, Async Tasks, Migration Strategy (from backend architect)
5. **Frontend Architecture** — Component Hierarchy, State Management, API Integration, Styling Approach (from frontend architect)
6. **Implementation Notes** — Suggested Build Order (backend-first: models, API, then frontend: state, components), Open Questions

### Step 6: Present Summary

After writing the file, present a concise summary to the user:
- Where the spec was saved
- Key decisions made across all stages
- Any open questions or concerns flagged by any agent
- Remind the user they can use `/eng-plan` to create an implementation plan from this spec

## Feature

$ARGUMENTS
