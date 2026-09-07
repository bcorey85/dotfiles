---
name: eng-arch
description: "Generate or update system architecture docs — auto-detects subsystems, runs architect agents, diff+merge existing docs. Modifiers: be/fe/fs, +quick, +deep."
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, Agent, AskUserQuestion]
---

# Engineering Architecture

Generate or update cross-cutting architecture docs in `docs/architecture/` — how the system works, not how to build one feature (that's `/eng-spec`).

## Modifiers

Parse modifiers from `$ARGUMENTS`:

| Modifier | Effect |
| --- | --- |
| `be` / `backend` | Backend scope only |
| `fe` / `frontend` | Frontend scope only |
| `fs` / `fullstack` | Fullstack (explicit — default with no scope) |
| `+quick` | Overview only, skip deep-dives |
| `+deep` | Overview + all deep-dives |
| `<topic>` | Regenerate one deep-dive (e.g. `/eng-arch data-model`) |
| `<adr-path>` | ADR-driven mode — update/create the matching deep-dive from an ADR, no codebase sweep |

A bare topic name = single deep-dive request. A `.md` path under `docs/decisions/` = **ADR-driven mode** (below).

## ADR-Driven Mode

Triggered by an `$ARGUMENTS` path under `docs/decisions/`. Skips Phase 2, replaces Phase 3 (no sweep); Phases 4–6 as written. Read ADR fully → `ls docs/architecture/` → identify target (AskUserQuestion: `Update <file>` / `Create <new-file>` / `Edit`) → read existing deep-dive if updating → dispatch scoped architect (prompt below) → diff/merge → write → summarize (ADR path, deep-dive path, drift).

### Architect prompt — required fields

- ADR content (ground truth), target path, existing deep-dive content if updating
- **Content instructions**: ADR is source of truth; verify cited paths against the branch (ADRs go stale). Durable architecture only (current-state, patterns, interfaces, limitations) — no migration story/alternatives/phases. Return text; don't write files.
- **Format directive**: pass `~/.claude/skills/_shared/skimmable-writing.md` contents verbatim, plus this addendum:

  > **One Diátaxis mode**: deep-dives are **reference** (_how_ the subsystem currently works). Do NOT recap migration, alternatives, or decision rationale — those live in the ADR. Cross-link.

## Instructions

### Phase 1: Gather Context

1. **Read foundations, in parallel**: `CLAUDE.md` + glob `docs/architecture/*.md` + glob `docs/plans/*.md` (scan plans for recurring patterns)

2. **Determine what exists.** Categorize:
   - **Fresh run** — `docs/architecture/` is empty or doesn't exist
   - **Update run** — `docs/architecture/` has existing docs
   - **Single topic** — user requested a specific deep-dive topic

3. **Scan key sources** per scope: backend (entry points, modules, controllers, services, entities), frontend (app, router, stores, components, utilities), shared (package.json, configs, schema)

### Phase 2: Scope & Plan

4. **Apply scope modifier** (or default to fullstack).

5. **Auto-detect deep-dive topics** by scanning for distinct subsystems (e.g. `data-model`, `api-contracts`, `websocket-events`, `mcp-protocol`, `auth`, `state-management`, `build-deploy`). Only where the codebase has meaningful content.

6. **Present plan**: overview + proposed deep-dives (`+quick`: overview only; `+deep`: all detected; single topic: confirm it). Ask before starting.

### Phase 3: Architect Analysis

7. **Launch architects** by scope (`backend-architect` / `frontend-architect`; parallel for fullstack, then synthesize): explore thoroughly, document per their briefs, read existing `docs/architecture/` as context, return analysis as text (do NOT write files). Omit `model` — frontmatter pins Opus (call-site `opus` is hook-blocked, `sonnet` silently downgrades).

8. **Scan `docs/plans/`** for recurring decisions and one-offs-become-conventions; mention as doc candidates.

### Phase 4: Diff+Merge (Update Runs Only)

**Skip this phase if `docs/architecture/` is empty (fresh run) or this is a single topic request with no existing doc for that topic.**

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

10. **New sections**: show + ask "Add?". **Unchanged sections**: preserve silently.

### Phase 5: Write Docs

12–14. **Write docs**: overview to `00-system-overview.md` + deep-dives to `<topic>.md` (unless `+quick`; single-topic writes only its file).

### Phase 6: Summary & Next Steps

15–16. **Summarize**: files written, patterns documented, drift detected, plans-promoted patterns. Flag drift as code-diverged-from-docs with the list.

## Overview Template

Overview (`00-system-overview.md`): System Map, Data Model, API Surface, Coding Conventions, Key Decisions + generation-date/scope header.

## Deep-Dive Template

Deep-dive (`<topic>.md`): Overview, Current Implementation (file:line refs), Patterns & Conventions, Interfaces, Known Limitations.

## Arguments

$ARGUMENTS
