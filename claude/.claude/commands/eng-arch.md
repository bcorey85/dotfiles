---
description: Generate or update system architecture docs — auto-detects subsystems, runs architect agents, diff+merge existing docs. Modifiers: be/fe/fs, +quick, +deep.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, Task, AskUserQuestion]
---

# Engineering Architecture

Generate or update cross-cutting architecture documentation in `eng-arch/`. Scans the codebase, dispatches architect agents, and produces structured docs that capture how the system works — not how to build a single feature (that's `/eng-plan`).

## Modifiers

Parse modifiers from `$ARGUMENTS`:

| Modifier | Effect |
|----------|--------|
| `be` or `backend` | Backend scope only |
| `fe` or `frontend` | Frontend scope only |
| `fs` or `fullstack` | Fullstack (explicit — default if no scope given) |
| `+quick` | Overview doc only, skip deep-dives |
| `+deep` | Overview + all deep-dives, use `model: "opus"` for architect agents |
| `<topic>` | Regenerate a single deep-dive (e.g., `/eng-arch data-model`) |

If a bare topic name is passed (not `be`/`fe`/`fs`/`+quick`/`+deep`), treat it as a single deep-dive request.

## Instructions

### Phase 1: Gather Context

1. **Read foundational files.** In parallel:
   - `CLAUDE.md` — project structure, conventions, stack
   - Glob `eng-arch/*.md` — existing architecture docs
   - Glob `eng-plan/*.md` — recent implementation plans (scan for recurring patterns)
   - Glob `product-specs/*.md` — product context

2. **Determine what exists.** Categorize:
   - **Fresh run** — `eng-arch/` is empty or doesn't exist
   - **Update run** — `eng-arch/` has existing docs
   - **Single topic** — user requested a specific deep-dive topic

3. **Read key source files** based on scope. Use Glob + Read to scan:
   - **Backend:** entry points, modules, controllers, services, entities, gateway files
   - **Frontend:** main app file, router, stores, key components, composables
   - **Shared:** package.json files, config files, database schema

### Phase 2: Scope & Plan

4. **Apply scope modifier** (or default to fullstack).

5. **Auto-detect deep-dive topics** by scanning the codebase for distinct subsystems. Common examples:
   - `data-model` — entities, relationships, constraints, migrations
   - `api-contracts` — REST endpoints, request/response shapes, status codes
   - `websocket-events` — event types, payloads, connection lifecycle
   - `mcp-protocol` — MCP transport, tools, resources, server setup
   - `auth` — authentication/authorization patterns
   - `state-management` — frontend state architecture
   - `build-deploy` — build pipeline, environment config

   Only propose topics where the codebase has meaningful content.

6. **Present plan to user:**
   - "Here's what I found. I'll generate:"
   - List: overview doc + proposed deep-dives (or just overview if `+quick`)
   - If `+quick`: skip deep-dives entirely
   - If `+deep`: propose all detected topics
   - If single topic: confirm the topic and proceed
   - Ask: "Want to adjust the list before I start?"

### Phase 3: Architect Analysis

7. **Launch architect agents** via Task tool based on scope:

   **Backend scope:**
   - Launch `backend-architect` (`subagent_type: backend-architect`). Instruct it to:
     - Explore the backend codebase thoroughly
     - Document: data model (entities, relationships, constraints), API surface (all endpoints with shapes), async patterns (queues, workers), error handling conventions, coding patterns
     - Read existing `eng-arch/` docs as context to understand what's already documented
     - Return structured analysis as text (do NOT write files)

   **Frontend scope:**
   - Launch `frontend-architect` (`subagent_type: frontend-architect`). Instruct it to:
     - Explore the frontend codebase thoroughly
     - Document: component architecture, state management, routing, API integration patterns, styling conventions, composables/utilities
     - Read existing `eng-arch/` docs as context
     - Return structured analysis as text (do NOT write files)

   **Fullstack (both):**
   - Launch both agents in parallel (single message, two Task tool calls)
   - Backend architect produces its analysis first conceptually, but both run concurrently
   - After both complete, synthesize into a unified system view

   For `+deep` modifier, pass `model: "opus"` to the Task tool calls.

8. **Scan `eng-plan/` for patterns** to promote. Look for:
   - Decisions that recur across multiple plans
   - Patterns that started as one-off choices but became conventions
   - Mention these as candidates for the architecture docs

### Phase 4: Diff+Merge (Update Runs Only)

**Skip this phase if `eng-arch/` is empty (fresh run) or this is a single topic request with no existing doc for that topic.**

9. **For each section in each doc that differs from existing content:**
   - Show the user a clear comparison:
     ```
     ### Section: [name]

     **EXISTING:**
     [current content]

     **PROPOSED:**
     [new content from architect]
     ```
   - Ask: "Accept proposed change, keep existing, or edit?"
   - Use AskUserQuestion with options: `Accept`, `Keep existing`, `Edit` (user provides custom text)

10. **For new sections** not in the existing doc:
    - Show the proposed content
    - Ask: "Add this new section?"

11. **For sections that haven't changed** — preserve as-is, no user prompt needed.

### Phase 5: Write Docs

12. **Write the overview doc** to `eng-arch/00-system-overview.md` using the template below.

13. **Write deep-dive docs** (unless `+quick`) to `eng-arch/<topic>.md` using the deep-dive template.

14. **For single topic requests**, only write the requested topic file.

### Phase 6: Summary & Next Steps

15. **Present summary:**
    - Files written/updated (with paths)
    - Key architectural patterns documented
    - Any drift detected (code differs from previously documented patterns)
    - Patterns promoted from `eng-plan/` (if any)

16. **Offer Notion push:** "Want to push these to the Notion Wiki? Run `/push-arch <filename>` for any doc."

17. **Flag drift** if detected: "These areas of code have diverged from the documented architecture: [list]. Consider updating the code or the docs."

## Overview Template

```markdown
# System Architecture Overview
> Generated by /eng-arch
> Date: YYYY-MM-DD
> Scope: [backend/frontend/fullstack]

## System Map

### Packages
[Package names, responsibilities, tech stack for each]

### Communication Flows
[How packages interact — HTTP, WebSocket, shared DB, etc.]

## Data Model

### Entities
[Tables/models with key fields and relationships]

### Relationships
[Entity relationship descriptions or diagram]

## API Surface

### REST Endpoints
[Grouped by resource — method, path, brief description]

### WebSocket Events (if applicable)
[Event names, direction, payload shape]

### MCP Tools (if applicable)
[Tool names, parameters, descriptions]

## Coding Conventions

### Naming
[File naming, variable naming, module structure patterns]

### Patterns
[Common patterns used — decorators, composition, dependency injection, etc.]

### Error Handling
[How errors are handled, formatted, propagated]

## Key Architectural Decisions

### [Decision Title]
- **Context:** Why this decision was needed
- **Decision:** What was decided
- **Rationale:** Why this over alternatives
- **Consequences:** What this means going forward
```

## Deep-Dive Template

```markdown
# [Topic Title]
> Generated by /eng-arch
> Date: YYYY-MM-DD

## Overview
[Brief description of this subsystem/concern]

## Current Implementation
[How it works today — be specific, reference files and line numbers]

## Patterns & Conventions
[Established patterns for this area]

## Interfaces
[APIs, contracts, or boundaries this subsystem exposes]

## Known Limitations
[Current constraints, tech debt, or areas for improvement]
```

## When to Suggest

Proactively suggest `/eng-arch` when:
- A new feature ships that introduces architectural patterns not yet documented
- Multiple `eng-plan/` files have accumulated since the last `eng-arch/` update
- Architectural drift is detected — code patterns diverge from what's documented in `eng-arch/`
- The user asks "how does X work?" and the answer requires deep codebase exploration
- A new developer or AI session would benefit from a system-level overview

## Relationship with Other Skills

- **`/eng-plan`** — per-ticket implementation plans. `/eng-arch` establishes the patterns that `/eng-plan` should reference and follow. If `/eng-arch` exists, architect agents in `/eng-plan` should read it as input context.
- **`/push-arch`** — pushes `eng-arch/*.md` docs to Notion Wiki. Run after `/eng-arch` to share docs.
- **`/feature-plan`** — product-level planning. `/eng-arch` documents how the system IS; `/feature-plan` plans what to build next.

## Arguments

$ARGUMENTS
