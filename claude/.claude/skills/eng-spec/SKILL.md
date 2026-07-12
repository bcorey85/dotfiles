---
name: eng-spec
description: Spec a feature — architect exploration first, then design decisions resolved with you one at a time, then a finalized plan. Auto-detects scope (fe/be/fullstack). Optionally writes spec to disk and/or dispatches coders.
allowed-tools:
  [
    Bash,
    Read,
    Write,
    Edit,
    Glob,
    Grep,
    Agent,
    AskUserQuestion,
    SendMessage,
    Skill,
  ]
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

1. **Check for context already in the thread.** The user may have run `/pull-ticket`, pasted a description, or just described what they want. If the skill argument is a path to a ticket/spec file (e.g. `TICKET.md`), read it and treat its contents as the feature to plan — no clarifying question needed. Use whatever is available. Do NOT independently fetch from Jira or Notion — if the user hasn't run `/pull-ticket` and a Jira ticket is relevant, **suggest they run `/pull-ticket` first** rather than fetching it yourself. This reinforces the workflow loop.

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
- **The skipped sections must say so, not go missing.** Go lean skips the framing pass (2.5), the interview (Phase 4), and the spec review (15a) — all of which exist to govern design decisions, and the whole premise of this path is that there are none. If the spec is saved, all three governed sections say why they are empty: `## Framing` reads `N/A — go-lean path (pure configuration, no design decisions)`, `## Decisions` reads `None — pure configuration; the constraints that forced it are under Constraints.`, and `## Approaches Considered and Not Taken` reads `N/A — go-lean path (no architect ran, so no approaches were explored)`. That last one is the easiest to leave dangling: counter-priming is an architect product, and go lean dispatches no architect. A dangling empty section is indistinguishable from one the process forgot to fill.
- **If you find yourself wanting to write a real decision block, the go-lean call was wrong.** Back out: run Phase 2.5 and dispatch the architect. The five conditions above are the bar, and a decision worth recording means at least one of them was false. This path exists for changes with no design in them — the moment there is design, it is the wrong path, and the cost of backing out is minutes against a decision nobody owns.

If uncertain, run the architect. A 2-minute architect pass that confirms "the approach is sound" is cheap insurance. A skipped architect that misses a coupling risk costs an entire review-fix cycle.

5. **If a scope hint was passed** (`be`, `fe`, `fs`), use it directly.

6. **If scope is ambiguous**, ask the user: "This could be frontend-only, backend-only, or fullstack. What's the scope?"

7. **Present scope to user**: "This is [frontend/backend/fullstack]. I'll spin up [which architects]. Sound right?"

### Phase 2.5: Framing Pass (the user speaks first — MANDATORY)

7a. **Before dispatching any architect, collect the user's framing.** Read `~/.claude/skills/_shared/framing-pass.md` and run the step it describes: the user's rough approach, the one thing it makes worse, and the fork they're unsure about.

**HARD STOP — do not dispatch architects, do not propose an approach, do not name a candidate design, until the user has answered.** If the architect speaks first, the option set is already the agent's and every downstream decision is a ratification. This step is the difference between the user designing and the user picking from a menu.

Skip ONLY on the "go lean" path in step 4a (pure configuration) — the same bar that skips the architect skips the framing.

### Phase 3: Architect Exploration (Stage 1 — no design yet)

8. **Read existing codebase context** for the affected areas — key files, existing patterns, relevant `eng-arch/` docs. Include this as context when launching architect agents.

