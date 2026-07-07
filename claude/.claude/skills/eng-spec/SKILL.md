---
name: eng-spec
description: Spec a feature — architect exploration first, then design decisions resolved with you one at a time, then a finalized plan. Auto-detects scope (fe/be/fullstack). Optionally writes spec to disk and/or dispatches coders.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Engineering Spec

Plan a feature or task. Consumes whatever context is already in the conversation thread (Jira ticket from `/pull-ticket`, user description, product spec, etc.). Does NOT fetch external context itself.

Auto-detects scope and launches the appropriate architect(s). After planning, asks whether to save to disk and/or implement immediately.

## Modifiers

- `be` or `backend` — force backend-only scope
- `fe` or `frontend` — force frontend-only scope
- `fs` or `fullstack` — force fullstack scope

## Instructions

### Phase 1: Gather Context

1. **Check for context already in the thread.** The user may have run `/pull-ticket`, pasted a description, or just described what they want. Use whatever is available. Do NOT independently fetch from Jira or Notion — if the user hasn't run `/pull-ticket` and a Jira ticket is relevant, **suggest they run `/pull-ticket` first** rather than fetching it yourself. This reinforces the workflow loop.

2. **If no context is apparent**, ask the user: "What are we building? Describe the feature or paste a ticket."

3. **Check for an existing eng spec** — Glob `docs/eng-specs/*.md` for matching files. If found, read it and ask: "Found an existing plan — update it or start fresh?"

### Phase 2: Scope Assessment

4. **Determine scope** (frontend, backend, or fullstack) based on the task description, conversation context, and codebase structure.

4a. **Assess whether architect agents are needed.** Default is YES — run the architects. Only skip Phases 3–5 if ALL of these are true:

- The task is pure configuration with zero implementation choices (e.g., installing a package, adding an env var, enabling a flag)
- No new files are being created
- No existing service/module signatures are changing
- No data model, API contract, or state management decisions are involved
- The entire change could be described in under 5 lines of diff

**A well-written ticket is NOT a reason to skip the architect.** Tickets describe the PM's intended approach. Architects validate that approach against the actual codebase — catching coupling risks, stale assumptions, and edge cases the ticket cannot see. If the ticket includes an "Approach" section, that is context FOR the architect, not a replacement for one.

If skipping:

- Write the plan directly based on existing codebase patterns
- Ask the user: "This is pure configuration — skip the architect and go lean?" **Wait for explicit confirmation.**
- **Still dispatch coder subagent(s) in Phase 6 if the user chooses "Implement now."** "Go lean" means skipping the architect, NOT skipping the coder. The coder dispatch is what triggers the auto-review chain — implementing inline breaks that chain.

If uncertain, run the architect. A 2-minute architect pass that confirms "the approach is sound" is cheap insurance. A skipped architect that misses a coupling risk costs an entire review-fix cycle.

5. **If a scope hint was passed** (`be`, `fe`, `fs`), use it directly.

6. **If scope is ambiguous**, ask the user: "This could be frontend-only, backend-only, or fullstack. What's the scope?"

7. **Present scope to user**: "This is [frontend/backend/fullstack]. I'll spin up [which architects]. Sound right?"

### Phase 3: Architect Exploration (Stage 1 — no design yet)

8. **Read existing codebase context** for the affected areas — key files, existing patterns, relevant `eng-arch/` docs. Include this as context when launching architect agents.

