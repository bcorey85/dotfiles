---
name: eng-arch
description: Generate or update system architecture docs — auto-detects subsystems, runs architect agents, diff+merge existing docs. Modifiers: be/fe/fs, +quick, +deep.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, Task, AskUserQuestion]
---

# Engineering Architecture

Generate or update cross-cutting architecture documentation in `docs/eng-arch/`. Scans the codebase, dispatches architect agents, and produces structured docs that capture how the system works — not how to build a single feature (that's `/eng-spec`).

## Modifiers

Parse modifiers from `$ARGUMENTS`:

| Modifier            | Effect                                                                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `be` or `backend`   | Backend scope only                                                                                                                          |
| `fe` or `frontend`  | Frontend scope only                                                                                                                         |
| `fs` or `fullstack` | Fullstack (explicit — default if no scope given)                                                                                            |
| `+quick`            | Overview doc only, skip deep-dives                                                                                                          |
| `+deep`             | Overview + all deep-dives                                                                                                                   |
| `<topic>`           | Regenerate a single deep-dive (e.g., `/eng-arch data-model`)                                                                                |
| `<adr-path>`        | ADR-driven mode — read an ADR (`docs/eng-specs/IQ-*.md`), update or create the matching deep-dive without scanning the rest of the codebase |

If a bare topic name is passed (not `be`/`fe`/`fs`/`+quick`/`+deep`), treat it as a single deep-dive request. If a path ending in `.md` under `docs/eng-specs/` is passed, enter **ADR-driven mode** (see below).

## ADR-Driven Mode

Triggered when `$ARGUMENTS` matches `docs/eng-specs/IQ-*.md`. Skips Phase 2 (no plan presentation), replaces Phase 3 (no codebase sweep). Uses Phases 4–6 as written.

| Step | Action                                                                                                                                                                                                     |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Read ADR FULLY                                                                                                                                                                                             |
| 2    | `ls docs/eng-arch/*.md` — filenames only                                                                                                                                                                   |
| 3    | Identify target from ADR's `Decision` + `Patterns to follow`. Existing match → propose update. No match → propose new kebab-case filename. AskUserQuestion: `Update <file>` / `Create <new-file>` / `Edit` |
| 4    | If updating, read the existing deep-dive FULLY                                                                                                                                                             |
| 5    | Dispatch scoped `frontend-architect` or `backend-architect`, omitting `model` — their frontmatter pins Opus. See prompt below                                                                              |
| 6    | Diff/merge per-section if updating (Phase 4 flow)                                                                                                                                                          |
| 7    | Write to target path                                                                                                                                                                                       |
| 8    | Summary: ADR path, deep-dive path, file-path drift the architect surfaced                                                                                                                                  |

### Architect prompt — required fields

- Full ADR content (ground truth)
- Target deep-dive path
- Existing deep-dive content (if updating)
- **Content instructions**: Use the ADR as source of truth for the decision. Verify cited file paths against the codebase on the current branch (ADR may be stale). Produce durable architecture — current-state, patterns, interfaces, limitations. Do NOT recap migration story, alternatives, or implementation phases — those belong in the ADR. Return content as text; do not write files.
- **Format directive — must pass to the architect verbatim:**

  > Engineers in problem-solving mode scan headings (NN/g layer-cake pattern), they don't read. Write to be skimmed.
  >
  > - **Headings = answers, not topics.** `Token interceptor` not `Implementation details`. `401 handling` not `Error section`.
  > - **BLUF at every level.** Start each section with the claim, not the setup.
  > - **Bullets > paragraphs. Tables > bullets** for comparisons (endpoints, phases, options, before/after).
  > - **`file:line` refs**, never "the file that handles X".
  > - **Bold the load-bearing word** in any multi-line bullet.
  > - **Cut connective tissue** ("Importantly", "It's worth noting", "Going forward").
  > - **One Diátaxis mode**: deep-dives are **reference** (_how_ the subsystem currently works). Do NOT recap migration, alternatives, or decision rationale — those live in the ADR. Cross-link.
  > - **If a section is one paragraph, it's probably wrong.** Split or cut.

## Instructions

### Phase 1: Gather Context

1. **Read foundational files.** In parallel:
   - `CLAUDE.md` — project structure, conventions, stack
   - Glob `docs/eng-arch/*.md` — existing architecture docs
   - Glob `docs/eng-specs/*.md` — recent implementation plans (scan for recurring patterns)

2. **Determine what exists.** Categorize:
   - **Fresh run** — `docs/eng-arch/` is empty or doesn't exist
   - **Update run** — `docs/eng-arch/` has existing docs
   - **Single topic** — user requested a specific deep-dive topic

3. **Read key source files** based on scope. Use Glob + Read to scan:
   - **Backend:** entry points, modules, controllers, services, entities, gateway files
   - **Frontend:** main app file, router, stores, key components, shared utilities
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
     - Read existing `docs/eng-arch/` docs as context to understand what's already documented
     - Return structured analysis as text (do NOT write files)

   **Frontend scope:**
   - Launch `frontend-architect` (`subagent_type: frontend-architect`). Instruct it to:
     - Explore the frontend codebase thoroughly
     - Document: component architecture, state management, routing, API integration patterns, styling conventions, shared utilities
     - Read existing `docs/eng-arch/` docs as context
     - Return structured analysis as text (do NOT write files)

   **Fullstack (both):**
   - Launch both agents in parallel (single message, two Task tool calls)
   - Backend architect produces its analysis first conceptually, but both run concurrently
   - After both complete, synthesize into a unified system view

   Omit `model` on architect dispatches — their frontmatter pins Opus. Call-site `model: "opus"` is hook-blocked, and a call-site `"sonnet"` would silently downgrade them.

8. **Scan `docs/eng-specs/` for patterns** to promote. Look for:
   - Decisions that recur across multiple plans
   - Patterns that started as one-off choices but became conventions
   - Mention these as candidates for the architecture docs

### Phase 4: Diff+Merge (Update Runs Only)

**Skip this phase if `docs/eng-arch/` is empty (fresh run) or this is a single topic request with no existing doc for that topic.**

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

12. **Write the overview doc** to `docs/eng-arch/00-system-overview.md` using the template below.

13. **Write deep-dive docs** (unless `+quick`) to `docs/eng-arch/<topic>.md` using the deep-dive template.

14. **For single topic requests**, only write the requested topic file.

### Phase 6: Summary & Next Steps

15. **Present summary:**
    - Files written/updated (with paths)
    - Key architectural patterns documented
    - Any drift detected (code differs from previously documented patterns)
    - Patterns promoted from `docs/eng-specs/` (if any)

16. **Flag drift** if detected: "These areas of code have diverged from the documented architecture: [list]. Consider updating the code or the docs."

## Overview Template

Write to `docs/eng-arch/00-system-overview.md`. Sections: System Map (packages + communication flows), Data Model (entities + relationships), API Surface (REST endpoints, WebSocket events, MCP tools as applicable), Coding Conventions (naming, patterns, error handling), Key Architectural Decisions (context, decision, rationale, consequences). Include a header with generation date and scope.

## Deep-Dive Template

Write deep-dives to `docs/eng-arch/<topic>.md`. Sections: Overview, Current Implementation (with file/line references), Patterns & Conventions, Interfaces, Known Limitations.

## Arguments

$ARGUMENTS