9. **Launch architect agent(s)** based on scope (both in parallel for fullstack — exploration has no contract dependency). Omit `model` — their frontmatter pins Opus. The dispatch asks for an EXPLORATION brief, not a plan. Include the user's Phase 2.5 framing **verbatim** in the dispatch. Read `~/.claude/skills/_shared/invariant-survey.md` (the canonical, version-tagged survey text) and include the instruction below verbatim, inserting that file's "Dispatch text" section in full as item 2:

   > **The user's stated approach** (from their framing pass, before you were dispatched):
   >
   > <insert the user's framing verbatim>
   >
   > Your job is to VALIDATE OR CHALLENGE that approach against the real codebase — not to silently replace it with your own. If the codebase shows it is wrong or costly, say so plainly and explain why, with refs. If it is sound, say that too. Returning an unrelated design that ignores the framing is a failed dispatch.
   >
   > Explore only — do NOT produce an implementation plan yet. Return an **exploration brief**:
   >
   > 1. **Current state** — what exists today, with `file:line` refs
   > 2. <insert the "Dispatch text" section of `_shared/invariant-survey.md` here, verbatim — it begins "**Invariant survey (do this BEFORE thinking about the feature)** — inventory the standing invariants…">

   > 3. **Patterns** — to follow and to avoid, with refs
   > 4. **Constraints** — technical and convention constraints you found
   > 5. **Verdict on the user's approach** — sound / sound with caveats / wrong, and why, with refs
   > 6. **Counter-priming** — name three implementation approaches you considered and are NOT recommending, one line each on why not. If you cannot name three, say so explicitly — that is diagnostic information about how narrowly you framed the problem, not a step to skip.
   > 7. **Decision points** — every place where two or more viable approaches exist: each with options, pros/cons, and your recommendation. Include decision points the user's framing already settles — mark those as "settled by framing" rather than dropping them, so the user can see what their approach committed them to.
   > 8. **Open questions** — ambiguities in the requirements only the user can resolve
   >
   > Exception: if the task genuinely has NO design decisions (exactly one reasonable approach), say so explicitly and return the full plan in your Output Format instead — but items 5 (verdict on the user's approach) and 6 (counter-priming) are still REQUIRED, prepended to the plan. "There was nothing to decide" is itself a claim about the user's framing, and it is the claim most worth checking.

10. If every architect returned a full plan (zero decision points and zero open questions), skip **the Phase 4 interview (steps 11–13) and the step-14 finalization** — there is nothing to interview about, and nothing to send back to an architect that already returned its final plan. Everything else stands. Go to step 15 and run the **spec review (15a) anyway.** Skipping the interview is not a reason to skip the gate: "zero decision points" is the architect's own claim about its own work, and 15a is what checks that claim. A spec with no decisions still gets its framing verdict recorded, its counter-priming recorded, its invariant checks run, and its phases checked for verticality. Every decision block in such a spec should be `(Locked)` — if any is not, the architect's "zero decision points" was wrong and the interview was skipped in error.

### Phase 4: Interactive Design Resolution (the point of this skill — never batch it)

11. **Present understanding FIRST**, before any decisions: current state, the patterns found (ask the user to confirm they're the RIGHT ones to follow), constraints, the architect's **verdict on the user's framing**, and its **three counter-primed out-of-scope approaches**. The user needs the chance to catch a wrong pattern — and to see what the architect ruled out on their behalf — before either propagates into every downstream decision.

12. **Resolve decision points ONE AT A TIME** — never as a single batched list. Ask follow-ups freely; there is no question quota, and "the conversation feels done" is not the completeness test — every decision point and open question resolved is.

    **Frame each question against the user's stated approach, not as an open menu.** The user has already named an approach in Phase 2.5; the interview's job is to STRESS-TEST it, not to re-elicit it from scratch:

    - Where the architect's exploration **supports** the framing: say so, state the decision as following from it, and move on. Do not manufacture a choice to look even-handed.
    - Where it **breaks** the framing: lead with the failure — "you said X; here's the case where X breaks, with refs" — then the alternative. The user is defending or abandoning their own position, which is a real decision.
    - Where the framing is **silent**: present the options with pros/cons and the architect's recommendation. This is the only case that is a genuine menu, and here the recommendation goes first (AskUserQuestion, recommended option first).

    Decisions made while the design is still liquid beat review of a finished proposal.

13. **Track resolved decisions AND their owner tags.** Tag each by the tests in `~/.claude/skills/_shared/design-decision-format.md` § Owner tags — read them; do not tag from memory, and do not shortcut to "the user answered, so it's theirs." Tag as you go: reconstructing owner tags after the fact is how every decision quietly becomes `(User-originated)`.

    Do NOT write any spec document and do NOT dispatch finalization until every decision point and open question is resolved.

### Phase 5: Architect Finalization (Stage 2)

14. **Continue each architect via `SendMessage`** (preferred): its Stage-1 context is intact, so send only the resolved decision list and the instruction to produce the full plan per its Output Format, NOT re-litigating resolved decisions — they carry the user's authority. If the Stage-1 agent is no longer addressable (session cleared, agent expired), fall back to a fresh dispatch (omit `model`) with its Stage-1 brief verbatim plus the resolved decisions.
    - **Fullstack ordering**: finalize `backend-architect` first — its plan must include a clearly defined **API contract** (endpoint URLs, methods, request/response shapes, status codes). Then finalize `frontend-architect` with the contract — design against it, not invent one.

15. **Synthesize the finalized plan(s)** — key decisions (and who made them), tradeoffs accepted, anything deferred.
    - **`DESIGN GAPS` returned by an architect**: resolve each with the user before the spec review, and add it to `## Decisions` as a proper block with its owner tag (tag by the tests in `design-decision-format.md` — they key on whose judgment shaped the outcome, not on which phase it happened in). These are choices finalization forced after the Phase 4 interview closed — settling them yourself would put an untagged decision into the spec looking exactly like one the user approved. **Then send the resolution back to that architect via `SendMessage`** and take its revised plan: its guess may have shaped implementation steps and success criteria well past the flagged line, and hand-patching the one marked spot leaves the rest of the plan built on the guess.
    - **Carry the architect's counter-priming into `## Approaches Considered and Not Taken`** — the three approaches it ruled out, each with its failure mode. They were shown to the user in step 11; this is where they land in the artifact.
    - **Carry the user's Phase 2.5 framing into `## Framing`, verbatim, with the architect's verdict on it.** Not paraphrased — this section is what 15a audits every `(User-originated)` tag against, so a reworded framing makes the whole decision ledger unauditable.
    - **Write `## Constraints` and `## External Contracts` — nothing upstream produces them.** The architect's Stage-1 constraints and the step-9 invariant survey are the raw material; this is the step that turns them into the artifact's sections. `## External Contracts` is mandatory and 15a checks it: name each provider/API/platform contract the change touches, the invariant it imposes, and what breaks if violated — or state "None" explicitly. Omitting it because the change "obviously touches nothing" is the exact case the explicit-None rule exists for.
    - **Fullstack: weave, don't concatenate.** Each architect returns a single-layer plan by design (the scope fence). Merging them as "backend phases, then frontend phases" is the horizontal anti-pattern `plan-format.md` forbids — a layer phase produces no end-to-end pass/fail signal for `/code`'s phase gates. Interleave into vertical slices: each phase delivers one increment of user-observable behavior end-to-end (its BE piece + its FE piece), independently verifiable at the gate. The API contract fixed in step 14 is what makes this safe — each slice's FE half designs against the contract, not against unbuilt code. A phase stays single-layer only when the work genuinely is (migration-only, infra-only).

15a. **Spec review before presenting** (mirrors deep-plan's phase reviews; same reviewer, same log). Draft the full spec (template below) to `docs/eng-specs/.spec-draft.md`, then dispatch `deep-plan-review` (omit `model`) with the draft path and this checklist:

    - Every `file:line` reference resolves and says what the spec claims.
    - **`## Framing` is present, quotes the user's Phase 2.5 answer verbatim, and carries the architect's verdict on it.** Missing, paraphrased, or verdict-less is an issue — the owner tags below are audited against this section, so a spec whose Framing is absent or reworded has an unauditable decision ledger, and `(User-originated)` becomes an assertion no one can check. (On the go-lean path this section reads `N/A — go-lean path (pure configuration, no design decisions)` — the exact string from the go-lean bullet above — and 15a does not run at all.)
    - Every decision block has all four fields (Choice / Reasoning with owner tag / Alternatives rejected / Trade-off accepted).
    - **Owner tags are one of the three valid values** (`User-originated` / `User-ratified` / `Locked`) — a bare `(User)` is an issue, since it hides whether the user designed the decision or accepted it.
    - **Ratification alarm** — read `~/.claude/skills/_shared/design-decision-format.md` § The ratification alarm and apply it exactly as written: it owns the threshold, both fire conditions, and the report lines. Report the full owner-tag distribution with your verdict. Do not restate or reinterpret the threshold here.
    - **Counter-priming survived to the spec** — the architect's three not-recommended approaches appear in `## Approaches Considered and Not Taken`, each with a named failure mode. Three approaches explored and silently dropped is an issue. (Exception: the architect explicitly said it could not name three — then the spec says that, and says how many it did name. That admission is diagnostic and must survive too.) Note this is a DIFFERENT axis from a decision block's "Alternatives rejected": counter-priming is whole approaches to the feature, Alternatives rejected is options within one decision. Do not accept one as satisfying the other.
    - **Decision trace** — every design-level choice the Implementation Plan commits to traces back to a decision block in `## Decisions`, and none contradicts one. A choice that meets the decision-block bar (two or more viable approaches with a user-visible consequence — data shape, contract, failure mode, retention/security behavior) but appears nowhere in `## Decisions` is an **unflagged design gap**: the architect settled it during Stage-2 finalization, after the Phase 4 interview closed, so it carries no owner tag and the user never saw it. That is a finding regardless of whether the choice is good. Tactical detail (import paths, test placement, helper names, phase wording) is explicitly out of scope for this check. Resolve any gap with the user and add a proper decision block before Phase 6 — `## Decisions` is the ledger the owner tags are audited against.
    - `## External Contracts` is present and either names each contract + invariant + breakage, or states "None" explicitly. **Where the change alters what an external tool ACCEPTS or ENFORCES at runtime** (verifier, policy engine, admission controller, parser, migration runner), each acceptance claim states its evidence class — `exercised` or `declared-only` — per `design-decision-format.md` § External Contracts rule. An acceptance claim resting on declared-only evidence with no staged exercise step is an issue: schema text and in-repo precedent describe intent, not runtime behavior.
    - **Scope-only rejections** (`design-decision-format.md` § Rules) — scan every `Alternatives rejected` field for an option turned down SOLELY on scope grounds ("not requested", "out of ticket scope", "scope creep") rather than a technical failure mode. Each one must be marked as requiring the user's explicit sign-off, not resolved by a default or by accepting the recommendation. Scope is the ticket-owner's call; both lanes have reliably surfaced the right alternative and then declined it on scope discipline, twice reproducing a regression the maintainer shipped and reverted.
    - The three invariant checks from `~/.claude/skills/_shared/invariant-survey.md` ("Review gate" section) — read the file and include them in this checklist verbatim: **Discovery check**, **Destructive-trigger check**, **Credentials-past-intent check**. They are the review-side counterpart of the step-9 survey and share its version tag.
    - Implementation phases are vertical — a phase scoped to a layer (named or shaped like "backend", "frontend", "the API", "the UI") is a finding unless the work is genuinely single-layer (migration-only, infra-only; such a phase must state `Manual Verification: N/A (infra-only)`). Phase 1 is the thinnest end-to-end skeleton. Every Phase Status line has a `(risk: ...)` tag, and Success Criteria use the project's real verification commands.
    - Multi-phase plans open with `Phase 0: Contracts` (committable contract content, risk: high) and `Phase 1: Walking skeleton` per `plan-format.md`; single-slice plans state explicitly that contracts fold into Phase 1. Missing or prose-only contracts is an issue.
    - The four mandatory closing phases (`~/.claude/skills/_shared/closing-phases.md`) are present, in order, after the last feature phase: Refactor pass, Verify pass, Orient pass, Finalize (`/adr` for this lane). Missing or reordered is an issue.

    Fix what it flags (max 1 revision round), log the verdict (`REVIEW_METRICS_FILE="$HOME/.claude/deep-plan-review.jsonl" bash ~/.claude/skills/review/log-review-metrics key=<ticket-or-slug> phase=spec verdict=<PASS|ESCALATED> rounds=<n> issues=<m>`), then present the corrected version. Delete the draft after Phase 6 resolves (it becomes the saved file on "yes", is removed on "no").

    **The ratification alarm is the ONE finding you may not fix** (rule and both report lines: `design-decision-format.md` § The ratification alarm). If it fires, surface the canonical line verbatim, immediately before the Phase 6 questions. Then continue — it never blocks.

### Phase 6: User Choice

16. **HARD STOP — no file writes, no coder dispatches, until the user answers.**

    Ask both questions in ONE **AskUserQuestion** call (two questions: "Save to disk?" and "Implement now?") — the blocking modal is the mechanism that makes this stop unskippable; asked as prose, it has been skipped before. Presenting the plan in the conversation is fine. Writing files or dispatching coders before the answers is NOT.

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
    - **If any code was changed during this session** (by dispatched coders — or by any edit that slipped through inline despite the dispatch rule above), tell the user: "Auto-dispatching `/review` to check the implementation before committing." Then invoke the `/review` skill using the Skill tool (`skill: "review"`). This runs AFTER all implementation is complete and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing. **Never skip peer review just because no coder subagent was dispatched** — the review is triggered by code changes, not by how those changes were made.

## Template (for saving to disk)

The spec has two layers in ONE file: a judgment layer (what a human reads at
the gate) and an implementation layer (what `/code` executes, in the shared
plan format so its phase gates work identically to `/deep-plan` output).

```markdown
# Title

> Jira: JIRAPROJECT-TICKETNUMBER (if applicable)
> Context sources: Jira ticket, Figma mockups (sourced via MCP)
> Date: YYYY-MM-DD

## Summary

One paragraph on what this accomplishes.

## Framing

<!-- The user's Phase 2.5 framing, verbatim: the approach they named, the
trade-off they accepted, the fork they were unsure about — plus the
architect's verdict on it (sound / sound with caveats / wrong, and why).
This is what makes the owner tags below auditable rather than asserted. -->

## Decisions

<!-- Every decision uses the four-field block from
~/.claude/skills/_shared/design-decision-format.md:
Choice / Reasoning (+ owner: User-originated|User-ratified|Locked) /
Alternatives rejected / Trade-off accepted. Never a table with one-line
rationales. Tag owners honestly — a spec with zero (User-originated)
decisions is a signal worth seeing, not a failure worth hiding. -->

## Approaches Considered and Not Taken

<!-- The architect's three counter-primed approaches, carried through from the
Phase 4 presentation. One line each: the approach, and the concrete failure
mode that ruled it out. Different axis from a decision's "Alternatives
rejected" — these are whole approaches to the feature, not options within one
decision. This is the section that stops the next reader from re-proposing
what was already ruled out; an alternative that lives only in the chat is one
that gets litigated again. If the architect could not name three, say so and
say how many it named. -->

## Constraints

<!-- What was fixed before design began and could not be traded away: platform
limits, existing contracts, deadlines, non-negotiables the user stated in
framing. This is where a "decision" with no real alternative belongs — if you
cannot name an option a constraint killed, it was never a decision, and it is
recorded here rather than as a hollow block in ## Decisions. Also the
destination the (Locked) rule in design-decision-format.md points at. -->

## External Contracts

<!-- Mandatory (see design-decision-format.md): every provider/API/platform
contract touched + the invariant it imposes + what breaks if violated.
Internal invariants with blast radius (identity construction, hidden
couplings) belong here too. "None" must be stated explicitly. -->

## Approach

- Breakdown by area (backend, frontend, etc.) — area framing lives in THIS section only; the Implementation Plan below slices vertically, never by area
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
criteria. This is what /code's phase-boundary gates and /verify consume.
Every spec ends with the four mandatory closing phases from
~/.claude/skills/_shared/closing-phases.md (Refactor → Verify → Orient →
Finalize; Finalize = /adr for this lane) — not negotiable, never omitted. -->
```

## Arguments

$ARGUMENTS