9. **Launch architect agent(s)** based on scope (both in parallel for fullstack — exploration has no contract dependency). Omit `model` — their frontmatter pins Opus. The dispatch asks for an EXPLORATION brief, not a plan. Include this instruction verbatim:

   > Explore only — do NOT produce an implementation plan yet. Return an **exploration brief**:
   >
   > 1. **Current state** — what exists today, with `file:line` refs
   > 2. **Invariant survey (do this BEFORE thinking about the feature)** — inventory the standing invariants of every surface the change will touch, stated independently of what the feature wants: identity/uniqueness construction, persistence formats and replay paths, ordering guarantees, authority/permission enforcement points (including paths that BYPASS the usual boundary — schedulers, hooks, headless execution), mode flags that change how tokens/data are classified, and lifecycle/liveness discriminators (for every entity the change will reclaim, expire, evict, revoke, or invalidate: what does "gone" mean for it, per the system that owns it?). These categories are examples, not the checklist — the misses live in the classes nobody enumerated. So also apply the generative rule: for each entity a destructive or irreversible action will target, enumerate that entity's FULL state machine (every state it can occupy, including dormant/suspended/resumable ones) and record what the action's trigger does in each state. When evaluating a candidate trigger signal, check it BOTH ways — states where it fails to fire (leak) and states where it fires but shouldn't (false destruction) — and say which cost is worse; a signal justified only by "fires reliably when needed" is half-analyzed. Each with `file:line`. The goal-shaped reading you'll do next anchors on the feature's mechanics; this survey is your one pass at the surface's own rules.
   > 3. **Patterns** — to follow and to avoid, with refs
   > 4. **Constraints** — technical and convention constraints you found
   > 5. **Decision points** — every place where two or more viable approaches exist: each with options, pros/cons, and your recommendation
   > 6. **Open questions** — ambiguities in the requirements only the user can resolve
   >
   > Exception: if the task genuinely has NO design decisions (exactly one reasonable approach), say so explicitly and return the full plan in your Output Format instead.

10. If every architect returned a full plan (zero decision points and zero open questions), skip Phases 4–5 and go to Phase 6.

### Phase 4: Interactive Design Resolution (the point of this skill — never batch it)

11. **Present understanding FIRST**, before any decisions: current state, the patterns found (ask the user to confirm they're the RIGHT ones to follow), and constraints. The user needs the chance to catch a wrong pattern before it propagates into every downstream decision.

12. **Resolve decision points ONE AT A TIME** — never as a single batched list. For each: present the options with pros/cons and the architect's recommendation, then wait for the answer before moving to the next (AskUserQuestion works well — recommended option first). Ask follow-ups freely. Decisions made while the design is still liquid beat review of a finished proposal.

13. **Track resolved decisions.** Do NOT write any spec document and do NOT dispatch finalization until every decision point and open question is resolved.

### Phase 5: Architect Finalization (Stage 2)

14. **Continue each architect via `SendMessage`** (preferred): its Stage-1 context is intact, so send only the resolved decision list and the instruction to produce the full plan per its Output Format, NOT re-litigating resolved decisions — they carry the user's authority. If the Stage-1 agent is no longer addressable (session cleared, agent expired), fall back to a fresh dispatch (omit `model`) with its Stage-1 brief verbatim plus the resolved decisions.
    - **Fullstack ordering**: finalize `backend-architect` first — its plan must include a clearly defined **API contract** (endpoint URLs, methods, request/response shapes, status codes). Then finalize `frontend-architect` with the contract — design against it, not invent one.

15. **Synthesize the finalized plan(s)** — key decisions (and who made them), tradeoffs accepted, anything deferred.

15a. **Spec review before presenting** (mirrors q-plan's phase reviews; same reviewer, same log). Draft the full spec (template below) to `docs/eng-specs/.spec-draft.md`, then dispatch `qrspi-review` (omit `model`) with the draft path and this checklist:

    - Every `file:line` reference resolves and says what the spec claims.
    - Every decision block has all four fields (Choice / Reasoning with owner tag / Alternatives rejected / Trade-off accepted).
    - `## External Contracts` is present and either names each contract + invariant + breakage, or states "None" explicitly.
    - **Discovery check (completeness, not presence)**: independently skim/grep the files the spec touches for candidate invariants — identity construction, enforcement points, persistence/replay contracts, non-HTTP execution paths. Every candidate found must appear in External Contracts or be explicitly ruled out in the spec. A diligent-but-incomplete section is the known failure mode.
    - **Destructive-trigger check**: for every destructive or irreversible operation the spec introduces (reap, expire, evict, revoke, invalidate, delete), the trigger predicate must be mapped against each state the target entity can occupy — an unmapped state is a finding. A predicate justified only by "fires reliably when reclamation is needed", with no analysis of states where it fires on a still-live target, is a finding.
    - Implementation phases are vertical, every Phase Status line has a `(risk: ...)` tag, and Success Criteria use the project's real verification commands.

    Fix what it flags (max 1 revision round), log the verdict (`REVIEW_METRICS_FILE="$HOME/.claude/qrspi-review.jsonl" bash ~/.claude/skills/review/log-review-metrics key=<ticket-or-slug> phase=spec verdict=<PASS|ESCALATED> rounds=<n> issues=<m>`), then present the corrected version. Delete the draft after Phase 6 resolves (it becomes the saved file on "yes", is removed on "no").

### Phase 6: User Choice

16. **HARD STOP — DO NOT WRITE ANY FILES OR DISPATCH ANY CODER AGENTS UNTIL THE USER ANSWERS THESE QUESTIONS.**

    This has been a recurring failure point. The user has corrected this behavior TWICE.
    You MUST present these questions and WAIT for explicit answers before taking any action.
    Presenting the plan in the conversation is fine. Writing files or dispatching coders is NOT.

    **Save to disk?**
    - Yes → Write to `docs/eng-specs/` using the template below. File naming:
      - If a Jira ticket was mentioned in context: `docs/eng-specs/JIRAPROJECT-TICKETNUMBER-description.md`
      - Otherwise: `docs/eng-specs/<feature-name>.md` (kebab-case from description)
    - No → Plan stays in the conversation only

    **Implement now?**
    - Yes, and the Implementation Plan has **more than one phase** → the spec must be saved to disk (save it even if the user answered "no" above — explain why), then invoke `/code` via the Skill tool with the spec path. `/code`'s phase-boundary machinery (auto-advance vs sign-off, drift gates) keys off the plan's Phase Status risk tags — a raw coder dispatch would bypass every phase gate the plan just defined.
    - Yes, single-phase → Dispatch coder agent(s) based on scope:
      - Backend only: launch `backend-coder` with the architect's plan
      - Frontend only: launch `frontend-coder` with the architect's plan
      - Fullstack: launch BOTH `backend-coder` and `frontend-coder` in parallel — frontend-coder also gets the API contract
        **IMPORTANT: Always dispatch a coder subagent. Do NOT implement code changes yourself.** The coder dispatch is what triggers the auto-review chain. Implementing inline bypasses peer review.
    - Later → Stop here

17. **Present summary**:
    - Key decisions made (and who made them)
    - File written (if saved)
    - What was implemented (if coded)
    - Remind to check Figma if frontend work is involved
    - **If any code was changed during this session** (whether by dispatched coders OR by you directly), tell the user: "Auto-dispatching `/review` to check the implementation before committing." Then invoke the `/review` skill using the Skill tool (`skill: "review"`). This runs AFTER all implementation is complete and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing. **Never skip peer review just because no coder subagent was dispatched** — the review is triggered by code changes, not by how those changes were made.

## Template (for saving to disk)

The spec has two layers in ONE file: a judgment layer (what a human reads at
the gate) and an implementation layer (what `/code` executes, in the shared
plan format so its phase gates work identically to `/q-plan` output).

```markdown
# Title

> Jira: JIRAPROJECT-TICKETNUMBER (if applicable)
> Context sources: Jira ticket, Figma mockups (sourced via MCP)
> Date: YYYY-MM-DD

## Summary

One paragraph on what this accomplishes.

## Decisions

<!-- Every decision uses the four-field block from
~/.claude/skills/_shared/design-decision-format.md:
Choice / Reasoning (+ owner: User|Locked) / Alternatives rejected /
Trade-off accepted. Never a table with one-line rationales. -->

## External Contracts

<!-- Mandatory (see design-decision-format.md): every provider/API/platform
contract touched + the invariant it imposes + what breaks if violated.
Internal invariants with blast radius (identity construction, hidden
couplings) belong here too. "None" must be stated explicitly. -->

## Approach

- Breakdown by area (backend, frontend, etc.)
- Specific patterns to follow
- API contract (fullstack: fixed here, frontend designs against it)

## Dependencies

- External packages to install
- Internal modules to build on

## Implementation Plan

<!-- From here down, follow ~/.claude/skills/_shared/plan-format.md IN FULL:
## Phase Status with (risk: low|high) tags, vertical phases, per-phase
Changes Required + Success Criteria (Automated/Manual Verification with the
project's real commands), Acceptance Stubs when the ticket has behavioral
criteria. This is what /code's phase-boundary gates and /q-verify consume. -->
```

## Arguments

$ARGUMENTS
